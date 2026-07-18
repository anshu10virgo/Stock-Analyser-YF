class TroughDetector:

    @staticmethod
    def detect_troughs(
        df,
        window=5
    ):

        if len(df) < (window * 2) + 1:
            return {
                "count": 0,
                "dates": [],
            }

        lows = df["Low"]

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

        return {
            "count": len(troughs),
            "dates": [x[0] for x in troughs],
        }
