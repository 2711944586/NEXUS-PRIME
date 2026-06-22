class EventHandlerRegistry:
    """Registry for mapping domain event types to handler callables."""

    def __init__(self, handlers=None):
        self._handlers = {}
        if handlers:
            self.register_many(handlers)

    def register(self, event_type, handler):
        handlers = self._handlers.setdefault(event_type, [])
        if handler not in handlers:
            handlers.append(handler)
        return handler

    def register_many(self, handlers_by_event_type):
        for event_type, handlers in handlers_by_event_type.items():
            for handler in handlers:
                self.register(event_type, handler)
        return self

    def handlers_for(self, event_type):
        return tuple(self._handlers.get(event_type, ()))

    def all(self):
        return {event_type: tuple(handlers) for event_type, handlers in self._handlers.items()}

    def apply_to_bus(self, bus):
        for event_type, handlers in self._handlers.items():
            registered = set(bus.handlers_for(event_type))
            for handler in handlers:
                if handler not in registered:
                    bus.subscribe(event_type, handler)
                    registered.add(handler)
        return bus
