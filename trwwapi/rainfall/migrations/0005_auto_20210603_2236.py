# Generated by Django 3.2.3 on 2021-06-04 02:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rainfall', '0004_auto_20210603_0910'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='garr5record',
            options={'managed': False, 'ordering': ['-ts', 'sid']},
        ),
        migrations.AlterModelOptions(
            name='garrrecord',
            options={'managed': False, 'ordering': ['-ts', 'sid']},
        ),
        migrations.AlterModelOptions(
            name='gaugerecord',
            options={'managed': False, 'ordering': ['-ts', 'sid']},
        ),
        migrations.AlterModelOptions(
            name='rtrg5record',
            options={'managed': False, 'ordering': ['-ts', 'sid']},
        ),
        migrations.AlterModelOptions(
            name='rtrgrecord',
            options={'managed': False, 'ordering': ['-ts', 'sid']},
        ),
        migrations.AlterModelOptions(
            name='rtrrrecord',
            options={'managed': False, 'ordering': ['-ts', 'sid']},
        ),
    ]
