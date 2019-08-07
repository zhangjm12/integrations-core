# (C) Datadog, Inc. 2018
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
import threading
import time

from six import iteritems

from datadog_checks.vsphere.errors import MetadataNotFoundError, MorNotFoundError


class VsphereCache:
    """
    Wraps configuration and status for the Morlist and Metadata caches.
    CacheConfig is threadsafe and can be used from different workers in the
    threading pool.
    """

    def __init__(self, interval):
        self._lock = threading.RLock()
        self.last_ts = 0
        self.interval = interval

    def clear(self):
        """
        Reset the config object to its initial state
        """
        self.last_ts = 0
        self.interval = None

    def should_refresh_cache(self):
        elapsed = time.time() - self.last_ts
        return elapsed > self.interval


class MetadataCache(VsphereCache):
    """
    Implements a thread safe storage for metrics metadata.
    For each instance key the cache maps: counter ID --> metric name, unit
    """

    def __init__(self, interval):
        super(MetadataCache, self).__init__(interval)
        self._metadata = {}

    def __contains__(self, counter_id):
        """
        Return whether a counter_id is present for a given instance key.
        If the key is not in the cache, raises a KeyError.
        """
        with self._lock:
            return counter_id in self._metadata

    def __getitem__(self, item):
        with self._lock:
            if item not in self._metadata:
                raise MetadataNotFoundError("No metadata for counter id '{}' found in the cache.".format(item))
            return self._metadata[item]

    def __setitem__(self, key, value):
        with self._lock:
            self._metadata[key] = value

    def set_metadata(self, metadata):
        """
        Store the metadata for the given instance key.
        """
        with self._lock:
            self._metadata = metadata

    def get_metric_ids(self):
        """
        Return the list of metric IDs to collect for the given instance key
        If the key is not in the cache, raises a KeyError.
        """
        with self._lock:
            return self._metadata.keys()
        

class MorCache(VsphereCache):
    """
    Implements a thread safe storage for Mor objects.
    The cache maps: mor_name --> mor_dict_object
    """

    def __init__(self, interval):
        super(MorCache, self).__init__(interval)
        self._mors = {}

    def __setitem__(self, key, value):
        with self._lock:
            self._mors[key] = value
            self._mors[key]['creation_time'] = time.time()

    def __getitem__(self, item):
        with self._lock:
            if item not in self._mors:
                raise MorNotFoundError("Mor object '{}' is not in the cache.".format(item))
            return self._mors[item]

    def iteritems(self):
        with self._lock:
            return iteritems(self._mors)

    def is_empty(self):
        with self._lock:
            return len(self._mors) > 0

    def size(self):
        """
        Return how many Mor objects are stored for the given instance.
        If the key is not in the cache, raises a KeyError.
        """
        with self._lock:
            return len(self._mors)

    def set_metrics(self, mor_name, metrics):
        """
        Store a list of metric identifiers for the given instance key and Mor
        object name.
        If the key is not in the cache, raises a KeyError.
        If the Mor object is not in the cache, raises a MorNotFoundError
        """
        with self._lock:
            if mor_name not in self._mors:
                raise MorNotFoundError("Mor object '{}' is not in the cache.".format(mor_name))
            self._mors[mor_name]['metrics'] = metrics

    def mors_batch(self, batch_size):
        """
        Generator returning as many dictionaries containing `batch_size` Mor
        objects as needed to iterate all the content of the cache. This has
        to be iterated twice, like:

            for batch in cache.mors_batch('key', 100):
                for name, mor in batch:
                    # use the Mor object here
        """
        with self._lock:
            if self._mors is None:
                yield {}

            mor_names = list(self._mors)
            mor_names.sort()
            total = len(mor_names)
            for idx in range(0, total, batch_size):
                names_chunk = mor_names[idx:min(idx + batch_size, total)]
                yield {name: self._mors[name] for name in names_chunk}

    def purge(self, ttl):
        """
        Remove all the items in the cache for the given key that are older than
        ttl seconds.
        """
        mors_to_purge = []
        now = time.time()
        with self._lock:
            # Don't change the dict during iteration!
            # First collect the names of the Mors to remove...
            for name, mor in iteritems(self._mors):
                age = now - mor['creation_time']
                if age > ttl:
                    mors_to_purge.append(name)

            # ...then actually remove the Mors from the cache.
            for name in mors_to_purge:
                del self._mors[name]

