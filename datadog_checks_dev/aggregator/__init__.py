# (C) Datadog, Inc. 2018-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
print("__path__1", __path__)
print("__name__", __name__)
__path__ = __import__('pkgutil').extend_path(__path__, __name__)  # type: ignore

print("__path__2", __path__)
print("hello")
