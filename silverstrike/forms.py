from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext as _

from silverstrike import importers, models
from silverstrike.models import Transaction, InvestmentOperation, Split, SecurityDistribution, SecurityDetails, \
    SecurityBondRegionTarget, SecurityBondMaturityTarget, SecurityBondMaturity


class ImportUploadForm(forms.ModelForm):
    class Meta:
        model = models.ImportFile
        fields = ['file']

    account = forms.ModelChoiceField(queryset=models.Account.objects.personal())
    importer = forms.ChoiceField(choices=enumerate(importers.IMPORTER_NAMES))


class AccountCreateForm(forms.ModelForm):
    class Meta:
        model = models.Account
        fields = ['name', 'initial_balance', 'active', 'show_on_dashboard']

    initial_balance = forms.DecimalField(max_digits=10, decimal_places=2, initial=0)

    def save(self, commit=True):
        account = super(AccountCreateForm, self).save(commit)
        if self.cleaned_data['initial_balance']:
            account.set_initial_balance(self.cleaned_data['initial_balance'])
        return account


class BudgetForm(forms.Form):
    budget_id = forms.IntegerField()
    category_id = forms.IntegerField()
    category_name = forms.CharField(max_length=64)
    spent = forms.CharField(max_length=32)
    amount = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    left = forms.CharField(max_length=32)
    month = forms.DateField()

    def save(self):
        if self.cleaned_data['budget_id'] == -1:
            if self.cleaned_data['amount'] != 0:
                # new budget
                models.Budget.objects.create(
                    category_id=self.cleaned_data['category_id'],
                    month=self.cleaned_data['month'],
                    amount=self.cleaned_data['amount'])
        elif self.cleaned_data['amount'] != 0:
            models.Budget.objects.update_or_create(id=self.cleaned_data['budget_id'], defaults={
                'amount': self.cleaned_data['amount']
            })
        else:
            models.Budget.objects.get(id=self.cleaned_data['budget_id']).delete()


BudgetFormSet = forms.formset_factory(BudgetForm, extra=0)


class TransactionForm(forms.ModelForm):
    class Meta:
        model = models.Transaction
        fields = ['title', 'source_account', 'destination_account',
                  'amount', 'date', 'value_date', 'category', 'notes']

    amount = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    category = forms.ModelChoiceField(
        queryset=models.Category.objects.exclude(active=False).order_by('name'), required=False)
    value_date = forms.DateField(required=False)

    source_account = forms.ModelChoiceField(queryset=models.Account.objects.filter(
        account_type=models.Account.PERSONAL, active=True))
    destination_account = forms.ModelChoiceField(queryset=models.Account.objects.filter(
        account_type=models.Account.PERSONAL, active=True))

    def save(self, commit=True):
        transaction = super().save(commit)
        src = self.cleaned_data['source_account']
        dst = self.cleaned_data['destination_account']
        amount = self.cleaned_data['amount']
        value_date = self.cleaned_data.get('value_date') or transaction.date
        models.Split.objects.update_or_create(
            transaction=transaction, amount__lt=0,
            defaults={'amount': -amount, 'account': src,
                      'opposing_account': dst, 'date': value_date,
                      'title': transaction.title,
                      'category': self.cleaned_data['category']})
        models.Split.objects.update_or_create(
            transaction=transaction, amount__gt=0,
            defaults={'amount': amount, 'account': dst,
                      'opposing_account': src, 'date': value_date,
                      'title': transaction.title,
                      'category': self.cleaned_data['category']})
        return transaction


class TransferForm(TransactionForm):
    def save(self, commit=True):
        transaction = super().save(commit)
        src = self.cleaned_data['source_account']
        dst = self.cleaned_data['destination_account']
        amount = self.cleaned_data['amount']
        models.Split.objects.update_or_create(
            transaction=transaction, amount__lt=0,
            defaults={'amount': -amount, 'account': src,
                      'opposing_account': dst, 'date': transaction.date,
                      'title': transaction.title,
                      'category': self.cleaned_data['category']})
        models.Split.objects.update_or_create(
            transaction=transaction, amount__gt=0,
            defaults={'amount': amount, 'account': dst,
                      'opposing_account': src, 'date': transaction.date,
                      'title': transaction.title,
                      'category': self.cleaned_data['category']})
        return transaction

    def clean(self):
        super().clean()
        self.instance.transaction_type = models.Transaction.TRANSFER
        if self.cleaned_data['source_account'] == self.cleaned_data['destination_account']:
            error = 'source and destination account have to be different'
            self.add_error('destination_account', error)
            self.add_error('source_account', error)


