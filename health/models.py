from django.conf import settings
from django.db import models


class WeightEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='weight_entries',
    )
    date = models.DateField()
    weight = models.DecimalField(max_digits=5, decimal_places=1, help_text="Weight in lbs")

    class Meta:
        ordering = ['date']
        unique_together = ['user', 'date']

    def __str__(self):
        return f"{self.user} — {self.date}: {self.weight} lbs"


YARDS_PER_MILE = 1760

ACTIVITY_CHOICES = [
    ('walk', 'Walk'),
    ('walk_run', 'Walk/Run'),
    ('run', 'Run'),
    ('bike', 'Bike'),
    ('swim', 'Swim'),
]


class ExerciseEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exercise_entries',
    )
    date = models.DateField()
    time = models.TimeField(help_text="Time of day (to allow multiple entries per day)")
    activity = models.CharField(max_length=20, choices=ACTIVITY_CHOICES)
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    distance_miles = models.DecimalField(max_digits=6, decimal_places=1, help_text="Distance in miles")
    distance_yards = models.PositiveIntegerField(null=True, blank=True, help_text="Raw yards entered (swim only)")

    class Meta:
        ordering = ['-date', '-time']

    def __str__(self):
        return f"{self.user} — {self.date} {self.time}: {self.get_activity_display()} {self.distance_miles}mi"
