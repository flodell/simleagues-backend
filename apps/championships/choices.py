from django.db import models


class ParticipantType(models.TextChoices):
    TEAM = "TEAM", "Team"
    INDIVIDUAL = "INDIVIDUAL", "Individual"
