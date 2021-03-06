import logging

from suds.client import Client
from atws.wrapper import AutotaskProcessException, AutotaskAPIException
from atws import Query, helpers, picklist
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from djautotask.utils import DjautotaskSettings

from djautotask import api, models

logger = logging.getLogger(__name__)


class InvalidObjectException(Exception):
    """
    If for any reason an object can't be created (for example, it references
    an unknown foreign object, or is missing a required field), raise this
    so that the synchronizer can catch it and continue with other records.
    """
    pass


def log_sync_job(f):
    def wrapper(*args, **kwargs):
        sync_instance = args[0]
        created_count = updated_count = deleted_count = 0
        sync_job = models.SyncJob()
        sync_job.start_time = timezone.now()
        if sync_instance.full:
            sync_job.sync_type = 'full'
        else:
            sync_job.sync_type = 'partial'

        try:
            created_count, updated_count, deleted_count = f(*args, **kwargs)
            sync_job.success = True
        except AutotaskProcessException as e:
            sync_job.message = api.parse_autotaskprocessexception(e)
            sync_job.success = False
            raise
        except AutotaskAPIException as e:
            sync_job.message = api.parse_autotaskapiexception(e)
            sync_job.success = False
            raise
        except Exception as e:
            sync_job.message = str(e.args[0])
            sync_job.success = False
            raise
        finally:
            sync_job.end_time = timezone.now()
            sync_job.entity_name = sync_instance.model_class.__name__
            sync_job.added = created_count
            sync_job.updated = updated_count
            sync_job.deleted = deleted_count
            sync_job.save()

        return created_count, updated_count, deleted_count

    return wrapper


class SyncResults:
    """Track results of a sync job."""

    def __init__(self):
        self.created_count = 0
        self.updated_count = 0
        self.deleted_count = 0
        self.synced_ids = set()


