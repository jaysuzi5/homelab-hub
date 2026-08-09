from django.db import migrations


def to_secondary(apps, schema_editor):
    WeightGoal = apps.get_model('health', 'WeightGoal')
    WeightGoal.objects.update(tier='secondary')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('health', '0009_alter_weightgoal_unique_together_weightgoal_tier_and_more'),
    ]

    operations = [
        migrations.RunPython(to_secondary, noop),
    ]
