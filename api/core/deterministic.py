# core/deterministic.py
"""
Deterministic Safety Enforcement

This module provides utilities for handling queries that require deterministic answers.
The key principle: if a query is deterministic in nature, the system should:

1. Attempt to find an exact answer from the database/files
2. If not found, return a clear "not found" response
3. NEVER fall back to having the LLM make up an answer

Usage:

    @deterministic_query
    def get_user_task(task_id: int, user_id: int) -> DeterministicResult:
        task = db.get_task(task_id, user_id)
        if not task:
            return DeterministicResult.not_found("task", task_id)
        return DeterministicResult.success(task)

    # In chat flow:
    result = get_user_task(123, user_id)
    if result.found:
        # Use result.data
    else:
        # Return clear "not found" message, don't fall through to LLM
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Generic

T = TypeVar("T")


class ResultStatus(Enum):
    """Status of a deterministic query result."""
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class DeterministicResult(Generic[T]):
    """
    Result of a deterministic query.

    This enforces the pattern: either we have a concrete answer, or we have
    a clear "not found" / "error" response. There is no ambiguity.
    """
    status: ResultStatus
    data: Optional[T] = None
    resource_type: Optional[str] = None
    resource_id: Optional[Any] = None
    message: Optional[str] = None

    @property
    def found(self) -> bool:
        return self.status == ResultStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        return self.status == ResultStatus.ERROR

    @classmethod
    def success(cls, data: T) -> "DeterministicResult[T]":
        """Create a successful result with data."""
        return cls(status=ResultStatus.SUCCESS, data=data)

    @classmethod
    def not_found(
        cls,
        resource_type: str,
        resource_id: Any = None,
        message: Optional[str] = None,
    ) -> "DeterministicResult[T]":
        """Create a not-found result."""
        msg = message or f"{resource_type} not found"
        if resource_id is not None:
            msg = f"{resource_type} with id {resource_id} not found"
        return cls(
            status=ResultStatus.NOT_FOUND,
            resource_type=resource_type,
            resource_id=resource_id,
            message=msg,
        )

    @classmethod
    def error(cls, message: str) -> "DeterministicResult[T]":
        """Create an error result."""
        return cls(status=ResultStatus.ERROR, message=message)

    def to_reply(self) -> str:
        """Convert to a user-facing reply message."""
        if self.found:
            if isinstance(self.data, str):
                return self.data
            return str(self.data) if self.data else "Found."
        return self.message or "Not found."


def deterministic_query(fn: Callable[..., DeterministicResult]) -> Callable[..., DeterministicResult]:
    """
    Decorator marking a function as a deterministic query.

    This is primarily for documentation/type-checking purposes, but also
    ensures the function returns a DeterministicResult.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs) -> DeterministicResult:
        result = fn(*args, **kwargs)
        if not isinstance(result, DeterministicResult):
            raise TypeError(
                f"@deterministic_query function {fn.__name__} must return "
                f"DeterministicResult, got {type(result).__name__}"
            )
        return result
    return wrapper


# ---------------------------------------------------------------------------
# Deterministic query patterns
# ---------------------------------------------------------------------------


class DeterministicQueries:
    """
    Collection of patterns that indicate a deterministic query.

    These patterns should be handled with exact lookups, never LLM fallback.
    """

    @staticmethod
    def is_exact_lookup_query(message: str) -> bool:
        """
        Check if a message is asking for an exact lookup.

        Examples:
        - "What is task 123?"
        - "Show me file xyz"
        - "What's the status of my reminder?"
        """
        msg = (message or "").lower().strip()

        exact_patterns = [
            # Task lookups
            "what is task",
            "show task",
            "get task",
            "task status",
            "what's the status of",
            # File lookups
            "show file",
            "show me file",
            "get file",
            "what's in file",
            # Project lookups
            "what's in project",
            "show project",
            "list files in",
        ]

        return any(pattern in msg for pattern in exact_patterns)

    @staticmethod
    def is_count_query(message: str) -> bool:
        """
        Check if a message is asking for a count.

        Examples:
        - "How many tasks do I have?"
        - "How many files are in this project?"
        """
        msg = (message or "").lower().strip()

        return "how many" in msg and any(
            word in msg for word in ["task", "file", "project", "conversation", "reminder"]
        )

    @staticmethod
    def is_list_query(message: str) -> bool:
        """
        Check if a message is asking for a list of items.

        Examples:
        - "List my tasks"
        - "Show all projects"
        """
        msg = (message or "").lower().strip()

        list_verbs = ["list", "show all", "show my", "what are my"]
        list_nouns = ["tasks", "files", "projects", "conversations", "reminders"]

        return any(
            verb in msg and noun in msg
            for verb in list_verbs
            for noun in list_nouns
        )


# ---------------------------------------------------------------------------
# Response formatter for deterministic results
# ---------------------------------------------------------------------------


def format_deterministic_response(result: DeterministicResult, query_type: str = "") -> dict:
    """
    Format a deterministic result into a standardized response.

    Returns a dict that can be used as an intent response:
    {
        "handled": True,
        "reply_text": "...",
        "deterministic": True,
        "meta": {...}
    }
    """
    if result.found:
        return {
            "handled": True,
            "reply_text": result.to_reply(),
            "deterministic": True,
            "meta": {
                "query_type": query_type,
                "status": "success",
                "data": result.data,
            },
        }

    return {
        "handled": True,
        "reply_text": result.to_reply(),
        "deterministic": True,
        "meta": {
            "query_type": query_type,
            "status": result.status.value,
            "resource_type": result.resource_type,
            "resource_id": result.resource_id,
        },
    }
