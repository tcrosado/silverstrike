from abc import ABC

from silverstrike.models import SecurityDetails
from silverstrike.utils.PriceGetter import PriceGetter
from silverstrike.utils.SecurityQuantityGetter import SecurityQuantityGetter


class InvestmentWeightCalculator(ABC):

    def __init__(self, security_quantity_getter=SecurityQuantityGetter()):
        self.priceGetter = PriceGetter()
        self.security_quantity_getter = security_quantity_getter

    def __get_security_quantities(self):
        return self.security_quantity_getter.get_quantities()

    @staticmethod
    def __get_type(isin):
        security = SecurityDetails.objects.get(isin=isin)
        return SecurityDetails.SECURITY_TYPES[security.security_type][1]

    def calculate_weights(self):
        raise NotImplementedError

    # TODO Target update get current data into edit