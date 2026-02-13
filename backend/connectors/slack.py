"""
Slack connector for syncing messages.
"""
from typing import List, Dict, Any, Optional
import httpx

from connectors.base import BaseConnector
from core.config import get_settings

settings = get_settings()


class SlackConnector(BaseConnector):
    """Connector for Slack integration."""

    SCOPES = [
        "channels:history",
        "channels:read",
        "groups:history",
        "groups:read",
        "im:history",
        "im:read",
        "users:read"
    ]

    @classmethod
    def get_oauth_url(cls, state: str) -> str:
        """Get Slack OAuth URL."""
        params = {
            "client_id": settings.SLACK_CLIENT_ID,
            "redirect_uri": f"{settings.FRONTEND_URL}/integrations/slack/callback",
            "scope": ",".join(cls.SCOPES),
            "state": state
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://slack.com/oauth/v2/authorize?{query}"

    @classmethod
    async def exchange_code(cls, code: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": settings.SLACK_CLIENT_ID,
                    "client_secret": settings.SLACK_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": f"{settings.FRONTEND_URL}/integrations/slack/callback"
                }
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                raise Exception(data.get("error", "Unknown error"))

            return {
                "access_token": data["access_token"],
                "team_id": data["team"]["id"],
                "team_name": data["team"]["name"]
            }

    async def fetch_items(self) -> List[Dict[str, Any]]:
        """Fetch messages from Slack channels."""
        items = []
        access_token = self.credentials.get("access_token")

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}"}

            # Get channels
            channels_response = await client.get(
                "https://slack.com/api/conversations.list",
                headers=headers,
                params={"types": "public_channel,private_channel", "limit": 100}
            )
            channels_data = channels_response.json()

            if not channels_data.get("ok"):
                return items

            for channel in channels_data.get("channels", []):
                channel_id = channel["id"]
                channel_name = channel["name"]

                # Get messages from channel
                messages_response = await client.get(
                    "https://slack.com/api/conversations.history",
                    headers=headers,
                    params={"channel": channel_id, "limit": 200}
                )
                messages_data = messages_response.json()

                if not messages_data.get("ok"):
                    continue

                for message in messages_data.get("messages", []):
                    if message.get("type") != "message" or message.get("subtype"):
                        continue

                    items.append({
                        "external_id": f"{channel_id}_{message.get('ts', '')}",
                        "title": f"#{channel_name} message",
                        "content": message.get("text", ""),
                        "source_url": None,
                        "metadata": {
                            "channel_id": channel_id,
                            "channel_name": channel_name,
                            "user": message.get("user"),
                            "timestamp": message.get("ts")
                        }
                    })

        return items

    async def test_connection(self) -> bool:
        """Test Slack connection."""
        access_token = self.credentials.get("access_token")
        if not access_token:
            return False

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            data = response.json()
            return data.get("ok", False)
