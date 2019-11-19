# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
from collections import namedtuple

from six import iteritems
from pyVmomi import vim  # pylint: disable=E0611

from datadog_checks.base import AgentCheck, is_affirmative
from datadog_checks.vsphere.api import VSphereAPI
from datadog_checks.vsphere.cache import VSphereCache
from datadog_checks.vsphere.utils import format_metric_name, is_excluded_by_filters

REALTIME_RESOURCES = [vim.VirtualMachine, vim.HostSystem]
HISTORICAL_RESOURCES = [vim.Datacenter, vim.Datastore, vim.ClusterComputeResource]


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
        self.infrastructure_cache = VSphereCache(interval_sec=180)
        self.metrics_metadata_cache = VSphereCache(interval_sec=600)

        self.collection_level = self.instance.get("collection_level", 1)
        self.collection_type = self.instance.get("collection_type", "realtime")
        self.resource_filters = self.instance.get("resource_filters", {})
        self.metric_filters = self.instance.get("metric_filters", {})

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
        metadata = {}
        for counter in self.api.get_perf_counter_by_level(self.collection_level):
            metadata[counter.key] = {"name": format_metric_name(counter), "unit": counter.unitInfo.key}

        self.metrics_metadata_cache.update(metadata)
        # TODO: Understand how much data actually changes between check runs
        # Apparently only when the server restarts?
        # https://pubs.vmware.com/vsphere-50/index.jsp?topic=%2Fcom.vmware.wssdk.pg.doc_50%2FPG_Ch16_Performance.18.5.html

    def refresh_infrastructure_cache(self):
        infrastucture_data = self.api.get_infrastructure()

        for mor, properties in iteritems(infrastucture_data):
            if not isinstance(mor, tuple(self.collected_resource_types)):
                # Do nothing for the resource types we do not collect
                continue
            if is_excluded_by_filters(mor, properties, self.resource_filters):
                # The resource does not match the specified patterns
                continue

            mor_tags = []


    def check(self, _):
        if self.metrics_metadata_cache.should_refresh_cache():
            self.metrics_metadata_cache.reset()
            #self.refresh_metrics_metadata_cache()

        if self.infrastructure_cache.should_refresh_cache():
            self.infrastructure_cache.reset()
            self.refresh_infrastructure_cache()
