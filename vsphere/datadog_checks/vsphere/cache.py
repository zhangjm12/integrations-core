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
        """
        Reset the config object to its initial state
        """
        with self._lock:
            self.last_ts = 0
            self.interval = None
            self._content = {}

    def is_expired(self):
        elapsed = time.time() - self.last_ts
        return elapsed > self.interval

    """def get(self, key, default=None):
        with self._lock:
            resource_type = MOR_TYPE_AS_STRING[type(key)]
            return self._content.get(key, default)

    def set(self, key, value):
        with self._lock:
            self._content[key] = value

    def contains(self, key):
        with self._lock:
            return key in self._content

    def size(self):
        with self._lock:
            return len(self._content)

    def keys(self):
        with self._lock:
            return self._content.keys()

    def update(self, data):
        with self._lock:
            return self._content.update(data)"""

class MetricsMetadataCache(VSphereCache):
    def get_metadata(self, resource_type):
        with self._lock:
            return self._content.get(resource_type)

    def set_metadata(self, resource_type, metadata):
        with self._lock:
            self._content[resource_type] = metadata


class InfrastructureCache(VSphereCache):
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
#
# class MetadataCache(VSphereCache):
#     """Implements a thread safe storage for metrics metadata.
#     For each instance key the cache maps: counter ID --> metric name, unit
#     """
#
#     def __init__(self, interval):
#         super(MetadataCache, self).__init__(interval)
#         self._metadata = {}
#
#     def set_metadata(self, metadata):
#         """
#         Store the metadata for the given instance key.
#         """
#         with self._lock:
#             self._metadata = metadata
#
#     def get_metric_ids(self):
#         """
#         Return the list of metric IDs to collect for the given instance key
#         If the key is not in the cache, raises a KeyError.
#         """
#         with self._lock:
#             return self._metadata.keys()
#
#
# class MorCache(VSphereCache):
#     """
#     Implements a thread safe storage for Mor objects.
#     The cache maps: mor_name --> mor_dict_object
#     """
#
#     def __init__(self, interval):
#         super(MorCache, self).__init__(interval)
#         self._mors = {}
#
#     def __setitem__(self, key, value):
#         with self._lock:
#             self._mors[key] = value
#             self._mors[key]['creation_time'] = time.time()
#
#     def __getitem__(self, item):
#         with self._lock:
#             if item not in self._mors:
#                 raise MorNotFoundError("Mor object '{}' is not in the cache.".format(item))
#             return self._mors[item]
#
#     def iteritems(self):
#         with self._lock:
#             yield iteritems(self._mors)
#
#     def is_empty(self):
#         with self._lock:
#             return len(self._mors) > 0
#
#     def size(self):
#         """
#         Return how many Mor objects are stored for the given instance.
#         If the key is not in the cache, raises a KeyError.
#         """
#         with self._lock:
#             return len(self._mors)
#
#     def set_metrics(self, mor_name, metrics):
#         """
#         Store a list of metric identifiers for the given instance key and Mor
#         object name.
#         If the key is not in the cache, raises a KeyError.
#         If the Mor object is not in the cache, raises a MorNotFoundError
#         """
#         with self._lock:
#             if mor_name not in self._mors:
#                 raise MorNotFoundError("Mor object '{}' is not in the cache.".format(mor_name))
#             self._mors[mor_name]['metrics'] = metrics
#
#     def mors_batch(self, batch_size):
#         """
#         Generator returning as many dictionaries containing `batch_size` Mor
#         objects as needed to iterate all the content of the cache. This has
#         to be iterated twice, like:
#             for batch in cache.mors_batch('key', 100):
#                 for name, mor in batch:
#                     # use the Mor object here
#         """
#         with self._lock:
#             if self._mors is None:
#                 yield {}
#
#             mor_names = list(self._mors)
#             mor_names.sort()
#             total = len(mor_names)
#             for idx in range(0, total, batch_size):
#                 names_chunk = mor_names[idx:min(idx + batch_size, total)]
#                 yield {name: self._mors[name] for name in names_chunk}
#
#     def purge(self, ttl):
#         """
#         Remove all the items in the cache for the given key that are older than
#         ttl seconds.
#         """
#         mors_to_purge = []
#         now = time.time()
#         with self._lock:
#             # Don't change the dict during iteration!
#             # First collect the names of the Mors to remove...
#             for name, mor in iteritems(self._mors):
#                 age = now - mor['creation_time']
#                 if age > ttl:
#                     mors_to_purge.append(name)
#
#             # ...then actually remove the Mors from the cache.
#             for name in mors_to_purge:
#                 del self._mors[name]
