# Generated by Django 2.1.14 on 2019-11-19 09:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djautotask', '0022_merge_20191031_1620'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='duration',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
