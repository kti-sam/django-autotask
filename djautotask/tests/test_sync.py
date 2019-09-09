from django.test import TestCase
from atws.wrapper import Wrapper
from dateutil.parser import parse

from djautotask.models import Ticket, SyncJob
from djautotask import sync
from djautotask.tests import fixtures, mocks, fixture_utils


def assert_sync_job(model_class):
    qset = SyncJob.objects.filter(entity_name=model_class.__name__)
    assert qset.exists()


class TestTicketSynchronizer(TestCase):

    def setUp(self):
        super().setUp()

        ticket = fixture_utils.generate_objects(
            'Ticket', [fixtures.API_SERVICE_TICKET])
        field_info = fixture_utils.generate_picklist_objects(
            'Status', fixtures.API_TICKET_STATUS_LIST)

        mocks.init_api_connection(Wrapper)
        mocks.service_ticket_status_api_call(field_info)
        mocks.service_ticket_api_call(ticket)

        status_synchronizer = sync.TicketStatusSynchronizer()
        status_synchronizer.sync()

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

    def test_sync_ticket(self):
        """
        Test to ensure ticket synchronizer saves a Ticket instance locally.
        """
        synchronizer = sync.TicketSynchronizer()
        synchronizer.sync()

        self.assertGreater(Ticket.objects.all().count(), 0)

        object_data = fixtures.API_SERVICE_TICKET
        instance = Ticket.objects.get(id=object_data['id'])

        self._assert_sync(instance, object_data)
        assert_sync_job(Ticket)

    def test_delete_stale_tickets(self):
        """Local ticket should be deleted if not returned during a full sync"""
        synchronizer = sync.TicketSynchronizer()
        synchronizer.sync()

        ticket_id = fixtures.API_SERVICE_TICKET['id']
        ticket_qset = Ticket.objects.filter(id=ticket_id)
        self.assertEqual(ticket_qset.count(), 1)

        mocks.service_ticket_api_call([])

        synchronizer = sync.TicketSynchronizer(full=True)
        synchronizer.sync()
        self.assertEqual(ticket_qset.count(), 0)
