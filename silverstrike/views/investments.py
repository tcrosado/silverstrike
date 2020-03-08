import decimal
from datetime import date, datetime
from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic

from silverstrike.lib import update_security_price
from silverstrike.models import InvestmentOperation, SecurityDetails, SecurityQuantity, SecurityDistribution, \
    SecurityPrice, SecurityTypeTarget, SecurityRegionTarget, SecurityBondMaturityTarget, SecurityBondRegionTarget, \
    SecuritySale, SecurityBondMaturity, CurrencyPreference
from silverstrike.forms import InvestmentOperationForm, InvestmentSecurityForm, InvestmentSecurityDistributionForm, \
    InvestmentTargetUpdateForm, InvestmentSecurityBondDistributionForm
from silverstrike.utils.AssetTypeWeightCalculator import AssetTypeWeightCalculator
from silverstrike.utils.BondMaturityWeightCalculator import BondMaturityWeightCalculator
from silverstrike.utils.InvestmentCalculator import InvestmentCalculator
from silverstrike.utils.InvestmentWeightCalculator import InvestmentWeightCalculator
from silverstrike.utils.PriceGetter import PriceGetter
from silverstrike.utils.RegionDistributionWeightCalculator import RegionDistributionWeightCalculator
from silverstrike.utils.SecurityOperationCalculationAdapter import SecurityOperationCalculationAdapter
from silverstrike.utils.SecurityQuantityMutableGetter import SecurityQuantityMutableGetter


