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

import sys
from numbers import Number
from collections import Set, Mapping, deque
from types import ModuleType, FunctionType
from gc import get_referents

try: # Python 2
    zero_depth_bases = (basestring, Number, xrange, bytearray)
    iteritems = 'iteritems'
except NameError: # Python 3
    zero_depth_bases = (str, bytes, Number, range, bytearray)
    iteritems = 'items'


def getsize(obj_0):
    """Recursively iterate to sum size of object & members."""
    _seen_ids = set()
    def inner(obj):
        obj_id = id(obj)
        if obj_id in _seen_ids:
            return 0
        _seen_ids.add(obj_id)
        size = sys.getsizeof(obj)
        if isinstance(obj, zero_depth_bases):
            pass  # bypass remaining control flow and return
        elif isinstance(obj, (tuple, list, Set, deque)):
            size += sum(inner(i) for i in obj)
        elif isinstance(obj, Mapping) or hasattr(obj, iteritems):
            size += sum(inner(k) + inner(v) for k, v in getattr(obj, iteritems)())
        # Check for custom object instances - may subclass above too
        if hasattr(obj, '__dict__'):
            size += inner(vars(obj))
        if hasattr(obj, '__slots__'): # can have __slots__ with __dict__
            size += sum(inner(getattr(obj, s)) for s in obj.__slots__ if hasattr(obj, s))
        return size
    return inner(obj_0)

# Custom objects know their class.
# Function objects seem to know way too much, including modules.
# Exclude modules as well.
BLACKLIST = type, ModuleType, FunctionType


def getsize2 (obj):
    """sum size of object & members."""
    if isinstance(obj, BLACKLIST):
        raise TypeError('getsize() does not take argument of type: '+ str(type(obj)))
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
