from django.db import migrations

def create_subcategories(apps, schema_editor):
    SubCat = apps.get_model('supplychain', 'Supplier_destination_sub_category')
    SubCat.objects.get_or_create(name='CONSUMABLES')
    SubCat.objects.get_or_create(name='SERVICES')

def remove_subcategories(apps, schema_editor):
    SubCat = apps.get_model('supplychain', 'Supplier_destination_sub_category')
    SubCat.objects.filter(name__in=['CONSUMABLES', 'SERVICES']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('supplychain', '0016_alter_destination_name'),
    ]

    operations = [
        migrations.RunPython(create_subcategories, reverse_code=remove_subcategories),
    ]