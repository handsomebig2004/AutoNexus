"""Schema package for structured agent inputs and outputs."""

from .requirement import TaskDefinition
from .user_request import UserRequest

__all__ = [
    "TaskDefinition",
    "UserRequest",
]
