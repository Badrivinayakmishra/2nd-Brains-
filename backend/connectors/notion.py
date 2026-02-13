"""
Notion connector for syncing pages and databases.
"""
from typing import List, Dict, Any, Optional
import httpx

from connectors.base import BaseConnector
from core.config import get_settings

settings = get_settings()


class NotionConnector(BaseConnector):
    """Connector for Notion integration."""

    NOTION_VERSION = "2022-06-28"

    @classmethod
    def get_oauth_url(cls, state: str) -> str:
        """Get Notion OAuth URL."""
        params = {
            "client_id": settings.NOTION_CLIENT_ID,
            "redirect_uri": f"{settings.FRONTEND_URL}/integrations/notion/callback",
            "response_type": "code",
            "owner": "user",
            "state": state
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://api.notion.com/v1/oauth/authorize?{query}"

    @classmethod
    async def exchange_code(cls, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        import base64

        credentials = base64.b64encode(
            f"{settings.NOTION_CLIENT_ID}:{settings.NOTION_CLIENT_SECRET}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.notion.com/v1/oauth/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json"
                },
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": f"{settings.FRONTEND_URL}/integrations/notion/callback"
                }
            )
            response.raise_for_status()
            data = response.json()

            return {
                "access_token": data["access_token"],
                "workspace_id": data.get("workspace_id"),
                "workspace_name": data.get("workspace_name")
            }

    async def fetch_items(self) -> List[Dict[str, Any]]:
        """Fetch pages from Notion."""
        items = []
        access_token = self.credentials.get("access_token")

        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": self.NOTION_VERSION
            }

            # Search for all pages
            response = await client.post(
                "https://api.notion.com/v1/search",
                headers=headers,
                json={
                    "filter": {"property": "object", "value": "page"},
                    "page_size": 100
                }
            )
            response.raise_for_status()
            data = response.json()

            for page in data.get("results", []):
                page_id = page["id"]

                # Get page content
                content = await self._get_page_content(client, headers, page_id)
                title = self._extract_title(page)

                items.append({
                    "external_id": page_id,
                    "title": title,
                    "content": content,
                    "source_url": page.get("url"),
                    "metadata": {
                        "created_time": page.get("created_time"),
                        "last_edited_time": page.get("last_edited_time"),
                        "parent_type": page.get("parent", {}).get("type")
                    }
                })

        return items

    async def _get_page_content(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        page_id: str
    ) -> str:
        """Get content blocks from a page."""
        content_parts = []

        try:
            response = await client.get(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                headers=headers,
                params={"page_size": 100}
            )
            response.raise_for_status()
            data = response.json()

            for block in data.get("results", []):
                text = self._extract_block_text(block)
                if text:
                    content_parts.append(text)

        except Exception:
            pass

        return "\n\n".join(content_parts)

    def _extract_title(self, page: Dict) -> str:
        """Extract title from page properties."""
        properties = page.get("properties", {})

        # Try common title property names
        for prop_name in ["title", "Title", "Name", "name"]:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get("type") == "title":
                    title_arr = prop.get("title", [])
                    if title_arr:
                        return title_arr[0].get("plain_text", "Untitled")

        return "Untitled"

    def _extract_block_text(self, block: Dict) -> str:
        """Extract text from a block."""
        block_type = block.get("type")
        block_data = block.get(block_type, {})

        if "rich_text" in block_data:
            return "".join(
                t.get("plain_text", "")
                for t in block_data["rich_text"]
            )

        return ""

    async def test_connection(self) -> bool:
        """Test Notion connection."""
        access_token = self.credentials.get("access_token")
        if not access_token:
            return False

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.notion.com/v1/users/me",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Notion-Version": self.NOTION_VERSION
                }
            )
            return response.status_code == 200
