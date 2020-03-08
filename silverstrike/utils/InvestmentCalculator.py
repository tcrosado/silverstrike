import operator

from silverstrike.models import SecurityDetails, SecurityTypeTarget, SecurityRegionTarget, SecurityBondMaturityTarget, \
    SecurityDistribution, SecurityBondMaturity, CurrencyPreference
from silverstrike.utils.AssetTypeWeightCalculator import AssetTypeWeightCalculator
from silverstrike.utils.BondMaturityWeightCalculator import BondMaturityWeightCalculator
from silverstrike.utils.PriceGetter import PriceGetter
from silverstrike.utils.RegionDistributionWeightCalculator import RegionDistributionWeightCalculator
from silverstrike.utils.SecurityQuantityGetter import SecurityQuantityGetter
from silverstrike.utils.SecurityQuantityMutableGetter import SecurityQuantityMutableGetter


class InvestmentCalculator:

    def __init__(self, user_id):
        self.price_getter = PriceGetter()
        self.security_quantity_getter = SecurityQuantityMutableGetter()
        self.region_weight_calculator = RegionDistributionWeightCalculator(self.security_quantity_getter)
        self.bond_weight_calculator = BondMaturityWeightCalculator(self.security_quantity_getter)
        self.asset_weight_calculator = AssetTypeWeightCalculator(self.security_quantity_getter)
        self.user_id = user_id

    def buy(self, amount):
        added_amount = 0
        updated = True

        # Set current security quantities
        self.security_quantity_getter.clear_list()
        current_security_quantity = SecurityQuantityGetter().get_quantities()
        for isin in current_security_quantity.keys():
            self.security_quantity_getter.set_security_quantity(isin, current_security_quantity[isin])

        while added_amount != amount and updated:
            # select asset to add
            delta_asset_weights = self.__get_delta_asset_weights()
            selected_asset = min(delta_asset_weights, key=delta_asset_weights.get)

            if selected_asset == SecurityDetails.STOCK:
                selected_isin = self.__select_buy_isin(self.__get_delta_region_weights, SecurityDetails.STOCK)
            elif selected_asset == SecurityDetails.BOND:
                selected_isin = self.__select_buy_isin(self.__get_delta_maturity_weights, SecurityDetails.BOND)
            elif selected_asset == SecurityDetails.REIT:
                try:
                    currency = CurrencyPreference.objects.get(user=self.user_id)
                    iso_currency = CurrencyPreference.CURRENCIES[currency.preferred_currency][1]
                except CurrencyPreference.DoesNotExist:
                    currency = None

                if currency is None:
                    selected_security_list = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT)
                else:
                    selected_security_list = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT, currency=iso_currency)
                if len(selected_security_list) == 0:
                    raise Exception("Impossible to use REIT")
                selected_security = selected_security_list[0]
                selected_isin = selected_security.isin
            else:
                raise Exception("Unknown asset selected")

            added_amount, amount, updated = self.__update_quantities("buy",selected_isin, added_amount, amount)
        return self.security_quantity_getter.get_quantities()

    @staticmethod
    def __get_weight_list(security_type, selected_delta, isin_list):
        if security_type == SecurityDetails.STOCK:
            return SecurityDistribution.objects.filter(region_id=selected_delta, isin__in=isin_list)
        elif security_type == SecurityDetails.BOND:
            return SecurityBondMaturity.objects.filter(maturity_id=selected_delta, isin__in=isin_list)
        else:
            return []

    def __get_delta_asset_weights(self):
        asset_weights = self.asset_weight_calculator.calculate_weights()
        asset_targets = SecurityTypeTarget.objects.all()  # FIXME single user
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

    def __update_quantities(self, operation, selected_isin, added_amount, amount):
        updated = False
        # get price
        # FIXME if no price avaliable
        price = float(self.price_getter.get_latest_prices([selected_isin])[selected_isin])

        if amount >= price:
            added_amount = added_amount + price
            amount = amount - price
            security_quantity = self.security_quantity_getter.get_security_quantity(selected_isin)
            if operation == "buy":
                self.security_quantity_getter.set_security_quantity(selected_isin, security_quantity + 1)
            elif operation == "sell":
                self.security_quantity_getter.set_security_quantity(selected_isin, security_quantity - 1)
            updated = True

        return added_amount, amount, updated

    @staticmethod
    def __select_buy_isin(delta_weight_function, security_type):
        # get delta_region_target
        delta_weights = delta_weight_function()
        # get min delta
        selected_delta = min(delta_weights, key=delta_weights.get)
        # get security with max region / maturity
        asset_list = SecurityDetails.objects.filter(security_type=security_type)
        isin_list = [asset.isin for asset in asset_list]
        weight_list = InvestmentCalculator.__get_weight_list(security_type, selected_delta, isin_list)
        selected_isin = max(weight_list, key=operator.attrgetter('allocation')).isin
        return selected_isin

    def __select_sell_isin(self, delta_weight_function, security_type):
        # get delta_region_target
        delta_weights = delta_weight_function()
        # get max delta
        selected_delta = max(delta_weights, key=delta_weights.get)
        # get current
        current_assets = self.security_quantity_getter.get_quantities()
        current_assets_isin = current_assets.keys()
        # get security with max region
        asset_list = SecurityDetails.objects.filter(security_type=security_type, isin__in=current_assets_isin)
        isin_list = [asset.isin for asset in asset_list]
        weight_list = InvestmentCalculator.__get_weight_list(security_type, selected_delta, isin_list)
        selected_isin = max(weight_list, key=operator.attrgetter('allocation')).isin
        return selected_isin

    def sell(self, amount):
        sold_amount = 0
        updated = True

        # Set current security quantities
        self.security_quantity_getter.clear_list()
        current_security_quantity = SecurityQuantityGetter().get_quantities()
        for isin in current_security_quantity.keys():
            self.security_quantity_getter.set_security_quantity(isin, current_security_quantity[isin])

        while sold_amount != amount and updated:
            # select asset to add
            delta_asset_weights = self.__get_delta_asset_weights()
            selected_asset = max(delta_asset_weights, key=delta_asset_weights.get)

            if selected_asset == SecurityDetails.STOCK:
                selected_isin = self.__select_sell_isin(self.__get_delta_region_weights, SecurityDetails.STOCK)
            elif selected_asset == SecurityDetails.BOND:
                selected_isin = self.__select_sell_isin(self.__get_delta_maturity_weights, SecurityDetails.BOND)
            elif selected_asset == SecurityDetails.REIT:
                # Selling prefer reducing position on less assets exchange
                # Selling prefer foreign currency
                # TODO
                try:
                    currency = CurrencyPreference.objects.get(user=self.user_id)
                    iso_currency = CurrencyPreference.CURRENCIES[currency.preferred_currency][1]
                except CurrencyPreference.DoesNotExist:
                    currency = None

                if currency is None:
                    selected_security_list = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT)
                else:
                    selected_security_list = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT,
                                                                            currency=iso_currency)
                if len(selected_security_list) == 0:
                    raise Exception("Impossible to use REIT")
                selected_security = selected_security_list[0]
                selected_isin = selected_security.isin
            else:
                raise Exception("Unknown asset selected")

            sold_amount, amount, updated = self.__update_quantities("sell", selected_isin, sold_amount, amount)
        return self.security_quantity_getter.get_quantities()

    def rebalance(self, amount):
        # TODO
        raise NotImplementedError
