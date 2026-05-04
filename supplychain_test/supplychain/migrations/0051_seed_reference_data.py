from django.db import migrations


UOMS = [
    ("EA", "Each"),
    ("KG", "Kilogram"),
    ("G", "Gram"),
    ("L", "Litre"),
    ("ML", "Millilitre"),
    ("M", "Metre"),
    ("CM", "Centimetre"),
    ("PK", "Pack"),
    ("BX", "Box"),
    ("CT", "Carton"),
    ("RL", "Roll"),
    ("PR", "Pair"),
    ("DOZ", "Dozen"),
    ("T", "Tonne"),
]

CATEGORIES = [
    "Electronics",
    "Office Supplies",
    "Furniture",
    "IT Hardware",
    "Cleaning Supplies",
    "Stationery",
    "Beverages",
    "Food Items",
    "Consumables",
    "Tools & Equipment",
    "Packaging Materials",
    "Personal Protective Equipment",
]


def seed_reference_data(apps, schema_editor):
    UnitOfMeasure = apps.get_model("supplychain", "UnitOfMeasure")
    for code, name in UOMS:
        UnitOfMeasure.objects.get_or_create(code=code, defaults={"name": name})

    Category = apps.get_model("supplychain", "Category")
    for name in CATEGORIES:
        Category.objects.get_or_create(name=name)


def reverse_seed_reference_data(apps, schema_editor):
    UnitOfMeasure = apps.get_model("supplychain", "UnitOfMeasure")
    UnitOfMeasure.objects.filter(code__in=[code for code, _ in UOMS]).delete()

    Category = apps.get_model("supplychain", "Category")
    Category.objects.filter(name__in=CATEGORIES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("supplychain", "0050_receiving_workflow_history"),
    ]

    operations = [
        migrations.RunPython(seed_reference_data, reverse_seed_reference_data),
    ]
