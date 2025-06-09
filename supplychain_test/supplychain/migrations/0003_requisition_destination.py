from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('supplychain', '0002_alter_invoicelineapproval_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='requisition',
            name='destination',
            field=models.CharField(
                choices=[('SUPPLIER', 'Supplier'), ('STORE', 'Store')],
                default='SUPPLIER',
                max_length=10,
            ),
        ),
    ]
