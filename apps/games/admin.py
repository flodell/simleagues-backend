from django.contrib import admin

from apps.games.models import Game


# Register your models here.


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    """Admin interface for Game model."""

    list_display = ["name", "short_name", "developer", "is_active"]
    list_filter = ["is_active", "developer"]
    search_fields = ["name", "short_name", "developer"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "short_name", "developer")}),
        ("Details", {"fields": ("release_date", "website", "is_active")}),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ["created_at", "updated_at"]
