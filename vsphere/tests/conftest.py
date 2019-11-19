import pytest


@pytest.fixture(scope='session')
def instance():
    return {
        'collection_level': 4,
        'empty_default_hostname': True,
        'use_legacy_check_version': False,
        'host': 'vcenter.localdomain',
        'username': 'administrator@vsphere.local',
        'name': 'main-vcenter',
        'password': 'vSpherer0cks!',
        'ssl_verify': False
    }
