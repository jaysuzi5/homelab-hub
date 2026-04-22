from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('claude_usage', '0004_claudetoolcount'),
    ]

    operations = [
        migrations.DeleteModel(name='ClaudeWeeklyPeak'),
    ]
