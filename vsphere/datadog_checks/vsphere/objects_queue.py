# (C) Datadog, Inc. 2010-2017
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
import threading


class ObjectsQueue:
    """
    Implements a queue to store Mor objects of any type for each instance.
    Objects are fill once in batch and then extracted one by one.
    The queue is thread safe.
    """

    def __init__(self):
        self._objects_queue = {}
        self._lock = threading.RLock()

    def fill(self, mor_dict):
        """
        Set a dict mapping (resource_type --> objects[]) for a given key
        """
        with self._lock:
            self._objects_queue = mor_dict

    #def contains(self, key):
    #    with self._lock:
    #        return key in self._objects_queue

    def size(self, resource_type):
        """
        Return the size of the queue for a given key and resource type.
        If the key is not in the cache, this will raise a KeyError.
        """
        with self._lock:
            return len(self._objects_queue.get(resource_type, []))

    def pop(self, resource_type):
        """
        Extract an object from the list.
        If the key is not in the cache, this will raise a KeyError.
        If the list is empty, method will return None
        """
        with self._lock:
            objects = self._objects_queue.get(resource_type, [])
            return objects.pop() if objects else None
