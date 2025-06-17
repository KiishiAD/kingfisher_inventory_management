from django.db import migrations


def create_requisition_types(apps, schema_editor):
    RequisitionType = apps.get_model('supplychain', 'RequisitionType')
    RequisitionType.objects.get_or_create(name='PURCHASE')
    RequisitionType.objects.get_or_create(name='STORE')


class Migration(migrations.Migration):
    dependencies = [
        ('supplychain', '0008_requisitiontype_remove_requisition_destination_and_more'),
    ]

    operations = [
        migrations.RunPython(create_requisition_types, migrations.RunPython.noop),
    ]
