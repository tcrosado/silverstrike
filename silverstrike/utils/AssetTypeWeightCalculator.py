from silverstrike.models import SecurityDetails
from silverstrike.utils.InvestmentWeightCalculator import InvestmentWeightCalculator


class AssetTypeWeightCalculator(InvestmentWeightCalculator):
    def __init__(self, security_quantity_getter=None):
        if security_quantity_getter is None:
            super().__init__()
        else:
            super().__init__(security_quantity_getter)

    def calculate_weights(self):
        weights = dict()

        quantities = self._InvestmentWeightCalculator__get_security_quantities()  # isin -> quantity
        prices = self.priceGetter.get_latest_prices(quantities.keys())  # isin -> price

        total_value = 0.0

        for isin in quantities.keys():
            security_type = self._InvestmentWeightCalculator__get_type(isin)
            security_value = float(quantities.get(isin, 0) * prices.get(isin, 0))
            total_value += security_value

            weights.setdefault(security_type, 0.0)
            weights[security_type] += security_value

        for (index, name) in SecurityDetails.SECURITY_TYPES:
            security_weight = weights.get(name,0)
            if security_weight == 0 or total_value == 0:
                weights[name] = 0
            else:
                weights[name] = float(weights.get(name) / total_value) * 100

        return weights
