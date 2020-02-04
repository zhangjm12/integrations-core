import pytest

SANDBOX_CONFIG = {
    'instances': [
        {
            'aci_url': 'https://sandboxapicdc.cisco.com',
            'username': 'admin',
            'pwd': 'ciscopsdt',
            'tls_verify': False,  # As of 2019-12-03, the sandbox endpoint doesn't have a valid TLS certificate.
        }
    ]
}


@pytest.fixture(scope="session")
def dd_environment():
    return SANDBOX_CONFIG