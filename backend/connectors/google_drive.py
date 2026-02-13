"""
Google Drive connector for syncing documents.
"""
from typing import List, Dict, Any, Optional
import httpx

from connectors.base import BaseConnector
from core.config import get_settings

settings = get_settings()


class GoogleDriveConnector(BaseConnector):
    """Connector for Google Drive integration."""

    SCOPES = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.metadata.readonly"
    ]

    @classmethod
    def get_oauth_url(cls, state: str) -> str:
        """Get Google OAuth URL."""
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": f"{settings.FRONTEND_URL}/integrations/google/callback",
            "response_type": "code",
            "scope": " ".join(cls.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    @classmethod
    async def exchange_code(cls, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": f"{settings.FRONTEND_URL}/integrations/google/callback"
                }
            )
            response.raise_for_status()
            return response.json()

    async def fetch_items(self) -> List[Dict[str, Any]]:
        """Fetch documents from Google Drive."""
        items = []
        access_token = self.credentials.get("access_token")

        async with httpx.AsyncClient() as client:
            # List files
            response = await client.get(
                "https://www.googleapis.com/drive/v3/files",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "pageSize": 100,
                    "fields": "files(id,name,mimeType,webViewLink,createdTime,modifiedTime)",
                    "q": "trashed=false and (mimeType contains 'document' or mimeType contains 'text' or mimeType contains 'pdf')"
                }
            )
            response.raise_for_status()
            data = response.json()

            for file in data.get("files", []):
                # Get file content
                content = await self._get_file_content(client, access_token, file["id"], file["mimeType"])

                items.append({
                    "external_id": file["id"],
                    "title": file["name"],
                    "content": content,
                    "source_url": file.get("webViewLink"),
                    "metadata": {
                        "mime_type": file["mimeType"],
                        "created_at": file.get("createdTime"),
                        "modified_at": file.get("modifiedTime")
                    }
                })

        return items

    async def _get_file_content(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        file_id: str,
        mime_type: str
    ) -> str:
        """Get content of a file."""
        try:
            # For Google Docs, export as text
            if "google-apps" in mime_type:
                export_type = "text/plain"
                response = await client.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"mimeType": export_type}
                )
            else:
                # For other files, try to get content
                response = await client.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"alt": "media"}
                )

            if response.status_code == 200:
                return response.text[:50000]  # Limit content size
        except Exception:
            pass

        return ""

    async def test_connection(self) -> bool:
        """Test Google Drive connection."""
        access_token = self.credentials.get("access_token")
        if not access_token:
            return False

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/drive/v3/about",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "user"}
            )
            return response.status_code == 200

    async def refresh_credentials(self) -> Optional[Dict[str, Any]]:
        """Refresh access token using refresh token."""
        refresh_token = self.credentials.get("refresh_token")
        if not refresh_token:
            return None

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    **self.credentials,
                    "access_token": data["access_token"]
                }

        return None
