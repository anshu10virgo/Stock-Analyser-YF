"""Shared user-facing labels for scanner rejection reasons."""

REJECTION_LABELS = {
    "Unable to download market data for this scan": "Market data could not be downloaded",
    "No complete market data was returned for the symbol": "No complete price history is available",
    "Short MA 5-session slope is not positive": "Short MA is not rising",
    "No Golden Cross within the configured age": "No recent Golden Cross",
    "Short MA is not above Long MA": "Short MA has not crossed above Long MA",
    "Short MA is farther below Long MA than the configured maximum gap": "Moving averages are farther apart than allowed",
    "Short MA 5-session slope is not greater than Long MA 5-session slope": "Short MA is not converging faster than Long MA",
    "Short MA was not strictly below Long MA throughout the configured pre-cross validation period": "Pre-cross trend was not stable for the selected period",
    "Insufficient Long MA history for 52-week high": "Not enough Long-MA history",
    "Long MA decline from 52-week high to trough is below configured minimum": "Long-MA decline is smaller than required",
    "Long MA decline from 52-week high to trough is shorter than configured minimum duration": "Long-MA decline duration is shorter than required",
    "Post-trough 5-session Long MA slope is not positive": "Long MA has not started rising after its trough",
    "Long MA is below its trough or its latest 5-session slope is negative": "Long MA is still falling",
    "Close price is not above Long MA": "Current price is not above Long MA",
    "Close price is too far above Long MA": "Current price is too far above Long MA",
    "Unexpected error while evaluating the symbol": "Stock could not be evaluated",
}


def friendly_rejection(reason: str) -> str:
    """Translate internal scanner wording into a compact user-facing label."""
    return REJECTION_LABELS.get(reason, reason)
