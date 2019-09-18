from django.test import TestCase
from atws.wrapper import Wrapper
from dateutil.parser import parse

from djautotask.models import Ticket, TicketStatus, Resource, SyncJob, \
    TicketSecondaryResource, TicketPriority, Queue, Account, Project, \
    ProjectType, ProjectStatus
from djautotask import sync
from djautotask.tests import fixtures, mocks, fixture_utils


def assert_sync_job(model_class):
    qset = SyncJob.objects.filter(entity_name=model_class.__name__)
    assert qset.exists()


class TestTicketSynchronizer(TestCase):

    def setUp(self):
        super().setUp()

        mocks.init_api_connection(Wrapper)

        fixture_utils.init_ticket_statuses()
        fixture_utils.init_resources()
        fixture_utils.init_tickets()

    def _assert_sync(self, instance, object_data):
        self.assertEqual(instance.id, object_data['id'])
        self.assertEqual(instance.title, object_data['Title'])
        self.assertEqual(instance.ticket_number, object_data['TicketNumber'])
        self.assertEqual(instance.completed_date,
                         parse(object_data['CompletedDate']))
        self.assertEqual(instance.create_date,
                         parse(object_data['CreateDate']))
        self.assertEqual(instance.description, object_data['Description'])
        self.assertEqual(instance.due_date_time,
                         parse(object_data['DueDateTime']))
        self.assertEqual(instance.estimated_hours,
                         object_data['EstimatedHours'])
        self.assertEqual(instance.last_activity_date,
                         parse(object_data['LastActivityDate']))
        self.assertEqual(instance.status.value, str(object_data['Status']))
        self.assertEqual(instance.assigned_resource.id,
                         object_data['AssignedResourceID'])

    def test_sync_ticket(self):
        """
        Test to ensure ticket synchronizer saves a Ticket instance locally.
        """
        self.assertGreater(Ticket.objects.all().count(), 0)

        object_data = fixtures.API_SERVICE_TICKET
        instance = Ticket.objects.get(id=object_data['id'])

        self._assert_sync(instance, object_data)
        assert_sync_job(Ticket)

    def test_delete_stale_tickets(self):
        """
        Local ticket should be deleted if not returned during a full sync
        """
        ticket_id = fixtures.API_SERVICE_TICKET['id']
        ticket_qset = Ticket.objects.filter(id=ticket_id)
        self.assertEqual(ticket_qset.count(), 1)

        mocks.ticket_api_call([])

        synchronizer = sync.TicketSynchronizer(full=True)
        synchronizer.sync()
        self.assertEqual(ticket_qset.count(), 0)


class AbstractPicklistSynchronizer(object):

    def setUp(self):
        mocks.init_api_connection(Wrapper)

    def _assert_sync(self, instance, object_data):
        self.assertEqual(instance.value, str(object_data['Value']))
        self.assertEqual(instance.label, object_data['Label'])
        self.assertEqual(
            instance.is_default_value, object_data['IsDefaultValue'])
        self.assertEqual(instance.sort_order, object_data['SortOrder'])
        self.assertEqual(instance.parent_value, object_data['ParentValue'])
        self.assertEqual(instance.is_active, object_data['IsActive'])
        self.assertEqual(instance.is_system, object_data['IsSystem'])

    def _evaluate_test_sync(self):
        instance_dict = {}
        for item in self.fixture:
            instance_dict[str(item['Value'])] = item

        for instance in self.model_class.objects.all():
            object_data = instance_dict[instance.value]

            self._assert_sync(instance, object_data)

        assert_sync_job(self.model_class)

    def _evaluate_objects_deleted(self):
        qset = self.model_class.objects.all()
        self.assertEqual(qset.count(), len(self.fixture))

        # Ensure that the get_field_info method returns no API objects
        # so that the full sync will remove the existing objects in the DB.
        mocks.get_field_info_api_calls()

        synchronizer = self.synchronizer(full=True)
        synchronizer.sync()
        self.assertEqual(qset.count(), 0)


