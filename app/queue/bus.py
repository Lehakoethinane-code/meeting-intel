import json
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from ..config import get_settings

settings = get_settings()


def enqueue_job(drive_item_id: str, drive_id: str) -> None:
    payload = json.dumps({"drive_item_id": drive_item_id, "drive_id": drive_id})
    with ServiceBusClient.from_connection_string(settings.servicebus_connection_string) as client:
        with client.get_queue_sender(settings.servicebus_queue_name) as sender:
            sender.send_messages(ServiceBusMessage(payload))


def receive_loop(handler) -> None:
    """Blocking consumer. Service Bus gives us DLQ + retry for free — on unhandled
    error we abandon (redelivery); after max delivery count it dead-letters."""
    with ServiceBusClient.from_connection_string(settings.servicebus_connection_string) as client:
        with client.get_queue_receiver(settings.servicebus_queue_name, max_wait_time=30) as receiver:
            for msg in receiver:
                try:
                    payload = json.loads(str(msg))
                    handler(payload["drive_item_id"], payload["drive_id"])
                    receiver.complete_message(msg)
                except Exception:
                    receiver.abandon_message(msg)
                    raise
