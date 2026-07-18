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
        pre_cross_days,
        slope_lookback,
        max_distance,
        require_pre_cross_trough=False,
        require_pre_cross_decline=False,
        require_post_cross_sessions=False,
        require_post_cross_increase=False,
        adjusted_prices=False,
    ):
        self.config = ScanConfig(
            short_ma=short_ma,
            long_ma=long_ma,
            max_cross_age=max_cross_age,
            pre_cross_days=pre_cross_days,
            slope_lookback=slope_lookback,
            max_distance=max_distance,
            require_pre_cross_trough=require_pre_cross_trough,
            require_pre_cross_decline=require_pre_cross_decline,
            require_post_cross_sessions=require_post_cross_sessions,
            require_post_cross_increase=require_post_cross_increase,
            adjusted_prices=adjusted_prices,
        )
        self._service = ScanService(self.config)

    def scan(self, symbols, progress_callback=None):
        """Run the typed service and preserve the dataframe result contract."""
        return self._service.scan(symbols, progress_callback).as_dataframes()
