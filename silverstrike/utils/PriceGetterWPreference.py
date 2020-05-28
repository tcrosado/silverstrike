from django.db.models import Max

from silverstrike.models import SecurityDetails, CurrencyPreference, CurrencyPairPrice
from silverstrike.utils.PriceGetter import PriceGetter


class PriceGetterWPreference(PriceGetter):

    def __init__(self,user_id) -> None:
        super().__init__()
        self.user_id = user_id

    @staticmethod
    def __get_price_in_currency(security_detail_list, preference_currency):
        price_dict = dict()  # dict(isin -> price_pref)
        for security in security_detail_list:
            price_list = super.__get_latest_price_ticker(list(security.ticker))
            currency_pair = security.currency+preference_currency
            currency_rate = CurrencyPairPrice.object.filter(pair=currency_pair).annotate(max_data=Max('date')).order_by()

            if not currency_rate:
                converted_price = 0
            else:
                converted_price = price_list * currency_rate
            price_dict[security.isin] = converted_price

        return price_dict

    def get_latest_prices(self, isin_list):
        default_currency_config = CurrencyPreference.objects.get(user=self.user_id)
        currency = default_currency_config.preferred_currency
        security_list_different_currency = SecurityDetails.objects.exclude(currency=currency).filter(isin_in=isin_list)

        isin_same_currency = isin_list
        for different_currency_isin in security_list_different_currency:
            if different_currency_isin in isin_list:
                isin_same_currency.remove(different_currency_isin)

        price_dict = self.__get_price_in_currency(security_list_different_currency)
        price_same_currency = super().get_latest_prices(isin_same_currency) # (isin -> price dict)
        for isin in price_same_currency.keys():
            price_dict[isin] = price_same_currency[isin]

        return price_dict


