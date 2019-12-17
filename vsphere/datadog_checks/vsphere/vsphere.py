# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
from collections import defaultdict
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import partial

from multiprocessing.pool import ThreadPool
from six import iteritems
from pyVmomi import vim  # pylint: disable=E0611

from datadog_checks.base import AgentCheck, is_affirmative, ensure_unicode, ConfigurationError
from datadog_checks.vsphere.api import ConnectionPool
from datadog_checks.vsphere.cache import InfrastructureCache, MetricsMetadataCache
from datadog_checks.vsphere.metrics import ALLOWED_METRICS_FOR_MOR, should_collect_per_instance_values, \
    get_mapped_instance_tag
from datadog_checks.vsphere.utils import format_metric_name, is_excluded_by_filters, get_parent_tags_recursively, \
    MOR_TYPE_AS_STRING, make_inventory_path

REALTIME_RESOURCES = [vim.VirtualMachine, vim.HostSystem]
HISTORICAL_RESOURCES = [vim.Datacenter, vim.Datastore, vim.ClusterComputeResource]
ALL_RESOURCES = REALTIME_RESOURCES + HISTORICAL_RESOURCES


class VSphereCheck(AgentCheck):
    __NAMESPACE__ = 'vsphere'

    def __new__(cls, name, init_config, instances):
        """For backward compatibility reasons, there are two side-by-side implementations of the VSphereCheck.
        Instantiating this class will return an instance of the legacy integration for existing users and
        an instance of the new implementation for new users."""
        if is_affirmative(instances[0].get('use_legacy_check_version', True)):
            from datadog_checks.vsphere.legacy.vsphere_legacy import VSphereLegacyCheck
            return VSphereLegacyCheck(name, init_config, instances)
        return super(VSphereCheck, cls).__new__(cls)

    def __init__(self, name, init_config, instances):
        AgentCheck.__init__(self, name, init_config, instances)
        self.conn_pool = ConnectionPool(self.instance)
        self.infrastructure_cache = InfrastructureCache(interval_sec=180)
        self.metrics_metadata_cache = MetricsMetadataCache(interval_sec=600)

        self.base_tags = self.instance.get("tags", [])
        self.collection_level = self.instance.get("collection_level", 1)
        self.collection_type = self.instance.get("collection_type", "realtime")
        self.resource_filters = self.instance.get("resource_filters", {})
        self.metric_filters = self.instance.get("metric_filters", {})
        self.use_guest_hostname = self.instance.get("use_guest_hostname", False)

        self.thread_count = self.instance.get("thread_count", 4)
        self.batch_morlist_size = self.instance.get("batch_morlist_size", 50)
        self.max_historical_metrics = self.instance.get("max_query_metrics", self.api.get_max_query_metrics())
        self.collected_resource_types = REALTIME_RESOURCES if self.collection_type == 'realtime' else HISTORICAL_RESOURCES

        self.latest_event_query = datetime.now()
        self.validate_and_format_config()

    @property
    def api(self):
        return self.conn_pool.get_api()

    def validate_and_format_config(self):
        if 'ssl_verify' in self.instance and 'ssl_capath' in self.instance:
            self.log.warning(
                "Your configuration is incorrectly attempting to "
                "specify both a CA path, and to disable SSL "
                "verification. You cannot do both. Proceeding with "
                "disabling ssl verification."
            )

        if self.collection_type not in ('realtime', 'historical'):
            raise ConfigurationError(
                "Your configuration is incorrectly attempting to "
                "set the `collection_type` to %s. It should be either "
                "'realtime' or 'historical'."
            )

        formatted_resource_filters = {}
        allowed_prop_names = ('name', 'inventory_path')
        allowed_prop_names_for_vm = allowed_prop_names + ('hostname', 'guest_hostname')
        for f in self.resource_filters:
            for (field, field_type) in {'resource': str, 'property': str, 'patterns': list}:
                if field not in f:
                    self.warning("Ignoring filter %r, it should define the field %s", f, field)
                    continue
                if not isinstance(f[field], field_type):
                    self.warning("Ignoring filter %r because field %s should have type %s", f, field, field_type)
                    continue

            if f['resource'] not in self.collected_resource_types:
                self.warning("Ignoring filter %r because resource %s"
                             "is not collected when collection_type is %s", f['resource'], self.collection_type)
                continue

            prop_names = allowed_prop_names_for_vm if f['resource'] == 'vm' else allowed_prop_names
            if f['property'] not in prop_names:
                self.warning(
                    "Ignoring filter %r because property '%s' is not valid "
                    "for resource type %s. Should be one of %r",
                    f, f['property'], f['resource'], prop_names
                )
                continue

            filter_key = (f['resource'], f['property'])
            if filter_key in formatted_resource_filters:
                self.warning(
                    "Ignoring filer %r because you already have a filter "
                    "for resource type %s and property %s",
                    f, f['resource'], f['property']
                )
                continue

            formatted_resource_filters[filter_key] = f['patterns']

        self.resource_filters = formatted_resource_filters

    def refresh_metrics_metadata_cache(self):
        counters = self.api.get_perf_counter_by_level(self.collection_level)

        for mor_type in ALL_RESOURCES:
            allowed_counters = [c for c in counters if format_metric_name(c) in ALLOWED_METRICS_FOR_MOR[mor_type]]

            metadata = {
                c.key: {"name": format_metric_name(c), "unit": c.unitInfo.key}
                for c in allowed_counters
            }
            self.metrics_metadata_cache.set_metadata(mor_type, metadata)

        # TODO: Understand how much data actually changes between check runs
        # Apparently only when the server restarts?
        # https://pubs.vmware.com/vsphere-50/index.jsp?topic=%2Fcom.vmware.wssdk.pg.doc_50%2FPG_Ch16_Performance.18.5.html

    def refresh_infrastructure_cache(self):
        """Fetch the complete infrastructure, generate tags for each monitored resources and store all of that
        into the infrastructure_cache. It also computes the resource `hostname` property to be used when submitting
        metrics for this mor."""
        infrastructure_data = self.api.get_infrastructure()

        from collections import defaultdict
        metrics_for_resource = defaultdict(set)

        for mor, properties in iteritems(infrastructure_data):
            if not isinstance(mor, tuple(self.collected_resource_types)):
                # Do nothing for the resource types we do not collect
                continue
            if is_excluded_by_filters(mor, infrastructure_data, self.resource_filters):
                # The resource does not match the specified patterns
                continue

            mor_name = properties.get("name", "unknown")
            mor_type = MOR_TYPE_AS_STRING[type(mor)]
            hostname = None
            tags = []

            if mor_type == vim.VirtualMachine:
                power_state = properties.get("runtime.powerState")
                if power_state != vim.VirtualMachinePowerState.poweredOn:
                    # Skipping because of not powered on
                    continue

                # Host are not considered parents of the VMs they run, we use the `runtime.host` property
                # to get the name of the ESX host
                runtime_host = properties.get("runtime.host")
                runtime_host_props = infrastructure_data.get(runtime_host, {})
                runtime_hostname = ensure_unicode(runtime_host_props.get("name", "unknown"))
                tags.append('vsphere_host:{}'.format(runtime_hostname))

                if self.use_guest_hostname:
                    hostname = properties.get("guest.hostName", mor_name)
                else:
                    hostname = mor_name
            elif mor_type == vim.HostSystem:
                hostname = mor_name
            else:
                tags.append('vsphere_{}:{}'.format(mor_type, mor_name))

            tags.extend(get_parent_tags_recursively(mor, infrastructure_data))
            tags.append('vsphere_type:{}'.format(mor_type))
            mor_payload = {"tags": tags}
            if hostname:
                mor_payload['hostname'] = hostname

            if (mor_type, 'inventory_path') in self.resource_filters:
                mor_payload['inv_path'] = make_inventory_path(mor, infrastructure_data)

            self.infrastructure_cache.set_mor_data(mor, mor_payload)

        print(metrics_for_resource)

    def submit_metrics_callback(self, task, resource_type):
        try:
            results = task.result()
        except Exception as e:
            # TODO better exception handling
            print("An error occurend in the thread:")
            print(task.__dict__)
            print(e)
            return
        metadata = self.metrics_metadata_cache.get_metadata(resource_type)
        if not results:
            return

        for result_per_mor in results:
            # TODO: IMPLEMENT ERROR HANDLING IF MOR NOT FOUND
            mor_props = self.infrastructure_cache.get_mor_props(result_per_mor.entity)

            for result in result_per_mor.value:
                counter = metadata.get(result.id.counterId)
                if not counter:
                    # Fail-safe
                    self.log.debug(
                        "Skipping value for counter %s, because there is no metadata about it",
                        ensure_unicode(result.id.counterId),
                    )
                    continue

                metric_name = counter['name']
                if not result.value:
                    self.log.debug("Skipping `%s` metric because the value is empty", ensure_unicode(metric_name))
                    continue

                # Get the most recent value that isn't negative
                valid_values = [v for v in result.value if v >= 0]
                if not valid_values:
                    continue
                value = valid_values[-1]
                if counter['unit'] == 'percent':
                    value = float(value)/100

                tags = []
                if should_collect_per_instance_values(metric_name):
                    instance_tag_key = get_mapped_instance_tag(metric_name)
                    instance_tag_value = result.id.instance or 'none'
                    tags.append('{}:{}'.format(instance_tag_key, instance_tag_value))

                if resource_type in HISTORICAL_RESOURCES:
                    tags.extend(mor_props['tags'])
                    hostname = None
                else:
                    hostname = ensure_unicode(mor_props.get('hostname'))

                tags.extend(self.base_tags)

                # vsphere "rates" should be submitted as gauges (rate is
                # precomputed).
                self.gauge(ensure_unicode(metric_name), value, hostname=hostname, tags=tags)

    def collect_metrics(self):
        """Keep all apis connections"""
        pool_executor = ThreadPoolExecutor(max_workers=self.thread_count)

        for resource_type in ALL_RESOURCES:
            mors = self.infrastructure_cache.get_mors(resource_type)
            if not mors:
                continue
            counters = self.metrics_metadata_cache.get_metadata(resource_type)
            metric_ids = []
            for counter_key, counter_info in iteritems(counters):
                instance = ""
                if should_collect_per_instance_values(counter_info['name']):
                    instance = "*"
                metric_ids.append(vim.PerformanceManager.MetricId(counterId=counter_key, instance=instance))

            for batch in self.make_batch(mors, metric_ids, resource_type):
                query_specs = []
                for mor, metrics in iteritems(batch):
                    mor_props = self.infrastructure_cache.get_mor_props(mor)
                    if not mor_props:
                        continue

                    query_spec = vim.PerformanceManager.QuerySpec()
                    query_spec.entity = mor
                    query_spec.metricId = metrics
                    if resource_type in REALTIME_RESOURCES:
                        query_spec.intervalId = 20  # FIXME: Make constant
                        query_spec.maxSample = 1  # Request a single datapoint
                    else:
                        # We cannot use `maxSample` for historical metrics, let's specify a timewindow that will
                        # contain at least one element
                        query_spec.startTime = datetime.now() - timedelta(hours=2)
                    query_specs.append(query_spec)
                if query_specs:
                    task = pool_executor.submit(lambda q: self.api.query_metrics(q), query_specs)
                    task.add_done_callback(lambda x, r=resource_type: self.submit_metrics_callback(x, r))

        pool_executor.shutdown()

    def make_batch(self, mors, metric_ids, resource_type):
        """All those mors must be of the same resource!!!!"""
        batch = defaultdict(list)
        batch_size = 0
        mors = [m for m in mors if type(m) == resource_type]

        if resource_type == vim.ClusterComputeResource:
            max_batch_size = 1
        elif resource_type in REALTIME_RESOURCES or self.max_historical_metrics < 0:
            max_batch_size = self.batch_morlist_size
        else:
            max_batch_size = min(self.batch_morlist_size, self.max_historical_metrics)

        for m in mors:
            for metric in metric_ids:
                if batch_size >= max_batch_size:
                    yield batch
                    batch = defaultdict(list)
                    batch_size = 0
                batch[m].append(metric)
                batch_size += 1
        yield batch

    def submit_external_host_tags(self):
        self.log.debug("Sending external_host_tags now")
        external_host_tags = []
        hosts = self.infrastructure_cache.get_mors(vim.HostSystem)
        vms = self.infrastructure_cache.get_mors(vim.VirtualMachine)
        for mor in hosts + vms:
            # Note: some mors have a None hostname
            mor_props = self.infrastructure_cache.get_mor_props(mor)
            hostname = mor_props.get('hostname')
            if hostname:
                external_host_tags.append((hostname, {self.__NAMESPACE__: mor_props['tags']}))

        self.set_external_tags(external_host_tags)

    def collect_events(self):
        try:
            new_events = self.api.get_new_events(start_time=self.latest_event_query)

            self.log.debug("Got %s new events from vCenter event manager", len(new_events))
            for event in new_events:
                # TODO: Submit the event
                pass
        except Exception as e:
            # Don't get stuck on a failure to fetch an event
            # Ignore them for next pass
            self.log.warning("Unable to fetch Events %s", e)

        self.latest_event_query = self.api.get_latest_event_timestamp() + timedelta(seconds=1)

    def check(self, _):
        import pdb; pdb.set_trace()
        self.thread_count = 4
        self.base_tags.append("flo:test")
        self.collection_type = 'historical'
        self.collected_resource_types = HISTORICAL_RESOURCES

        # resource_filters:
        #   - resource: vm
        #     property: name
        #     patterns:
        #       - <VM_REGEX_1>
        #       - <VM_REGEX_2>
        #   - resource: vm
        #     property: hostname
        #     patterns:
        #       - <HOSTNAME_REGEX>
        #   - resource: vm
        #     property: guest_hostname
        #     patterns:
        #       - <GUEST_HOSTNAME_REGEX>
        #   - resource: host
        #     property: inventory_path
        #     patterns:
        #       - <INVENTORY_PATH_REGEX>
        self.resource_filters = [
            {'resource': 'vm', 'property': 'name', 'patterns': ['cpu\..*']}
        ]

        self.max_historical_metrics = self.instance.get("max_query_metrics", self.api.get_max_query_metrics())

        if self.metrics_metadata_cache.is_expired():
            with self.metrics_metadata_cache.update():
                self.refresh_metrics_metadata_cache()

        if self.infrastructure_cache.is_expired():
            with self.infrastructure_cache.update():
                self.refresh_infrastructure_cache()
            if self.collection_type == 'realtime':
                self.submit_external_host_tags()

        self.collect_metrics()
