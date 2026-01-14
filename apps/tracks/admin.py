from django.contrib import admin

from apps.tracks.models import Track


# Register your models here.
@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    """Admin interface for Track model."""

    list_display = [
        "name",
        "game",
        "country",
        "length",
        "corners",
        "is_dlc",
    ]

    list_filter = [
        "game",
        "country",
        "is_dlc",
    ]

    search_fields = [
        "name",
        "location",
        "country",
    ]

    fieldsets = (
        ("Game Reference", {"fields": ("game",)}),
        ("Basic Information", {"fields": ("name", "location", "country", "layout")}),
        ("Track Specifications", {"fields": ("length", "corners", "description")}),
        ("Settings", {"fields": ("is_dlc",)}),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ["created_at", "updated_at"]

    ordering = ["game", "name", "layout"]

    # Custom actions
    actions = ["mark_as_active", "mark_as_inactive", "mark_as_dlc"]

    @admin.action(description="Mark selected tracks as DLC")
    def mark_as_dlc(self, request, queryset):
        updated = queryset.update(is_dlc=True)
        self.message_user(request, f"{updated} track(s) marked as DLC.")
