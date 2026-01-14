from django.contrib import admin

from apps.cars.models import Car, CarSubCategory


# Register your models here.


@admin.register(CarSubCategory)
class CarSubcategoryAdmin(admin.ModelAdmin):
    """Admin interface for CarSubcategory model."""

    list_display = ["name", "code", "category", "description"]
    list_filter = ["category"]
    search_fields = ["name", "code"]
    ordering = ["category", "name"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "code", "category")}),
        (
            "Details",
            {
                "fields": ("description",),
            },
        ),
    )


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    """Admin interface for Car model."""

    list_display = [
        "name",
        "game",
        "category",
        "subcategory",
        "year",
        "power_hp",
        "weight",
        "is_dlc",
        "is_active",
    ]

    list_filter = [
        "game",
        "category",
        "subcategory",
        "manufacturer",
        "year",
        "is_dlc",
        "is_active",
    ]

    search_fields = [
        "name",
        "manufacturer",
    ]

    fieldsets = (
        (
            "Game Referenace",
            {
                "fields": ("game",),
            },
        ),
        (
            "Basic Information",
            {"fields": ("name", "manufacturer", "category", "subcategory", "year")},
        ),
        (
            "Technical Specifications",
            {"fields": ("engine", "power_hp", "weight", "transmission")},
        ),
        (
            "Dimensions",
            {
                "fields": ("length", "width", "height"),
                "classes": ("collapse",),
            },
        ),
        ("Game Reference", {"fields": ("is_active", "is_dlc")}),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ["created_at", "updated_at"]

    ordering = ["category", "subcategory", "manufacturer", "name"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Filter subcategories based on selected category in the form.
        This improves UX by only showing relevant subcategories.
        """
        if db_field.name == "subcategory":
            # If we're editing an existing car, filter by its category
            obj_id = request.resolver_match.kwargs.get("object_id")
            if obj_id:
                try:
                    car = Car.objects.get(pk=obj_id)
                    kwargs["queryset"] = CarSubCategory.objects.filter(
                        category=car.category
                    )
                except Car.DoesNotExist:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # Optional: Add custom actions
    actions = ["mark_as_active", "mark_as_inactive", "mark_as_dlc"]

    @admin.action(description="Mark selected cars as active")
    def mark_as_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} car(s) marked as active.")

    @admin.action(description="Mark selected cars as inactive")
    def mark_as_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} car(s) marked as inactive.")

    @admin.action(description="Mark selected cars as DLC")
    def mark_as_dlc(self, request, queryset):
        updated = queryset.update(is_dlc=True)
        self.message_user(request, f"{updated} car(s) marked as DLC.")
