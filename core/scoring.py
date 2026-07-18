class ScoringEngine:

    @staticmethod
    def score_cross(
        days_since_cross
    ):

        if days_since_cross is None:
            return 0

        if days_since_cross <= 10:
            return 20

        if days_since_cross <= 30:
            return 15

        return 10

    @staticmethod
    def score_slope(
        slope_label
    ):

        mapping = {

            "STRONG_POSITIVE": 20,
            "POSITIVE": 15,
            "FLAT": 5,
            "NEGATIVE": 0

        }

        return mapping.get(
            slope_label,
            0
        )

    @staticmethod
    def score_troughs(
        count
    ):

        if count >= 3:
            return 15

        if count == 2:
            return 10

        if count == 1:
            return 5

        return 0

    @staticmethod
    def score_distance(
        distance
    ):

        distance = abs(distance)

        if distance <= 2:
            return 15

        if distance <= 5:
            return 10

        if distance <= 10:
            return 5

        return 0

    @staticmethod
    def score_pe(
        pe
    ):

        if pe is None:
            return 0

        if pe < 20:
            return 10

        if pe < 40:
            return 5

        return 0

    @staticmethod
    def score_eps(
        eps
    ):

        if eps is None:
            return 0

        if eps > 0:
            return 10

        return 0

    @staticmethod
    def score_market_cap(
        market_cap
    ):

        if market_cap is None:
            return 0

        if market_cap > 200000000000:
            return 10

        if market_cap > 50000000000:
            return 5

        return 0