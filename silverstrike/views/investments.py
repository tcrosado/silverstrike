import decimal
from datetime import date,datetime

from dateutil.relativedelta import relativedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.handlers.wsgi import WSGIRequest
from django.db.models import Max, Count, Subquery
from django.db.models.functions import Lower
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic

from silverstrike.lib import update_security_price
from silverstrike.models import InvestmentOperation, SecurityDetails, SecurityQuantity, SecurityDistribution, \
    SecurityPrice, SecurityTypeTarget, SecurityRegionTarget, SecurityBondMaturityTarget, SecurityBondRegionTarget
from silverstrike.forms import InvestmentOperationForm, InvestmentSecurityForm, InvestmentSecurityDistributionForm, \
    InvestmentTargetUpdateForm


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
        securityQuant = dict()
        securityPrices = dict()
        securityTotals = dict()
        securityWeights = dict()
        stockWeight = 0
        reitWeight = 0
        bondWeight = 0
        totalMoneyRegion = dict()
        stockWeightRegions = dict()
        def transform_to_security_overview(list):
            return [
                InvestmentView.SecurityOverview(
                    weight=securityWeights[security.isin],
                    ticker=security.ticker,
                    quantity=securityQuant[security.isin],
                    currentPrice=securityPrices[security.isin],
                    averagePrice=0,
                    totalPrice=securityTotals[security.isin],
                    totalReturn=0,
                    ytdReturn=0) for security in list]

        for security in quantities:
            securityQuant[security.isin] = security.quantity

        stocks = SecurityDetails.objects.filter(security_type=SecurityDetails.STOCK,isin__in=securityQuant.keys())
        reit = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT,isin__in=securityQuant.keys())
        bonds = SecurityDetails.objects.filter(security_type=SecurityDetails.BOND,isin__in=securityQuant.keys())

        tickersMap = dict()
        for security in stocks:
            tickersMap[security.ticker] = security.isin
        for security in reit:
            tickersMap[security.ticker] = security.isin
        for security in bonds:
            tickersMap[security.ticker] = security.isin

        latestDates = SecurityPrice.objects.filter(ticker__in=tickersMap.keys()).values('ticker').annotate(max_date=Max('date')).order_by()

        prices = []
        for security in latestDates:
            result = SecurityPrice.objects.get(ticker=security['ticker'], date=security['max_date'])
            prices.append(result)

        for security in prices:
            isin = tickersMap[security.ticker]
            securityPrices[isin] = security.price
            securityTotals[isin] = security.price * securityQuant[isin]

        # Individual weights and total Value
        context['totalValue'] = sum(securityTotals[key] for key in securityTotals.keys())
        for isin in securityTotals.keys():
            securityWeights[isin] = float(securityTotals[isin] / context['totalValue']) * 100

        # weight asset distribution
        for security in stocks:
            stockWeight = stockWeight + securityWeights[security.isin]
        for security in reit:
            reitWeight = reitWeight + securityWeights[security.isin]
        for security in bonds:
            bondWeight = bondWeight + securityWeights[security.isin]
        # weight world distribution
        securityDistribution = SecurityDistribution.objects.filter(isin__in=securityQuant.keys())

        for dist in securityDistribution:

            totalRegion = totalMoneyRegion.get(dist.region_id)
            total = float(securityTotals[dist.isin]) * float(dist.allocation / 100)
            if totalRegion == None:
                totalMoneyRegion[dist.region_id] = total
            else:
                totalMoneyRegion[dist.region_id] = totalRegion + total

        for dist in securityDistribution:
            totalRegion = stockWeightRegions.get(dist.region_id)
            if totalMoneyRegion[dist.region_id] == 0:
                allocation = 0
            else:
                allocation = (float(securityTotals[dist.isin]) * float(dist.allocation) / (float(stockWeight) * float(context['totalValue']))) * 100
            print(float(stockWeight / 100) * float(context['totalValue']))
            if totalRegion == None:
                stockWeightRegions[dist.region_id] = allocation
            else:
                stockWeightRegions[dist.region_id] = totalRegion + allocation

        # weight bond distribution

        context['securities'] = {
            'Stocks': transform_to_security_overview(stocks),
            'REIT': transform_to_security_overview(reit),
            'Bonds': transform_to_security_overview(bonds)}
        context['stocksWeight'] = stockWeight
        context['REITWeight'] = reitWeight
        context['bondsWeight'] = bondWeight
        context['worldDistribution'] = stockWeightRegions
        context['REGIONS'] = securityDistribution[0].REGIONS
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
    template_name = 'silverstrike/investments.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment-calculator'

        return context


