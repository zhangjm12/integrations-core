from datetime import datetime, timedelta

import pytest
from mock import MagicMock, patch

from datadog_checks.vsphere.cache import VSphereCache


def test_generic_cache_usage():
    interval = 120
    with patch('datadog_checks.vsphere.cache.time') as time:
        mocked_timestamps = [object() for _ in range(3)]
        time.time = MagicMock(side_effect=mocked_timestamps)
        cache = VSphereCache(interval)
        # Assert initialization
        assert cache._last_ts is mocked_timestamps[0]
        assert cache._interval == interval
        assert not cache._content

        # Update the content
        with cache.update():
            assert cache._last_ts is mocked_timestamps[0]
            cache._content['foo'] = 'bar'

        # Assert that the cache last ts was updated successfully
        assert cache._last_ts is mocked_timestamps[1]

        # Update the content but an error is raised
        with pytest.raises(Exception), cache.update():
            assert not cache._content
            cache._content['foo'] = 'baz'
            raise Exception('foo')

        # Because of the exception the content and the timestamps were not updated
        assert cache._last_ts is mocked_timestamps[1]
        assert cache._content['foo'] == 'bar'


def test_refresh():
    interval = 120
    with patch('datadog_checks.vsphere.cache.time') as time:
        base_time = 1576263848
        mocked_timestamps = [base_time + 50 * i for i in range(4)]
        time.time = MagicMock(side_effect=mocked_timestamps)
        cache = VSphereCache(interval)

        assert cache.is_expired()
        cache._last_ts = base_time

        assert not cache.is_expired()  # Only 50 seconds
        assert not cache.is_expired()  # Only 100 seconds
        assert cache.is_expired()  # 150 > 120 seconds


def test_metrics_metadata_cache():
    # TODO
    pass


def test_infrastructure_cache():
    # TODO
    pass