class Synchronizer:
    lookup_key = 'id'
    db_lookup_key = lookup_key
    last_updated_field = None

    def __init__(self, full=False, *args, **kwargs):
        self.full = full
        self.at_api_client = None

    def set_relations(self, instance, object_data):
        for object_field, value in self.related_meta.items():
            model_class, field_name = value
            self._assign_relation(
                instance,
                object_data,
                object_field,
                model_class,
                field_name
            )

    @staticmethod
    def _assign_null_relation(instance, model_field):
        """
        Set the FK to null, but handle issues like the FK being non-null.
        """
        try:
            setattr(instance, model_field, None)
        except ValueError:
            # The model_field may have been non-null.
            raise InvalidObjectException(
                "Unable to set field {} on {} to null, as it's required.".
                format(model_field, instance)
            )

    def _assign_relation(self, instance, object_data,
                         object_field, model_class, field_name):

        relation_id = object_data.get(object_field)
        if relation_id is None:
            self._assign_null_relation(instance, field_name)
            return

        try:
            related_instance = model_class.objects.get(pk=relation_id)
            setattr(instance, field_name, related_instance)
        except model_class.DoesNotExist:
            logger.warning(
                'Failed to find {} {} for {} {}.'.format(
                    object_field, relation_id, type(instance), instance.id
                )
            )

    def _instance_ids(self, filter_params=None):
        if not filter_params:
            ids = self.model_class.objects.all().order_by(self.db_lookup_key)\
                .values_list('id', flat=True)
        else:
            ids = self.model_class.objects.filter(filter_params)\
                .order_by(self.db_lookup_key)\
                .values_list('id', flat=True)
        return set(ids)

    def build_base_query(self, sync_job_qset):
        query = Query(self.model_class.__name__)

        if sync_job_qset.exists() and self.last_updated_field \
                and not self.full:

            last_sync_job_time = sync_job_qset.last().start_time
            query.WHERE(self.last_updated_field,
                        query.GreaterThanorEquals, last_sync_job_time)
        else:
            query.WHERE('id', query.GreaterThanorEquals, 0)

        return query

    def get(self, results):
        """
        Fetch records from the API. ATWS automatically makes multiple separate
        queries if the request is over 500 records.
        """
        sync_job_qset = models.SyncJob.objects.filter(
            entity_name=self.model_class.__name__
        )
        query = self.build_base_query(sync_job_qset)

        # Apply extra conditions if they exist, else nothing happens
        self._get_query_conditions(query)

        logger.info(
            'Fetching {} records.'.format(self.model_class)
        )
        self.fetch_records(query, results)

        return results

    def fetch_records(self, query, results):
        for record in self.at_api_client.query(query):
            self.persist_record(record, results)

    def persist_record(self, record, results):
        """Persist each record to the DB."""
        try:
            with transaction.atomic():
                _, created = self.update_or_create_instance(record)
            if created:
                results.created_count += 1
            else:
                results.updated_count += 1
        except InvalidObjectException as e:
            logger.warning('{}'.format(e))

        results.synced_ids.add(int(record[self.lookup_key]))

        return results

    def update_or_create_instance(self, record):
        """Creates and returns an instance if it does not already exist."""
        created = False
        api_instance = Client.dict(record)

        try:
            instance_pk = api_instance[self.lookup_key]
            instance = self.model_class.objects.get(pk=instance_pk)
        except self.model_class.DoesNotExist:
            instance = self.model_class()
            created = True

        try:
            self._assign_field_data(instance, api_instance)
            instance.save()
        except IntegrityError as e:
            msg = "IntegrityError while attempting to create {}." \
                  " Error: {}".format(self.model_class, e)
            logger.error(msg)
            raise InvalidObjectException(msg)

        logger.info(
            '{}: {} {}'.format(
                'Created' if created else 'Updated',
                self.model_class.__name__,
                instance
            )
        )

        return instance, created

    def prune_stale_records(self, initial_ids, synced_ids):
        """
        Delete records that existed when sync started but were
        not seen as we iterated through all records from the API.
        """
        stale_ids = initial_ids - synced_ids
        deleted_count = 0
        if stale_ids:
            delete_qset = self.model_class.objects.filter(pk__in=stale_ids)
            deleted_count = delete_qset.count()

            logger.info(
                'Removing {} stale records for model: {}'.format(
                    len(stale_ids), self.model_class,
                )
            )
            delete_qset.delete()

        return deleted_count

    @log_sync_job
    def sync(self):
        results = SyncResults()
        self.at_api_client = api.init_api_connection()

        # Set of IDs of all records prior
        # to sync, to find stale records for deletion.
        results = self.get(results)

        if self.full:
            initial_ids = self._instance_ids()
            results.deleted_count = self.prune_stale_records(
                initial_ids, results.synced_ids
            )

        return \
            results.created_count, results.updated_count, results.deleted_count

    def _get_query_conditions(self, query):
        pass


class PicklistSynchronizer(Synchronizer):
    lookup_key = 'Value'

    @log_sync_job
    def sync(self):
        """
        Fetch picklist for a field from the API and persist in the database.
        """
        results = SyncResults()
        picklist_objects = None
        self.at_api_client = api.init_api_connection()

        field_info = \
            helpers.get_field_info(self.at_api_client, self.entity_type)

        try:
            field_picklist = \
                picklist.get_field_picklist(self.picklist_field, field_info)
            picklist_objects = field_picklist.PicklistValues[0]

        except KeyError as e:
            logger.warning(
                'Failed to find {} picklist field. {}'.format(
                    self.picklist_field, e
                )
            )

        if picklist_objects:
            logger.info(
                'Fetching {} records.'.format(self.model_class)
            )
            for record in picklist_objects:
                self.persist_record(record, results)

        if self.full:
            initial_ids = self._instance_ids()
            results.deleted_count = self.prune_stale_records(
                initial_ids, results.synced_ids
            )

        return \
            results.created_count, results.updated_count, results.deleted_count

    def _assign_field_data(self, instance, object_data):

        instance.id = object_data.get('Value')
        instance.label = object_data.get('Label')
        instance.is_default_value = object_data.get('IsDefaultValue')
        instance.sort_order = object_data.get('SortOrder')
        instance.is_active = object_data.get('IsActive')
        instance.is_system = object_data.get('IsSystem')

        return instance


