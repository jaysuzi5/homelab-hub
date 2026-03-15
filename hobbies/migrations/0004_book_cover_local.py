from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hobbies', '0003_alter_book_options_book_comment_book_rating_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='cover_local',
            field=models.CharField(
                blank=True,
                max_length=500,
                help_text='Relative path under MEDIA_ROOT to locally cached cover image',
            ),
        ),
    ]
