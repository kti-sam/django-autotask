from suds.client import Client
from atws.wrapper import QueryCursor
import urllib
import os


def mock_query_generator(suds_objects):
    """
    A generator to return suds objects to mock the same behaviour as the
    ATWS Wrapper query method.
    """
    for obj in suds_objects:
        yield obj


def set_attributes(suds_object, fixture_object):
    """
    Set attributes on suds object from the given fixture.
    """
    for key, value in fixture_object.items():
        setattr(suds_object, key, value)

    return suds_object


def generate_objects(object_type, fixture_objects):
    """
    Generate multiple objects based on the given fixtures.
    """
    path = os.path.abspath("djautotask/tests/atws.wsdl")
    url = urllib.parse.urljoin('file:', urllib.request.pathname2url(path))
    client = Client(url)
    object_list = []

    # Create test suds objects from the list of fixtures.
    for fixture in fixture_objects:
        suds_object = \
            set_attributes(client.factory.create(object_type), fixture)

        object_list.append(suds_object)

    return QueryCursor(mock_query_generator(object_list))
