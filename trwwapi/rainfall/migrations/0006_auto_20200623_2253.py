# Generated by Django 3.0.7 on 2020-06-24 02:53

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rainfall', '0005_auto_20200623_1437'),
    ]

    operations = [
        migrations.CreateModel(
            name='RainfallGauge',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('web_id', models.IntegerField()),
                ('ext_id', models.CharField(max_length=10)),
                ('nws_des', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('address', models.TextField()),
                ('ant_elev', models.FloatField()),
                ('elev_ft', models.FloatField()),
                ('geom', django.contrib.gis.db.models.fields.PointField(srid=4326)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RainfallPixel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pixel_id', models.CharField(max_length=12)),
                ('geom', django.contrib.gis.db.models.fields.PolygonField(srid=4326)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AlterModelOptions(
            name='garrobservation',
            options={'ordering': ['-timestamp']},
        ),
        migrations.AlterModelOptions(
            name='gaugeobservation',
            options={'ordering': ['-timestamp']},
        ),
        migrations.AlterModelOptions(
            name='rtrrobservation',
            options={'ordering': ['-timestamp']},
        ),
        migrations.RemoveField(
            model_name='garrobservation',
            name='metadata',
        ),
        migrations.RemoveField(
            model_name='gaugeobservation',
            name='metadata',
        ),
        migrations.RemoveField(
            model_name='rtrrobservation',
            name='metadata',
        ),
    ]
