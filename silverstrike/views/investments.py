from datetime import date

from dateutil.relativedelta import relativedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic

from silverstrike.models import InvestmentOperation, SecurityDetails, SecurityQuantity, SecurityDistribution, \
    SecurityPrice
from silverstrike.forms import InvestmentOperationForm, InvestmentSecurityForm, InvestmentSecurityDistributionForm


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
    template_name = 'silverstrike/investment_config.html'
    model = SecurityPrice
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'investment_security_pricing'
        return context

class SecurityDetailsCreate(LoginRequiredMixin, generic.edit.CreateView):  # FIXME
    model = SecurityDetails
    template_name = 'silverstrike/investment_security_create.html'
    form_class = InvestmentSecurityForm

    def get_context_data(self, **kwargs):
        context = super(SecurityDetailsCreate, self).get_context_data(**kwargs)
        context['menu'] = 'transactions'
        return context

class SecurityDistributionCreate(LoginRequiredMixin, generic.edit.FormView):  # FIXME
    template_name = 'silverstrike/investment_security_distribution_edit.html'
    form_class = InvestmentSecurityDistributionForm

    def get_context_data(self, **kwargs):
        context = super(SecurityDistributionCreate, self).get_context_data(**kwargs)
        context['menu'] = 'transactions'
        return context

    def post(self, request, *args, **kwargs):
        context = super().get_context_data(**kwargs)
        security_id = context['pk']
        security = SecurityDetails.objects.get(pk=security_id)
        request_data = dict(request.POST.lists())
        for key in request_data.keys():
            if key == 'csrfmiddlewaretoken': #FIXME
                continue
            SecurityDistribution.objects.create(isin=security.isin, allocation=float(request_data[key][0]), region_id=int(key))

        return HttpResponseRedirect("/")

class SecurityDetailsInformation(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/investment_security_information.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'security_details'
        context['securityDetails'] = SecurityDetails.objects.get(pk=context['pk'])
        context['currentAssets'] = SecurityQuantity.objects.get(isin=context['securityDetails'].isin).quantity
        return context
