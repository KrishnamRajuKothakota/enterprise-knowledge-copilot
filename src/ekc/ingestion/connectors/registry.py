"""
Connector registry — maps file extensions to connector instances.
"""
from src.ekc.ingestion.connectors.base import SourceConnector
from src.ekc.ingestion.connectors.pdf import PDFConnector
from src.ekc.ingestion.connectors.csv_connector import CSVConnector
from src.ekc.ingestion.connectors.pptx_connector import PPTXConnector

_CONNECTORS: list[SourceConnector] = [
    PDFConnector(),
    CSVConnector(),
    PPTXConnector(),
]


def get_connector(path: str) -> SourceConnector | None:
    for connector in _CONNECTORS:
        if connector.can_handle(path):
            return connector
    return None