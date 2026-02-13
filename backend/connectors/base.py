"""
Base connector class with common functionality.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseConnector(ABC):
    """Base class for all connectors."""

    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials

    @classmethod
    @abstractmethod
    def get_oauth_url(cls, state: str) -> str:
        """Get OAuth authorization URL."""
        pass

    @classmethod
    @abstractmethod
    async def exchange_code(cls, code: str) -> Dict[str, Any]:
        """Exchange OAuth code for credentials."""
        pass

    @abstractmethod
    async def fetch_items(self) -> List[Dict[str, Any]]:
        """
        Fetch items from the connector source.
        Returns list of items with:
        - title: str
        - content: str
        - external_id: str
        - source_url: Optional[str]
        - metadata: Dict
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the connection is valid."""
        pass

    async def refresh_credentials(self) -> Optional[Dict[str, Any]]:
        """Refresh credentials if supported. Returns new credentials or None."""
        return None
