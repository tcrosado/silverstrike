from abc import ABC

from silverstrike.models import SecurityQuantity


class SecurityQuantityGetter:

    def __init__(self):
        self.security_quantity = SecurityQuantity

    def get_quantities(self):
        # isin -> quantity
        quantities = self.security_quantity.objects.all()
        security_quantities = dict()

        for security_quantity in quantities:
            isin = security_quantity.security.isin # FIXME use reference as here
            security_quantities[isin] = security_quantity.quantity
        return security_quantities
        #TODO test Bond and REIT
    #TODO CronJob price update