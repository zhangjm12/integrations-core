# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
import time
from collections import defaultdict
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime, timedelta
from itertools import chain

from pyVmomi import vim  # pylint: disable=E0611
from six import iteritems

from datadog_checks.base import AgentCheck, ConfigurationError, ensure_unicode, is_affirmative
from datadog_checks.vsphere.api import MetricCollector, VSphereAPI
from datadog_checks.vsphere.cache import InfrastructureCache, MetricsMetadataCache
from datadog_checks.vsphere.constants import (
    ALL_RESOURCES_WITH_METRICS,
    ALLOWED_FILTER_PROPERTIES,
    DEFAULT_BATCH_MORLIST_SIZE,
    DEFAULT_MAX_QUERY_METRICS,
    DEFAULT_THREAD_COUNT,
    EXTRA_FILTER_PROPERTIES_FOR_VMS,
    HISTORICAL_RESOURCES,
    REALTIME_RESOURCES,
)
from datadog_checks.vsphere.legacy.event import VSphereEvent
from datadog_checks.vsphere.metrics import ALLOWED_METRICS_FOR_MOR, PERCENT_METRICS
from datadog_checks.vsphere.utils import (
    MOR_TYPE_AS_STRING,
    format_metric_name,
    get_mapped_instance_tag,
    get_parent_tags_recursively,
    is_metric_excluded_by_filters,
    is_resource_excluded_by_filters,
    should_collect_per_instance_values,
)


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
        self.infrastructure_cache = InfrastructureCache(interval_sec=180)
        self.metrics_metadata_cache = MetricsMetadataCache(interval_sec=600)
        self.api = None

        self.base_tags = self.instance.get("tags", [])
        self.collection_level = self.instance.get("collection_level", 1)
        self.collection_type = self.instance.get("collection_type", "realtime")
        self.resource_filters = self.instance.get("resource_filters", {})
        self.metric_filters = self.instance.get("metric_filters", {})
        self.use_guest_hostname = self.instance.get("use_guest_hostname", False)
        self.event_config = self.instance.get("event_config")

        self.thread_count = self.instance.get("thread_count", DEFAULT_THREAD_COUNT)
        self.batch_morlist_size = self.instance.get("batch_morlist_size", DEFAULT_BATCH_MORLIST_SIZE)
        self.max_historical_metrics = DEFAULT_MAX_QUERY_METRICS
        self.collected_resource_types = (
            REALTIME_RESOURCES if self.collection_type == 'realtime' else HISTORICAL_RESOURCES
        )

        self.latest_event_query = datetime.now()
        self.validate_and_format_config()

    def validate_and_format_config(self):
        """Validate that the config is correct and transform resource filters into a more manageable object."""

        if 'ssl_verify' in self.instance and 'ssl_capath' in self.instance:
            self.warning(
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
        allowed_resource_types = [MOR_TYPE_AS_STRING[k] for k in self.collected_resource_types]

        for f in self.resource_filters:
            for (field, field_type) in iteritems({'resource': str, 'property': str, 'patterns': list}):
                if field not in f:
                    self.warning("Ignoring filter %r because it doesn't contain a %s field.", f, field)
                    continue
                if not isinstance(f[field], field_type):
                    self.warning("Ignoring filter %r because field %s should have type %s.", f, field, field_type)
                    continue

            if f['resource'] not in allowed_resource_types:
                self.warning(
                    "Ignoring filter %r because resource %s" "is not collected when collection_type is %s.",
                    f,
                    f['resource'],
                    self.collection_type,
                )
                continue

            allowed_prop_names = ALLOWED_FILTER_PROPERTIES
            if f['resource'] == MOR_TYPE_AS_STRING[vim.Datastore]:
                allowed_prop_names += EXTRA_FILTER_PROPERTIES_FOR_VMS

            if f['property'] not in allowed_prop_names:
                self.warning(
                    "Ignoring filter %r because property '%s' is not valid "
                    "for resource type %s. Should be one of %r.",
                    f,
                    f['property'],
                    f['resource'],
                    allowed_prop_names,
                )
                continue

            filter_key = (f['resource'], f['property'])
            if filter_key in formatted_resource_filters:
                self.warning(
                    "Ignoring filer %r because you already have a filter " "for resource type %s and property %s.",
                    f,
                    f['resource'],
                    f['property'],
                )
                continue

            formatted_resource_filters[filter_key] = f['patterns']

        self.resource_filters = formatted_resource_filters

    def refresh_metrics_metadata_cache(self):
        """Request the list of counters (metrics) from vSphere and store them in a cache."""
        counters = self.api.get_perf_counter_by_level(self.collection_level)

        for mor_type in ALL_RESOURCES_WITH_METRICS:
            allowed_counters = []
            for c in counters:
                metric_name = format_metric_name(c)
                if metric_name in ALLOWED_METRICS_FOR_MOR[mor_type] and not is_metric_excluded_by_filters(
                    metric_name, mor_type, self.metric_filters
                ):
                    allowed_counters.append(c)
            metadata = {c.key: format_metric_name(c) for c in allowed_counters}
            self.metrics_metadata_cache.set_metadata(mor_type, metadata)

        # TODO: Later - Understand how much data actually changes between check runs
        # Apparently only when the server restarts?
        # https://pubs.vmware.com/vsphere-50/index.jsp?topic=%2Fcom.vmware.wssdk.pg.doc_50%2FPG_Ch16_Performance.18.5.html

    def refresh_infrastructure_cache(self):
        """Fetch the complete infrastructure, generate tags for each monitored resources and store all of that
        into the infrastructure_cache. It also computes the resource `hostname` property to be used when submitting
        metrics for this mor."""
        infrastructure_data = self.api.get_infrastructure()

        for mor, properties in iteritems(infrastructure_data):
            if not isinstance(mor, tuple(self.collected_resource_types)):
                # Do nothing for the resource types we do not collect
                continue
            if is_resource_excluded_by_filters(mor, infrastructure_data, self.resource_filters):
                # The resource does not match the specified patterns
                continue

            mor_name = properties.get("name", "unknown")
            mor_type_str = MOR_TYPE_AS_STRING[type(mor)]
            hostname = None
            tags = []

            if isinstance(mor, vim.VirtualMachine):
                power_state = properties.get("runtime.powerState")
                if power_state != vim.VirtualMachinePowerState.poweredOn:
                    # Skipping because of not powered on
                    # TODO: Sometimes VM are "poweredOn" but "disconnected" and thus have no metrics
                    continue

                # Hosts are not considered as parents of the VMs they run, we use the `runtime.host` property
                # to get the name of the ESX host
                runtime_host = properties.get("runtime.host")
                runtime_host_props = infrastructure_data.get(runtime_host, {})
                runtime_hostname = ensure_unicode(runtime_host_props.get("name", "unknown"))
                tags.append('vsphere_host:{}'.format(runtime_hostname))

                if self.use_guest_hostname:
                    hostname = properties.get("guest.hostName", mor_name)
                else:
                    hostname = mor_name
            elif isinstance(mor, vim.HostSystem):
                hostname = mor_name
            else:
                tags.append('vsphere_{}:{}'.format(mor_type_str, mor_name))

            tags.extend(get_parent_tags_recursively(mor, infrastructure_data))
            tags.append('vsphere_type:{}'.format(mor_type_str))
            mor_payload = {"tags": tags}
            if hostname:
                mor_payload['hostname'] = hostname

            self.infrastructure_cache.set_mor_data(mor, mor_payload)

    def submit_metrics_callback(self, task):
        """Callback of the collection of metrics. This is run in the main thread!"""
        try:
            results = task.result()
        except Exception:
            # TODO better exception handling
            self.log.exception("An error occured in a thread.")
            return

        if not results:
            # No metric from this call, maybe the mor is disconnected?
            return

        for results_per_mor in results:
            mor_props = self.infrastructure_cache.get_mor_props(results_per_mor.entity)
            if mor_props is None:
                self.log.debug(
                    "Skipping results for mor %s because the integration doesn't have any information about it.",
                    results_per_mor.entity,
                )
                continue
            resource_type = type(results_per_mor.entity)
            metadata = self.metrics_metadata_cache.get_metadata(resource_type)
            for result in results_per_mor.value:
                metric_name = metadata.get(result.id.counterId)
                if not metric_name:
                    # Fail-safe
                    self.log.debug(
                        "Skipping value for metric %s, because the integration doesn't have metadata about it.",
                        result.id.counterId,
                    )
                    continue

                if not result.value:
                    self.log.debug("Skipping metric %s because the value is empty", ensure_unicode(metric_name))
                    continue

                # Get the most recent value that isn't negative
                valid_values = [v for v in result.value if v >= 0]
                if not valid_values:
                    self.log.debug(
                        "Skipping metric %s because the value returned by vCenter"
                        " is negative (aka the metric is not yet available).",
                        ensure_unicode(metric_name),
                    )
                    continue
                value = valid_values[-1]
                if metric_name in PERCENT_METRICS:
                    # Convert the percentage to a float.
                    value = float(value) / 100

                tags = []
                if should_collect_per_instance_values(metric_name, resource_type):
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
                print("Submitted {}={}, for host={} and tags={}".format(metric_name, value, hostname, tags))
                self.gauge(ensure_unicode(metric_name), value, hostname=hostname, tags=tags)

    def collect_metrics(self):
        """Creates a pool of thread and run the query_metrics calls in parallel."""
        pool_executor = ThreadPoolExecutor(max_workers=self.thread_count)
        tasks = []
        for resource_type in ALL_RESOURCES_WITH_METRICS:
            mors = self.infrastructure_cache.get_mors(resource_type)
            if not mors:
                continue
            counters = self.metrics_metadata_cache.get_metadata(resource_type)
            metric_ids = []
            for counter_key, metric_name in iteritems(counters):
                instance = ""
                if should_collect_per_instance_values(metric_name, resource_type):
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
                    tasks.append(pool_executor.submit(lambda q: self.api.query_metrics(q), query_specs))

        # TODO: ugly but works
        t0 = time.time()
        while tasks:
            finished_tasks = []
            for task in tasks:
                if task.done():
                    self.submit_metrics_callback(task)
                    finished_tasks.append(task)

            for task in finished_tasks:
                tasks.remove(task)
            time.sleep(0.1)

        pool_executor.shutdown()
        print("Metric collection: {}".format(time.time() - t0))

    def make_batch(self, mors, metric_ids, resource_type):
        """Iterates over mor and generate batches with a fixed number of metrics to query.
        Querying multiple resource types in the same call is error prone if we query a cluster metric. Indeed,
        cluster metrics result in an unpredicatable number of internal metric queries which all count towards
        max_query_metrics. Therefore often collecting a single cluster metric can make the whole call to fail. That's
        why we should never batch cluster metrics with anything else.
        """

        batch = defaultdict(list)
        batch_size = 0
        # Safeguard, let's avoid collecting multiple resources in the same call
        mors = [m for m in mors if type(m) == resource_type]

        if resource_type == vim.ClusterComputeResource:
            # Cluster metrics are unpredictable and a single one can reach the limit. Always collect them one by one.
            max_batch_size = 1
        elif resource_type in REALTIME_RESOURCES or self.max_historical_metrics < 0:
            # No limitation regarding `max_query_metrics` on vCenter side.
            max_batch_size = self.batch_morlist_size
        else:
            # Collection is limited by the value of `max_query_metrics` (aliased to self.max_historical_metrics)
            max_batch_size = min(self.batch_morlist_size, self.max_historical_metrics)

        for m in mors:
            for metric in metric_ids:
                if batch_size == max_batch_size:
                    yield batch
                    batch = defaultdict(list)
                    batch_size = 0
                batch[m].append(metric)
                batch_size += 1
        yield batch

    def submit_external_host_tags(self):
        """Send external host tags to the Datadog backend. This can only be done for a REALTIME instance because
        only VMs and Hosts appear as 'datadog hosts'."""
        external_host_tags = []
        hosts = self.infrastructure_cache.get_mors(vim.HostSystem)
        vms = self.infrastructure_cache.get_mors(vim.VirtualMachine)

        for mor in chain(hosts, vms):
            # Note: some mors have a None hostname
            mor_props = self.infrastructure_cache.get_mor_props(mor)
            hostname = mor_props.get('hostname')
            if hostname:
                # TODO: Implement https://github.com/DataDog/integrations-core/pull/5201
                external_host_tags.append((hostname, {self.__NAMESPACE__: mor_props['tags']}))

        self.set_external_tags(external_host_tags)

    def collect_events(self):
        try:
            new_events = self.api.get_new_events(start_time=self.latest_event_query)

            self.log.debug("Got %s new events from vCenter event manager", len(new_events))
            for event in new_events:
                normalized_event = VSphereEvent(event, self.event_config, self.base_tags)
                # Can return None if the event if filtered out
                event_payload = normalized_event.get_datadog_payload()
                if event_payload is not None:
                    self.event(event_payload)

        except Exception as e:
            # Don't get stuck on a failure to fetch an event
            # Ignore them for next pass
            self.log.warning("Unable to fetch Events %s", e)

        self.latest_event_query = self.api.get_latest_event_timestamp() + timedelta(seconds=1)

    def check(self, _):
        if self.api is None:
            self.api = VSphereAPI(self.instance)

        self.max_historical_metrics = self.instance.get("max_query_metrics", self.api.get_max_query_metrics())
        self.max_historical_metrics = 20

        if self.metrics_metadata_cache.is_expired():
            with self.metrics_metadata_cache.update():
                t0 = time.time()
                self.refresh_metrics_metadata_cache()
                print("Metadata: {}".format(time.time() - t0))

        if self.infrastructure_cache.is_expired():
            with self.infrastructure_cache.update():
                t0 = time.time()
                self.refresh_infrastructure_cache()
                print("Infra: {}".format(time.time() - t0))
            if self.collection_type == 'realtime':
                self.submit_external_host_tags()

        t0 = time.time()
        self.collect_metrics()
        print("Total collect_metrics: {}".format(time.time() - t0))
