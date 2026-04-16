"""SDK types — re-exports from per-domain type files.

Import from here, not from individual files:
    from awaithumans.types import TaskStatus, AwaitHumanOptions, VerifierConfig
"""

from awaithumans.types.form import (
    FORM_DEFINITION_VERSION,
    FormDefinition,
    FormField,
    FormFieldBase,
)
from awaithumans.types.routing import (
    AssignTo,
    HumanIdentity,
    MarketplaceAssignment,
    PoolAssignment,
    RoleAssignment,
    UserAssignment,
)
from awaithumans.types.task import (
    AwaitHumanOptions,
    TaskRecord,
    TaskStatus,
    TERMINAL_STATUSES,
)
from awaithumans.types.verification import (
    VerificationContext,
    VerifierConfig,
    VerifierResult,
)

__all__ = [
    "AssignTo",
    "AwaitHumanOptions",
    "FORM_DEFINITION_VERSION",
    "FormDefinition",
    "FormField",
    "FormFieldBase",
    "HumanIdentity",
    "MarketplaceAssignment",
    "PoolAssignment",
    "RoleAssignment",
    "TaskRecord",
    "TaskStatus",
    "TERMINAL_STATUSES",
    "UserAssignment",
    "VerificationContext",
    "VerifierConfig",
    "VerifierResult",
]
