"""Migration metadata registry. Application never creates tables at startup."""

from offerpilot.modules.applications import models as applications
from offerpilot.modules.control import models as control
from offerpilot.modules.discovery import models as discovery
from offerpilot.modules.identity import models as identity
from offerpilot.modules.interview import models as interview
from offerpilot.modules.jobs import models as jobs
from offerpilot.modules.offers import models as offers
from offerpilot.modules.operations import models as operations
from offerpilot.modules.preparation import models as preparation
from offerpilot.modules.profiles import models as profiles
from offerpilot.modules.runs import models as runs
from offerpilot.modules.tasks import models as tasks

__all__ = [
    "applications",
    "discovery",
    "identity",
    "interview",
    "jobs",
    "preparation",
    "profiles",
    "runs",
    "tasks",
    "offers",
    "operations",
    "control",
]

from offerpilot.infrastructure.constraints import install_constraints

install_constraints()
