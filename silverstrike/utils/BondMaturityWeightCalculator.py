from silverstrike.models import SecurityBondMaturity
from silverstrike.utils.InvestmentWeightCalculator import InvestmentWeightCalculator


class BondMaturityWeightCalculator(InvestmentWeightCalculator):
    def calculate_weights(self):
        total_money_maturity = dict()
        bond_weight_maturity = dict()
        security_totals = dict()
        total_value = 0.0
        quantities = self._InvestmentWeightCalculator__get_security_quantities()
        bond_maturity_distribution = SecurityBondMaturity.objects.filter(security__in=quantities.keys())
        prices = self.priceGetter.get_latest_prices([distribution.security.isin for distribution in bond_maturity_distribution])

        # Get total money on bonds
        for isin in prices.keys():
            security_totals[isin] = prices[isin] * quantities[isin]
            total_value += float(security_totals[isin])

        # Get total money per maturity level (Year range)
        for maturity in bond_maturity_distribution:
            total_maturity = total_money_maturity.get(maturity.maturity_id)
            total = float(security_totals[maturity.security.isin]) * float(maturity.allocation / 100)
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
                allocation = (float(security_totals[maturity.security.isin]) * float(maturity.allocation) / total_value)

            if total_maturity is None:
                bond_weight_maturity[maturity.maturity_id] = allocation
            else:
                bond_weight_maturity[maturity.maturity_id] = total_maturity + allocation

        return bond_weight_maturity
