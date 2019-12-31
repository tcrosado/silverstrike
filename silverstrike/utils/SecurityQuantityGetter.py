from abc import ABC

from silverstrike.models import SecurityQuantity


class SecurityQuantityGetter:

    def __init__(self):
        self.security_quantity = SecurityQuantity

    def get_quantities(self):
        # isin -> quantity
        quantities = self.security_quantity.objects.all()
        security_quantities = dict()

        for security in quantities:
            security_quantities[security.isin] = security.quantity
        return security_quantities
