"""Qloo client package for service-taste.

Public surface: :class:`QlooClient` plus the shared error taxonomy. The typed
payload models live in :mod:`karum_service_taste.qloo.models`; fixture replay
lives in :mod:`karum_service_taste.qloo.fixtures`.
"""

from karum_service_taste.qloo.client import QlooClient
from karum_service_taste.qloo.errors import ErrorCode, QlooError

__all__ = ["ErrorCode", "QlooClient", "QlooError"]
