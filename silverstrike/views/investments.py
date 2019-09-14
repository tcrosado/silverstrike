import decimal
from datetime import date,datetime

from dateutil.relativedelta import relativedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.handlers.wsgi import WSGIRequest
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_overview'
        quantities = SecurityQuantity.objects.all()
        securityQuant = dict()
        for security in quantities:
            securityQuant[security.isin] = security.quantity
        stocks = SecurityDetails.objects.filter(security_type=SecurityDetails.STOCK,isin__in=securityQuant.keys())
        reit = SecurityDetails.objects.filter(security_type=SecurityDetails.REIT,isin__in=securityQuant.keys())
        bonds = SecurityDetails.objects.filter(security_type=SecurityDetails.BOND,isin__in=securityQuant.keys())

        context['stocks'] = [(securityQuant[security.isin], security) for security in stocks]
        context['reit'] = [(securityQuant[security.isin], security) for security in reit]
        context['bonds'] = [(securityQuant[security.isin], security) for security in bonds]
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