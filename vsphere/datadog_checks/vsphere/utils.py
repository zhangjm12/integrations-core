import functools
import re
from pyVmomi import vim
from datadog_checks.base import ensure_unicode

SHORT_ROLLUP = {
    "average": "avg",
    "summation": "sum",
    "maximum": "max",
    "minimum": "min",
    "latest": "latest",
    "none": "raw",
}

RESOURCE_TO_CONFIG_MAPPING = {
    vim.HostSystem: 'host',
    vim.VirtualMachine: 'vm',
    vim.Datacenter: 'datacenter',
    vim.Datastore: 'datastore',
    vim.ClusterComputeResource: 'cluster'
}


def smart_retry(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        api_instance = args[0]
        try:
            return f(*args, **kwargs)
        except Exception:
            api_instance.smart_connect()
            return f(*args, **kwargs)
    return wrapper


def format_metric_name(counter):
    return "{}.{}.{}".format(
        ensure_unicode(counter.groupInfo.key),
        ensure_unicode(counter.nameInfo.key),
        ensure_unicode(SHORT_ROLLUP[str(counter.rollupType)]),
    )


def is_excluded_by_filters(mor, properties, resource_filters):
    if isinstance(mor, vim.HostSystem):
        resource_type = 'host'
    elif isinstance(mor, vim.VirtualMachine):
        resource_type = 'vm'
    elif isinstance(mor, vim.Datacenter):
        resource_type = 'datacenter'
    elif isinstance(mor, vim.Datastore):
        resource_type = 'datastore'
    elif isinstance(mor, vim.ClusterComputeResource):
        resource_type = 'cluster'
    else:
        # log something
        return True

    regex = resource_filters.get(resource_type)
    mor_name = properties.get("name", "")
    if not regex:
        # No filter specified for this resource type, collect everything
        return False
    match = re.search(regex, mor_name)  # FIXME: Should we use re.IGNORECASE like legacy?

    return not match


def get_tags_for_mor(infrastructure_data, mor, properties):
    tags = []
    if isinstance(mor, vim.VirtualMachine):
        vsphere_type = 'vsphere_type:vm'
        mor_type = "vm"
        power_state = properties.get("runtime.powerState")

        host_mor = properties.get("runtime.host")
        host_props = infrastructure_data.get(host_mor, {})
        hostname = ensure_unicode(host_props.get("name", "unknown"))
        tags.append('vsphere_host:{}'.format(hostname))
        tags = [
            'vsphere_type:vm',
            ''
        ]
    elif isinstance(obj, vim.HostSystem):
        vsphere_type = 'vsphere_type:host'
        vimtype = vim.HostSystem
        mor_type = "host"
    elif isinstance(obj, vim.Datastore):
        vsphere_type = 'vsphere_type:datastore'
        instance_tags.append(
            'vsphere_datastore:{}'.format(ensure_unicode(properties.get("name", "unknown")))
        )
        hostname = None
        vimtype = vim.Datastore
        mor_type = "datastore"
    elif isinstance(obj, vim.Datacenter):
        vsphere_type = 'vsphere_type:datacenter'
        instance_tags.append(
            "vsphere_datacenter:{}".format(ensure_unicode(properties.get("name", "unknown")))
        )
        hostname = None
        vimtype = vim.Datacenter
        mor_type = "datacenter"
    elif isinstance(obj, vim.ClusterComputeResource):
        vsphere_type = 'vsphere_type:cluster'
        instance_tags.append("vsphere_cluster:{}".format(ensure_unicode(properties.get("name", "unknown"))))
        hostname = None
        vimtype = vim.ClusterComputeResource
        mor_type = "cluster"
    else:
        vsphere_type = None



import sys
from types import ModuleType, FunctionType
from gc import get_referents

# Custom objects know their class.
# Function objects seem to know way too much, including modules.
# Exclude modules as well.
BLACKLIST = type, ModuleType, FunctionType


def getsize(obj):
    """sum size of object & members."""
    if isinstance(obj, BLACKLIST):
        raise TypeError('getsize() does not take argument of type: ' + str(type(obj)))
    seen_ids = set()
    size = 0
    objects = [obj]
    while objects:
        need_referents = []
        for obj in objects:
            if not isinstance(obj, BLACKLIST) and id(obj) not in seen_ids:
                seen_ids.add(id(obj))
                size += sys.getsizeof(obj)
                need_referents.append(obj)
        objects = get_referents(*need_referents)
    return size
