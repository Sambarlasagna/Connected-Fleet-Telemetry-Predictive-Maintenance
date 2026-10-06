"""
producer.py — Kafka producer for FleetGuard vehicle telemetry.

Sends one JSON message per vehicle per simulation tick to the
"vehicle-telemetry" Kafka topic.

Used by simulator/runner.py when Kafka is available.
Falls back silently if Kafka is not reachable (so local dev still works
without Docker Kafka running).
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TOPIC = os.getenv("KAFKA_TOPIC", "vehicle-telemetry")
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")

_producer = None
_kafka_unavailable = False  # Set to True after first failed connection attempt


def get_producer():
    """Get or create the Kafka producer singleton. Returns None if Kafka is unavailable."""
    global _producer, _kafka_unavailable
    if _kafka_unavailable:
        return None
    if _producer is not None:
        return _producer

    try:
        from kafka import KafkaProducer
        _producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8"),
            acks="all",
            retries=3,
            request_timeout_ms=5000,
            api_version_auto_timeout_ms=5000,
        )
        logger.info(f"[Kafka] Producer connected to {BOOTSTRAP_SERVERS}")
        return _producer
    except Exception as e:
        _kafka_unavailable = True  # Stop retrying on every tick
        logger.warning(f"[Kafka] Producer unavailable - running in direct-DB mode: {e}")
        return None


def send_telemetry(event: dict) -> bool:
    """
    Send a telemetry event to Kafka.

    Args:
        event: dict with keys: machine_id, timestamp, volt, rotate,
               pressure, vibration, scenario, degradation

    Returns:
        True if sent successfully, False if Kafka unavailable.
    """
    producer = get_producer()
    if producer is None:
        return False

    try:
        producer.send(
            topic=TOPIC,
            key=event["machine_id"],
            value=event,
        )
        return True
    except Exception as e:
        logger.warning(f"[Kafka] Send failed for machine {event.get('machine_id')}: {e}")
        return False


def flush():
    """Flush pending messages. Call after each simulation tick."""
    producer = get_producer()
    if producer:
        try:
            producer.flush(timeout=2)
        except Exception:
            pass


def close():
    """Close the producer cleanly on shutdown."""
    global _producer
    if _producer:
        try:
            _producer.close(timeout=5)
        except Exception:
            pass
        _producer = None
