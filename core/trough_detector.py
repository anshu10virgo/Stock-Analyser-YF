import pandas as pd
import numpy as np


class TroughDetector:

    @staticmethod
    def detect_troughs(
        df,
        lookback=120,
        window=5
    ):

        if len(df) < lookback:
            return {
                "count": 0,
                "dates": [],
                "higher_low": False
            }

        working_df = df.tail(lookback)

        lows = working_df["Low"]

        troughs = []

        for i in range(window, len(lows) - window):

            current = lows.iloc[i]

            left = lows.iloc[i-window:i]
            right = lows.iloc[i+1:i+window+1]

            if current <= left.min() and current <= right.min():

                troughs.append(
                    (
                        lows.index[i],
                        current
                    )
                )

        higher_low = False

        if len(troughs) >= 2:

            higher_low = (
                troughs[-1][1]
                >
                troughs[-2][1]
            )

        return {
            "count": len(troughs),
            "dates": [x[0] for x in troughs],
            "higher_low": higher_low
        }