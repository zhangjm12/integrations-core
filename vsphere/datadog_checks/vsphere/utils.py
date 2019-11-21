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

MOR_TYPE_AS_STRING = {
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


def get_parent_tags_recursively(mor, infrastructure_data):
    """Go up the resources hierarchy from the given mor. Note that a host running a VM is not considered to be a
    parent of that VM.

    rootFolder(vim.Folder):
      - vm(vim.Folder):
          VM1-1
          VM1-2
      - host(vim.Folder):
          HOST1
          HOST2

    """
    mor_props = infrastructure_data.get(mor)
    parent = mor_props.get('parent')
    parent_props = infrastructure_data.get(parent, {})
    if parent:
        tags = []
        parent_name = ensure_unicode(parent_props.get('name', 'unknown'))
        if isinstance(parent, vim.HostSystem):
            tags.append('vsphere_host:{}'.format(parent_name))
        elif isinstance(parent, vim.Folder):
            tags.append('vsphere_folder:{}'.format(parent_name))
        elif isinstance(parent, vim.ComputeResource):
            if isinstance(parent, vim.ClusterComputeResource):
                tags.append('vsphere_cluster:{}'.format(parent_name))
            tags.append('vsphere_compute:{}'.format(parent_name))
        elif isinstance(parent, vim.Datacenter):
            tags.append('vsphere_datacenter:{}'.format(parent_name))

        parent_tags = get_parent_tags_recursively(parent, infrastructure_data)
        parent_tags.extend(tags)
        return parent_tags
    return []



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
