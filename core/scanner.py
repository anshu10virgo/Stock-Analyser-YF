"""Backward-compatible facade for the scan application service.

New code should use :class:`services.scan_service.ScanService` with a
``ScanConfig`` directly. This class preserves the established UI and script API.
"""

from models.scan_config import ScanConfig
from services.scan_service import ScanService


class StockScanner:
    """Compatibility adapter returning the existing dataframe dictionary."""

    def __init__(
        self,
        short_ma,
        long_ma,
        max_cross_age,
        min_long_ma_decline_duration=60,
        min_long_ma_decline=10,
        max_price_premium=10,
        require_post_cross_sessions=False,
        adjusted_prices=False,
    ):
        self.config = ScanConfig(
            short_ma=short_ma,
            long_ma=long_ma,
            max_cross_age=max_cross_age,
            min_long_ma_decline_duration=min_long_ma_decline_duration,
            min_long_ma_decline=min_long_ma_decline,
            max_price_premium=max_price_premium,
            require_post_cross_sessions=require_post_cross_sessions,
            adjusted_prices=adjusted_prices,
        )
        self._service = ScanService(self.config)

    def scan(self, symbols, progress_callback=None):
        """Run the typed service and preserve the dataframe result contract."""
        return self._service.scan(symbols, progress_callback).as_dataframes()
