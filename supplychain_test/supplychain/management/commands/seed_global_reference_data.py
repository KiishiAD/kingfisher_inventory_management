from django.core.management.base import BaseCommand

from supplychain.models import UnitOfMeasure, Category


UOM_SEED = [
    ("kg", "Kilogram"),
    ("g", "Gram"),
    ("L", "Litre"),
    ("mL", "Millilitre"),
    ("pcs", "Pieces"),
    ("box", "Box"),
    ("carton", "Carton"),
]

CATEGORY_SEED = [
    "Produce",
    "Meat",
    "Dairy",
    "Dry Goods",
    "Beverages",
    "Cleaning",
    "Supplies",
]


class Command(BaseCommand):
    help = "Create global (org-independent) UOM and Category records."

    def handle(self, **options):
        self._seed_uoms(options["verbosity"])
        self._seed_categories(options["verbosity"])
        self.stdout.write(self.style.SUCCESS("Global reference data seeded."))

    def _seed_uoms(self, verbosity):
        for code, name in UOM_SEED:
            _, created = UnitOfMeasure.objects.get_or_create(
                code=code, defaults={"name": name}
            )
            if verbosity >= 2:
                self.stdout.write(
                    f"  {'Created' if created else 'Skipped'} UOM: {name} ({code})"
                )

    def _seed_categories(self, verbosity):
        for name in CATEGORY_SEED:
            _, created = Category.objects.get_or_create(name=name)
            if verbosity >= 2:
                self.stdout.write(
                    f"  {'Created' if created else 'Skipped'} Category: {name}"
                )
