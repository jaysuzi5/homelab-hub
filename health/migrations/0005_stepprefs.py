from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('health', '0004_stepentry'),
    ]

    operations = [
        migrations.CreateModel(
            name='StepPrefs',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('steps_per_mile', models.PositiveIntegerField(default=2200, help_text='Steps counted as one mile')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='step_prefs', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
