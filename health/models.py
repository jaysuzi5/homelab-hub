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


GOAL_TIER_CHOICES = [
    ('primary', 'Primary'),
    ('secondary', 'Secondary'),
]


class WeightGoal(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='weight_goals',
    )
    target_date = models.DateField()
    target_weight = models.DecimalField(max_digits=5, decimal_places=1, help_text="Target weight in lbs")
    label = models.CharField(max_length=100, blank=True)
    tier = models.CharField(max_length=10, choices=GOAL_TIER_CHOICES, default='primary')

    class Meta:
        ordering = ['target_date']
        unique_together = ['user', 'target_date', 'tier']

    def __str__(self):
        return f"{self.user} — {self.target_date}: {self.target_weight} lbs {self.tier} goal"


class WeightChartPrefs(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='weight_chart_prefs',
    )
    chart_start_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} weight chart prefs"


class StepEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='step_entries',
    )
    date = models.DateField()
    steps = models.PositiveIntegerField(help_text="Steps taken that day")
    bike_miles = models.DecimalField(max_digits=5, decimal_places=1, default=0,
                                     help_text="Miles biked that day")

    class Meta:
        ordering = ['-date']
        unique_together = ['user', 'date']

    def __str__(self):
        return f"{self.user} — {self.date}: {self.steps} steps"


DEFAULT_STEPS_PER_MILE = 2200
DEFAULT_STEPS_PER_BIKE_MILE = 500


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