class InvestmentView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investments.html'

    class SecurityOverview:
        def __init__(self, weight, ticker, quantity, currentPrice, averagePrice, totalPrice, totalReturn, ytdReturn):
            self.weight = weight
            self.ticker = ticker
            self.quantity = quantity
            self.currentPrice = currentPrice
            self.averagePrice = averagePrice
            self.totalPrice = totalPrice
            self.totalReturn = totalReturn
            self.ytdReturn = ytdReturn

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_overview'
        quantities = SecurityQuantity.objects.all()
        securityAveragePrices = dict()
        securityTotalReturn = dict()
        securityQuant = dict()
        securityPrices = dict()
        securityTotals = dict()
        securityWeights = dict()
        stockWeightRegionsDelta = dict()
        bondWeightMaturityDelta = dict()

        def transform_to_security_overview(list):
            return [
                InvestmentView.SecurityOverview(
                    weight=securityWeights[security.isin],
                    ticker=security.ticker,
                    quantity=securityQuant[security.isin],
                    currentPrice=securityPrices[security.isin],
                    averagePrice=securityAveragePrices[isin],
                    totalPrice=securityTotals[security.isin],
                    totalReturn=securityTotalReturn[security.isin],
                    ytdReturn=0) for security in list]

        def get_security_type_name(index):
            return SecurityDetails.SECURITY_TYPES[index][1]

        for security in quantities:
            securityQuant[security.isin] = security.quantity

        stocks = SecurityDetails.objects.filter(security_type=SecurityDetails.STOCK, isin__in=securityQuant.keys())
        reit = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT, isin__in=securityQuant.keys())
        bonds = SecurityDetails.objects.filter(security_type=SecurityDetails.BOND, isin__in=securityQuant.keys())

        # get latest prices
        securities = SecurityDetails.objects.filter(isin__in=securityQuant.keys())
        securityPrices = PriceGetter().get_latest_prices([security.isin for security in securities])

        for isin in securityPrices.keys():
            securityTotals[isin] = securityPrices[isin] * securityQuant[isin]
        # Calculate average price

        # sum(nr stock * price) / nr stocks
        sellTracked = SecuritySale.objects.all()
        quantityOwned = dict()
        valuePayed = dict()
        ids = []
        for sale in sellTracked:
            if sale.original_operation_id.quantity != sale.quantity:
                isin = sale.original_operation_id.isin
                price = sale.original_operation_id.price
                owned_quantity = sale.original_operation_id.quantity - sale.quantity
                quantityOwned[isin] = quantityOwned.get(isin, 0) + owned_quantity
                valuePayed[isin] = valuePayed.get(isin, 0) + (owned_quantity * price)

            ids.append(sale.original_operation_id.id)

        operations = InvestmentOperation.objects.exclude(id__in=ids).filter(operation_type=InvestmentOperation.BUY)

        for operation in operations:
            quantityOwned[operation.isin] = quantityOwned.get(operation.isin, 0) + operation.quantity
            valuePayed[operation.isin] = valuePayed.get(operation.isin, 0) + (operation.price * operation.quantity)

        for isin in quantityOwned.keys():
            securityAveragePrices[isin] = valuePayed[isin] / quantityOwned[isin]
            securityTotalReturn[isin] = (1 - (valuePayed[isin] / (securityPrices[isin] * quantityOwned[isin]))) * 100

        # Individual weights and total Value

        context['totalValue'] = sum(securityTotals[key] for key in securityTotals.keys())
        for isin in securityTotals.keys():
            securityWeights[isin] = float(securityTotals[isin] / context['totalValue']) * 100

        # weight asset distribution (InvestmentWeightCalculator)

        asset_type_weights = AssetTypeWeightCalculator().calculate_weights()

        stock_weight = asset_type_weights.get(get_security_type_name(SecurityDetails.STOCK))
        reit_weight = asset_type_weights.get(get_security_type_name(SecurityDetails.REIT))
        bond_weight = asset_type_weights.get(get_security_type_name(SecurityDetails.BOND))

        # weight world distribution (InvestmentWeightCalculator)
        stockWeightRegions = RegionDistributionWeightCalculator().calculate_weights()
        # weight bond distribution (InvestmentWeightCalculator)
        bondWeightMaturity = BondMaturityWeightCalculator().calculate_weights()

        # DELTAS
        # Security type delta target
        targets = SecurityTypeTarget.objects.all()

        for target in targets:
            if target.security_type == SecurityDetails.STOCK:
                context['stocksWeightDelta'] = stock_weight - target.allocation
            elif target.security_type == SecurityDetails.REIT:
                context['REITWeightDelta'] = reit_weight - target.allocation
            elif target.security_type == SecurityDetails.BOND:
                context['BondWeightDelta'] = bond_weight - target.allocation

        # Delta World
        stockRegionTarget = SecurityRegionTarget.objects.all()

        for target in stockRegionTarget:
            actual_allocation = stockWeightRegions.get(target.region_id)
            if actual_allocation == None:
                actual_allocation = 0
            stockWeightRegionsDelta[target.region_id] = target.allocation - actual_allocation

        bondsTarget = SecurityBondMaturityTarget.objects.all()

        for target in bondsTarget:
            actual_allocation = bondWeightMaturity.get(target.maturity_id)
            if actual_allocation == None:
                actual_allocation = 0
            bondWeightMaturityDelta[target.maturity_id] = target.allocation - actual_allocation

        context['securities'] = {
            'Stocks': transform_to_security_overview(stocks),
            'REIT': transform_to_security_overview(reit),
            'Bonds': transform_to_security_overview(bonds)}

        context['stocksWeight'] = stock_weight
        context['REITWeight'] = reit_weight
        context['bondsWeight'] = bond_weight
        context['maturityDistribution'] = bondWeightMaturity
        context['maturityDistributionDelta'] = bondWeightMaturityDelta
        context['worldDistribution'] = stockWeightRegions
        context['worldDistributionDelta'] = stockWeightRegionsDelta
        context['REGIONS'] = SecurityDistribution.REGIONS
        context['totalInvested'] = sum(valuePayed.values())
        context['totalDividends'] = 0  # TODO
        if context['totalInvested'] == 0:
            context['totalValuePercent'] = 0
        else:
            context['totalValuePercent'] = (context['totalValue'] / context['totalInvested']) * 100
        context['totalReturn'] = (context['totalValue'] + context['totalDividends']) - context['totalInvested']
        return context


class InvestmentOperationsView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_operations_overview.html'
    model = InvestmentOperation
    context_object_name = 'transactions'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_operations'
        context['transactions'] = InvestmentOperation.objects.all()
        return context


