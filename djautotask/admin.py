from django.contrib import admin
import datetime

from . import models


@admin.register(models.Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'title')
    search_fields = ('id', 'title')


@admin.register(models.SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'start_time', 'end_time', 'duration_or_zero', 'entity_name',
        'success', 'added', 'updated', 'deleted', 'sync_type',
    )
    list_filter = ('sync_type', 'success', 'entity_name', )

    def duration_or_zero(self, obj):
        """
        Return the duration, or just the string 0 (otherwise we get 0:00:00)
        """
        duration = obj.duration()
        if duration:
            # Get rid of the microseconds part
            duration_seconds = duration - datetime.timedelta(
                microseconds=duration.microseconds
            )
            return duration_seconds if duration_seconds else '0'
    duration_or_zero.short_description = 'Duration'
