import time

from datadog_checks.cisco_aci import CiscoACICheck
from .conftest import SANDBOX_CONFIG

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
