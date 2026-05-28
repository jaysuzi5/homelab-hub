from decimal import Decimal
from django.db import migrations, models
import financial.models


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0007_dob_and_tax_rate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='forecastsettings',
            name='effective_tax_rate',
        ),
        migrations.AddField(
            model_name='forecastsettings',
            name='filing_status',
            field=models.CharField(
                choices=[('MFJ', 'Married Filing Jointly'), ('SINGLE', 'Single')],
                default='MFJ',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='forecastsettings',
            name='federal_standard_deduction',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('32200.00'),
                help_text='Standard deduction (2026 MFJ default: $32,200)',
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='forecastsettings',
            name='federal_brackets',
            field=models.JSONField(
                default=financial.models._default_federal_brackets,
                help_text='List of [threshold, rate] pairs for federal income tax brackets (taxable income thresholds)',
            ),
        ),
        migrations.AddField(
            model_name='forecastsettings',
            name='pa_flat_rate',
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal('0.0307'),
                help_text='Pennsylvania flat income tax rate (default 3.07%)',
                max_digits=6,
            ),
        ),
        migrations.AddField(
            model_name='forecastsettings',
            name='pa_retirement_age',
            field=models.DecimalField(
                decimal_places=1,
                default=Decimal('59.5'),
                help_text='Age at which PA exempts traditional IRA/401k withdrawals',
                max_digits=4,
            ),
        ),
    ]
