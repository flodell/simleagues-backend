from django.db import models

from apps.games.models import Game


# Create your models here.

class Track(models.Model):
    """
    Represents a racing circuit/track available in a game.

    A track can have multiple layouts (e.g., Full Circuit, Short, Night).
    """
    # Basic informations
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='tracks')
    name = models.CharField(max_length=200, unique=True)
    location = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    layout = models.CharField(max_length=100, blank=True, help_text="Track layout (e.g. Full Circuit, Short, GP)")
    length = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    corners = models.IntegerField(help_text="Number of corners")

    # Additional information
    description = models.TextField(
        blank=True,
        help_text="Track description and history"
    )

    #Flags
    is_dlc = models.BooleanField(default=False)

    #Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['game', 'name', 'layout', 'length', 'corners']
        verbose_name = 'Track'
        verbose_name_plural = 'Tracks'
