# (C) Datadog, Inc. 2020-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from datadog_checks.base import AgentCheck

import jpype
from jpype import java
from jpype import javax


class JmxClient(object):
    """
    Documentation:
    https://docs.oracle.com/javase/7/docs/api/javax/management/MBeanServer.html#getMBeanInfo(javax.management.ObjectName)
    """
    def __init__(self, config):
        host = config['host']
        port = config['port']
        self._connection = self._get_connection(host, port)

    def get_beans_name(self, queryFilter):
        query = javax.management.ObjectName(queryFilter)
        beans = self._connection.queryNames(query, None)
        return beans

    def get_bean_info(self, bean):
        return self._connection.getMBeanInfo(bean)

    def get_beans(self, queryFilter):
        query = javax.management.ObjectName(queryFilter)
        beans = self._connection.queryMBeans(query, None)
        return [Bean(b) for b in beans]

    def get_attribute(self, bean, attribute):
        return self._connection.getAttribute(bean, attribute)

    @staticmethod
    def _get_connection(host, port):
        url = "service:jmx:rmi:///jndi/rmi://{}:{}/jmxrmi".format(host, port)

        # TODO: Call jpype.shutdownJVM()
        jpype.startJVM(convertStrings=False)

        jhash = java.util.HashMap()
        jmxurl = javax.management.remote.JMXServiceURL(url)
        jmxsoc = javax.management.remote.JMXConnectorFactory.connect(jmxurl, jhash)
        connection = jmxsoc.getMBeanServerConnection()
        return connection


class Bean(object):
    def __init__(self, bean):
        self._bean = bean

        self.clazz = str(self._bean.getClassName())

        self._object_name = self._bean.getObjectName()

        self.name = str(self._object_name)
        self.domain = str(self._object_name.getDomain())
        self.name_properties = hashmap_to_dict(self._object_name.getKeyPropertyList())

    def __str__(self):
        return "Bean(clazz='{}', name='{}', domian='{}', name_properties='{}')".format(
            self.clazz, self.name, self.domain, self.name_properties)


def hashmap_to_dict(hashmap):
    props = {}
    for key in hashmap:
        props[str(key)] = str(hashmap[key])
    return props
