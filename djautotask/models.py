from django.db import models
from django.db.models import Q
from django_extensions.db.models import TimeStampedModel
from django.utils import timezone
from djautotask import api

OFFSET_TIMEZONE = 'America/New_York'


class SyncJob(models.Model):
    start_time = models.DateTimeField(null=False)
    end_time = models.DateTimeField(blank=True, null=True)
    entity_name = models.CharField(max_length=100)
    added = models.PositiveIntegerField(null=True)
    updated = models.PositiveIntegerField(null=True)
    deleted = models.PositiveIntegerField(null=True)
    success = models.NullBooleanField()
    message = models.TextField(blank=True, null=True)
    sync_type = models.CharField(max_length=32, default='full')

    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time


class ResourceAssignableModel:

    def update_resource(self):
        """
        Send assigned resource updates to Autotask
        """
        return api.update_assigned_resource(
            self, self.assigned_resource, self.assigned_resource_role)


class Ticket(TimeStampedModel, ResourceAssignableModel):
    ticket_number = models.CharField(blank=True, null=True, max_length=50)
    completed_date = models.DateTimeField(blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True, null=True, max_length=8000)
    due_date_time = models.DateTimeField(null=False)
    estimated_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
    last_activity_date = models.DateTimeField(blank=True, null=True)
    title = models.CharField(blank=True, null=True, max_length=255)

    status = models.ForeignKey(
        'Status', blank=True, null=True, on_delete=models.SET_NULL
    )
    priority = models.ForeignKey(
        'Priority', blank=True, null=True, on_delete=models.SET_NULL
    )
    assigned_resource = models.ForeignKey(
        'Resource', blank=True, null=True, on_delete=models.SET_NULL
    )
    secondary_resources = models.ManyToManyField(
        'Resource', through='TicketSecondaryResource',
        related_name='secondary_resource_tickets'
    )
    queue = models.ForeignKey(
        'Queue', blank=True, null=True, on_delete=models.SET_NULL
    )
    account = models.ForeignKey(
        'Account', blank=True, null=True, on_delete=models.SET_NULL
    )
    project = models.ForeignKey(
        'Project', blank=True, null=True, on_delete=models.SET_NULL
    )
    category = models.ForeignKey(
        'TicketCategory', blank=True, null=True, on_delete=models.SET_NULL
    )
    source = models.ForeignKey(
        'Source', blank=True, null=True, on_delete=models.SET_NULL
    )
    issue_type = models.ForeignKey(
        'IssueType', blank=True, null=True, on_delete=models.SET_NULL
    )
    sub_issue_type = models.ForeignKey(
        'SubIssueType', blank=True, null=True, on_delete=models.SET_NULL
    )
    type = models.ForeignKey(
        'TicketType', blank=True, null=True, on_delete=models.SET_NULL
    )
    assigned_resource_role = models.ForeignKey(
        'Role', blank=True, null=True, on_delete=models.SET_NULL
    )
    allocation_code = models.ForeignKey(
        'AllocationCode', null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = 'Ticket'

    def __str__(self):
        return '{}-{}'.format(self.id, self.title)

    def save(self, *args, **kwargs):
        """
        Save the object.

        If update_at as a kwarg is True, then update Autotask with changes.
        """

        update_at = kwargs.pop('update_at', False)
        super().save(*args, **kwargs)
        if update_at:
            self.update_at()

    def update_at(self):
        fields_to_update = {
            'Status': self.status.id
        }
        return api.update_object('Ticket', self.id, fields_to_update)


class AvailablePicklistManager(models.Manager):
    """ Return only active Picklist objects. """

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class Picklist(TimeStampedModel):
    label = models.CharField(blank=True, null=True, max_length=50)
    is_default_value = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)

    objects = models.Manager()
    available_objects = AvailablePicklistManager()

    class Meta:
        ordering = ('label',)
        abstract = True

    def __str__(self):
        return self.label if self.label else self.pk


class Status(Picklist):
    pass

    class Meta:
        ordering = ('label',)
        verbose_name_plural = 'Statuses'


