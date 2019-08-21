# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from datadog_checks.mapr import MaprCheck
import pytest


@pytest.mark.unit
def test_whitelist(instance):
    instance['whitelist'] = ['mapr.fs.*', 'mapr.db.*']
    check = MaprCheck('mapr', {}, [instance])

    assert check.should_collect_metric('mapr.fs.read_cachemisses')
    assert check.should_collect_metric('mapr.db.get_currpcs')
    assert not check.should_collect_metric('mapr.cache.misses_largefile')


def test_check(aggregator, instance):
    check = MaprCheck('mapr', {}, {})
    check.check(instance)

    aggregator.assert_all_metrics_covered()
