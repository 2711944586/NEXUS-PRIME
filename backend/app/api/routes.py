"""Compatibility facade for legacy imports from app.api.routes.

Route handlers now live in focused modules, but existing code can keep importing
helpers and handlers from this module while domains are migrated incrementally.
"""

from .resource_support import *  # noqa: F401,F403
from .auth_routes import *  # noqa: F401,F403
from .profile_routes import *  # noqa: F401,F403
from .generic_crud_routes import *  # noqa: F401,F403
from .business_action_routes import *  # noqa: F401,F403
