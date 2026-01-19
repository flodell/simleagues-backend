from django.db import models

from core.models.choices import CarCategory
from core.models.game import Game




class CarSubCategory(models.Model):
    """
    Subcategories for racing cars.
    Each subcategory is linked to a specific category.
    """

    name = models.CharField(max_length=40, unique=True)
    code = models.CharField(max_length=20, unique=True)
    category = models.CharField(max_length=30, choices=CarCategory.choices)
    description = models.TextField(blank=True, help_text="Optional description")

    class Meta:
        verbose_name = "Car Subcategory"
        verbose_name_plural = "Car Subcategories"
        ordering = ["category", "name"]
        unique_together = ["category", "code"]

    def __str__(self):
        return f"{self.name} ({self.category})"


class Car(models.Model):
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="cars",
        help_text="Game where this car is available",
    )

    # Basic informations
    name = models.CharField(max_length=200)
    manufacturer = models.CharField(max_length=100)
    category = models.CharField(max_length=30, choices=CarCategory.choices)
    subcategory = models.ForeignKey(
        CarSubCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cars",
    )
    year = models.IntegerField()

    # Technical specs
    engine = models.CharField(max_length=200, blank=True)
    power_hp = models.IntegerField(null=True, blank=True, verbose_name="Power (HP)")
    weight = models.IntegerField(null=True, blank=True, verbose_name="Weight (Kg)")
    length = models.IntegerField(null=True, blank=True, verbose_name="Length (mm)")
    width = models.IntegerField(null=True, blank=True, verbose_name="Width (mm)")
    height = models.IntegerField(null=True, blank=True, verbose_name="Height (mm)")
    transmission = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_dlc = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "-created_at",
            "-updated_at",
            "name",
            "manufacturer",
            "category",
            "subcategory",
            "year",
        ]
        verbose_name = "Car"
        verbose_name_plural = "Cars"

    def __str__(self):
        year_str = f" ({self.year})" if self.year else ""
        subcategory_str = f" [{self.subcategory.code}]" if self.subcategory else ""
        return f"{self.manufacturer} {self.name} - {self.category} - {subcategory_str} - {year_str}"

    @property
    def power_to_weight_ration(self):
        """
        Calculate power-to-weight ratio (HP/kg).

        Returns:
            float: HP per kg, or None if data is missing
        """
        if self.power_hp and self.weight:
            return round(self.power_hp / self.weight, 3)
        return None

    def clean(self):
        """Validate that subcategory matches the car's category."""
        from django.core.exceptions import ValidationError

        if self.subcategory and self.subcategory.category != self.category:
            raise ValidationError(
                {
                    "subcategory": f'Subcategory "{self.subcategory}" is not valid for category "{self.category}".'
                }
            )
