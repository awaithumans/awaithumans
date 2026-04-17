"""Slack routes — interactivity webhook + OAuth install flow + installations CRUD.

Each sub-router registers handlers on its own `APIRouter` instance
(no prefix). This module aggregates them under the shared
`/channels/slack` prefix and exports the combined `router` for `app.py`.
"""

from __future__ import annotations

from fastapi import APIRouter

from awaithumans.server.routes.slack.installations import router as _installations_router
from awaithumans.server.routes.slack.interactions import router as _interactions_router
from awaithumans.server.routes.slack.oauth import router as _oauth_router

router = APIRouter(prefix="/channels/slack", tags=["channels"])
router.include_router(_interactions_router)
router.include_router(_oauth_router)
router.include_router(_installations_router)
