#!/usr/bin/env python
import django

from django.conf import settings
from django.core.management import call_command

settings.configure(
    DEBUG=True,
    INSTALLED_APPS=(
        'djautotask',
    ),
)


def makemigrations():
    django.setup()
    # If a migration ever says to run makemigrations --merge, run this:
    # call_command('makemigrations', 'djautotask', '--merge')
    # (And consider adding --merge to this script.)
    call_command('makemigrations', 'djautotask')


if __name__ == '__main__':
    makemigrations()
