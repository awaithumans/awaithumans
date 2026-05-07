"""API request/response schemas — re-exports from per-domain schema files.

Import schemas from here, not from individual files:
    from awaithumans.server.schemas import TaskResponse, CreateTaskRequest
"""

from awaithumans.server.schemas.audit import AuditEntryResponse
from awaithumans.server.schemas.email import IdentityCreateRequest, IdentityResponse
from awaithumans.server.schemas.health import HealthResponse
from awaithumans.server.schemas.slack import SlackInstallationResponse
from awaithumans.server.schemas.stats import TaskStats, TaskStatsByDay
from awaithumans.server.schemas.status import SystemStatus
from awaithumans.server.schemas.task import (
    CompleteTaskRequest,
    CreateTaskRequest,
    PollResponse,
    TaskResponse,
)
from awaithumans.server.schemas.webhook import WebhookDeliveryResponse

__all__ = [
    "AuditEntryResponse",
    "CompleteTaskRequest",
    "CreateTaskRequest",
    "HealthResponse",
    "IdentityCreateRequest",
    "IdentityResponse",
    "PollResponse",
    "SlackInstallationResponse",
    "SystemStatus",
    "TaskResponse",
    "TaskStats",
    "TaskStatsByDay",
    "WebhookDeliveryResponse",
]
