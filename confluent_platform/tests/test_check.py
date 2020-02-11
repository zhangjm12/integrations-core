# (C) Datadog, Inc. 2019-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)

import pytest
from six import iteritems

from .common import ACTIVEMQ_E2E_METRICS


@pytest.mark.e2e
def test(dd_agent_check):
    instance = {}
    aggregator = dd_agent_check(instance)

    for metric_name, metrics in iteritems(aggregator._metrics):
        print("{} => {}".format(metric_name, metrics))
    1/0
    # for metric in ACTIVEMQ_E2E_METRICS:
    #     aggregator.assert_metric(metric)
