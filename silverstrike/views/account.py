from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import Http404
from django.urls import reverse_lazy
from django.views import generic

from silverstrike.forms import AccountCreateForm, ReconcilationForm
from silverstrike.lib import last_day_of_month
from silverstrike.models import Account, Split, Transaction


class AccountCreate(LoginRequiredMixin, generic.edit.CreateView):
    model = Account
    form_class = AccountCreateForm
    success_url = reverse_lazy('accounts')

    def get_context_data(self, **kwargs):
        context = super(AccountCreate, self).get_context_data(**kwargs)
        context['menu'] = 'accounts'
        return context


class AccountUpdate(LoginRequiredMixin, generic.edit.UpdateView):
    model = Account
    fields = ['name', 'active', 'show_on_dashboard']

    def get_form_class(self):
        if self.object.account_type == Account.SYSTEM:
            raise Http404("You aren't allowed to edit this account")
        if self.object.account_type != Account.PERSONAL:
            self.fields = ['name']
        return super(AccountUpdate, self).get_form_class()


class AccountDelete(LoginRequiredMixin, generic.edit.DeleteView):
    model = Account
    success_url = reverse_lazy('accounts')

    def get_context_data(self, **kwargs):
        if self.object.account_type == Account.SYSTEM:
            raise Http404("You are not allowed to delete this account")
        return super(AccountDelete, self).get_context_data(**kwargs)


class AccountIndex(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['menu'] = 'accounts'
        balances = Split.objects.personal().past().order_by('account_id').values(
            'account_id').annotate(Sum('amount'))
        accounts = list(Account.objects.filter(account_type=Account.PERSONAL).values(
            'id', 'name', 'active'))
        for a in accounts:
            a['balance'] = 0
        for b in balances:
            for a in accounts:
                if a['id'] == b['account_id']:
                    a['balance'] = b['amount__sum']
        context['accounts'] = accounts
        return context


class AccountView(LoginRequiredMixin, generic.ListView):
    template_name = 'silverstrike/account_detail.html'
    context_object_name = 'transactions'
    model = Split
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        if 'month' in self.kwargs:
            self.month = date(kwargs.pop('year'), kwargs.pop('month'), 1)
        else:
            self.month = date.today().replace(day=1)

        self.dend = last_day_of_month(self.month)
        return super(AccountView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(account=self.kwargs.get('pk')).select_related(
            'category', 'account', 'transaction', 'opposing_account')
        queryset = queryset.date_range(self.month, self.dend)
        return queryset

    def get_context_data(self, **kwargs):
        account = Account.objects.get(pk=self.kwargs['pk'])
        if account.account_type == Account.SYSTEM:
            raise Http404('Account not accessible')
        context = super().get_context_data(**kwargs)
        context['account'] = account
        context['menu'] = 'accounts'
        context['month'] = self.month

        context['previous_month'] = (self.month - timedelta(days=1)).replace(day=1)
        context['next_month'] = self.dend + timedelta(days=1)

        income = 0
        expenses = 0
        today = date.today()
        for s in context['transactions']:
            if s.date > today:
                continue
            if s.amount < 0:
                expenses += s.amount
            elif s.amount > 0:
                income += s.amount
        context['in'] = income
        context['out'] = expenses
        context['difference'] = context['in'] + context['out']

        delta = timedelta(days=3)
        if account.account_type == Account.PERSONAL:
            context['dataset'] = account.get_data_points(
                self.month - delta, self.dend + delta)
        context['balance'] = account.balance
        return context


class ReconcileView(LoginRequiredMixin, generic.edit.CreateView):
    template_name = 'silverstrike/reconcile.html'
    form_class = ReconcilationForm
    model = Transaction

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = Account.objects.get(pk=self.kwargs['pk'])
        if context['account'].account_type != Account.PERSONAL:
            raise Http404("You can't reconcile this account")
        return context

    def get_form_kwargs(self):
        kwargs = super(ReconcileView, self).get_form_kwargs()
        kwargs['account'] = self.kwargs['pk']
        return kwargs
