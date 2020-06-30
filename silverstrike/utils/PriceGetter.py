from django.db.models import Max

from silverstrike.models import SecurityPrice, SecurityDetails


class PriceGetter:
    def get_latest_prices(self,isin_list):
        ticker_map = self.__get_ticker_to_isin_map(isin_list)
        prices = self.__get_latest_price_ticker(ticker_list=ticker_map.keys())
        security_prices = dict()
        for security in prices:
            isin = ticker_map[security.ticker]
            security_prices[isin] = security.price
            # securityTotals[isin] = security.price * securityQuant[isin]

        return security_prices

    @staticmethod
    def __get_latest_price_ticker(ticker_list):
        latest_dates = SecurityPrice.objects.filter(ticker__in=ticker_list).values('ticker').annotate(
            max_date=Max('date')).order_by()

        prices = []
        for security in latest_dates:
            result = SecurityPrice.objects.get(ticker=security['ticker'], date=security['max_date'])

            prices.append(result)

        return prices

    @staticmethod
    def __get_ticker_to_isin_map(isin_list):
        securities = SecurityDetails.objects.filter(isin__in=isin_list)
        # Map ticker to isin
        tickers_map = dict()
        for security in securities:
            tickers_map[security.ticker] = security.isin

        return tickers_map