# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
from pyVmomi import vim

ALLOWED_FILTER_PROPERTIES = ['name', 'inventory_path']
EXTRA_FILTER_PROPERTIES_FOR_VMS = ['hostname', 'guest_hostname']

ALL_RESOURCES = [
    vim.VirtualMachine,
    vim.HostSystem,
    vim.Datacenter,
    vim.Datastore,
    vim.ClusterComputeResource,
    vim.ComputeResource,
    vim.Folder,
]
REALTIME_RESOURCES = [vim.VirtualMachine, vim.HostSystem]
HISTORICAL_RESOURCES = [vim.Datacenter, vim.Datastore, vim.ClusterComputeResource]
ALL_RESOURCES_WITH_METRICS = REALTIME_RESOURCES + HISTORICAL_RESOURCES

DEFAULT_BATCH_COLLECTOR_SIZE = 500
DEFAULT_BATCH_MORLIST_SIZE = 500
DEFAULT_MAX_QUERY_METRICS = 256
DEFAULT_THREAD_COUNT = 8
