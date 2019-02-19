import csv
import datetime
import logging

from silverstrike.importers.import_statement import ImportStatement

logger = logging.getLogger(__name__)

def import_transactions(csv_path):
    lines = []
    with open(csv_path, encoding='latin-1') as csv_file:
        i = 0
        csv_content = csv.reader(csv_file, delimiter=";")
        for line in csv_content:
            i += 1
            if i == 1:
                continue
            try:
                print(line)
                lines.append(ImportStatement(
                    book_date=datetime.datetime.strptime(line[1], '%Y-%m-%d').date(),
                    transaction_date=datetime.datetime.strptime(line[0], '%Y-%m-%d').date(),
                    account=line[2],
                    notes=line[3],# Payee
                    iban=line[2],
                    amount=float(line[5].replace('.', '').replace(',', '.'))
                ))
            except ValueError:
                print('Error')
                # first line contains headers
                pass
        return lines
