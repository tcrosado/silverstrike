from silverstrike.models import SecurityDistribution
from silverstrike.utils.InvestmentWeightCalculator import InvestmentWeightCalculator


class RegionDistributionWeightCalculator(InvestmentWeightCalculator):
    def calculate_weights(self):
        total_money_region = dict()
        security_totals = dict()
        stock_weight_regions = dict()
        total_value = 0.0
        quantities = self._InvestmentWeightCalculator__get_security_quantities()
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
