from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('claude_usage', '0003_remove_message_count'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClaudeToolCount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('tool_name', models.CharField(max_length=64)),
                ('count', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['-date', 'tool_name'],
                'unique_together': {('date', 'tool_name')},
            },
        ),
    ]
