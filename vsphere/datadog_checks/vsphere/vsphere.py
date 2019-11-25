# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
from collections import namedtuple, defaultdict

from six import iteritems
from pyVmomi import vim  # pylint: disable=E0611

from datadog_checks.base import AgentCheck, is_affirmative, ensure_unicode
from datadog_checks.vsphere.api import VSphereAPI
from datadog_checks.vsphere.cache import InfrastructureCache, MetricsMetadataCache
from datadog_checks.vsphere.constants import ALLOWED_METRICS_FOR_MOR
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

        self.collection_level = self.instance.get("collection_level", 1)
        self.collection_type = self.instance.get("collection_type", "realtime")
        self.resource_filters = self.instance.get("resource_filters", {})
        self.metric_filters = self.instance.get("metric_filters", {})
        self.use_guest_hostname = self.instance.get("use_guest_hostname", False)

        self.batch_morlist_size = self.instance.get("batch_morlist_size", 50)
        self.max_historical_metrics = self.instance.get("max_historical_metrics", 64)
        self.collected_resource_types = REALTIME_RESOURCES if self.collection_type == 'realtime' else HISTORICAL_RESOURCES

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

            hostname = None
            tags = []

            if isinstance(mor, vim.VirtualMachine):
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
                    hostname = properties.get("guest.hostName", properties.get("name", "unknown"))
                else:
                    hostname = properties.get("name", "unknown")
            elif isinstance(mor, vim.HostSystem):
                hostname = properties.get("name", "unknown")

            mor_type = MOR_TYPE_AS_STRING[type(mor)]
            tags.extend(get_parent_tags_recursively(mor, infrastucture_data))
            tags.append('vsphere_type:{}'.format(mor_type))

            mor_payload = {"tags": tags}
            if hostname:
                mor_payload['hostname'] = hostname

            self.infrastructure_cache.set_mor_data(mor, mor_payload)

    def collect_metrics_async(self, mors_batch):
        #self.api.collect_metrics(mors_batch)
        pass

    def collect_metrics(self):
        for resource_type in ALL_RESOURCES:
            mors = self.infrastructure_cache.get_mors(resource_type)

            for batch in self.make_batch(mors):

    def make_batch(self, mors):
        """All those mors must be of the same resource!!!!"""
        batch = {}
        hist_metrics_count = 0

        for mor in mors:
            if mor

    def check(self, _):
        import time
        t = time.time()
        import pdb; pdb.set_trace()
        if self.metrics_metadata_cache.is_expired():
            self.metrics_metadata_cache.reset()
            self.refresh_metrics_metadata_cache()

        delta1 = time.time() - t
        if self.infrastructure_cache.is_expired():
            self.infrastructure_cache.reset()
            self.refresh_infrastructure_cache()

        self.collect_metrics()
        delta2 = time.time() - t
