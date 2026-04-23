from django.conf import settings
from django.db import models


GUITAR_CATEGORY_CHOICES = [
    ('yousician', 'Yousician'),
    ('youtube', 'YouTube'),
    ('free_play', 'Free Play'),
    ('other', 'Other'),
]

GUITAR_SKILL_FIELDS = [
    ('skill_lead', 'Lead'),
    ('skill_chords', 'Chords'),
    ('skill_finger_picking', 'Finger Picking'),
    ('skill_strumming', 'Strumming Patterns'),
    ('skill_scales', 'Scales'),
]


class GuitarSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='guitar_sessions',
    )
    date = models.DateField()
    time = models.TimeField(help_text="Time of day (allows multiple entries per day)")
    category = models.CharField(max_length=20, choices=GUITAR_CATEGORY_CHOICES)
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    description = models.CharField(max_length=500, blank=True)
    skill_lead = models.BooleanField(default=False)
    skill_chords = models.BooleanField(default=False)
    skill_finger_picking = models.BooleanField(default=False)
    skill_strumming = models.BooleanField(default=False)
    skill_scales = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date', '-time']

    def __str__(self):
        return f"{self.user} — {self.date} {self.get_category_display()} {self.duration}min"

    def skill_labels(self):
        return [label for field, label in GUITAR_SKILL_FIELDS if getattr(self, field)]


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
    cover_local = models.CharField(max_length=500, blank=True,
                                   help_text="Relative path under MEDIA_ROOT to locally cached cover image")
    open_library_key = models.CharField(max_length=100, blank=True)
    summary = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)  # 0-5
    comment = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_read']

    def __str__(self):
        return f"{self.title} by {self.author}"
