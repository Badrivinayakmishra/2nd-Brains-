"""
Connector registry and factory.
"""
from typing import Optional, Type
from database.models import ConnectorType

# Lazy imports to avoid circular dependencies
_connector_classes = {}


def get_connector_class(connector_type: ConnectorType) -> Optional[Type]:
    """Get connector class by type."""
    if connector_type not in _connector_classes:
        # Lazy load connector classes
        if connector_type == ConnectorType.GOOGLE_DRIVE:
            from connectors.google_drive import GoogleDriveConnector
            _connector_classes[connector_type] = GoogleDriveConnector
        elif connector_type == ConnectorType.GMAIL:
            from connectors.gmail import GmailConnector
            _connector_classes[connector_type] = GmailConnector
        elif connector_type == ConnectorType.SLACK:
            from connectors.slack import SlackConnector
            _connector_classes[connector_type] = SlackConnector
        elif connector_type == ConnectorType.NOTION:
            from connectors.notion import NotionConnector
            _connector_classes[connector_type] = NotionConnector
        elif connector_type == ConnectorType.GITHUB:
            from connectors.github import GitHubConnector
            _connector_classes[connector_type] = GitHubConnector
        elif connector_type == ConnectorType.WEBSCRAPER:
            from connectors.webscraper import WebScraperConnector
            _connector_classes[connector_type] = WebScraperConnector

    return _connector_classes.get(connector_type)
