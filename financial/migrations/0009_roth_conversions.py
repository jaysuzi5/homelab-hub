from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0008_forecast_tax_brackets'),
    ]

    operations = [
        migrations.AddField(
            model_name='forecastsettings',
            name='roth_conversions',
            field=models.JSONField(
                default=list,
                help_text='List of Roth conversion periods: [{"label":"...", "start_year":2026, "end_year":2030, "annual_amount":30000}]',
            ),
        ),
    ]