class QueryConditionMixin:

    def _get_query_conditions(self, query):
        # Don't sync the 'Complete' status for tickets and tasks.
        # Most if not all tickets/tasks end up here and stay here forever
        # or until deleted. This would cause ticket/task syncs to take a
        # very long time. Instead only get completed tickets X number of
        # hours in the past, defined in the settings.
        request_settings = DjautotaskSettings().get_settings()
        query.open_bracket('AND')
        query.WHERE(
            'Status',
            query.NotEqual,
            self.at_api_client.picklist['Ticket']['Status']['Complete']
        )
        query.open_bracket('OR')
        query.WHERE(
            self.completed_date_field,
            query.GreaterThan,
            (timezone.now() - timezone.timedelta(
                hours=request_settings.get('keep_completed_hours')
            )).isoformat()
        )
        query.close_bracket()
        query.close_bracket()
        return query


class BatchQueryMixin:
    """
    Fetch records from the API only fetching records if the related model(s)
    are already in the database.
    """

    def __init__(self, *args, **kwargs):
        settings = DjautotaskSettings().get_settings()
        self.batch_size = settings.get('batch_query_size')
        super().__init__(*args, **kwargs)

    def build_batch_queries(self, sync_job_qset):
        raise NotImplementedError

    def get(self, results):

        sync_job_qset = models.SyncJob.objects.filter(
            entity_name=self.model_class.__name__
        )
        object_queries = self.build_batch_queries(sync_job_qset)

        logger.info(
            'Fetching {} records.'.format(self.model_class)
        )
        for query in object_queries:
            # Apply extra conditions if they exist, and then run the query.
            self._get_query_conditions(query)
            self.fetch_records(query, results)

        return results

    def _build_fk_batch(
            self, model_class, object_id_field, sync_job_qset):
        """
        Generic batching method for batching based off of the fk relation of
        an object currently present in the local DB.
        """

        queries = []
        object_ids = list(model_class.objects.order_by(self.db_lookup_key)
                          .values_list('id', flat=True))

        while object_ids:
            query = self.build_base_query(sync_job_qset)
            query.open_bracket('AND')

            batch = object_ids[:self.batch_size]
            del object_ids[:self.batch_size]

            # Create queries from batches of records
            for object_id in batch:
                query.OR(object_id_field, query.Equals, object_id)

            query.close_bracket()
            queries.append(query)

        return queries


class TicketSynchronizer(QueryConditionMixin, Synchronizer):
    model_class = models.Ticket
    last_updated_field = 'LastActivityDate'
    completed_date_field = 'CompletedDate'

    related_meta = {
        'Status': (models.Status, 'status'),
        'AssignedResourceID': (models.Resource, 'assigned_resource'),
        'Priority': (models.Priority, 'priority'),
        'QueueID': (models.Queue, 'queue'),
        'AccountID': (models.Account, 'account'),
        'ProjectID': (models.Project, 'project'),
        'TicketCategory': (models.TicketCategory, 'category'),
        'TicketType': (models.TicketType, 'type'),
        'Source': (models.Source, 'source'),
        'IssueType': (models.IssueType, 'issue_type'),
        'SubIssueType': (models.SubIssueType, 'sub_issue_type'),
        'AssignedResourceRoleID': (models.Role, 'assigned_resource_role'),
        'AllocationCodeID': (models.AllocationCode, 'allocation_code'),
    }

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.title = object_data['Title']

        instance.ticket_number = object_data.get('TicketNumber')
        instance.completed_date = object_data.get('CompletedDate')
        instance.create_date = object_data.get('CreateDate')
        instance.description = object_data.get('Description')
        instance.due_date_time = object_data.get('DueDateTime')
        instance.estimated_hours = object_data.get('EstimatedHours')
        instance.last_activity_date = object_data.get('LastActivityDate')

        self.set_relations(instance, object_data)
        return instance

    def fetch_sync_by_id(self, instance_id):
        self.at_api_client = api.init_api_connection()
        query = Query(self.model_class.__name__)
        query.WHERE('id', query.Equals, instance_id)
        ticket = self.at_api_client.query(query).fetch_one()
        instance, _ = self.update_or_create_instance(ticket)
        return instance