class Priority(Picklist):
    pass

    class Meta:
        ordering = ('sort_order',)
        verbose_name_plural = 'Priorities'


class Queue(Picklist):
    pass

    class Meta:
        ordering = ('label',)
        verbose_name_plural = 'Queues'


class ProjectStatus(Picklist):
    COMPLETE = 'Complete'

    class Meta:
        ordering = ('label',)
        verbose_name_plural = 'Project statuses'


class DisplayColor(Picklist):
    pass

    class Meta:
        ordering = ('label',)
        verbose_name_plural = 'Display colors'


class ProjectType(Picklist):
    TEMPLATE = 'Template'
    BASELINE = 'Baseline'


class Source(Picklist):
    pass


class IssueType(Picklist):
    pass


class TicketType(Picklist):
    pass


class SubIssueType(Picklist):
    parent_value = models.ForeignKey(
        'IssueType', blank=True, null=True, on_delete=models.CASCADE
    )

    def __str__(self):
        return "{}/{}".format(self.parent_value, self.label) \
            if self.parent_value else self.label


class LicenseType(Picklist):
    pass


class NoteType(Picklist):
    pass


class TaskTypeLink(Picklist):
    pass


class UseType(Picklist):
    pass


class RegularResourceManager(models.Manager):
    API_USER_LICENSE_ID = 7

    def get_queryset(self):
        return super().get_queryset().exclude(
            license_type=self.API_USER_LICENSE_ID)


class Resource(TimeStampedModel):
    user_name = models.CharField(max_length=32)
    email = models.CharField(max_length=50)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    active = models.BooleanField(default=False)
    license_type = models.ForeignKey(
        'LicenseType', null=True, on_delete=models.SET_NULL
    )
    default_service_desk_role = models.ForeignKey(
        'Role', null=True, blank=True, on_delete=models.SET_NULL
    )
    objects = models.Manager()
    regular_objects = RegularResourceManager()

    class Meta:
        ordering = ('first_name', 'last_name')

    def __str__(self):
        return '{} {}'.format(self.first_name, self.last_name)


