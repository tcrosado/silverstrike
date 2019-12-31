from silverstrike.utils.SecurityQuantityGetter import SecurityQuantityGetter


class SecurityQuantityMutableGetter(SecurityQuantityGetter):
    def __init__(self):
        self.quantities = dict()

    def get_quantities(self):
        return self.quantities

    def clear_list(self):
        self.quantities = dict()

    def remove_security(self, isin):
        self.quantities.pop(isin)

    def set_security_quantity(self, isin, quantity):
        self.quantities[isin] = quantity

    def get_security_quantity(self, isin):
        return self.quantities.get(isin, 0)