class TicketPicklistSynchronizer(PicklistSynchronizer):
    entity_type = 'Ticket'


class StatusSynchronizer(TicketPicklistSynchronizer):
    model_class = models.Status
    picklist_field = 'Status'


class PrioritySynchronizer(TicketPicklistSynchronizer):
    model_class = models.Priority
    picklist_field = 'Priority'


class QueueSynchronizer(TicketPicklistSynchronizer):
    model_class = models.Queue
    picklist_field = 'QueueID'


class SourceSynchronizer(TicketPicklistSynchronizer):
    model_class = models.Source
    picklist_field = 'Source'


class IssueTypeSynchronizer(TicketPicklistSynchronizer):
    model_class = models.IssueType
    picklist_field = 'IssueType'


class SubIssueTypeSynchronizer(TicketPicklistSynchronizer):
    model_class = models.SubIssueType
    picklist_field = 'SubIssueType'

    related_meta = {
        'parentValue': (models.IssueType, 'parent_value'),
    }

    def _assign_field_data(self, instance, object_data):

        self.set_relations(instance, object_data)
        super()._assign_field_data(instance, object_data)

        return instance


class TicketTypeSynchronizer(TicketPicklistSynchronizer):
    model_class = models.TicketType
    picklist_field = 'TicketType'


class ProjectStatusSynchronizer(PicklistSynchronizer):
    model_class = models.ProjectStatus
    entity_type = 'Project'
    picklist_field = 'Status'


class ProjectTypeSynchronizer(PicklistSynchronizer):
    model_class = models.ProjectType
    entity_type = 'Project'
    picklist_field = 'Type'


class DisplayColorSynchronizer(PicklistSynchronizer):
    model_class = models.DisplayColor
    entity_type = 'TicketCategory'
    picklist_field = 'DisplayColorRGB'


class LicenseTypeSynchronizer(PicklistSynchronizer):
    model_class = models.LicenseType
    entity_type = 'Resource'
    picklist_field = 'LicenseType'


class NoteTypeSynchronizer(PicklistSynchronizer):
    # We are using ticket note to get the picklist, but like Ticket Status
    # and Task Status both use one status type, so do Ticket and Task notes
    model_class = models.NoteType
    entity_type = 'TicketNote'
    picklist_field = 'NoteType'


class TaskTypeLinkSynchronizer(PicklistSynchronizer):
    model_class = models.TaskTypeLink
    entity_type = 'TimeEntry'
    picklist_field = 'Type'


class UseTypeSynchronizer(PicklistSynchronizer):
    model_class = models.UseType
    entity_type = 'AllocationCode'
    picklist_field = 'UseType'


class ResourceSynchronizer(Synchronizer):
    model_class = models.Resource
    last_updated_field = None

    related_meta = {
        'LicenseType': (models.LicenseType, 'license_type'),
        'DefaultServiceDeskRoleID': (models.Role, 'default_service_desk_role'),
    }

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.user_name = object_data.get('UserName')
        instance.email = object_data.get('Email')
        instance.first_name = object_data.get('FirstName')
        instance.last_name = object_data.get('LastName')
        instance.active = object_data.get('Active')

        self.set_relations(instance, object_data)

        return instance


class TicketCategorySynchronizer(Synchronizer):
    model_class = models.TicketCategory
    last_updated_field = None

    related_meta = {
        'DisplayColorRGB': (models.DisplayColor, 'display_color')
    }

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.name = object_data.get('Name')
        instance.active = object_data.get('Active')

        self.set_relations(instance, object_data)

        return instance


