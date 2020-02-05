# C Datadog, Inc. 2020-Present
# All rights reserved
# Licensed under Simplified BSD License see LICENSE

from datadog_checks.cisco_aci import CiscoACICheck

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


def test_check(benchmark):
    ciscocheck = CiscoACICheck('cisco_aci', {}, SANDBOX_CONFIG)
    '''
    for _ in range(3):
        try:
            ciscocheck.check(SANDBOX_CONFIG)
        except Exception:
            time.sleep(1)
    '''
    benchmark(ciscocheck.check, SANDBOX_CONFIG)
