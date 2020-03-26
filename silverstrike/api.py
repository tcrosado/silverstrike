import datetime
import operator

from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse

from .models import Account, Split, SecurityPrice, SecurityDetails, InvestmentOperation, SecurityQuantity


@login_required
def get_accounts(request, account_type):
    accounts = Account.objects.exclude(account_type=Account.SYSTEM)
    if account_type != 'all':
        account_type = getattr(Account, account_type)
        accounts = accounts.filter(account_type=account_type)

    return JsonResponse(list(accounts.values_list('name', flat=True)), safe=False)


@login_required
def get_accounts_balance(request, dstart, dend):
    dstart = datetime.datetime.strptime(dstart, '%Y-%m-%d').date()
    dend = datetime.datetime.strptime(dend, '%Y-%m-%d').date()
    dataset = []
    for account in Account.objects.personal().active():
        data = list(zip(*account.get_data_points(dstart, dend)))
        dataset.append({'name': account.name, 'data': data[1]})
    if dataset:
        labels = [datetime.datetime.strftime(x, '%d %b %Y') for x in data[0]]
    else:
        labels = []
    return JsonResponse({'labels': labels, 'dataset': dataset})


@login_required
def get_account_balance(request, account_id, dstart, dend):
    dstart = datetime.datetime.strptime(dstart, '%Y-%m-%d').date()
    dend = datetime.datetime.strptime(dend, '%Y-%m-%d').date()
    account = Account.objects.get(pk=account_id)
    labels, data = zip(*account.get_data_points(dstart, dend))
    return JsonResponse({'data': data, 'labels': labels})


@login_required
def get_balances(request, dstart, dend):
    dstart = datetime.datetime.strptime(dstart, '%Y-%m-%d').date()
    dend = datetime.datetime.strptime(dend, '%Y-%m-%d').date()
    balance = Split.objects.personal().exclude_transfers().filter(date__lt=dstart).aggregate(
            models.Sum('amount'))['amount__sum'] or 0
    splits = Split.objects.personal().exclude_transfers().date_range(dstart, dend).order_by('date')
    data_points = []
    labels = []
    days = (dend - dstart).days
    if days > 50:
        step = days / 50 + 1
    else:
        step = 1
    for split in splits:
        while split.date > dstart:
            data_points.append(balance)
            labels.append(datetime.datetime.strftime(dstart, '%Y-%m-%d'))
            dstart += datetime.timedelta(days=step)
        balance += split.amount
    data_points.append(balance)
    labels.append(datetime.datetime.strftime(dend, '%Y-%m-%d'))
    return JsonResponse({'labels': labels, 'data': data_points})


@login_required
def category_spending(request, dstart, dend):
    dstart = datetime.datetime.strptime(dstart, '%Y-%m-%d')
    dend = datetime.datetime.strptime(dend, '%Y-%m-%d')
    res = Split.objects.expense().past().date_range(dstart, dend).order_by('category').values(
        'category__name').annotate(spent=models.Sum('amount'))
    if res:
        res = [(e['category__name'] or 'No category', abs(e['spent'])) for e in res if e['spent']]
        categories, spent = zip(*res)
    else:
        categories, spent = [], []
    return JsonResponse({'categories': categories, 'spent': spent})


@login_required
def get_security_prices(request,isin,dstart,dend):
    dstart = datetime.datetime.strptime(dstart, '%Y-%m-%d')
    dend = datetime.datetime.strptime(dend, '%Y-%m-%d')
    security = SecurityDetails.objects.get(isin=isin)
    res = SecurityPrice.objects.filter(ticker=security.ticker,date__range=[dstart,dend])
    data = []
    labels = []
    for security_price in res.iterator():
        data.append(float(security_price.price))
        labels.append(security_price.date)

    return JsonResponse({'data': data, 'labels': labels})

# TODO New Investment Operation list securities

