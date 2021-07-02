# Generated by Django 3.1.5 on 2021-01-04 21:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rainfall', '0011_auto_20200720_1548'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ReportEvent',
            new_name='RainfallEvent',
        ),
        migrations.AlterField(
            model_name='garrobservation',
            name='data',
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name='gaugeobservation',
            name='data',
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name='rtrgobservation',
            name='data',
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name='rtrrobservation',
            name='data',
            field=models.JSONField(),
        ),
    ]