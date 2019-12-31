import operator

from silverstrike.models import SecurityDetails, SecurityTypeTarget, SecurityRegionTarget, SecurityBondMaturityTarget, \
    SecurityDistribution, SecurityBondMaturity
from silverstrike.utils.AssetTypeWeightCalculator import AssetTypeWeightCalculator
from silverstrike.utils.BondMaturityWeightCalculator import BondMaturityWeightCalculator
from silverstrike.utils.InvestmentWeightCalculator import InvestmentWeightCalculator
from silverstrike.utils.PriceGetter import PriceGetter
from silverstrike.utils.RegionDistributionWeightCalculator import RegionDistributionWeightCalculator
from silverstrike.utils.SecurityQuantityGetter import SecurityQuantityGetter
from silverstrike.utils.SecurityQuantityMutableGetter import SecurityQuantityMutableGetter


class InvestmentCalculator:

    def __init__(self):
        self.price_getter = PriceGetter()
        self.security_quantity_getter = SecurityQuantityMutableGetter()
        self.region_weight_calculator = RegionDistributionWeightCalculator(self.security_quantity_getter)
        self.bond_weight_calculator = BondMaturityWeightCalculator(self.security_quantity_getter)
        self.asset_weight_calculator = AssetTypeWeightCalculator(self.security_quantity_getter)

    def buy(self, amount):
        added_amount = 0
        updated = True

        #Set current security quantities
        self.security_quantity_getter.clear_list()
        current_security_quantity = SecurityQuantityGetter().get_quantities()
        for isin in current_security_quantity.keys():
            self.security_quantity_getter.set_security_quantity(isin,current_security_quantity[isin])

        while added_amount != amount and updated:
            print(self.security_quantity_getter.get_quantities())
            updated = False
            # select asset to add
            delta_asset_weights = self.__get_delta_asset_weights()
            print(delta_asset_weights)
            selected_asset = min(delta_asset_weights, key=delta_asset_weights.get)
            print(selected_asset)

            if selected_asset == SecurityDetails.STOCK:
                # get delta_region_target
                delta_region_weights = self.__get_delta_region_weights()
                # get min delta_region
                selected_region = min(delta_region_weights, key=delta_region_weights.get)
                # get security with max region
                stock_list = SecurityDetails.objects.filter(security_type=SecurityDetails.STOCK)
                isin_list = [stock.isin for stock in stock_list]
                region_weight_list = SecurityDistribution.objects.filter(region_id=selected_region, isin__in=isin_list)
                selected_isin = max(region_weight_list, key=operator.attrgetter('allocation')).isin

                # get price
                #FIXME if no price avaliable
                price = float(self.price_getter.get_latest_prices([selected_isin])[selected_isin])

                if amount >= price:
                    added_amount = added_amount + price
                    amount = amount - price
                    security_quantity = self.security_quantity_getter.get_security_quantity(selected_isin)
                    self.security_quantity_getter.set_security_quantity(selected_isin, security_quantity + 1)
                    updated = True

            elif selected_asset == SecurityDetails.BOND:
                # get delta_maturity_target
                delta_maturity_weights = self.__get_delta_maturity_weights()
                # get min delta_maturity
                selected_maturity = min(delta_maturity_weights, key=delta_maturity_weights.get)

                # get bond with max maturity
                bond_list = SecurityDetails.objects.filter(security_type=SecurityDetails.BOND)
                isin_list = [bond.isin for bond in bond_list]
                maturity_weight_list = SecurityBondMaturity.objects.filter(maturity_id=selected_maturity, isin__in=isin_list)
                selected_allocaion = max(maturity_weight_list, key=operator.attrgetter('allocation'))
                selected_isin = selected_allocaion.isin
                # get price
                price = float(self.price_getter.get_latest_prices([selected_isin])[selected_isin])
                # update amount
                if amount >= price:
                    added_amount = added_amount + price
                    amount = amount - price
                    security_quantity = self.security_quantity_getter.get_security_quantity(selected_isin)
                    self.security_quantity_getter.set_security_quantity(selected_isin, security_quantity + 1)
                    updated = True

            elif selected_asset == SecurityDetails.REIT:
                # add reit asset
                #FIXME if more than 1 REIT
                selected_security = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT)[0]
                selected_isin = selected_security.isin
                price = float(self.price_getter.get_latest_prices([selected_isin])[selected_isin])

                if amount >= price:
                    added_amount = added_amount + price
                    amount = amount - price
                    security_quantity = self.security_quantity_getter.get_security_quantity(selected_isin)
                    self.security_quantity_getter.set_security_quantity(selected_isin, security_quantity + 1)
                    updated = True
            else:
                raise Exception("Unknown asset selected")


        #TODO Test
        print("End Cal")
        return self.security_quantity_getter.get_quantities()

    #TODO refactor deltas
    def __get_delta_asset_weights(self):
        asset_weights = self.asset_weight_calculator.calculate_weights()
        print("Asset Weights")
        print(asset_weights)
        asset_targets = SecurityTypeTarget.objects.all() #FIXME single user
        delta_asset_weigths = dict()

        for target in asset_targets:
            asset_name = SecurityDetails.SECURITY_TYPES[target.security_type][1]
            delta_asset_weigths[target.security_type] = asset_weights.get(asset_name, 0) - target.allocation

        return delta_asset_weigths

    def __get_delta_region_weights(self):
        region_weights = self.region_weight_calculator.calculate_weights()
        region_targets = SecurityRegionTarget.objects.all()
        delta_region_weigths = dict()

        for target in region_targets:
            delta_region_weigths[target.region_id] = region_weights.get(target.region_id, 0) - target.allocation

        return delta_region_weigths

    def __get_delta_maturity_weights(self):
        maturity_weights = self.bond_weight_calculator.calculate_weights()
        maturity_targets = SecurityBondMaturityTarget.objects.all()
        delta_maturity_weights = dict()

        for target in maturity_targets:
            delta_maturity_weights[target.maturity_id] = maturity_weights.get(target.maturity_id, 0) - target.allocation

        return delta_maturity_weights

    def sell(self,amount):
        return None

    def rebalance(self):
        return None