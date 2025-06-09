from django.db import migrations, models


def forwards(apps, schema_editor):
    Destination = apps.get_model('supplychain', 'Destination')
    Requisition = apps.get_model('supplychain', 'Requisition')

    store_dest = Destination.objects.create(name='Store', dest_type='STORE')
    supplier_dest = Destination.objects.create(name='Supplier', dest_type='SUPPLIER')

    for req in Requisition.objects.all():
        if req.destination == 'STORE':
            req.destination_new_id = store_dest.id
        else:
            req.destination_new_id = supplier_dest.id
        req.save(update_fields=['destination_new'])


def backwards(apps, schema_editor):
    Requisition = apps.get_model('supplychain', 'Requisition')
    for req in Requisition.objects.all():
        if req.destination and req.destination.dest_type == 'STORE':
            req.destination = 'STORE'
        else:
            req.destination = 'SUPPLIER'
        req.save(update_fields=['destination'])
    Destination = apps.get_model('supplychain', 'Destination')
    Destination.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('supplychain', '0003_requisition_destination'),
    ]

    operations = [
        migrations.CreateModel(
            name='Destination',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=200)),
                ('dest_type', models.CharField(choices=[('SUPPLIER', 'Supplier'), ('STORE', 'Store')], max_length=10)),
                ('supplier', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='destinations', to='supplychain.supplier')),
            ],
            options={'abstract': False},
        ),
        migrations.AddField(
            model_name='requisition',
            name='destination_new',
            field=models.ForeignKey(null=True, on_delete=models.PROTECT, related_name='+', to='supplychain.destination'),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField('requisition', 'destination'),
        migrations.RenameField('requisition', 'destination_new', 'destination'),
    ]
