# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
import threading
import time

from six import iteritems

#from datadog_checks.vsphere.errors import MetadataNotFoundError, MorNotFoundError
from datadog_checks.vsphere.utils import MOR_TYPE_AS_STRING


class VSphereCache(object):
    """
    Wraps configuration and status for the Morlist and Metadata caches.
    CacheConfig is threadsafe and can be used from different workers in the
    threading pool.
    """

    def __init__(self, interval_sec):
        self._lock = threading.Lock()
        self.last_ts = 0
        self.interval = interval_sec
        self._content = {}

    def reset(self):
        """Reset the cache object to its initial state
        """
        with self._lock:
            self.last_ts = 0
            self.interval = None
            self._content = {}

    def is_expired(self):
        elapsed = time.time() - self.last_ts
        return elapsed > self.interval


class MetricsMetadataCache(VSphereCache):
    """A VSphere cache dedicated to store the metrics metadata from a user environment.
    Data is stored like this:

    _content = {
        vim.HostSystem: {
            <COUNTER_KEY>: {
                name: <DD_METRIC_NAME>,
                unit: <METRIC_UNIT>
            },
            ...
        },
        vim.VirtualMachine: {...},
        ...
    }
    """
    def get_metadata(self, resource_type):
        with self._lock:
            return self._content.get(resource_type)

    def set_metadata(self, resource_type, metadata):
        with self._lock:
            self._content[resource_type] = metadata


class InfrastructureCache(VSphereCache):
    """A VSphere cache dedicated to store the infrastructure data from a user environment.
    Data is stored like this:

    _content = {
        vim.VirtualMachine: {
            <MOR_REFERENCE>: <MOR_PROPS>
        }

    }
    """
    def get_mor_props(self, mor, default=None):
        with self._lock:
            mor_type = type(mor)
            return self._content.get(mor_type, {}).get(mor, default)

    def get_mors(self, resource_type):
        with self._lock:
            return self._content.get(resource_type, {}).keys()

    def set_mor_data(self, mor, mor_data):
        with self._lock:
            mor_type = type(mor)
            if mor_type not in self._content:
                self._content[mor_type] = {}
            self._content[mor_type][mor] = mor_data
