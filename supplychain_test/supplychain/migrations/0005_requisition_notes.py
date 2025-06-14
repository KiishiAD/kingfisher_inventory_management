from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('supplychain', '0004_destination_issuancerequest_requisition_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='requisition',
            name='notes',
            field=models.TextField(blank=True),
        ),
    ]