class WithdrawForm(TransactionForm):
    destination_account = forms.CharField(max_length=64, label=_('Debitor'),
                                          widget=forms.TextInput(attrs={'autocomplete': 'off'}))

    def save(self, commit=True):
        account, _ = models.Account.objects.get_or_create(
            name=self.cleaned_data['destination_account'],
            account_type=models.Account.FOREIGN)
        self.cleaned_data['destination_account'] = account
        return super().save(commit)

    def clean(self):
        super().clean()
        self.instance.transaction_type = models.Transaction.WITHDRAW


class DepositForm(TransactionForm):
    source_account = forms.CharField(max_length=64, label=_('Creditor'),
                                     widget=forms.TextInput(attrs={'autocomplete': 'off'}))

    def save(self, commit=True):
        account, _ = models.Account.objects.get_or_create(name=self.cleaned_data['source_account'],
                                                          account_type=models.Account.FOREIGN)
        self.cleaned_data['source_account'] = account
        return super().save(commit)

    def clean(self):
        super().clean()
        self.instance.transaction_type = models.Transaction.DEPOSIT


class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = models.RecurringTransaction
        fields = ['title', 'date', 'amount', 'src', 'dst', 'category',
                  'interval', 'multiplier', 'weekend_handling', 'usual_month_day']

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount < 0:
            raise forms.ValidationError(_('Amount has to be positive'))
        return amount

    def clean(self):
        super(RecurringTransactionForm, self).clean()
        src = self.cleaned_data['src']
        dst = self.cleaned_data['dst']
        if src.account_type == models.Account.PERSONAL:
            if dst.account_type == models.Account.PERSONAL:
                self.transaction_type = models.Transaction.TRANSFER
            else:
                self.transaction_type = models.Transaction.WITHDRAW
        elif dst.account_type == models.Account.PERSONAL:
            self.transaction_type = models.Transaction.DEPOSIT
        else:
            raise forms.ValidationError(
                _('You are trying to create a transaction between two foreign accounts'))

    def save(self, commit=False):
        recurrence = super(RecurringTransactionForm, self).save(commit=False)
        recurrence.transaction_type = self.transaction_type
        recurrence.save()
        return recurrence


