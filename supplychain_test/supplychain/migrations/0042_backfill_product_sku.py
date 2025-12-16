from django.db import migrations
from django.utils.text import slugify

def forwards(apps, schema_editor):
    Product = apps.get_model("supplychain", "Product")

    for p in Product.objects.all().only("id", "name", "sku"):
        if p.sku:
            continue
        base = slugify(p.name)[:40] or "product"
        # pk suffix guarantees uniqueness
        p.sku = f"{base}-{p.id}"
        p.save(update_fields=["sku"])

class Migration(migrations.Migration):
    dependencies = [
        ("supplychain", "0041_product_sku"),  # adjust to your actual previous migration
    ]
    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
