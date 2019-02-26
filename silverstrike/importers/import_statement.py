class ImportStatement(object):
    account = ''
    opposing_account = ''
    book_date = ''
    transaction_date = ''
    amount = 0
    notes = ''
    account_iban = ''
    opposing_account_iban = ''

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)
        self.transaction_date = self.transaction_date or self.book_date

    def __str__(self):
        return self.account_iban+" "+self.opposing_account_iban+" "+self.notes+" "+str(self.amount)