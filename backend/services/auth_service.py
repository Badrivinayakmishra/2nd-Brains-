"""
Authentication service with JWT tokens and secure password hashing.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from database.models import User, RefreshToken, Tenant

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> tuple[str, datetime]:
    """Create a JWT refresh token and return with expiry."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, expire


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


class AuthService:
    """Service for handling authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get a user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        password: Optional[str] = None,
        full_name: Optional[str] = None,
        is_verified: bool = False
    ) -> User:
        """Create a new user with associated tenant."""
        user = User(
            email=email.lower(),
            hashed_password=get_password_hash(password) if password else None,
            full_name=full_name,
            is_verified=is_verified,
        )
        self.db.add(user)
        await self.db.flush()

        # Create tenant for user
        tenant = Tenant(
            name=f"{full_name or email}'s Workspace",
            owner_id=user.id
        )
        self.db.add(tenant)
        await self.db.flush()

        return user

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user with email and password."""
        user = await self.get_user_by_email(email)
        if not user or not user.hashed_password:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def create_tokens(self, user: User) -> dict:
        """Create access and refresh tokens for a user."""
        # Get tenant ID
        result = await self.db.execute(
            select(Tenant).where(Tenant.owner_id == user.id)
        )
        tenant = result.scalar_one_or_none()

        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "tenant_id": str(tenant.id) if tenant else None
        }

        access_token = create_access_token(token_data)
        refresh_token, expires_at = create_refresh_token(token_data)

        # Store refresh token
        db_refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at
        )
        self.db.add(db_refresh_token)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    async def refresh_access_token(self, refresh_token: str) -> Optional[dict]:
        """Refresh an access token using a refresh token."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        # Verify token exists in database and not expired
        result = await self.db.execute(
            select(RefreshToken).where(
                and_(
                    RefreshToken.token == refresh_token,
                    RefreshToken.expires_at > datetime.utcnow()
                )
            )
        )
        db_token = result.scalar_one_or_none()
        if not db_token:
            return None

        # Get user
        user = await self.get_user_by_id(db_token.user_id)
        if not user or not user.is_active:
            return None

        # Create new tokens
        return await self.create_tokens(user)

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token."""
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        db_token = result.scalar_one_or_none()
        if db_token:
            await self.db.delete(db_token)
            return True
        return False

    async def get_tenant_for_user(self, user_id: UUID) -> Optional[Tenant]:
        """Get tenant associated with a user."""
        result = await self.db.execute(
            select(Tenant).where(Tenant.owner_id == user_id)
        )
        return result.scalar_one_or_none()
