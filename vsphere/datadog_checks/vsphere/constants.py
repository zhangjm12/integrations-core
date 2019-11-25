from pyVmomi import vim  # pylint: disable=E0611


VM_METRICS = {
    'cpu.costop.sum',
    'cpu.demand.avg',
    'cpu.demandEntitlementRatio.latest',
    'cpu.entitlement.latest',
    'cpu.idle.sum',
    'cpu.latency.avg',
    'cpu.maxlimited.sum',
    'cpu.overlap.sum',
    'cpu.readiness.avg',
    'cpu.ready.sum',
    'cpu.run.sum',
    'cpu.swapwait.sum',
    'cpu.system.sum',
    'cpu.usage.avg',
    'cpu.usage.min',
    'cpu.usage.max',
    'cpu.usage.raw',  # Are you even a thing?
    'cpu.usagemhz.avg',
    'cpu.usagemhz.min',
    'cpu.usagemhz.max',
    'cpu.usagemhz.raw',  # Are you even a thing?
    'cpu.used.sum',
    'cpu.wait.sum'
}

HOST_METRICS = {}
DATACENTER_METRICS = {}
DATASTORE_METRICS = {}
CLUSTER_METRICS = {}

ALLOWED_METRICS_FOR_MOR = {
    vim.VirtualMachine: VM_METRICS,
    vim.HostSystem: HOST_METRICS,
    vim.Datacenter: DATACENTER_METRICS,
    vim.Datastore: DATASTORE_METRICS,
    vim.ClusterComputeResource: CLUSTER_METRICS
}
