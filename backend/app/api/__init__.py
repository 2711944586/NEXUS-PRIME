from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

from . import routes  # noqa: E402,F401
from . import health  # noqa: E402,F401
from . import exports  # noqa: E402,F401
from . import workflow  # noqa: E402,F401
from . import inventory  # noqa: E402,F401
from . import sales  # noqa: E402,F401
from . import procurement  # noqa: E402,F401
from . import finance  # noqa: E402,F401
from . import files  # noqa: E402,F401
from . import notifications  # noqa: E402,F401
from . import insights  # noqa: E402,F401
from . import lookups  # noqa: E402,F401
from . import reports  # noqa: E402,F401
from . import ai  # noqa: E402,F401  — AI routes (extracted from experience)
from . import experience  # noqa: E402,F401