class TestTicketStatusSynchronizer(AbstractPicklistSynchronizer, TestCase):
    model_class = TicketStatus
    fixture = fixtures.API_TICKET_STATUS_LIST
    synchronizer = sync.TicketStatusSynchronizer

    def setUp(self):
        super().setUp()
        fixture_utils.init_ticket_statuses()

    def test_sync_ticket_status(self):
        """
        Test to ensure ticket status synchronizer saves a TicketStatus
        instance locally.
        """
        self._evaluate_test_sync()

    def test_delete_stale_ticket_statuses(self):
        """
        Test that ticket status is deleted if not returned during a full sync.
        """
        self._evaluate_objects_deleted()


class TestTicketPrioritySynchronizer(AbstractPicklistSynchronizer, TestCase):
    model_class = TicketPriority
    fixture = fixtures.API_TICKET_PRIORITY_LIST
    synchronizer = sync.TicketPrioritySynchronizer

    def setUp(self):
        super().setUp()
        fixture_utils.init_ticket_priorities()

    def test_sync_ticket_priority(self):
        self._evaluate_test_sync()

    def test_delete_stale_ticket_priorities(self):
        self._evaluate_objects_deleted()


class TestQueueSynchronizer(AbstractPicklistSynchronizer, TestCase):
    model_class = Queue
    fixture = fixtures.API_QUEUE_LIST
    synchronizer = sync.QueueSynchronizer

    def setUp(self):
        super().setUp()
        fixture_utils.init_queues()

    def test_sync_queue(self):
        self._evaluate_test_sync()

    def test_delete_stale_queue(self):
        self._evaluate_objects_deleted()


class TestProjectStatusSynchronizer(AbstractPicklistSynchronizer, TestCase):
    model_class = ProjectStatus
    fixture = fixtures.API_PROJECT_STATUS_LIST
    synchronizer = sync.ProjectStatusSynchronizer

    def setUp(self):
        super().setUp()
        fixture_utils.init_project_statuses()

    def test_sync_project_status(self):
        self._evaluate_test_sync()

    def test_delete_stale_project_status(self):
        self._evaluate_test_sync()


class TestProjectTypeSynchronizer(AbstractPicklistSynchronizer, TestCase):
    model_class = ProjectType
    fixture = fixtures.API_PROJECT_TYPE_LIST
    synchronizer = sync.ProjectTypeSynchronizer

    def setUp(self):
        super().setUp()
        fixture_utils.init_project_types()

    def test_sync_project_type(self):
        self._evaluate_test_sync()

    def test_delete_stale_project_type(self):
        self._evaluate_objects_deleted()


class TestResourceSynchronizer(TestCase):

    def setUp(self):
        super().setUp()

        mocks.init_api_connection(Wrapper)
        fixture_utils.init_resources()

    def _assert_sync(self, instance, object_data):
        self.assertEqual(instance.id, object_data['id'])
        self.assertEqual(instance.user_name, object_data['UserName'])
        self.assertEqual(instance.first_name, object_data['FirstName'])
        self.assertEqual(instance.last_name, object_data['LastName'])
        self.assertEqual(instance.email, object_data['Email'])
        self.assertEqual(instance.active, object_data['Active'])

    def test_sync_resource(self):
        """
        Test to ensure resource synchronizer saves a Resource
        instance locally.
        """
        self.assertGreater(Resource.objects.all().count(), 0)

        object_data = fixtures.API_RESOURCE
        instance = Resource.objects.get(id=object_data['id'])

        self._assert_sync(instance, object_data)
        assert_sync_job(Resource)

    def test_delete_stale_resources(self):
        """
        Test that resource is removed if not fetched from the API during a
        full sync.
        """
        resource_qset = Resource.objects.all()
        self.assertEqual(resource_qset.count(), 1)

        mocks.resource_api_call([])

        synchronizer = sync.ResourceSynchronizer(full=True)
        synchronizer.sync()
        self.assertEqual(resource_qset.count(), 0)


