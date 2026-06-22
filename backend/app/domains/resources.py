from importlib import import_module

from app.platform.crud.resource_registry import registry


DOMAIN_RESOURCE_MODULES = (
    ("app.domains.identity.resources", "identity_resources"),
    ("app.domains.master_data.resources", "master_data_resources"),
    ("app.domains.inventory.resources", "inventory_resources"),
    ("app.domains.sales.resources", "sales_resources"),
    ("app.domains.procurement.resources", "procurement_resources"),
    ("app.domains.finance.resources", "finance_resources"),
    ("app.domains.workflow.resources", "workflow_resources"),
    ("app.domains.reporting.resources", "reporting_resources"),
    ("app.domains.files.resources", "file_resources"),
    ("app.domains.content.resources", "content_resources"),
    ("app.domains.notifications.resources", "notification_resources"),
    ("app.domains.ai.resources", "ai_resources"),
    ("app.domains.integration.resources", "integration_resources"),
)


def iter_domain_resources():
    for module_name, attribute_name in DOMAIN_RESOURCE_MODULES:
        module = import_module(module_name)
        yield getattr(module, attribute_name)


def register_resources(target_registry=None, *, reset=False):
    target = registry if target_registry is None else target_registry
    if reset:
        target.reset()
    for resources in iter_domain_resources():
        target.register_many(resources)
    return target
