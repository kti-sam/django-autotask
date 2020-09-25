# Generated by Django 3.1 on 2020-09-23 09:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('djautotask', '0075_taskpredecessor'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='allocationcode',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='servicecall',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='servicecalltask',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='servicecalltaskresource',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='servicecallticket',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='servicecallticketresource',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='task',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='tasknote',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='taskpredecessor',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='tasksecondaryresource',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='ticketnote',
            options={'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='ticketsecondaryresource',
            options={'get_latest_by': 'modified'},
        ),
    ]