class TestTicketSecondaryResourceSynchronizer(TestCase):

    def setUp(self):
        super().setUp()
        fixture_utils.init_resources()
        fixture_utils.init_tickets()
        fixture_utils.init_secondary_resources()

    def _assert_sync(self, instance, object_data):
        self.assertEqual(instance.id, object_data['id'])
        self.assertEqual(instance.ticket.id, object_data['TicketID'])
        self.assertEqual(instance.resource.id, object_data['ResourceID'])

    def test_sync_ticket_secondary_resource(self):
        self.assertGreater(TicketSecondaryResource.objects.all().count(), 0)
        object_data = fixtures.API_SECONDARY_RESOURCE_LIST[0]
        instance = TicketSecondaryResource.objects.get(id=object_data['id'])

        self._assert_sync(instance, object_data)
        assert_sync_job(TicketSecondaryResource)

    def test_delete_ticket_secondary_resource(self):
        secondary_resources_qset = TicketSecondaryResource.objects.all()
        self.assertEqual(secondary_resources_qset.count(), 2)

        mocks.secondary_resource_api_call([])

        synchronizer = sync.TicketSecondaryResourceSynchronizer(full=True)
        synchronizer.sync()
        self.assertEqual(secondary_resources_qset.count(), 0)


class TestAccountSynchronizer(TestCase):

    def setUp(self):
        super().setUp()
        fixture_utils.init_accounts()

    def _assert_sync(self, instance, object_data):
        self.assertEqual(instance.id, object_data['id'])
        self.assertEqual(instance.name, object_data['AccountName'])
        self.assertEqual(instance.number, str(object_data['AccountNumber']))
        self.assertEqual(instance.active, object_data['Active'])
        self.assertEqual(instance.last_activity_date,
                         parse(object_data['LastActivityDate']))

    def test_sync_account(self):
        self.assertGreater(Account.objects.all().count(), 0)
        object_data = fixtures.API_ACCOUNT_LIST[0]
        instance = Account.objects.get(id=object_data['id'])

        self._assert_sync(instance, object_data)
        assert_sync_job(Account)

    def test_delete_stale_account(self):
        account_qset = Account.objects.all()
        self.assertEqual(account_qset.count(), 1)

        mocks.account_api_call([])

        synchronizer = sync.AccountSynchronizer(full=True)
        synchronizer.sync()
        self.assertEqual(account_qset.count(), 0)


class TestProjectSynchronizer(TestCase):

    def setUp(self):
        super().setUp()
        fixture_utils.init_resources()
        fixture_utils.init_accounts()
        fixture_utils.init_project_statuses()
        fixture_utils.init_project_types()
        fixture_utils.init_projects()

    def _assert_sync(self, instance, object_data):
        self.assertEqual(instance.id, object_data['id'])
        self.assertEqual(instance.name, object_data['ProjectName'])
        self.assertEqual(instance.number, object_data['ProjectNumber'])
        self.assertEqual(instance.description, object_data['Description'])
        self.assertEqual(instance.actual_hours, object_data['ActualHours'])
        self.assertEqual(instance.completed_date_time,
                         parse(object_data['CompletedDateTime']))
        self.assertEqual(instance.completed_percentage,
                         object_data['CompletedPercentage'])
        self.assertEqual(instance.duration, object_data['Duration'])
        self.assertEqual(instance.start_date_time,
                         parse(object_data['StartDateTime']))
        self.assertEqual(instance.end_date_time,
                         parse(object_data['EndDateTime']))
        self.assertEqual(instance.estimated_time, object_data['EstimatedTime'])
        self.assertEqual(instance.last_activity_date_time,
                         parse(object_data['LastActivityDateTime']))
        self.assertEqual(instance.project_lead_resource.id,
                         object_data['ProjectLeadResourceID'])
        self.assertEqual(instance.account.id, object_data['AccountID'])
        self.assertEqual(instance.status.id, object_data['Status'])
        self.assertEqual(instance.type.id, object_data['Type'])

    def test_sync_project(self):
        self.assertGreater(Project.objects.all().count(), 0)
        object_data = fixtures.API_PROJECT_LIST[0]
        instance = Project.objects.get(id=object_data['id'])

        self._assert_sync(instance, object_data)
        assert_sync_job(Project)

    def test_delete_stale_project(self):
        project_qset = Project.objects.all()
        self.assertEqual(project_qset.count(), 1)

        mocks.project_api_call([])

        synchronizer = sync.ProjectSynchronizer(full=True)
        synchronizer.sync()
        self.assertEqual(project_qset.count(), 0)
