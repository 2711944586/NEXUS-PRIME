"""Domain event platform primitives."""

from .dispatcher import EventDispatcher, event_dispatcher
from .event import DomainEventMessage
from .event_bus import EventBus, event_bus
from .handlers import default_handler_registry, register_default_handlers
from .outbox import Outbox, outbox
from .registry import EventHandlerRegistry

__all__ = [
    "DomainEventMessage",
    "EventBus",
    "EventDispatcher",
    "EventHandlerRegistry",
    "Outbox",
    "default_handler_registry",
    "event_bus",
    "event_dispatcher",
    "outbox",
    "register_default_handlers",
]
