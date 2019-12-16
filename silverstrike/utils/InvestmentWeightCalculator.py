from django.db.models import Max

from silverstrike.models import SecurityQuantity, SecurityDetails, SecurityBondMaturity, \
    SecurityDistribution
from silverstrike.utils.PriceGetter import PriceGetter


class InvestmentWeightCalculator:

    def __init__(self):
        self.priceGetter = PriceGetter()

    @staticmethod
    def __get_security_quantities():
        quantities = SecurityQuantity.objects.all()
        security_quantities = dict()

        for security in quantities:
            security_quantities[security.isin] = security.quantity
        return security_quantities

    @staticmethod
    def __get_type(isin):
        security = SecurityDetails.objects.get(isin=isin)
        return SecurityDetails.SECURITY_TYPES[security.security_type][1]


    def get_asset_type_weights(self):
        weights = dict()

        quantities = self.__get_security_quantities()  # isin -> quantity
        prices = self.priceGetter.get_latest_prices(quantities.keys())  # isin -> price

        total_value = 0.0

        for isin in quantities.keys():
            security_type = self.__get_type(isin)
            security_value = float(quantities.get(isin, 0) * prices.get(isin, 0))
            total_value += security_value

            weights.setdefault(security_type, 0.0)
            weights[security_type] += float(weights[security_type]) + security_value

        for (index, name) in SecurityDetails.SECURITY_TYPES:
            weights[name] = float(weights.get(name) / total_value) * 100

        return weights

    def get_bond_maturity_weights(self):
        total_money_maturity = dict()
        bond_weight_maturity = dict()
        security_totals = dict()
        total_value = 0.0
        quantities = self.__get_security_quantities()
        bond_maturity_distribution = SecurityBondMaturity.objects.filter(isin__in=quantities.keys())
        prices = self.priceGetter.get_latest_prices([bond.isin for bond in bond_maturity_distribution])

        # Get total money on bonds
        for isin in prices.keys():
            security_totals[isin] = prices[isin] * quantities[isin]
            total_value += float(security_totals[isin])

        # Get total money per maturity level (Year range)
        for maturity in bond_maturity_distribution:
            total_maturity = total_money_maturity.get(maturity.maturity_id)
            total = float(security_totals[maturity.isin]) * float(maturity.allocation / 100)
            if total_maturity is None:
                total_money_maturity[maturity.maturity_id] = total
            else:
                total_money_maturity[maturity.maturity_id] = total_maturity + total

        # Get bond maturity by year range %
        for maturity in bond_maturity_distribution:
            total_maturity = bond_weight_maturity.get(maturity.maturity_id)
            if total_money_maturity[maturity.maturity_id] == 0:
                allocation = 0
            else:
                allocation = (float(security_totals[maturity.isin]) * float(maturity.allocation) / total_value)

            if total_maturity is None:
                bond_weight_maturity[maturity.maturity_id] = allocation
            else:
                bond_weight_maturity[maturity.maturity_id] = total_maturity + allocation

        return bond_weight_maturity

    def get_world_distribution_weights(self):
        total_money_region = dict()
        security_totals = dict()
        stock_weight_regions = dict()
        total_value = 0.0
        quantities = self.__get_security_quantities()
        security_distribution = SecurityDistribution.objects.filter(isin__in=quantities.keys())
        prices = self.priceGetter.get_latest_prices([security.isin for security in security_distribution])

        # Get total money on bonds
        for isin in prices.keys():
            security_totals[isin] = prices[isin] * quantities[isin]
            total_value += float(security_totals[isin])

        for dist in security_distribution:

            total_region = total_money_region.get(dist.region_id)
            total = float(security_totals[dist.isin]) * float(dist.allocation / 100)
            if total_region is None:
                total_money_region[dist.region_id] = total
            else:
                total_money_region[dist.region_id] = total_region + total

        for dist in security_distribution:
            total_region = stock_weight_regions.get(dist.region_id)
            if total_money_region[dist.region_id] == 0:
                allocation = 0
            else:
                allocation = float(security_totals[dist.isin]) * float(dist.allocation) / total_value

            if total_region is None:
                stock_weight_regions[dist.region_id] = allocation
            else:
                stock_weight_regions[dist.region_id] = total_region + allocation

        return stock_weight_regions


    #TODO Target update get current data into edit
    #TODO Move this to separate calculators