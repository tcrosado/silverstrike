# Generated by Django 2.2.5 on 2019-09-22 19:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('silverstrike', '0016_securitysale'),
    ]

    operations = [
        migrations.CreateModel(
            name='SecurityBondMaturity',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('isin', models.CharField(max_length=12)),
                ('allocation', models.FloatField(default=0.0)),
                ('maturity', models.IntegerField(choices=[(0, '1-3Y'), (1, '3-5Y'), (2, '5-7Y'), (3, '7-10Y'), (4, '10-15Y'), (5, '15-20Y'), (6, '20-30Y'), (7, '30+')], default=0)),
            ],
        ),
    ]
