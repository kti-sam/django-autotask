# Generated by Django 2.1.14 on 2019-11-27 12:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('djautotask', '0027_auto_20191125_1103'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='secondary_resources',
            field=models.ManyToManyField(related_name='secondary_resource_tasks', through='djautotask.TaskSecondaryResource', to='djautotask.Resource'),
        ),
    ]
