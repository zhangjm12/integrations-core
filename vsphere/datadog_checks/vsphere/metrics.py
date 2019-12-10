from pyVmomi import vim  # pylint: disable=E0611


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

HOST_METRICS_WITH_INSTANCE = {

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


