from pyVmomi import vim  # pylint: disable=E0611
# https://code.vmware.com/apis/358/vsphere/doc/cpu_counters.html

"""TODO:
cluster_services ? (seems like cluster level, hard to replicate, unsure if useful)
host-based replication ? (VM and Hosts, probably not useful)
management agent ? (consumption of hostd and  vpxd, potentially useful, TBD: what is the instance field?)
network
power
resource scheduler

"""
VM_METRICS = {
    'cpu.costop.sum',
    'cpu.demand.avg',
    'cpu.demandEntitlementRatio.latest',
    'cpu.entitlement.latest',
    'cpu.latency.avg',
    'cpu.readiness.avg',
    'cpu.ready.sum',
    'cpu.swapwait.sum',
    'cpu.usagemhz.avg',
    'cpu.usagemhz.min',
    'cpu.usagemhz.max',
    'cpu.usagemhz.raw',  # Are you even a thing?
    'cpu.wait.sum',

    'mem.active.avg',
    'mem.active.min',
    'mem.active.max',
    'mem.active.raw',
    'mem.activewrite.avg',
    'mem.compressed.avg',
    'mem.compressionRate.avg',
    'mem.consumed.avg',
    'mem.consumed.min',
    'mem.consumed.max',
    'mem.consumed.raw',
    'mem.decompressionRate.avg',
    'mem.entitlement.avg',
    'mem.granted.avg',
    'mem.granted.min',
    'mem.granted.max',
    'mem.granted.raw',
    'mem.latency.avg',

    # Have per core data
    'cpu.idle.sum',
    'cpu.maxlimited.sum',
    'cpu.overlap.sum',
    'cpu.run.sum',
    'cpu.system.sum',
    'cpu.usage.avg',
    'cpu.usage.min',
    'cpu.usage.max',
    'cpu.usage.raw',  # Are you even a thing?
    'cpu.used.sum'
}

HOST_METRICS = {
    'cpu.costop.sum',
    'cpu.demand.avg',
    'cpu.latency.avg',
    'cpu.readiness.avg',
    'cpu.ready.sum',
    'cpu.reservedCapacity.avg',
    'cpu.swapwait.sum',
    'cpu.totalCapacity.avg',
    'cpu.usagemhz.avg',
    'cpu.usagemhz.min',
    'cpu.usagemhz.max',
    'cpu.usagemhz.raw',  # Are you even a thing?
    'cpu.wait.sum',

    'mem.active.avg',
    'mem.active.min',
    'mem.active.max',
    'mem.active.raw',
    'mem.activewrite.avg',
    'mem.compressed.avg',
    'mem.compressionRate.avg',
    'mem.consumed.avg',
    'mem.consumed.min',
    'mem.consumed.max',
    'mem.consumed.raw'
    'mem.decompressionRate.avg',
    'mem.granted.avg',
    'mem.granted.min',
    'mem.granted.max',
    'mem.granted.raw',
    'mem.heap.avg',
    'mem.heap.min',
    'mem.heap.max',
    'mem.heap.raw',
    'mem.heapfree.avg',
    'mem.heapfree.min',
    'mem.heapfree.max',
    'mem.heapfree.raw',
    'mem.latency.avg',
    # Have per-core data
    'cpu.coreUtilization.avg',
    'cpu.coreUtilization.min',
    'cpu.coreUtilization.max',
    'cpu.coreUtilization.raw',  # ?
    'cpu.idle.sum',
    'cpu.usage.avg',
    'cpu.usage.min',
    'cpu.usage.max',
    'cpu.usage.raw',  # Are you even a thing?
    'cpu.used.sum',
    'cpu.utilization.avg',
    'cpu.utilization.min',
    'cpu.utilization.max',
    'cpu.utilization.raw',
}



DATACENTER_METRICS = {}
DATASTORE_METRICS = {
    'disk.used.latest'
}
CLUSTER_METRICS = {}

ALLOWED_METRICS_FOR_MOR = {
    vim.VirtualMachine: VM_METRICS,
    vim.HostSystem: HOST_METRICS,
    vim.Datacenter: DATACENTER_METRICS,
    vim.Datastore: DATASTORE_METRICS,
    vim.ClusterComputeResource: CLUSTER_METRICS
}


def should_collect_per_instance_values(metric_name):
    if metric_name.startswith('cpu.us'):
        return True
    elif metric_name.startswith('disk.used.latest'):
        return True
    return False


def get_mapped_instance_tag(metric_name):
    if metric_name.startswith('cpu'):
        return 'cpu_core'
    return 'instance'


