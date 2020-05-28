import datetime

from silverstrike.models import SecurityPrice, CurrencyPairPrice
import yfinance as yf

def last_day_of_month(any_day):
    next_month = any_day.replace(day=28) + datetime.timedelta(days=4)
    return next_month - datetime.timedelta(days=next_month.day)

def update_security_price(ticker,start=None,end=None):
    most_recent = SecurityPrice.objects.filter(ticker=ticker).order_by('date').last()
    now = datetime.datetime.now()
    if most_recent != None:

        if most_recent.date.year == now.year and most_recent.date.day == now.day and most_recent.date.month == now.month:
            return True

        next_date = most_recent.date + datetime.timedelta(days=1)
        data_list = yf.download(ticker, start=next_date.strftime('%Y-%m-%d'))['Close']
    else:
        data_list = yf.download(ticker)['Close']

    for i in range(len(data_list)):
        date = data_list.index[i]
        price = data_list[i]

        SecurityPrice.objects.create(ticker=ticker, date=date, price=price)
    return True

def update_currency_pair(base_currency,quote_currency,start=None,end=None):
    pair = base_currency+quote_currency
    yahoo_pair = base_currency+quote_currency+"=X"
    most_recent = CurrencyPairPrice.objects.filter(pair=pair).order_by('date').last()
    now = datetime.datetime.now()
    if most_recent != None:
        if most_recent.date.year == now.year and most_recent.date.day == now.day and most_recent.date.month == now.month:
            return True

        next_date = most_recent.date + datetime.timedelta(days=1)
        data_list = yf.download(yahoo_pair, start= next_date.strftime('%Y-%m-%d'))['Close']
    else:
        data_list = yf.download(yahoo_pair)['Close']

    for i in range(len(data_list)):
        date = data_list.index[i]
        price = data_list[i]

        CurrencyPairPrice.objects.create(pair=pair, date=date, price=price)
    return True