# (C) Datadog, Inc. 2020-present
# All rights reserved
# Licensed under a 3-clause BSD style license (see LICENSE)
from datadog_checks.base.stubs.aggregator import AggregatorStub
from datadog_checks.confluent_platform import ConfluentPlatformCheck


BROKER_GAUGE_METRICS = [
    'kafka.cluster.at_min_isr',
    'kafka.cluster.caught_up_replicas_count',
    'kafka.cluster.in_sync_replicas_count',
    'kafka.cluster.is_not_caught_up',
    'kafka.cluster.last_stable_offset_lag',
    'kafka.cluster.observer_replicas_count',
    'kafka.cluster.replicas_count',
    'kafka.cluster.under_min_isr',
    'kafka.cluster.under_replicated',
    'kafka.controller.active_controller_count',
    'kafka.controller.controller_state',
    'kafka.controller.event_queue_size',
    'kafka.controller.global_partition_count',
    'kafka.controller.global_topic_count',
    'kafka.controller.offline_partitions_count',
    'kafka.controller.preferred_replica_imbalance_count',
    'kafka.controller.queue_size',
    'kafka.controller.replicas_ineligible_to_delete_count',
    'kafka.controller.replicas_to_delete_count',
    'kafka.controller.topics_ineligible_to_delete_count',
    'kafka.controller.topics_to_delete_count',
    'kafka.controller.total_queue_size',
    'kafka.coordinator.group.num_groups',
    'kafka.coordinator.group.num_groups_completing_rebalance',
    'kafka.coordinator.group.num_groups_dead',
    'kafka.coordinator.group.num_groups_empty',
    'kafka.coordinator.group.num_groups_preparing_rebalance',
    'kafka.coordinator.group.num_groups_stable',
    'kafka.coordinator.group.num_offsets',
    'kafka.coordinator.transaction.log_append_retry_queue_size',
    'kafka.coordinator.transaction.unknown_destination_queue_size',
    'kafka.log.cleaner_recopy_percent',
    'kafka.log.dead_thread_count',
    'kafka.log.log_directory_offline',
    'kafka.log.log_end_offset',
    'kafka.log.log_start_offset',
    'kafka.log.max_buffer_utilization_percent',
    'kafka.log.max_clean_time_secs',
    'kafka.log.max_compaction_delay_secs',
    'kafka.log.max_dirty_percent',
    'kafka.log.num_log_segments',
    'kafka.log.offline_log_directory_count',
    'kafka.log.size',
    'kafka.log.tier_size',
    'kafka.log.time_since_last_run_ms',
    'kafka.log.total_size',
    'kafka.log.uncleanable_bytes',
    'kafka.log.uncleanable_partitions_count',
    'kafka.network.control_plane_expired_connections_killed_count',
    'kafka.network.control_plane_network_processor_avg_idle_percent',
    'kafka.network.expired_connections_killed_count',
    'kafka.network.idle_percent',
    'kafka.network.memory_pool_available',
    'kafka.network.memory_pool_used',
    'kafka.network.network_processor_avg_idle_percent',
    'kafka.network.request_queue_size',
    'kafka.network.response_queue_size',
    'kafka.server.at_min_isr_partition_count',
    'kafka.server.broker_state',
    'kafka.server.dead_thread_count',
    'kafka.server.failed_partitions_count',
    'kafka.server.leader_count',
    'kafka.server.max_lag',
    'kafka.server.min_fetch_rate',
    'kafka.server.not_caught_up_partition_count',
    'kafka.server.num_delayed_operations',
    'kafka.server.num_incremental_fetch_partitions_cached',
    'kafka.server.num_incremental_fetch_sessions',
    'kafka.server.offline_replica_count',
    'kafka.server.partition_count',
    'kafka.server.purgatory_size',
    'kafka.server.under_min_isr_partition_count',
    'kafka.server.under_replicated_partitions',
    'kafka.server.yammer_metrics_count',
]


def test_check(aggregator):
    # type: (AggregatorStub) -> None
    instance = {
        'host': 'localhost',
        'port': '31001',
    }
    check = ConfluentPlatformCheck('confluent_platform', {}, [instance])
    check.check(instance)

    tags = ['topic:_confluent-controlcenter-5-4-0-1-MetricsAggregateStore-repartition', 'partition:0']
    aggregator.assert_metric('kafka.log.log_end_offset', 1665161, tags)

    for m in BROKER_GAUGE_METRICS:
        aggregator.assert_metric(m)

    aggregator.assert_all_metrics_covered()
