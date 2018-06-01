# Generated by Django 2.0.5 on 2018-06-01 10:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djautotask', '0017_auto_20180601_1032'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='description',
            field=models.TextField(blank=True, max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='department',
            name='name',
            field=models.TextField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='department',
            name='number',
            field=models.TextField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='department',
            name='primary_location_id',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
    ]