class InvestmentCalculatorView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_calculator.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment-calculator'
        context['target_assets'] = SecurityTypeTarget.objects.all()
        context['regionList'] = SecurityDistribution.REGIONS
        context['bondMaturityList'] = SecurityBondMaturity.MATURITY
        context['targetWorld'] = SecurityRegionTarget.objects.all()
        context['targetMaturityBonds'] = SecurityBondMaturityTarget.objects.all()
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        data = dict(request.GET)
        if len(data.keys()) != 0:
            # TODO check amount and operation exists
            # TODO set operation on html select
            # TODO set loader on calc
            # TODO save button
            # TODO edit Operations/ Tx
            # TODO add balance to investment Operations
            # TODO dont assume dictionaries are ordered (template)
            context['amount'] = float(data.pop('amount')[0])
            context['operation'] = data.pop('operation')[0]
            if len(data.keys()) != 0:
                # TODO
                securities = dict()
                for isin in data.keys():
                    securities[isin] = int(data[isin][0])
                security_operation_list = SecurityOperationCalculationAdapter(securities).get_operation_list()
                # TODO method
                security_getter = SecurityQuantityMutableGetter()
                for isin in securities.keys():
                    security_getter.set_security_quantity(isin, securities[isin])
                context['region_weights'] = RegionDistributionWeightCalculator(security_getter).calculate_weights()
                # Calculate delta regions
                context['delta_region'] = dict()
                for actual in context['targetWorld']:
                    context['delta_region'][actual.region_id] = context['region_weights'][
                                                                    actual.region_id] - actual.allocation

                asset_weights = AssetTypeWeightCalculator(security_getter).calculate_weights()
                context['asset_weights'] = dict()
                for (index, name) in SecurityDetails.SECURITY_TYPES:
                    context['asset_weights'][index] = asset_weights[name]
                context['bond_weights'] = BondMaturityWeightCalculator(security_getter).calculate_weights()
                # Calculate delta assets
                context['delta_assets'] = dict()

                for actual, index in zip(context['target_assets'], range(len(context['target_assets']))):
                    context['delta_assets'][index] = context['asset_weights'][index] - actual.allocation

                # Calculate delta maturity
                context['delta_maturity'] = dict()
                for actual in context['targetMaturityBonds']:
                    context['delta_maturity'][actual.maturity_id] = context['bond_weights'][
                                                                        actual.maturity_id] - actual.allocation

                context['security_operations'] = security_operation_list
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        amount = float(request.POST.get('amount'))
        op = request.POST.get('select')
        new_security_list = dict()
        # TODO enum buy sell
        if op == "buy":
            new_security_list = self.buy_calculator(request.user.id, amount)
        elif op == "sell":
            new_security_list = self.sell_calculator(request.user.id, amount)
        elif op == "rebalance":
            new_security_list = self.rebalance_calculator(request.user.id, amount)
        else:
            print("Nothing to do here")

        new_security_list['amount'] = amount
        new_security_list['operation'] = op

        base_url = reverse('investment-calculator')  # 1 /products/
        query_string = urlencode(new_security_list)  # 2 category=42
        url = '{}?{}'.format(base_url, query_string)  # 3 /products/?category=42

        # TODO Fix Last updated date
        # TODO Lastest Price
        # - Operations (Buy/Sell/Rebalance)
        # - New world

        # TODO Get stock and bond current distribution
        # TODO Sell on amount should take into account taxes

        return HttpResponseRedirect(url)

    def buy_calculator(self, user_id, amount):
        investment_calculator = InvestmentCalculator(user_id)
        return investment_calculator.buy(amount)

    def rebalance_calculator(self, user_id, amount):
        investment_calculator = InvestmentCalculator(user_id)
        return investment_calculator.rebalance(amount)

    def sell_calculator(self, user_id, amount):
        investment_calculator = InvestmentCalculator(user_id)
        return investment_calculator.sell(amount)


class InvestmentOperationCreate(LoginRequiredMixin, generic.edit.CreateView):  # FIXME
    model = InvestmentOperation
    template_name = 'silverstrike/investment_operation_edit.html'
    form_class = InvestmentOperationForm

    def get_context_data(self, **kwargs):
        context = super(InvestmentOperationCreate, self).get_context_data(**kwargs)
        context['menu'] = 'transactions'
        context['element'] = +10
        return context


class InvestmentConfigView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_config.html'
    model = SecurityDetails

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_security_list'
        context['stocks'] = SecurityDetails.objects.filter(security_type=SecurityDetails.STOCK)
        context['reit'] = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT)
        context['bonds'] = SecurityDetails.objects.filter(security_type=SecurityDetails.BOND)
        return context


class InvestmentConfigPriceView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_config.html'
    model = SecurityPrice

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_security_pricing'
        return context


