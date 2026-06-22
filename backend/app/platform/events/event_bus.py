class EventBus:
    def __init__(self):
        self._handlers = {}

    def subscribe(self, event_type, handler):
        self._handlers.setdefault(event_type, []).append(handler)
        return handler

    def handlers_for(self, event_type):
        return tuple(self._handlers.get(event_type, ()))

    def publish(self, event):
        for handler in self.handlers_for(event.event_type):
            handler(event)


event_bus = EventBus()