class TicketSecondaryResourceSynchronizer(Synchronizer):
    model_class = models.TicketSecondaryResource
    last_updated_field = None

    related_meta = {
        'ResourceID': (models.Resource, 'resource'),
        'TicketID': (models.Ticket, 'ticket'),
    }

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        self.set_relations(instance, object_data)

        return instance


class AccountSynchronizer(Synchronizer):
    model_class = models.Account
    last_updated_field = 'LastActivityDate'

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.name = object_data.get('AccountName')
        instance.number = object_data.get('AccountNumber')
        instance.active = object_data.get('Active')
        instance.last_activity_date = object_data.get('LastActivityDate')

        return instance


class FilterProjectStatusMixin:

    def fetch_records(self, query, results):
        active_object_ids = self.get_active_ids()

        for record in self.at_api_client.query(query):

            object_id = getattr(record, self.object_filter_field)
            if active_object_ids and object_id:

                if object_id not in active_object_ids:
                    logger.info(
                        'Project with ID: {} is set to an inactive status. '
                        'Skipping this {}.'.format(
                            object_id, self.model_class.__name__)
                    )
                    continue

            self.persist_record(record, results)


class ProjectSynchronizer(FilterProjectStatusMixin, Synchronizer):
    model_class = models.Project
    last_updated_field = 'LastActivityDateTime'
    object_filter_field = 'Status'

    related_meta = {
        'ProjectLeadResourceID': (models.Resource, 'project_lead_resource'),
        'AccountID': (models.Account, 'account'),
        'Status': (models.ProjectStatus, 'status'),
        'Type': (models.ProjectType, 'type'),
    }

    def get_active_ids(self):
        active_project_statuses = models.ProjectStatus.objects.exclude(
            is_active=False).values_list('id', flat=True).order_by(
            self.db_lookup_key)

        return active_project_statuses

    def _get_query_conditions(self, query):

        try:
            status = models.ProjectStatus.objects.get(
                label=models.ProjectStatus.COMPLETE)
            query.open_bracket('AND')
            query.WHERE('Status', query.NotEqual, status.id)
            query.close_bracket()

        except models.ProjectStatus.DoesNotExist as e:
            logger.warning(
                'Failed to find project status - {}. {}'.format(
                    models.ProjectStatus.COMPLETE, e)
            )

        return query

    def _assign_field_data(self, instance, object_data):

        completed_date = object_data.get('CompletedDateTime')
        end_date = object_data.get('EndDateTime')
        start_date = object_data.get('StartDateTime')

        instance.id = object_data['id']
        instance.name = object_data.get('ProjectName')
        instance.number = object_data.get('ProjectNumber')
        instance.description = object_data.get('Description')
        instance.actual_hours = object_data.get('ActualHours')
        instance.completed_percentage = object_data.get('CompletedPercentage')
        instance.duration = object_data.get('Duration')
        instance.estimated_time = object_data.get('EstimatedTime')
        instance.last_activity_date_time = \
            object_data.get('LastActivityDateTime')

        if instance.description:
            # Autotask docs say the max description length is 2000
            # characters but we've seen descriptions that are longer than that.
            # So truncate the field to 2000 characters just in case.
            instance.description = instance.description[:2000]

        if completed_date:
            instance.completed_date = completed_date.date()

        if end_date:
            instance.end_date = end_date.date()

        if start_date:
            instance.start_date = start_date.date()

        self.set_relations(instance, object_data)

        return instance


class PhaseSynchronizer(Synchronizer):
    model_class = models.Phase
    last_updated_field = 'LastActivityDateTime'

    related_meta = {
        'ProjectID': (models.Project, 'project'),
        'ParentPhaseID': (models.Phase, 'parent_phase'),
    }

    def _assign_field_data(self, instance, object_data):

        instance.id = object_data['id']
        instance.title = object_data.get('Title')
        instance.number = object_data.get('PhaseNumber')
        instance.description = object_data.get('Description')
        instance.start_date = object_data.get('StartDate')
        instance.due_date = object_data.get('DueDate')
        instance.estimated_hours = object_data.get('EstimatedHours')
        instance.last_activity_date = object_data.get('LastActivityDateTime')

        self.set_relations(instance, object_data)

        return instance