class InvestmentConfigUpdateView(LoginRequiredMixin, generic.FormView):
    template_name = 'silverstrike/investment_config_update.html'
    form_class = InvestmentTargetUpdateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['menu'] = 'investment_target_update'  # FIXME add to context current
        context['currencyList'] = CurrencyPreference.CURRENCIES
        try:
            context['originalSelectedCurrency'] = CurrencyPreference.objects.get(user_id=user.id).preferred_currency
        except CurrencyPreference.DoesNotExist:
            context['originalSelectedCurrency'] = -1
        return context

    def get_success_url(self):
        return reverse('investment_portfolio_target')

    def post(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        request_data = dict(request.POST.lists())
        user = request.user

        for key in request_data.keys():
            if key == 'csrfmiddlewaretoken':  # FIXME
                continue
            elif key == "currency":
                preferred_currency = int(request_data[key][0])
                try:
                    currency_preference = CurrencyPreference.objects.get(user_id=user.id)
                    currency_preference.preferred_currency = preferred_currency
                    currency_preference.save()
                except CurrencyPreference.DoesNotExist:
                    CurrencyPreference.objects.create(preferred_currency=preferred_currency, user=user)

            elif key.startswith('BR'):
                region_id = int(key.split('BR')[1])
                allocation = float(request_data[key][0])
                try:
                    target_asset = SecurityBondRegionTarget.objects.get(region_id=region_id)
                    target_asset.allocation = allocation
                    target_asset.save()
                except SecurityBondRegionTarget.DoesNotExist:
                    SecurityBondRegionTarget.objects.create(region_id=region_id, allocation=allocation)

        return HttpResponseRedirect(reverse('investment_portfolio_target'))


class InvestmentConfigTargetView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_portfolio_target.html'

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_portfolio_target'
        context['targetAssets'] = SecurityTypeTarget.objects.all()
        context['regionList'] = SecurityDistribution.REGIONS
        context['bondMaturityList'] = SecurityBondMaturity.MATURITY
        context['targetWorld'] = SecurityRegionTarget.objects.all()
        context['targetMaturityBonds'] = SecurityBondMaturityTarget.objects.all()
        context['targetRegionBonds'] = SecurityBondRegionTarget.objects.all()
        try:
            context['defaultCurrency'] = \
                CurrencyPreference.CURRENCIES[CurrencyPreference.objects.get(user_id=user.id).preferred_currency][1]
        except CurrencyPreference.DoesNotExist:
            context['defaultCurrency'] = "Not set"
        return context


class InvestmentTargetUpdateView(LoginRequiredMixin, generic.FormView):
    template_name = 'silverstrike/investment_target_update.html'
    form_class = InvestmentTargetUpdateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_target_update'  # FIXME add to context current
        return context

    def get_success_url(self):
        return reverse('investment_portfolio_target')

    def post(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        request_data = dict(request.POST.lists())

        for key in request_data.keys():

            if key == 'csrfmiddlewaretoken':  # FIXME
                continue
            elif key.startswith('R'):
                region_id = int(key.split('R')[1])
                allocation = float(request_data[key][0])

                try:
                    target_asset = SecurityRegionTarget.objects.get(region_id=region_id)
                    target_asset.allocation = allocation
                    target_asset.save()
                except SecurityRegionTarget.DoesNotExist:
                    SecurityRegionTarget.objects.create(region_id=region_id, allocation=allocation)
            elif key.startswith('A'):
                security_type = int(key.split('A')[1])
                allocation = float(request_data[key][0])
                try:
                    target_asset = SecurityTypeTarget.objects.get(security_type=security_type)
                    target_asset.allocation = allocation
                    target_asset.save()
                except SecurityTypeTarget.DoesNotExist:
                    SecurityTypeTarget.objects.create(security_type=security_type, allocation=allocation)
            elif key.startswith('BM'):
                maturity_id = int(key.split('BM')[1])
                allocation = float(request_data[key][0])
                try:
                    target_asset = SecurityBondMaturityTarget.objects.get(maturity_id=maturity_id)
                    target_asset.allocation = allocation
                    target_asset.save()
                except SecurityBondMaturityTarget.DoesNotExist:
                    SecurityBondMaturityTarget.objects.create(maturity_id=maturity_id, allocation=allocation)
            elif key.startswith('BR'):
                region_id = int(key.split('BR')[1])
                allocation = float(request_data[key][0])
                try:
                    target_asset = SecurityBondRegionTarget.objects.get(region_id=region_id)
                    target_asset.allocation = allocation
                    target_asset.save()
                except SecurityBondRegionTarget.DoesNotExist:
                    SecurityBondRegionTarget.objects.create(region_id=region_id, allocation=allocation)

        return HttpResponseRedirect(reverse('investment_portfolio_target'))


class SecurityDetailsCreate(LoginRequiredMixin, generic.edit.CreateView):  # FIXME
    model = SecurityDetails
    template_name = 'silverstrike/investment_security_create.html'
    form_class = InvestmentSecurityForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['menu'] = 'transactions'
        return context

    def get_success_url(self):
        return reverse('investment_security_list')


class SecurityDetailsUpdate(LoginRequiredMixin, generic.edit.UpdateView):  # FIXME
    model = SecurityDetails
    template_name = 'silverstrike/investment_security_create.html'
    form_class = InvestmentSecurityForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'transactions'
        return context

    def get_success_url(self):
        return reverse('investment_security_list')


class SecurityDistributionCreate(LoginRequiredMixin, generic.edit.FormView):  # FIXME
    template_name = 'silverstrike/investment_security_distribution_edit.html'
    form_class = InvestmentSecurityDistributionForm

    def get_context_data(self, **kwargs):
        context = super(SecurityDistributionCreate, self).get_context_data(**kwargs)
        context['menu'] = 'transactions'  # FIXME add to context current
        return context

    def get(self, request, *args, **kwargs):
        security_id = kwargs['pk']
        security = SecurityDetails.objects.get(pk=security_id)
        if security.security_type == SecurityDetails.BOND:
            self.form_class = InvestmentSecurityBondDistributionForm
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        security_id = context['pk']
        security = SecurityDetails.objects.get(pk=security_id)
        request_data = dict(request.POST.lists())

        if security.security_type == SecurityDetails.BOND:
            data_class = SecurityBondMaturity
        else:
            data_class = SecurityDistribution

        for key in request_data.keys():
            if key == 'csrfmiddlewaretoken':  # FIXME
                continue
            try:
                if security.security_type == SecurityDetails.BOND:
                    dist = data_class.objects.get(isin=security.isin, maturity_id=int(key))
                else:
                    dist = data_class.objects.get(isin=security.isin, region_id=int(key))
                dist.allocation = float(request_data[key][0])
                dist.save()
            except data_class.DoesNotExist:
                if security.security_type == SecurityDetails.BOND:
                    data_class.objects.create(isin=security.isin, maturity_id=int(key),
                                              allocation=float(request_data[key][0]))
                else:
                    data_class.objects.create(isin=security.isin, region_id=int(key),
                                              allocation=float(request_data[key][0]))
        return HttpResponseRedirect(reverse('investment_security_details', args=[security_id]))


# TODO Last Operations Security view
# TODO new Operation ISIN

class SecurityDetailsInformation(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_security_information.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'security_details'
        context['securityDetails'] = SecurityDetails.objects.get(pk=context['pk'])
        last_price = SecurityPrice.objects.order_by('date').last()
        context['securityPrice'] = last_price
        today = date.today()
        begining = datetime.strptime(str(today.year), '%Y')

        context['dates'] = [begining.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")]
        try:
            assets = SecurityQuantity.objects.get(isin=context['securityDetails'].isin).quantity
        except SecurityQuantity.DoesNotExist:
            assets = 0
        context['currentAssets'] = assets
        if last_price == None:
            context['totalPrice'] = 0
        else:
            context['totalPrice'] = last_price.price * assets
        if context['securityDetails'].security_type == SecurityDetails.BOND:
            context['distributionLabels'] = [element[1] for element in SecurityBondMaturity.MATURITY]
            context['securityDistribution'] = SecurityBondMaturity.objects.filter(isin=context['securityDetails'].isin)
        else:
            context['distributionLabels'] = [element[1] for element in SecurityDistribution.REGIONS]
            context['securityDistribution'] = SecurityDistribution.objects.filter(isin=context['securityDetails'].isin)
        price_distribution = []
        for region in context['securityDistribution']:
            price_distribution.append(context['totalPrice'] * decimal.Decimal(region.allocation / 100))
        context['securityDistributionPrice'] = price_distribution

        return context

    # FIXME switch to api
    def post(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        security_id = context['pk']
        security = SecurityDetails.objects.get(pk=security_id)
        update_security_price(security.ticker)
        return HttpResponseRedirect(reverse('investment_security_details', args=[security_id]))
