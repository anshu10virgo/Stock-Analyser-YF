from datetime import datetime


class GoldenCrossDetector:

    @staticmethod
    def find_cross(
        df,
        max_age_days,
        pre_cross_days
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

        cross_position = (
            df.index.get_loc(cross_date)
        )

        start_position = max(
            0,
            cross_position
            - pre_cross_days
        )

        validation_df = (
            df.iloc[
                start_position:
                cross_position
            ]
        )

        if len(validation_df) < pre_cross_days:
            return result

        pre_cross_valid = (
            validation_df["MA_SHORT"]
            <
            validation_df["MA_LONG"]
        ).all()

        if not pre_cross_valid:
            return result

        result["valid"] = True
        result["cross_date"] = cross_date
        result["days_since_cross"] = days_since

        return result