class ReconcilationForm(forms.ModelForm):
    class Meta:
        model = models.Transaction
        fields = ['title', 'balance', 'notes']

    balance = forms.DecimalField(max_digits=10, decimal_places=2, required=True,
                                 label=_('Actual balance'))

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account')
        super(ReconcilationForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        transaction = super().save(False)
        transaction.transaction_type = models.Transaction.SYSTEM
        transaction.save()
        src = models.Account.objects.get(account_type=models.Account.SYSTEM).pk
        dst = models.Account.objects.get(pk=self.account)
        balance = self.cleaned_data['balance']
        amount = balance - dst.balance
        models.Split.objects.create(transaction=transaction, amount=-amount,
                                    account_id=src, opposing_account=dst, title=transaction.title)
        models.Split.objects.create(transaction=transaction, amount=amount,
                                    account=dst, opposing_account_id=src, title=transaction.title)
        return transaction

    def clean(self):
        super().clean()
        if self.cleaned_data['balance'] == models.Account.objects.get(pk=self.account).balance:
            self.add_error('balance', 'You provided the same balance!')


class SplitForm(forms.ModelForm):
    class Meta:
        model = models.Split
        fields = ['title', 'account', 'opposing_account', 'date', 'amount', 'category']

    account = forms.ModelChoiceField(queryset=models.Account.objects.exclude(
        account_type=models.Account.SYSTEM))
    opposing_account = forms.ModelChoiceField(queryset=models.Account.objects.exclude(
        account_type=models.Account.SYSTEM))


TransactionFormSet = forms.models.inlineformset_factory(
    models.Transaction, models.Split, form=SplitForm, extra=1
)


class ExportForm(forms.Form):
    start = forms.DateField()
    end = forms.DateField()
    accounts = forms.ModelMultipleChoiceField(
        queryset=models.Account.objects.personal())


class InvestmentOperationForm(forms.ModelForm):
    class Meta:
        model = models.InvestmentOperation
        fields = [ 'account', 'security', 'quantity', 'date', 'price','exchange_rate', 'category',
                  'operation_type']

    account = forms.ModelChoiceField(queryset=models.Account.objects.filter(
        account_type=models.Account.PERSONAL, active=True))
    security = forms.ModelChoiceField(queryset=models.SecurityDetails.objects.all())
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    # price or amount
    price = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    category = forms.ModelChoiceField(
        queryset=models.Category.objects.exclude(active=False).order_by('name'), required=False)
    exchange_rate = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01, required=False) #FIXME check on backend receive
    operation_type = forms.ChoiceField(choices=models.InvestmentOperation.OPERATION_TYPES, required=True)
    date = forms.DateField(required=False)

    def save(self, commit=True):
        dst = models.Account.objects.get(account_type=models.Account.SYSTEM)
        src = self.cleaned_data['account']
        category = self.cleaned_data['category']
        operation_type = self.cleaned_data['operation_type']
        unit_price = self.cleaned_data['price']
        quantity = self.cleaned_data['quantity']
        security = self.cleaned_data['security']
        total_price = quantity * unit_price
        date = self.cleaned_data['date']

        if 'exchange_rate' in self.cleaned_data:
            exchange_rate = self.cleaned_data['exchange_rate']
            total_price = quantity * unit_price * exchange_rate
        else:
            exchange_rate = None

        title = str(models.InvestmentOperation.OPERATION_TYPES[int(operation_type)][1])+" "+str(self.cleaned_data['security'].ticker)+" "+str(self.cleaned_data['quantity'])+"@"+str(self.cleaned_data['price']) #FIXME add currency and exchange rate

        transaction = models.Transaction.objects.create(title=title,date=date,transaction_type=Transaction.TRANSFER,last_modified=date)
        if operation_type == str(models.InvestmentOperation.BUY):
            origin_account = src
            destination_account = dst

            if src.balance < total_price:
                raise forms.ValidationError("Not enough Funds")

            try:
                securityQuantity = models.SecurityQuantity.objects.get(account=src, security=security)
                securityQuantity.quantity = securityQuantity.quantity + quantity
                securityQuantity.save()
            except ObjectDoesNotExist:
                models.SecurityQuantity.objects.create(account = src, security= security, quantity = quantity)

        elif operation_type == str(models.InvestmentOperation.SELL):
            origin_account = dst
            destination_account = src

            try:
                securityQuantity = models.SecurityQuantity.objects.get(account=src,security=security)

                if securityQuantity.quantity < quantity:
                    raise forms.ValidationError("The account does not own that many securities")

                securityQuantity.quantity = securityQuantity.quantity - quantity

                orders = models.InvestmentOperation.objects.filter(account = src,security = security,operation_type = InvestmentOperation.BUY).order_by('date')
                already_sold = 0
                for order in orders:
                    if already_sold == quantity:
                        break

                    try:
                        securitySale = models.SecuritySale.objects.get(original_operation_id=order)
                        # 1         10
                        if securitySale.quantity < order.quantity:
                            # 9
                            difference = order.quantity - securitySale.quantity
                            if difference >= (quantity -already_sold):
                                #   1 + 9
                                securitySale.quantity = securitySale.quantity + (quantity - already_sold)
                                already_sold = already_sold + (quantity -already_sold)

                                securitySale.save()
                    except ObjectDoesNotExist:
                        to_sell = quantity - already_sold
                        if order.quantity >= to_sell:
                            models.SecuritySale.objects.create(original_operation_id=order,quantity=to_sell)
                            already_sold = quantity
                        else:
                            models.SecuritySale.objects.create(original_operation_id=order, quantity=order.quantity)
                            already_sold = already_sold + order.quantity

                securityQuantity.save()

            except ObjectDoesNotExist:
                raise forms.ValidationError("The account does not own that many securities")

        elif operation_type == str(models.InvestmentOperation.DIV):
            origin_account = dst
            destination_account = src
            try:
                securityQuantity = models.SecurityQuantity.objects.get(account=src, security =security)
                if securityQuantity.quantity < quantity:
                    raise forms.ValidationError("The account does not own that many securities")
            except ObjectDoesNotExist:
                raise forms.ValidationError("The account does not own that many securities")
        else:
            raise ValueError('Invalid operation type selected')
        #FIXME on tx delete investment operation deleted but SecurityQuantity not updated
        investmentOperation = models.InvestmentOperation.objects.create(date=date,
                                                                        price=unit_price, account=src,
                                                                        operation_type=operation_type,
                                                                        security=security, category=category, quantity=quantity,
                                                                        exchange_rate=exchange_rate,
                                                                        transaction_id=transaction)

        models.Split.objects.update_or_create(
            transaction=transaction, amount__lt=0,
            defaults={'amount': -total_price, 'account': origin_account,
                      'opposing_account': destination_account, 'date': date,
                      'title': transaction.title,
                      'category': category})

        models.Split.objects.update_or_create(
            transaction=transaction, amount__gt=0,
            defaults={'amount': total_price, 'account': destination_account,
                      'opposing_account': origin_account, 'date': date,
                      'title': transaction.title,
                      'category': category})

        return transaction


