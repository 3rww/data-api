# Generated by Django 3.0.7 on 2020-06-23 18:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rainfall', '0004_auto_20200619_1404'),
    ]

    operations = [
        migrations.AlterField(
            model_name='garrobservation',
            name='timestamp',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='gaugeobservation',
            name='timestamp',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='rtrrobservation',
            name='timestamp',
            field=models.DateTimeField(db_index=True),
        ),
    ]