class TicketCategory(TimeStampedModel):
    name = models.CharField(max_length=30)
    active = models.BooleanField(default=False)
    display_color = models.ForeignKey(
        'DisplayColor', null=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'Ticket categories'

    def __str__(self):
        return self.name


class TicketSecondaryResource(TimeStampedModel):
    resource = models.ForeignKey(
        'Resource', blank=True, null=True, on_delete=models.SET_NULL
    )
    ticket = models.ForeignKey(
        'Ticket', blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return '{} {}'.format(self.resource, self.ticket)


class TicketNote(TimeStampedModel):
    title = models.CharField(max_length=250)
    description = models.CharField(max_length=3200)
    create_date_time = models.DateTimeField(blank=True, null=True)
    last_activity_date = models.DateTimeField(blank=True, null=True)

    note_type = models.ForeignKey(
        'NoteType', blank=True, null=True, on_delete=models.SET_NULL
    )
    creator_resource = models.ForeignKey(
        'Resource', blank=True, null=True, on_delete=models.SET_NULL
    )
    ticket = models.ForeignKey(
        'Ticket', blank=True, null=True, on_delete=models.SET_NULL
    )


class TaskNote(TimeStampedModel):
    title = models.CharField(max_length=250)
    description = models.CharField(max_length=3200)
    create_date_time = models.DateTimeField(blank=True, null=True)
    last_activity_date = models.DateTimeField(blank=True, null=True)

    note_type = models.ForeignKey(
        'NoteType', blank=True, null=True, on_delete=models.SET_NULL
    )
    creator_resource = models.ForeignKey(
        'Resource', blank=True, null=True, on_delete=models.SET_NULL
    )
    task = models.ForeignKey(
        'Task', blank=True, null=True, on_delete=models.SET_NULL
    )


class Account(TimeStampedModel):
    name = models.CharField(max_length=100)
    number = models.CharField(max_length=50)
    active = models.BooleanField(default=True)
    last_activity_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class AvailableProjectManager(models.Manager):
    """
    Exclude projects whose type is 'Template' or 'Baseline'. Neither of these
    types provide any use for us, so just exclude them.
    """
    def get_queryset(self):
        return super().get_queryset().exclude(
            Q(type__label=ProjectType.TEMPLATE) |
            Q(type__label=ProjectType.BASELINE)
        )


class Project(TimeStampedModel):
    name = models.CharField(max_length=100)
    number = models.CharField(null=True, max_length=50)
    description = models.CharField(max_length=2000)
    actual_hours = models.DecimalField(
        null=True, decimal_places=2, max_digits=9)
    completed_date = models.DateField(null=True)
    completed_percentage = models.PositiveSmallIntegerField(default=0)
    duration = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    estimated_time = models.DecimalField(
        null=True, decimal_places=2, max_digits=9
    )
    last_activity_date_time = models.DateTimeField(null=True)

    project_lead_resource = models.ForeignKey(
        'Resource', null=True, on_delete=models.SET_NULL
    )
    account = models.ForeignKey(
        'Account', null=True, on_delete=models.SET_NULL
    )
    status = models.ForeignKey(
        'ProjectStatus', null=True, on_delete=models.SET_NULL
    )
    type = models.ForeignKey(
        'ProjectType', null=True, on_delete=models.SET_NULL
    )

    objects = models.Manager()
    available_objects = AvailableProjectManager()

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Phase(TimeStampedModel):
    title = models.CharField(blank=True, null=True, max_length=255)
    description = models.CharField(blank=True, null=True, max_length=8000)
    start_date = models.DateTimeField(blank=True, null=True)
    # due_date is end date in autotask UI
    due_date = models.DateTimeField(blank=True, null=True)
    estimated_hours = models.PositiveIntegerField(default=0)
    number = models.CharField(blank=True, null=True, max_length=50)
    scheduled = models.BooleanField(default=False)
    last_activity_date = models.DateTimeField(blank=True, null=True)

    parent_phase = models.ForeignKey(
        'self', null=True, on_delete=models.SET_NULL
    )

    project = models.ForeignKey(
        'Project', null=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ('title',)

    def __str__(self):
        return self.title


class Task(TimeStampedModel, ResourceAssignableModel):
    title = models.CharField(blank=True, null=True, max_length=255)
    number = models.CharField(blank=True, null=True, max_length=50)
    description = models.CharField(blank=True, null=True, max_length=8000)
    completed_date = models.DateTimeField(blank=True, null=True)
    create_date = models.DateTimeField(blank=True, null=True)
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    estimated_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
    remaining_hours = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=6)
    last_activity_date = models.DateTimeField(blank=True, null=True)

    assigned_resource = models.ForeignKey(
        'Resource', null=True, on_delete=models.SET_NULL
    )
    secondary_resources = models.ManyToManyField(
        'Resource', through='TaskSecondaryResource',
        related_name='secondary_resource_tasks'
    )
    project = models.ForeignKey(
        'Project', null=True, on_delete=models.SET_NULL
    )
    priority = models.ForeignKey(
        'Priority', null=True, blank=True, on_delete=models.SET_NULL
    )
    status = models.ForeignKey(
        'Status', null=True, on_delete=models.SET_NULL
    )
    phase = models.ForeignKey(
        'Phase', null=True,
        on_delete=models.SET_NULL
    )
    allocation_code = models.ForeignKey(
        'AllocationCode', null=True, blank=True, on_delete=models.SET_NULL
    )
    assigned_resource_role = models.ForeignKey(
        'Role', blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Save the object.

        If update_at as a kwarg is True, then update Autotask with changes.
        """

        update_at = kwargs.pop('update_at', False)
        super().save(*args, **kwargs)
        if update_at:
            self.update_at()

    def update_at(self):
        fields_to_update = {
            'Status': self.status.id, 'RemainingHours': self.remaining_hours
        }
        return api.update_object('Task', self.id, fields_to_update)


class TaskSecondaryResource(TimeStampedModel):
    resource = models.ForeignKey(
        'Resource', blank=True, null=True, on_delete=models.SET_NULL
    )
    task = models.ForeignKey(
        'Task', blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return '{} {}'.format(self.resource, self.task)


class TimeEntry(TimeStampedModel):
    date_worked = models.DateTimeField(blank=True, null=True)
    start_date_time = models.DateTimeField(blank=True, null=True)
    end_date_time = models.DateTimeField(blank=True, null=True)
    summary_notes = models.TextField(blank=True, null=True, max_length=8000)
    internal_notes = models.TextField(blank=True, null=True, max_length=8000)
    non_billable = models.BooleanField(default=False)
    hours_worked = models.DecimalField(
        blank=True, null=True, decimal_places=4, max_digits=9)
    hours_to_bill = models.DecimalField(
        blank=True, null=True, decimal_places=4, max_digits=9)
    offset_hours = models.DecimalField(
        blank=True, null=True, decimal_places=4, max_digits=9)

    resource = models.ForeignKey(
        'Resource', blank=True, null=True, on_delete=models.CASCADE)
    ticket = models.ForeignKey(
        'Ticket', blank=True, null=True, on_delete=models.CASCADE)
    task = models.ForeignKey(
        'Task', blank=True, null=True, on_delete=models.CASCADE)
    type = models.ForeignKey(
        'TaskTypeLink', blank=True, null=True, on_delete=models.SET_NULL)
    allocation_code = models.ForeignKey(
        'AllocationCode', blank=True, null=True, on_delete=models.SET_NULL)
    role = models.ForeignKey(
        'Role', blank=True, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name_plural = 'Time entries'
        ordering = ('-start_date_time', 'id')

    def __str__(self):
        return str(self.id) or ''

    def get_entered_time(self):
        """
        In Autotask, tickets are required to have start and end times.
        Start and end times for project tasks can be optional.
        In the case that a task has no start or end time, use the
        date_worked field.
        """
        if self.end_date_time:
            entered_time = self.end_date_time
        else:
            # Autotask gives us date_worked as a datetime, even though the
            # time is always set to EST midnight (00:00:00).
            est_offset = timezone.localtime(
                timezone=timezone.pytz.timezone(OFFSET_TIMEZONE)).utcoffset()
            local_offset = timezone.localtime().utcoffset()

            # We want to end up with a UTC datetime that is midnight in the
            # local timezone.
            date_worked = self.date_worked + est_offset
            entered_time = date_worked - local_offset

        return entered_time


class AllocationCode(TimeStampedModel):
    name = models.CharField(blank=True, null=True, max_length=200)
    description = models.CharField(blank=True, null=True, max_length=500)
    active = models.BooleanField(default=False)

    use_type = models.ForeignKey(
        'UseType', blank=True, null=True, on_delete=models.SET_NULL
    )

    def __str__(self):
        return self.name if self.name else self.pk


class Role(models.Model):
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    description = models.CharField(blank=True, null=True, max_length=200)
    hourly_factor = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    hourly_rate = models.DecimalField(
        blank=True, null=True, decimal_places=2, max_digits=9)
    role_type = models.PositiveIntegerField(blank=True, null=True)
    system_role = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True, max_length=1000)
    number = models.CharField(blank=True, null=True, max_length=50)

    def __str__(self):
        return self.name


class ResourceRoleDepartment(models.Model):
    id = models.BigAutoField(primary_key=True, verbose_name='ID')
    active = models.BooleanField(default=True)
    default = models.BooleanField(default=False)
    department_lead = models.BooleanField(default=False)

    def __str__(self):
        return "{} - {} - {}".format(
            self.resource, self.role, self.department)

    department = models.ForeignKey(
        'Department', on_delete=models.CASCADE)
    role = models.ForeignKey(
        'Role', on_delete=models.CASCADE)
    resource = models.ForeignKey(
        'Resource', on_delete=models.CASCADE)


class ResourceServiceDeskRole(models.Model):
    active = models.BooleanField(default=True)
    default = models.BooleanField(default=False)

    def __str__(self):
        return "{} - {}".format(
            self.resource, self.role)

    role = models.ForeignKey(
        'Role', on_delete=models.CASCADE)
    resource = models.ForeignKey(
        'Resource', on_delete=models.CASCADE)
