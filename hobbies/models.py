from django.conf import settings
from django.db import models


class Book(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='books',
        null=True,
        blank=True,
    )
    date_read = models.DateField(help_text="Date the book was finished")
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=500, blank=True)
    pages = models.IntegerField(null=True, blank=True)
    cover_url = models.URLField(max_length=500, blank=True)
    open_library_key = models.CharField(max_length=100, blank=True)
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_read']

    def __str__(self):
        return f"{self.title} by {self.author}"
