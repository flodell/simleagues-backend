from django.db import models

# CAR CHOICES


class CarCategory(models.TextChoices):
    HYPERCAR = "HYPERCAR", "Hypercar"
    LMGT3 = "LMGT3", "LMGT3"
    LPM2 = "LPM2", "LPM2"
    LPM3 = "LPM3", "LPM3"
    GTE = "GTE", "GTE"


# RACE CHOICES


class RaceStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class RaceEntryStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    BANNED = "BANNED", "Banned"


class RaceVisibility(models.TextChoices):
    PUBLIC = "PUBLIC", "Public (Anyone can view)"
    UNLISTED = "UNLISTED", "Unlisted (Only with link)"
    PRIVATE = "PRIVATE", "Private (League members only)"


class FuelUsage(models.TextChoices):
    OFF = 'OFF', 'Off'
    X1 = 'X1', 'x1'
    X2 = 'X2', 'x2'
    X3 = 'X3', 'x3'
    X5 = 'X5', 'x5'


class TireWear(models.TextChoices):
    X1 = 'X1', 'x1'
    X2 = 'X2', 'x2'
    X3 = 'X3', 'x3'


class MechanicalFailures(models.TextChoices):
    OFF = 'OFF', 'Off'
    NORMAL = 'NORMAL', 'Normal'
    TIME_SCALED = 'TIME_SCALED', 'Time-scaled'


class FlagRules(models.TextChoices):
    FULL = 'FULL', 'Full'
    PARTIAL = 'PARTIAL', 'Partial'
    NONE = 'NONE', 'None'


class TrackLimits(models.TextChoices):
    STRICT = 'STRICT', 'Strict'
    NORMAL = 'NORMAL', 'Normal'
    RELAXED = 'RELAXED', 'Relaxed'


class SkyCondition(models.TextChoices):
    CLEAR = 'CLEAR', 'Clear'
    PARTLY_CLOUDY = 'PARTLY_CLOUDY', 'Partly cloudy'
    OVERCAST = 'OVERCAST', 'Overcast'
    LIGHT_RAIN = 'LIGHT_RAIN', 'Light rain'
    HEAVY_RAIN = 'HEAVY_RAIN', 'Heavy rain'

# LEAGUE CHOICES


class LeagueMemberRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    MODERATOR = "MODERATOR", "Moderator"
    MEMBER = "MEMBER", "Member"


class LeagueVisibility(models.TextChoices):
    PUBLIC = "PUBLIC", "Public (Anyone can join)"
    INVITE_ONLY = "INVITE_ONLY", "Invite Only (Need invitation code)"
    PRIVATE = "PRIVATE", "Private (Admin approval required)"


class JoinRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


# CHAMPIONSHIP CHOICES


class ChampionshipStatus(models.TextChoices):
    UPCOMING = "UPCOMING", "Upcoming"
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class ChampionshipEntryStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    BANNED = "BANNED", "Banned"


# PARTICIPANT CHOICES


class ParticipantType(models.TextChoices):
    TEAM = "TEAM", "Team"
    INDIVIDUAL = "INDIVIDUAL", "Individual"


# TEAM CHOICES


class TeamRole(models.TextChoices):
    OWNER = "OWNER", "Owner"
    MANAGER = "MANAGER", "Manager"
    DRIVER = "DRIVER", "Driver"
    RESERVE = "RESERVE", "Reserve"


class TeamJoinRequestStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"


class LeagueTeamRegistrationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    BANNED = "BANNED", "Banned"
