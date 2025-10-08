# /services/kafka_service.py
import json

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
DICTATION_TOPIC = "dictation_events"

producer = None
consumer = None


async def init_kafka():
    """初始化 Kafka 連線"""
    global producer, consumer
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    print("[Kafka] Producer connected")

    consumer = AIOKafkaConsumer(
        DICTATION_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="socketio_listener_group",
    )
    await consumer.start()
    print("[Kafka] Consumer connected")


async def send_event(topic: str, event: dict):
    """發送事件至 Kafka"""
    if not producer:
        raise RuntimeError("Kafka producer not initialized")
    await producer.send_and_wait(topic, event)
    print(f"[Kafka] Sent event: {event}")


async def consume_events():
    """持續監聽 Kafka Topic"""
    if not consumer:
        raise RuntimeError("Kafka consumer not initialized")
    async for msg in consumer:
        yield msg.topic, msg.value