class InvestmentSecurityForm(forms.ModelForm):
    class Meta:
        model = models.SecurityDetails
        fields = ['isin', 'name', 'ticker', 'exchange', 'currency', 'security_type', "ter"]

    isin = forms.CharField(max_length=12, label=_('ISIN'),
                                     widget=forms.TextInput(attrs={'autocomplete': 'off'}))
    name = forms.CharField()
    ticker = forms.CharField()
    exchange = forms.CharField()
    currency = forms.CharField(max_length=3)
    security_type = forms.ChoiceField(choices=models.SecurityDetails.SECURITY_TYPES, required=True)
    ter = forms.FloatField()


class InvestmentSecurityDistributionForm(forms.Form):
    options = SecurityDistribution.REGIONS

    class Region:
        def __init__(self, id, name):
            self.id = id
            self.name = name
            self.field = forms.FloatField(max_value=100.0, min_value=0.0)
            #TODO total sum must be less than 100%

    distributions = []
    for i in options:
        reg = Region(i[0],i[1])
        distributions.append(reg)


class InvestmentSecurityBondDistributionForm(forms.Form):
    options = SecurityBondMaturity.MATURITY

    class Region:
        def __init__(self, id, name):
            self.id = id
            self.name = name
            self.field = forms.FloatField(max_value=100.0, min_value=0.0)
            # TODO total sum must be less than 100%

    distributions = []
    for i in options:
        reg = Region(i[0], i[1])
        distributions.append(reg)


class InvestmentTargetUpdateForm(forms.Form):
    class Target:
        def __init__(self, id, name):
            self.id = id
            self.name = name
            self.field = forms.FloatField(max_value=100.0, min_value=0.0)

    regionDistributions = []
    securityTypeDistributions = []

    bondMaturityDistributions = []
    bondRegionDistributions = []

    for i in SecurityDistribution.REGIONS:
        reg = Target(i[0],i[1])
        regionDistributions.append(reg)

    for i in SecurityDetails.SECURITY_TYPES:
        reg = Target(i[0], i[1])
        securityTypeDistributions.append(reg)

    for i in SecurityBondMaturity.MATURITY:
        reg = Target(i[0], i[1])
        bondMaturityDistributions.append(reg)

    for i in SecurityBondRegionTarget.REGIONS:
        reg = Target(i[0], i[1])
        bondRegionDistributions.append(reg)


CategoryAssignFormset = forms.modelformset_factory(models.Split, fields=('category',), extra=0)
