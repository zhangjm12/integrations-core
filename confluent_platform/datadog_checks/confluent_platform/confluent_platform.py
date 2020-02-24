# (C) Datadog, Inc. 2020-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from six import iteritems

from datadog_checks.base import AgentCheck

import jpype
from jpype import java
from jpype import javax

from . import utils
from .jmx_client import JmxClient, Bean


def gauge_processor(check, bean):
    # type: (ConfluentPlatformCheck, Bean) -> None
    # TODO: Why type: ConfluentPlatformCheck does not work ?

    metric_name = "{}.{}".format(bean.domain, utils.underscore(bean.name_properties['name']))

    tags = ["{}:{}".format(k, v) for k, v in iteritems(bean.name_properties) if k not in ['name', 'type']]

    raw_value = check.jmx._connection.getAttribute(bean._bean.getObjectName(), 'Value')
    try:
        value = float(raw_value)
    except TypeError as e:
        check.log.debug('Value is not a number: %s', e)
        print('The metric `{}` value `{}` is not a number: {}'.format(metric_name, raw_value, e))
    else:
        print("{} : {} : {}".format(metric_name, raw_value, tags))
        check.gauge(metric_name, value, tags=tags)


SUBMIT_PROCESSORS = {
    'com.yammer.metrics.reporting.JmxReporter$Gauge': gauge_processor,
}


class ConfluentPlatformCheck(AgentCheck):
    def __init__(self, *args, **kwargs):
        super(ConfluentPlatformCheck, self).__init__(*args, **kwargs)
        self.jmx = JmxClient(self.instance)

    def check(self, instance):
        beans = self.jmx.get_beans("kafka.*:*")

        for bean in list(beans):
            if bean.clazz in SUBMIT_PROCESSORS:
                SUBMIT_PROCESSORS[bean.clazz](self, bean)


            # info = self.connection.getMBeanInfo(javax.management.ObjectName(bean_name))
            # attrs = info.getAttributes()
            # for attr in list(attrs):
            #     print("    {}:{}".format(attr.getName(), attr.getDescription()))
