# Generated by Django 3.0.4 on 2020-04-04 23:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('silverstrike', '0026_auto_20200326_1733'),
    ]

    operations = [
        migrations.AddField(
            model_name='investmentoperation',
            name='exchange_rate',
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True),
        ),
    ]
