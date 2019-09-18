from mock import patch


WRAPPER_QUERY_METHOD = 'atws.wrapper.Wrapper.query'
GET_FIELD_INFO_METHOD = 'atws.helpers.get_field_info'


def create_mock_call(method_name, return_value, side_effect=None):
    """Utility function for mocking the specified function or method"""
    _patch = patch(method_name, side_effect=side_effect)
    mock_get_call = _patch.start()

    if not side_effect:
        mock_get_call.return_value = return_value

    return mock_get_call, _patch


def init_api_connection(return_value):
    method_name = 'djautotask.sync.Synchronizer.init_api_connection'

    return create_mock_call(method_name, return_value)


def ticket_api_call(return_value):
    return create_mock_call(WRAPPER_QUERY_METHOD, return_value)


def resource_api_call(return_value):
    return create_mock_call(WRAPPER_QUERY_METHOD, return_value)


def secondary_resource_api_call(return_value):
    return create_mock_call(WRAPPER_QUERY_METHOD, return_value)


def account_api_call(return_value):
    return create_mock_call(WRAPPER_QUERY_METHOD, return_value)


def project_api_call(return_value):
    return create_mock_call(WRAPPER_QUERY_METHOD, return_value)


def ticket_status_api_call(return_value):
    return create_mock_call(GET_FIELD_INFO_METHOD, return_value)


def ticket_priority_api_call(return_value):
    return create_mock_call(GET_FIELD_INFO_METHOD, return_value)


def queue_api_call(return_value):
    return create_mock_call(GET_FIELD_INFO_METHOD, return_value)


def project_status_api_call(return_value):
    return create_mock_call(GET_FIELD_INFO_METHOD, return_value)


def project_type_api_call(return_value):
    return create_mock_call(GET_FIELD_INFO_METHOD, return_value)


def wrapper_query_api_calls(side_effect=None):
    """
    Patch the Wrapper query method to return values based on the
    supplied side effect.
    """
    _patch = patch(WRAPPER_QUERY_METHOD, side_effect=side_effect)
    _patch.start()


def get_field_info_api_calls(side_effect=None):
    """
    Patch the get_info_field method to return values based on the
    supplied side effect.
    """
    _patch = patch(GET_FIELD_INFO_METHOD, side_effect=side_effect)
    _patch.start()
