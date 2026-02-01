# ADR-0003: Use Apache Kafka for Event Streaming

## Status

Accepted

## Context

The platform requires asynchronous communication between services for:
- Claim lifecycle events (submitted, verified, failed)
- Reputation transactions
- Challenge notifications
- Knowledge graph updates
- Audit logging

Requirements:
- At-least-once delivery guarantees
- Event replay capability for debugging/recovery
- High throughput for verification events
- Consumer group support for scaling
- Durable storage of events

Options considered:
1. **Apache Kafka** - Distributed streaming platform
2. **RabbitMQ** - Traditional message broker
3. **Redis Streams** - Lightweight streaming
4. **AWS SQS/SNS** - Managed, cloud-specific
5. **NATS** - Lightweight, cloud-native

## Decision

We will use **Apache Kafka** for event streaming between services.

## Rationale

1. **Durability**: Events are persisted to disk with configurable retention, enabling replay and audit trails

2. **High throughput**: Can handle millions of messages per second, suitable for high-frequency verification events

3. **Consumer groups**: Multiple consumers can process events in parallel with automatic partition assignment

4. **Ordering guarantees**: Messages within a partition maintain order, important for claim state transitions

5. **Schema registry**: Avro/Protobuf schemas prevent breaking changes between services

6. **Ecosystem**: Kafka Connect for integrations, ksqlDB for stream processing, extensive monitoring tools

7. **Event sourcing ready**: Foundation for future event-sourced architecture if needed

## Consequences

### Positive
- Reliable event delivery with replay capability
- Scales to very high message volumes
- Decouples services effectively
- Built-in partitioning for parallelism

### Negative
- Operational complexity (Zookeeper, though KRaft mode removes this)
- Higher resource requirements than simpler brokers
- Learning curve for developers new to Kafka

### Mitigations
- Use managed Kafka (Confluent Cloud, AWS MSK) in production
- Provide Kafka UI (AKHQ) for visibility
- Document common patterns in CONTRIBUTING.md
- Use KRaft mode to eliminate Zookeeper dependency

## Topic Design

| Topic | Partitions | Retention | Purpose |
|-------|------------|-----------|---------|
| claims.submitted | 12 | 7 days | New claims |
| claims.verified | 12 | 30 days | Verification results |
| verification.* | 6-12 | 1 day | Domain-specific queues |
| reputation.* | 6 | 30 days | Karma transactions |
| audit.events | 12 | 1 year | Audit trail |

## References

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Confluent Schema Registry](https://docs.confluent.io/platform/current/schema-registry/)
- [Kafka vs RabbitMQ](https://www.confluent.io/blog/kafka-vs-rabbitmq/)