class TaskSynchronizer(QueryConditionMixin,
                       FilterProjectStatusMixin, Synchronizer):
    model_class = models.Task
    last_updated_field = 'LastActivityDateTime'
    object_filter_field = 'ProjectID'
    completed_date_field = 'CompletedDateTime'

    related_meta = {
        'AssignedResourceID': (models.Resource, 'assigned_resource'),
        'ProjectID': (models.Project, 'project'),
        'PhaseID': (models.Phase, 'phase'),
        'Status': (models.Status, 'status'),
        'PriorityLabel': (models.Priority, 'priority'),
        'AssignedResourceRoleID': (models.Role, 'assigned_resource_role'),
        'AllocationCodeID': (models.AllocationCode, 'allocation_code'),
    }

    def get_active_ids(self):
        active_projects = models.Project.objects.exclude(
            Q(status__is_active=False) |
            Q(status__label=models.ProjectStatus.COMPLETE)
        ).values_list('id', flat=True).order_by(self.db_lookup_key)

        return active_projects

    def _assign_field_data(self, instance, object_data):

        instance.id = object_data['id']
        instance.title = object_data.get('Title')
        instance.number = object_data.get('TaskNumber')
        instance.description = object_data.get('Description')
        instance.completed_date = object_data.get('CompletedDateTime')
        instance.create_date = object_data.get('CreateDateTime')
        instance.start_date = object_data.get('StartDateTime')
        instance.end_date = object_data.get('EndDateTime')
        instance.estimated_hours = object_data.get('EstimatedHours')
        instance.remaining_hours = object_data.get('RemainingHours')
        instance.last_activity_date = object_data.get('LastActivityDateTime')

        self.set_relations(instance, object_data)

        return instance


class TaskSecondaryResourceSynchronizer(Synchronizer):
    model_class = models.TaskSecondaryResource
    last_updated_field = None

    related_meta = {
        'ResourceID': (models.Resource, 'resource'),
        'TaskID': (models.Task, 'task'),
    }

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']

        self.set_relations(instance, object_data)

        return instance


class NoteSynchronizer(Synchronizer):
    def _assign_field_data(self, instance, object_data):

        instance.id = object_data['id']
        instance.title = object_data.get('Title')
        instance.description = object_data.get('Description')
        instance.create_date_time = object_data.get('CreateDateTime')
        instance.last_activity_date = object_data.get('LastActivityDate')

        if instance.description:
            # Autotask docs say the max description length is 3200
            # characters but we've seen descriptions that are longer than that.
            # So truncate the field to 3200 characters just in case.
            instance.description = instance.description[:3200]

        self.set_relations(instance, object_data)

        return instance

    def _get_query_conditions(self, query):
        query.open_bracket('AND')
        query.WHERE(
            'NoteType',
            query.NotEqual,
            self.at_api_client.picklist
            ['TicketNote']['NoteType']['Workflow Rule Note - Task']
        )
        query.close_bracket()
        return query


class TicketNoteSynchronizer(
        BatchQueryMixin, NoteSynchronizer):

    model_class = models.TicketNote
    last_updated_field = 'LastActivityDate'

    related_meta = {
        'NoteType': (models.NoteType, 'note_type'),
        'CreatorResourceID': (models.Resource, 'creator_resource'),
        'TicketID': (models.Ticket, 'ticket'),
    }

    def build_batch_queries(self, sync_job_qset):
        batch_query_list = self._build_fk_batch(
            models.Ticket, 'TicketID', sync_job_qset)

        return batch_query_list


