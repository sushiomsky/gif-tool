"""Service adapters for GIF upload targets."""
from .klipy import KlipyClient
from .tenor import TenorClient
from .giphy import GiphyClient

__all__ = ["KlipyClient", "TenorClient", "GiphyClient"]