@login_required
def get_investment_overview_data(request, dstart, dend):
    def get_total_security_prices_datapoints(quantities):
        data_point = dict()
        data_point['x'] = date
        for security in list(quantities):
            # Price
            security_info = SecurityDetails.objects.filter(isin=security[0])[0]
            delta_date = datetime.timedelta(days=5)
            date_start_range = date - delta_date
            security_price_list = SecurityPrice.objects.filter(ticker=security_info.ticker,
                                                               date__range=[date_start_range, date]).order_by('-date')
            security_price = security_price_list[0]
            data_point.setdefault('y', 0)
            data_point['y'] += security[1] * security_price.price
        return data_point

    def merge_dictionary(dict1, dict2):
        dictionary_list = [dict1,dict2]
        merged_dictionary = dict()
        for dictionary in dictionary_list:
            for key in dictionary.keys():
                merged_dictionary[key] = dictionary[key]
        return merged_dictionary


    def merge_day_operations(operation_list1, operation_list2):
        def merge_operation_list(operation_list, merged=dict()):
            for operation in operation_list:
                date = operation['x']
                value = operation['y']
                date_value = dict()
                date_value.setdefault('x', date)
                date_value.setdefault('y', 0)
                merged.setdefault(date, date_value)
                merged[date]['y'] += value
                # FIXME simplify N*M
            return merged

        merge = merge_operation_list(operation_list1)
        return list(merge_operation_list(operation_list2, merge).values())

    dstart = datetime.datetime.fromtimestamp(float(dstart)/1000.0)
    dend = datetime.datetime.fromtimestamp(float(dend)/1000.0)

    operations = InvestmentOperation.objects.filter(date__range=[dstart, dend]).order_by('date')
    # TODO select single user
    current_quantities = SecurityQuantity.objects.all()
    tracked_quatities = dict()
    # Go to security price list get security price for each date

    acc = dict()
    acc[InvestmentOperation.DIV] = dict()
    acc[InvestmentOperation.SELL] = dict()
    acc[InvestmentOperation.BUY] = dict()

    quantities_dates = dict()
    quantities = dict()

    for operation in operations:
        data = dict()
        data['x'] = operation.date
        if len(acc[operation.operation_type].values()) == 0:
            data['y'] = operation.price * operation.quantity
        else:
            data['y'] = list(acc[operation.operation_type].values())[-1]['y'] + (operation.price * operation.quantity)

        tracked_quatities.setdefault(operation.isin, 0)

        if operation.operation_type == InvestmentOperation.SELL:
            data['y'] *= -1
            tracked_quatities[operation.isin] = tracked_quatities.get(operation.isin) - operation.quantity
        elif operation.operation_type == InvestmentOperation.BUY:
            tracked_quatities[operation.isin] = tracked_quatities.get(operation.isin) + operation.quantity

        acc[operation.operation_type][operation.date] = data

        #set quantitites
        isin = operation.isin
        quantities.setdefault(isin, 0)
        if operation.operation_type == InvestmentOperation.SELL:
            quantities[isin] -= operation.quantity
        elif operation.operation_type == InvestmentOperation.BUY:
            quantities[isin] += operation.quantity

        quantities_dates.setdefault(operation.date,dict())
        quantities_dates[operation.date].setdefault(isin, 0)
        quantities_dates[operation.date][isin] = quantities[isin]

    #get prices and create graph data on total value
    invested = merge_day_operations(acc[InvestmentOperation.BUY].values(), acc[InvestmentOperation.SELL].values())
    dividends = list(acc[InvestmentOperation.DIV].values())
    total_value = [] # x (date), y (value)
    keys = list(quantities_dates.keys())
    merged_cumulative_quantities = dict()
    date = None
    for i in range(len(keys)):
        date = keys[i]
        if i != 0:
            last_date = keys[i-1]
            last_quantities = merged_cumulative_quantities[last_date]
            current_quantities = quantities_dates[date]
            merged_cumulative_quantities[date] = merge_dictionary(last_quantities,current_quantities)
        else:
            merged_cumulative_quantities[date] = quantities_dates[date]

        data_point = get_total_security_prices_datapoints(merged_cumulative_quantities[date].items())
        total_value.append(data_point)

    # add day point if not included
    today = datetime.date.today()
    if today not in keys:
        data_point = get_total_security_prices_datapoints(merged_cumulative_quantities[date].items())
        total_value.append(data_point)
    # TODO Different currencies
    # TODO not allowed buy/sell when market closed
    # TODO change graph based on buttons
    # TODO edit operations
    # TODO Add total networth tracker
    return JsonResponse({'dividends': dividends, 'totalValue': total_value, 'invested': invested})
