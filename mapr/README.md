# Agent Check: MapR

## Overview

This check monitors [MapR][1] through the Datadog Agent.

## Setup

Follow the instructions below to install and configure this check for an Agent running on a host.

### Installation

The MapR check is included in the [Datadog Agent][2] package. However, some additional installation steps are necessary.

1. Agent 6 uses Upstart or systemd to orchestrate the `datadog-agent` service. To configure the MapR Event Store for
Apache Kafka C Client, a `LD_LIBRARY_PATH` variable need to be set to `/opt/mapr/lib` in the service configuration files at the default locations of
`/etc/init/datadog-agent.conf` (Upstart) or `/lib/systemd/system/datadog-agent.service` (systemd). See documentation on [Upstart](14)
or [systemd](15) for more information on how to configure these settings.
2. Create a password for the `dd-agent` user, then add this user to every node of the cluster with the same `UID`/`GID` so it is recognized by MapR. See [Managing users and groups][10] for additional details.
3. Generate a [long-lived ticket][8] for the `dd-agent` user.


### Configuration
#### Metric collection

1. Edit the `mapr.d/conf.yaml` file, in the `conf.d/` folder at the root of your Agent's configuration directory to collect your MapR performance data. See the [sample mapr.d/conf.yaml][3] for all available configuration options.

2. [Restart the Agent][4].

#### Log collection

 MapR uses fluentD for logs. Use the [fluentd datadog plugin][11] to collect MapR logs.
 
### Validation

[Run the Agent's status subcommand][5] and look for `mapr` under the Checks section.

## Data Collected

### Metrics

See [metadata.csv][13] for a list of default metrics provided by this integration.

### Service Checks

The MapR check does not include any service checks.

### Events

The MapR check does not include any events.




## Troubleshooting

Need help? Contact [Datadog support][6].

[1]: https://mapr.com
[2]: https://docs.datadoghq.com/agent/autodiscovery/integrations
[3]: https://github.com/DataDog/integrations-core/blob/master/mapr/datadog_checks/mapr/data/conf.yaml.example
[4]: https://docs.datadoghq.com/agent/guide/agent-commands/?tab=agentv6#start-stop-and-restart-the-agent
[5]: https://docs.datadoghq.com/agent/guide/agent-commands/?tab=agentv6#agent-status-and-information
[6]: https://docs.datadoghq.com/help
[7]: https://mapr.com/docs/61/MapR_Streams/MapRStreamsPythonExample.html
[8]: https://mapr.com/docs/61/SecurityGuide/GeneratingServiceTicket.html
[9]: https://mapr.com/docs/60/MapR_Streams/MapRStreamCAPISetup.html
[10]: https://mapr.com/docs/61/AdministratorGuide/c-managing-users-and-groups.html
[11]: https://www.rubydoc.info/gems/fluent-plugin-datadog
[12]: https://mapr.com/docs/61/AdvancedInstallation/SettingUptheClient-install-mapr-client.html
[13]: https://github.com/DataDog/integrations-core/blob/master/mapr/metadata.csv
[14]: http://upstart.ubuntu.com/cookbook/#environment-variables
[15]: https://www.freedesktop.org/software/systemd/man/systemd.service.html#Command%20lines
