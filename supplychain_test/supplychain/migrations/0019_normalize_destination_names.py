from django.db import migrations

def forwards(apps, schema_editor):
    Destination = apps.get_model('supplychain', 'Destination')
    Requisition = apps.get_model('supplychain', 'Requisition')

    # Ensure target 'PURCHASE' exists (new choice)
    purchase, _ = Destination.objects.get_or_create(name='PURCHASE')

    # Move any requisitions referencing old 'SUPPLIER' rows to the PURCHASE row,
    # then remove the old supplier rows to avoid duplicate unique values.
    for old in Destination.objects.filter(name='SUPPLIER'):
        Requisition.objects.filter(destination_id=old.id).update(destination_id=purchase.id)
        old.delete()

def backwards(apps, schema_editor):
    Destination = apps.get_model('supplychain', 'Destination')
    Requisition = apps.get_model('supplychain', 'Requisition')

    # Recreate 'SUPPLIER' if missing and move requisitions from 'PURCHASE' back to it.
    supplier, _ = Destination.objects.get_or_create(name='SUPPLIER')

    for pur in Destination.objects.filter(name='PURCHASE'):
        Requisition.objects.filter(destination_id=pur.id).update(destination_id=supplier.id)
        pur.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('supplychain', '0018_alter_destination_name'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=backwards),
    ]