import csv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.views import generic

from silverstrike import forms
from silverstrike import importers
from silverstrike import models


class ImportView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/import.html'


class ImportUploadView(LoginRequiredMixin, generic.edit.CreateView):
    model = models.ImportFile
    form_class = forms.ImportUploadForm
    template_name = 'silverstrike/import_upload.html'

    def form_valid(self, form):
        self.object = form.save()
        account = form.cleaned_data['account']
        importer = form.cleaned_data['importer']
        print(importer)
        return HttpResponseRedirect(
            reverse('import_process', args=[self.object.pk, account.pk, importer]))


class ImportProcessView(LoginRequiredMixin, generic.TemplateView):
    template_name = 'silverstrike/import_configure_upload.html'

    def get_context_data(self, **kwargs):
        context = super(ImportProcessView, self).get_context_data(**kwargs)
        file = models.ImportFile.objects.get(uuid=self.kwargs['uuid'])
        importer = self.kwargs['importer']
        context['data'] = importers.IMPORTERS[importer].import_transactions(file.file.path)
        context['recurrences'] = models.RecurringTransaction.objects.exclude(
            interval=models.RecurringTransaction.DISABLED).order_by('title')
        return context

    def post(self, request, *args, **kwargs):
        file = models.ImportFile.objects.get(uuid=self.kwargs['uuid'])
        importer = self.kwargs['importer']
        data = importers.IMPORTERS[importer].import_transactions(file.file.path)
        for i in range(len(data)):
            account = data[i].account
            account_iban = data[i].account_iban
            opposing_account = data[i].opposing_account
            opposing_account_iban = data[i].opposing_account_iban
            date = data[i].transaction_date
            book_date = data[i].book_date
            title = request.POST.get('title-{}'.format(i), '')
            recurrence = int(request.POST.get('recurrence-{}'.format(i), '-1'))

            if not title:
                title = data[i].opposing_account
            amount = float(data[i].amount)
            if amount == 0:
                continue

            # Account setup
            account, _ = models.Account.objects.get_or_create(
                iban=account_iban,
                defaults={'account_type': models.Account.FOREIGN,
                          'iban': account_iban})

            if not account.last_modified and hasattr(data[i], 'iban'):
                account.iban = data[i].iban
                account.save()

            # Opposing Account setup
            opposing_account, _ = models.Account.objects.get_or_create(
                name=opposing_account,
                defaults={'account_type': models.Account.FOREIGN,
                          'iban': opposing_account_iban}
            )

            # Set transaction type
            transaction_type = -1
            if account.account_type == models.Account.PERSONAL:
                transaction_type = models.Transaction.TRANSFER
            elif account.account_type == models.Account.FOREIGN:
                if amount < 0:
                    transaction_type = models.Transaction.WITHDRAW
                else:
                    transaction_type = models.Transaction.DEPOSIT

            transaction = models.Transaction()
            transaction.title = title
            transaction.date = date
            transaction.transaction_type = transaction_type
            if recurrence > 0:
                transaction.recurrence_id = recurrence
            transaction.save()

            models.Split.objects.create(
                title=title,
                amount=amount,
                date=book_date,
                transaction=transaction,
                account=account,
                opposing_account=opposing_account
                )
            models.Split.objects.create(
                title=title,
                amount=-amount,
                date=date,
                transaction=transaction,
                account=opposing_account,
                opposing_account=account
                )
        return HttpResponseRedirect('/')


class ImportFireflyView(LoginRequiredMixin, generic.edit.CreateView):
    model = models.ImportFile
    fields = ['file']
    template_name = 'silverstrike/import_upload.html'

    def form_valid(self, form):
        self.object = form.save()
        importers.firefly.import_firefly(self.object.file.path)
        return HttpResponseRedirect(reverse('index'))


class ExportView(LoginRequiredMixin, generic.edit.FormView):
    template_name = 'silverstrike/export.html'
    form_class = forms.ExportForm

    def form_valid(self, form):
        response = HttpResponse(content_type='text/csv')

        splits = models.Split.objects.date_range(
            form.cleaned_data['start'], form.cleaned_data['end']).transfers_once()
        splits = splits.filter(account__in=form.cleaned_data['accounts'])
        csv_writer = csv.writer(response, delimiter=';')
        headers = [
            'account',
            'opposing_account',
            'date',
            'amount',
            'category'
            ]
        csv_writer.writerow(headers)
        for split in splits.values_list('account__name', 'opposing_account__name',
                                        'date', 'amount', 'category__name'):
            csv_writer.writerow(split)

        response['Content-Disposition'] = 'attachment; filename=export.csv'
        return response