class TaskNoteSynchronizer(
        BatchQueryMixin, NoteSynchronizer):

    model_class = models.TaskNote
    last_updated_field = 'LastActivityDate'

    related_meta = {
        'NoteType': (models.NoteType, 'note_type'),
        'CreatorResourceID': (models.Resource, 'creator_resource'),
        'TaskID': (models.Task, 'task'),
    }

    def build_batch_queries(self, sync_job_qset):
        batch_query_list = self._build_fk_batch(
            models.Task, 'TaskID', sync_job_qset)

        return batch_query_list


class TimeEntrySynchronizer(BatchQueryMixin, Synchronizer):
    model_class = models.TimeEntry
    last_updated_field = 'LastModifiedDateTime'

    related_meta = {
        'ResourceID': (models.Resource, 'resource'),
        'TicketID': (models.Ticket, 'ticket'),
        'TaskID': (models.Task, 'task'),
        'Type': (models.TaskTypeLink, 'type'),
        'AllocationCodeID': (models.AllocationCode, 'allocation_code'),
        'RoleID': (models.Role, 'role'),
    }

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.date_worked = object_data.get('DateWorked')
        instance.start_date_time = object_data.get('StartDateTime')
        instance.end_date_time = object_data.get('EndDateTime')
        instance.summary_notes = object_data.get('SummaryNotes')
        instance.internal_notes = object_data.get('InternalNotes')
        instance.non_billable = object_data.get('NonBillable')
        instance.hours_worked = object_data.get('HoursWorked')
        instance.hours_to_bill = object_data.get('HoursToBill')
        instance.offset_hours = object_data.get('OffsetHours')

        self.set_relations(instance, object_data)

        return instance

    def build_batch_queries(self, sync_job_qset):
        batch_query_list = []

        batch_query_list.extend(
            self._build_fk_batch(
                models.Ticket, 'TicketID', sync_job_qset))
        batch_query_list.extend(
            self._build_fk_batch(
                models.Task, 'TaskID', sync_job_qset))

        return batch_query_list

    def create_new_entry(self, entry_body):
        """
        Accepts a time entry dictionary which is then used to create a
        time entry Autotask object and created via the API.
        """
        instance = api.create_object('TimeEntry', entry_body)

        return self.update_or_create_instance(instance)


class AllocationCodeSynchronizer(Synchronizer):
    model_class = models.AllocationCode
    last_updated_field = None

    related_meta = {
        'UseType': (models.UseType, 'use_type')
    }

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.name = object_data.get('Name')
        instance.description = object_data.get('Description')
        instance.active = object_data.get('Active')

        self.set_relations(instance, object_data)

        return instance


class RoleSynchronizer(Synchronizer):
    model_class = models.Role

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.active = object_data.get('Active')
        instance.name = object_data.get('Name')
        instance.description = object_data.get('Description')
        instance.hourly_factor = object_data.get('HourlyFactor')
        instance.hourly_rate = object_data.get('HourlyRate')
        instance.role_type = object_data.get('RoleType')
        instance.system_role = object_data.get('SystemRole')


class DepartmentSynchronizer(Synchronizer):
    model_class = models.Department

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.name = object_data.get('Name')
        instance.description = object_data.get('Description')
        instance.number = object_data.get('Number')


class ResourceRoleDepartmentSynchronizer(Synchronizer):
    model_class = models.ResourceRoleDepartment

    related_meta = {
        'ResourceID': (models.Resource, 'resource'),
        'RoleID': (models.Role, 'role'),
        'DepartmentID': (models.Department, 'department'),
    }

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.active = object_data.get('Active')
        instance.default = object_data.get('Default')
        instance.department_lead = object_data.get('DepartmentLead')

        self.set_relations(instance, object_data)

        return instance


class ResourceServiceDeskRoleSynchronizer(Synchronizer):
    model_class = models.ResourceServiceDeskRole

    related_meta = {
        'ResourceID': (models.Resource, 'resource'),
        'RoleID': (models.Role, 'role'),
    }

    def _assign_field_data(self, instance, object_data):
        instance.id = object_data['id']
        instance.active = object_data.get('Active')
        instance.default = object_data.get('Default')

        self.set_relations(instance, object_data)

        return instance
