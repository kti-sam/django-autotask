# Generated by Django 3.1.2 on 2020-10-15 11:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('djautotask', '0080_accountphysicallocationtracker_accounttracker_accounttypetracker_allocationcodetracker_contracttrack'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='department',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='djautotask.department'),
        ),
    ]