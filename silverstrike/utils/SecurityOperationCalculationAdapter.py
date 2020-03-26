from django.core.exceptions import ObjectDoesNotExist

from silverstrike.models import SecurityDetails, SecurityQuantity
from silverstrike.utils.PriceGetter import PriceGetter


class SecurityOperationCalculationAdapter:
    def __init__(self,security_list):
        # TODO should be a dict isin -> quantity
        self.security_list = security_list

    def get_operation_list(self):
        # TODO add account
        operation_list = []
        details = SecurityDetails.objects.filter(isin__in=self.security_list.keys())
        for security_detail in details:
            operation = ""
            ticker = security_detail.ticker
            isin = security_detail.isin
            try:
                current_quantity = SecurityQuantity.objects.get(security=security_detail).quantity
            except ObjectDoesNotExist:
                current_quantity = 0
            price = PriceGetter().get_latest_prices([isin])[isin]
            #TODO check last price is on
            new_quantity = self.security_list[isin]
            if current_quantity < new_quantity:
                # TODO enum buy sell
                operation = "buy"
            else:
                operation = "sell"

            quantity_difference = new_quantity-current_quantity
            if quantity_difference != 0:
                result = InvestmentCalculationResult(operation, ticker,quantity_difference , price, new_quantity)
                operation_list.append(result)
        return operation_list

class InvestmentCalculationResult:
    def __init__(self, operation, ticker, units, unit_price, total_units):
        self.operation = operation
        #TODO change name operration see html inv calc
        self.ticker = ticker
        self.units = units
        self.unit_price = unit_price
        self.total_units = total_units
        self.total_price = self.__total_price()

    def __total_price(self):
        return abs(self.units) * self.unit_price

