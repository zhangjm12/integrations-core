# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime, timedelta
from functools import partial

from multiprocessing.pool import ThreadPool
from six import iteritems
from pyVmomi import vim  # pylint: disable=E0611

from datadog_checks.base import AgentCheck, is_affirmative, ensure_unicode, to_string
from datadog_checks.vsphere.api import VSphereAPI, MetricCollector
from datadog_checks.vsphere.cache import InfrastructureCache, MetricsMetadataCache
from datadog_checks.vsphere.metrics import ALLOWED_METRICS_FOR_MOR, should_collect_per_instance_values, \
    get_mapped_instance_tag
from datadog_checks.vsphere.utils import format_metric_name, is_excluded_by_filters, get_parent_tags_recursively, \
    MOR_TYPE_AS_STRING

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
        self.validate_config()

        self.api = VSphereAPI(self.instance)
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
        self.max_historical_metrics = self.instance.get("max_historical_metrics", 64)
        self.collected_resource_types = REALTIME_RESOURCES if self.collection_type == 'realtime' else HISTORICAL_RESOURCES

        self.latest_event_query = datetime.now()

    def validate_config(self):
        if 'ssl_verify' in self.instance and 'ssl_capath' in self.instance:
            self.log.debug(
                "Your configuration is incorrectly attempting to "
                "specify both a CA path, and to disable SSL "
                "verification. You cannot do both. Proceeding with "
                "disabling ssl verification."
            )

        # TODO: VALIDATE FILTERS

    def refresh_metrics_metadata_cache(self):
        counters = self.api.get_perf_counter_by_level(self.collection_level)

        for mor_type in ALL_RESOURCES:
            allowed_counters = [c for c in counters if format_metric_name(c) in ALLOWED_METRICS_FOR_MOR[mor_type]]
            metadata = {
                c.key: {"name": format_metric_name(c), "unit": c.unitInfo.key}
                for c in allowed_counters
            }
            self.metrics_metadata_cache.set_metadata(mor_type, metadata)

        #self.metrics_metadata_cache.update(metadata)
        # TODO: Understand how much data actually changes between check runs
        # Apparently only when the server restarts?
        # https://pubs.vmware.com/vsphere-50/index.jsp?topic=%2Fcom.vmware.wssdk.pg.doc_50%2FPG_Ch16_Performance.18.5.html

    def refresh_infrastructure_cache(self):
        """Fetch the complete infrastructure, generate tags for each monitored resources and store all of that
        into the infrastructure_cache. It also computes the resource `hostname` property to be used when submitting
        metrics for this mor."""
        infrastucture_data = self.api.get_infrastructure()

        for mor, properties in iteritems(infrastucture_data):
            if not isinstance(mor, tuple(self.collected_resource_types)):
                # Do nothing for the resource types we do not collect
                continue
            if is_excluded_by_filters(mor, properties, self.resource_filters):
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
                runtime_host_props = infrastucture_data.get(runtime_host, {})
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

            tags.extend(get_parent_tags_recursively(mor, infrastucture_data))
            tags.append('vsphere_type:{}'.format(mor_type))

            mor_payload = {"tags": tags}
            if hostname:
                mor_payload['hostname'] = hostname

            self.infrastructure_cache.set_mor_data(mor, mor_payload)

    def submit_metrics(self, task, resource_type):
        results = task.result()
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
                print("Submitting vsphere.{}={} for hostname={} and tags={}".format(metric_name, value, hostname, tags))
                self.gauge(ensure_unicode(metric_name), value, hostname=hostname, tags=tags)

    def collect_metrics(self):
        pool_executor = ThreadPoolExecutor(max_workers=self.thread_count)
        metric_collector = MetricCollector(self.instance)

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

            for batch in self.make_batch(mors, resource_type):
                query_specs = []
                for mor in batch:
                    mor_props = self.infrastructure_cache.get_mor_props(mor)
                    if not mor_props:
                        continue

                    query_spec = vim.PerformanceManager.QuerySpec()
                    query_spec.entity = mor
                    query_spec.metricId = metric_ids
                    if resource_type in REALTIME_RESOURCES:
                        query_spec.intervalId = 20  # FIXME: Make constant
                        query_spec.maxSample = 1  # Request a single datapoint
                    else:
                        # We cannot use `maxSample` for historical metrics, let's specify a timewindow that will
                        # contain at least one element
                        query_spec.startTime = datetime.now() - timedelta(hours=2)
                    query_specs.append(query_spec)
                if query_specs:
                    task = pool_executor.submit(metric_collector.query_metrics, query_specs)
                    task.add_done_callback(lambda x, r=resource_type: self.submit_metrics(x, r))

        print("Shutting down")
        pool_executor.shutdown()

    def make_batch(self, mors, resource_type):
        """All those mors must be of the same resource!!!!"""
        batch = []
        mors = [m for m in mors if type(m) == resource_type]

        if resource_type in REALTIME_RESOURCES:
            batch_size = self.batch_morlist_size
        elif resource_type == vim.ClusterComputeResource:
            batch_size = 1
        else:
            metrics_count = len(self.metrics_metadata_cache.get_metadata(resource_type))
            batch_size = min(self.batch_morlist_size, self.max_historical_metrics/metrics_count)

        for m in mors:
            if len(batch) == batch_size:
                yield batch
                batch = []
            batch.append(m)
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
        self.batch_morlist_size = 1
        self.thread_count = 4
        self.base_tags.append("flo:test")
        self.collection_type = 'historical'
        self.collected_resource_types = [vim.Datastore]

        if self.metrics_metadata_cache.is_expired():
            self.metrics_metadata_cache.reset()
            self.refresh_metrics_metadata_cache()

        if self.infrastructure_cache.is_expired():
            self.infrastructure_cache.reset()
            self.refresh_infrastructure_cache()
            if self.collection_type == 'realtime':
                self.submit_external_host_tags()

        self.collect_metrics()
