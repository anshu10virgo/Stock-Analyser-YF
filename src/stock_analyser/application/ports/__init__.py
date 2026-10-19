"""Provider contracts consumed by application use cases."""

from .fundamentals import FundamentalsPort, IndustryValuationPort, ScreenerFundamentalsPort
from .mailer import MailerPort
from .market_data import MarketDataPort
from .model_provider import ModelProviderPort
from .storage import StoragePort

__all__ = [
    "FundamentalsPort",
    "IndustryValuationPort",
    "MailerPort",
    "MarketDataPort",
    "ModelProviderPort",
    "ScreenerFundamentalsPort",
    "StoragePort",
]
