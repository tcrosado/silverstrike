import datetime

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
def get_security_prices(request,security_id,dstart,dend):
    dstart = datetime.datetime.strptime(dstart, '%Y-%m-%d')
    dend = datetime.datetime.strptime(dend, '%Y-%m-%d')
    security = SecurityDetails.objects.get(id=security_id)
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

    def merge_accumulation(operation_list1, operation_list2):
        def merge_operation_list(operation_list, merged=dict()):
            for operation in operation_list:
                date = operation['date']
                value = operation['value']
                date_value = dict()
                date_value.setdefault('date', date)
                date_value.setdefault('value', 0)
                merged.setdefault(date, date_value)
                merged[date]['value'] += value
                # FIXME simplify N*M
            return merged

        merge = merge_operation_list(operation_list1)
        return list(merge_operation_list(operation_list2, merge).values())

    dstart = datetime.datetime.strptime(dstart, '%Y-%m-%d')
    dend = datetime.datetime.strptime(dend, '%Y-%m-%d')
    dividends = InvestmentOperation.objects.filter(operation_type= InvestmentOperation.DIV, date__range=[dstart,dend]).order_by('date')
    operations = InvestmentOperation.objects.filter(date__range=[dstart, dend]).order_by('date')
    # TODO only if dend == today
    # TODO select single user
    current_quantities = SecurityQuantity.objects.all()
    tracked_quatities = dict()
    # Go to security price list get security price for each date

    acc = dict()
    acc[InvestmentOperation.DIV] = []
    acc[InvestmentOperation.SELL] = []
    acc[InvestmentOperation.BUY] = []

    for operation in operations:
        data = dict()
        data['date'] = operation.date

        if len(acc[operation.operation_type]) == 0:
            data['value'] = operation.price * operation.quantity
        else:
            data['value'] = acc[operation.operation_type][-1]['value'] + (operation.price * operation.quantity)

        tracked_quatities.setdefault(operation.isin, 0)

        if operation.operation_type == InvestmentOperation.SELL:
            data['value'] *= -1
            tracked_quatities[operation.isin] = tracked_quatities.get(operation.isin) - operation.quantity
        elif operation.operation_type == InvestmentOperation.BUY:
            tracked_quatities[operation.isin] = tracked_quatities.get(operation.isin) + operation.quantity

        acc[operation.operation_type] += [data]
    print('stuff')
    invested = merge_accumulation(acc[InvestmentOperation.BUY], acc[InvestmentOperation.SELL])
    print('stuff +')
    dividends = acc[InvestmentOperation.DIV]
    print('stuff + 2')
    total_value = 0 # based on price history (isin to ticker map)
    print({'dividends': dividends, 'totalValue': total_value, 'invested': invested})
    #(quantities * history price)+dividends
    # Data cumulative dividends
    # Label date
    # get current quantitites and go back in time to get initial ones
    # TODO add money added
    # TODO add total value
    return JsonResponse({'dividends': dividends, 'totalValue': total_value, 'invested': invested})
