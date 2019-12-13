from mock import patch, MagicMock, ANY
import pytest
from pyVmomi import vim
from datadog_checks.vsphere import VSphereCheck
from datadog_checks.vsphere.api import VSphereAPI, MetricCollector


def test_connect_success(realtime_instance):
    with patch('datadog_checks.vsphere.api.connect') as connect:
        connection = MagicMock()
        smart_connect = connect.SmartConnect
        smart_connect.return_value = connection
        current_time = connection.CurrentTime

        api = VSphereAPI(realtime_instance)
        smart_connect.assert_called_once_with(
            host=realtime_instance['host'],
            user=realtime_instance['username'],
            pwd=realtime_instance['password'],
            sslContext=ANY,
        )
        current_time.assert_called_once()

        assert api._conn == connection


def test_connect_failure(realtime_instance):
    with patch('datadog_checks.vsphere.api.connect') as connect:
        connection = MagicMock()
        smart_connect = connect.SmartConnect
        smart_connect.return_value = connection
        current_time = connection.CurrentTime
        current_time.side_effect = Exception('foo')

        with pytest.raises(ConnectionError):
            api = VSphereAPI(realtime_instance)
            assert api._conn is None

        smart_connect.assert_called_once_with(
            host=realtime_instance['host'],
            user=realtime_instance['username'],
            pwd=realtime_instance['password'],
            sslContext=ANY,
        )
        current_time.assert_called_once()


def test_get_infrastructure(realtime_instance):
    with patch('datadog_checks.vsphere.api.connect'):
        api = VSphereAPI(realtime_instance)

        container_view = api._conn.content.viewManager.CreateContainerView.return_value
        container_view.__class__ = vim.ManagedObject

        obj1 = MagicMock(missingSet=None, obj="foo")
        obj2 = MagicMock(missingSet=None, obj="bar")
        api._conn.content.propertyCollector.RetrievePropertiesEx.return_value = MagicMock(
            objects=[obj1],
            token=['baz']
        )
        api._conn.content.propertyCollector.ContinueRetrievePropertiesEx.return_value = MagicMock(
            objects=[obj2],
            token=None
        )

        root_folder = api._conn.content.rootFolder
        root_folder.name = 'root-folder'
        infrastructure_data = api.get_infrastructure()
        assert infrastructure_data == {
            'foo': {},
            'bar': {},
            root_folder: {'name': 'root-folder', 'parent': None}
        }


def test_smart_retry(realtime_instance):
    with patch('datadog_checks.vsphere.api.connect') as connect:
        smart_connect = connect.SmartConnect
        api = VSphereAPI(realtime_instance)
        query_perf_counter = api._conn.content.perfManager.QueryPerfCounterByLevel
        query_perf_counter.side_effect = [Exception('error'), 'success']
        api.get_perf_counter_by_level(None)

        assert query_perf_counter.call_count == 2
        assert smart_connect.call_count == 2


def test_metric_collection(realtime_instance):
    num_queries = 100
    num_threads = 10
    with patch('datadog_checks.vsphere.api.connect') as connect, patch('datadog_checks.vsphere.api.threading') as threading:
        threading.get_ident.side_effect = [i % num_threads for i in range(num_queries)]
        metric_collector = MetricCollector(realtime_instance)
        assert not metric_collector._apis

        query_specs = MagicMock()
        for i in range(num_queries):
            metric_collector.query_metrics(query_specs)

        assert connect.SmartConnect.call_count == num_threads
        assert len(metric_collector._apis) == num_threads


def test_vsphere(historical_instance, aggregator):
    check = VSphereCheck('vsphere', {}, [historical_instance])
    import pdb; pdb.set_trace()
    check.check(historical_instance)
    print("Hey")
