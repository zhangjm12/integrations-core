# (C) Datadog, Inc. 2019
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)
import functools
import ssl

from pyVim import connect
from pyVmomi import vim, vmodl  # pylint: disable=E0611

from datadog_checks.base import is_affirmative, ensure_unicode
from datadog_checks.vsphere.utils import smart_retry, getsize


ALL_RESOURCES = [vim.VirtualMachine, vim.HostSystem, vim.Datacenter, vim.Datastore, vim.ClusterComputeResource, vim.ComputeResource, vim.Folder]
BATCH_COLLETOR_SIZE = 500


class VSphereAPI(object):
    def __init__(self, instance):
        self.host = instance['host']
        self.username = instance['username']
        self.password = instance['password']
        self.ssl_verify = is_affirmative(instance.get('ssl_verify', True))
        self.ssl_capath = instance.get('ssl_capath')
        self._conn = self.smart_connect()

    def smart_connect(self):
        context = None
        if not self.ssl_verify:
            context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            context.verify_mode = ssl.CERT_NONE
        elif self.ssl_capath:
            context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(capath=self.ssl_capath)

        try:
            # Object returned by SmartConnect is a ServerInstance
            # https://www.vmware.com/support/developer/vc-sdk/visdk2xpubs/ReferenceGuide/vim.ServiceInstance.html
            conn = connect.SmartConnect(
                host=self.host,
                user=self.username,
                pwd=self.password,
                sslContext=context,
            )
            # FIXME: Sometimes the connection can be in an unhealthy state where CurrentTime works
            # FIXME: but not other kind of requests.
            conn.CurrentTime()
        except Exception as e:
            err_msg = "Connection to {} failed: {}".format(ensure_unicode(self.host), e)
            raise ConnectionError(err_msg)

        return conn

    @smart_retry
    def get_perf_counter_by_level(self, collection_level):
        return self._conn.content.perfManager.QueryPerfCounterByLevel(collection_level)

    @smart_retry
    def get_infrastructure(self):
        """

        :return: {
            'vim.VirtualMachine-VM0': {
              'name': 'VM-0',
              ...
            }
            ...
        }
        """
        content = self._conn.content
        view_ref = content.viewManager.CreateContainerView(content.rootFolder, ALL_RESOURCES, True)
        # Object used to query MORs as well as the attributes we require in one API call
        # See https://code.vmware.com/apis/358/vsphere#/doc/vmodl.query.PropertyCollector.html
        collector = content.propertyCollector

        # Specify the root object from where we collect the rest of the objects
        obj_spec = vmodl.query.PropertyCollector.ObjectSpec()
        obj_spec.obj = view_ref
        obj_spec.skip = True

        # Specify the attribute of the root object to traverse to obtain all the attributes
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec()
        traversal_spec.path = "view"
        traversal_spec.skip = False
        traversal_spec.type = view_ref.__class__
        obj_spec.selectSet = [traversal_spec]

        property_specs = []
        # Specify which attributes we want to retrieve per object
        for resource in ALL_RESOURCES:
            property_spec = vmodl.query.PropertyCollector.PropertySpec()
            property_spec.type = resource
            property_spec.pathSet = ["name", "parent", "customValue"]
            if resource == vim.VirtualMachine:
                property_spec.pathSet.append("runtime.powerState")
                property_spec.pathSet.append("runtime.host")
                property_spec.pathSet.append("guest.hostName")
            property_specs.append(property_spec)

        # Create our filter spec from the above specs
        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = [obj_spec]
        filter_spec.propSet = property_specs

        retr_opts = vmodl.query.PropertyCollector.RetrieveOptions()
        # To limit the number of objects retrieved per call.
        # If batch_collector_size is 0, collect maximum number of objects.
        retr_opts.maxObjects = BATCH_COLLETOR_SIZE

        # Collect the objects and their properties
        res = collector.RetrievePropertiesEx([filter_spec], retr_opts)
        mors = res.objects
        # Results can be paginated
        while res.token is not None:
            res = collector.ContinueRetrievePropertiesEx(res.token)
            mors.extend(res.objects)

        infrastucture_data = {
            mor.obj: {
                prop.name: prop.val for prop in mor.propSet
            }
            for mor in mors if mor.propSet
        }

        rootFolder = self._conn.content.rootFolder
        infrastucture_data[rootFolder] = {"name": rootFolder.name, "parent": None}
        return infrastucture_data
