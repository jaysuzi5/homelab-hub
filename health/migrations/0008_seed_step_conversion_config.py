from django.db import migrations

DEFAULTS = {
    'STEPS_PER_MILE': '2200',
    'STEPS_PER_BIKE_MILE': '1400',
}


def seed(apps, schema_editor):
    HubConfig = apps.get_model('config', 'HubConfig')
    for key, value in DEFAULTS.items():
        HubConfig.objects.get_or_create(key=key, defaults={'value': value})


def unseed(apps, schema_editor):
    HubConfig = apps.get_model('config', 'HubConfig')
    HubConfig.objects.filter(key__in=DEFAULTS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('health', '0007_delete_stepprefs'),
        ('config', '0002_value_to_textfield'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