class InvestmentOperationCreate(LoginRequiredMixin, generic.edit.CreateView):  # FIXME
    model = InvestmentOperation
    template_name = 'silverstrike/investment_operation_edit.html'
    form_class = InvestmentOperationForm

    def get_context_data(self, **kwargs):
        context = super(InvestmentOperationCreate, self).get_context_data(**kwargs)
        context['menu'] = 'transactions'
        return context


class InvestmentConfigView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_config.html'
    model = SecurityDetails

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_security_list'
        context['stocks'] = SecurityDetails.objects.filter(security_type=SecurityDetails.STOCK)
        context['reit'] = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT)
        return context

class InvestmentConfigPriceView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_config.html'
    model = SecurityPrice
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_security_pricing'
        return context

class InvestmentConfigTargetView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_portfolio_target.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_portfolio_target'
        context['targetAssets'] = SecurityTypeTarget.objects.all()
        context['regionList'] = SecurityDistribution.REGIONS
        context['targetWorld'] = SecurityRegionTarget.objects.all()
        context['targetMaturityBonds'] = SecurityBondMaturityTarget.objects.all()
        context['targetRegionBonds'] = SecurityBondRegionTarget.objects.all()
        return context

class InvestmentTargetUpdateView(LoginRequiredMixin, generic.FormView):
    template_name = 'silverstrike/investment_target_update.html'
    form_class = InvestmentTargetUpdateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_target_update' #FIXME add to context current
        return context

    def get_success_url(self):
        return reverse('investment_portfolio_target')

    def post(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        request_data = dict(request.POST.lists())

        for key in request_data.keys():
            print(key)

            if key == 'csrfmiddlewaretoken': #FIXME
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
                    SecurityTypeTarget.objects.create(security_type=security_type,allocation=allocation)
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
        if 'pk' in context:
            print(context['pk'])
        print(context)
        context['menu'] = 'transactions'
        return context

    def get_success_url(self):
        return reverse('investment_security_list')

class SecurityDistributionCreate(LoginRequiredMixin, generic.edit.FormView):  # FIXME
    template_name = 'silverstrike/investment_security_distribution_edit.html'
    form_class = InvestmentSecurityDistributionForm

    def get_context_data(self, **kwargs):
        context = super(SecurityDistributionCreate, self).get_context_data(**kwargs)
        context['menu'] = 'transactions' #FIXME add to context current
        return context

    def post(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        security_id = context['pk']
        security = SecurityDetails.objects.get(pk=security_id)
        request_data = dict(request.POST.lists())
        for key in request_data.keys():
            if key == 'csrfmiddlewaretoken': #FIXME
                continue
            try:
                dist = SecurityDistribution.objects.get(isin=security.isin,region_id=int(key))
                dist.allocation = float(request_data[key][0])
                dist.save()
            except SecurityDistribution.DoesNotExist:
                SecurityDistribution.objects.create(isin=security.isin, region_id=int(key), allocation=float(request_data[key][0]))

        return HttpResponseRedirect("/")

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
        context['securityDistribution'] = SecurityDistribution.objects.filter(isin=context['securityDetails'].isin)
        price_distribution = []
        for region in context['securityDistribution']:
            price_distribution.append(context['totalPrice'] * decimal.Decimal(region.allocation/100))
        context['securityDistributionPrice'] = price_distribution

        return context

    #FIXME switch to api
    def post(self,request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        security_id = context['pk']
        security = SecurityDetails.objects.get(pk=security_id)
        update_security_price(security.ticker)
        #TODO wait for price update on frontend
        return HttpResponseRedirect(reverse('investment_security_details', args=[security_id]))