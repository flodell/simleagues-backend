from django.db import models


class Game(models.Model):
    """
    Represents a racing simulator game.

    This model stores information about supported racing games
    and serves as a reference for cars and tracks.
    """

    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=20, unique=True)
    developer = models.CharField(max_length=100, blank=True)
    publisher = models.CharField(max_length=100, blank=True)
    release_date = models.DateField(null=True, blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(
        default=True, help_text="Game is currently supported"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Game"
        verbose_name_plural = "Games"
