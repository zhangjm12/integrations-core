import pytest


@pytest.fixture(scope='session')
def realtime_instance():
    return {
        'collection_level': 4,
        'empty_default_hostname': True,
        'use_legacy_check_version': False,
        'host': 'vcenter.localdomain',
        'username': 'administrator@vsphere.local',
        'name': 'main-vcenter',
        'password': 'vSpherer0cks!',
        'ssl_verify': False,
    }


@pytest.fixture(scope='session')
def historical_instance():
    return {
        'collection_level': 1,
        'empty_default_hostname': True,
        'use_legacy_check_version': False,
        'host': 'vcenter.localdomain',
        'username': 'administrator@vsphere.local',
        'name': 'main-vcenter',
        'password': 'vSpherer0cks!',
        'ssl_verify': False,
        'collection_type': 'historical',
    }
