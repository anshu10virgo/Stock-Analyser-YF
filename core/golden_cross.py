from datetime import datetime


class GoldenCrossDetector:

    @staticmethod
    def find_cross(
        df,
        max_age_days,
    ):

        result = {
            "valid": False,
            "cross_date": None,
            "days_since_cross": None
        }

        if len(df) < 250:
            return result

        short_ma = df["MA_SHORT"]
        long_ma = df["MA_LONG"]

        cross_mask = (
            (short_ma.shift(1) <= long_ma.shift(1))
            &
            (short_ma > long_ma)
        )

        cross_dates = df.index[cross_mask]

        if len(cross_dates) == 0:
            return result

        cross_date = cross_dates[-1]

        days_since = (
            datetime.today().date()
            -
            cross_date.date()
        ).days

        if days_since > max_age_days:
            return result

        result["valid"] = True
        result["cross_date"] = cross_date
        result["days_since_cross"] = days_since

        return result
