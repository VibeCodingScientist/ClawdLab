"""Research Frontiers module for open problems management."""

from platform.frontier.service import FrontierService
from platform.frontier.api import router as frontier_router

__all__ = ["FrontierService", "frontier_router"]
