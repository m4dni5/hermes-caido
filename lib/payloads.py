"""Payload helpers for Caido Automate.

Configure what values get injected into placeholders during fuzzing.
Strategy determines how many payload sets are needed and how they combine.

Strategies:
  ALL        — 1 set. Each value replaces ALL placeholders at once.
  SEQUENTIAL — 1 set. Each value replaces placeholders one at a time.
  MATRIX     — N sets (one per placeholder). Cartesian product.
  PARALLEL   — N sets (one per placeholder). Zip through in lockstep.

All functions validate against the session's current placeholders and strategy.
"""

from __future__ import annotations

from typing import Any


class PayloadError(Exception):
    """Raised when payload configuration is invalid."""


def _validate_sets_for_strategy(
    strategy: str,
    num_placeholders: int,
    num_sets: int,
    set_lengths: list[int] | None = None,
) -> None:
    """Validate payload set count and lengths against the strategy.

    Args:
        strategy: ALL, SEQUENTIAL, MATRIX, or PARALLEL.
        num_placeholders: Number of placeholders in the session.
        num_sets: Number of payload sets being configured.
        set_lengths: Length of each set (required for PARALLEL validation).

    Raises:
        PayloadError with a human-readable message on mismatch.
    """
    if strategy in ("ALL", "SEQUENTIAL"):
        if num_sets != 1:
            raise PayloadError(
                f"{strategy} requires exactly 1 payload set, got {num_sets}. "
                f"Use a single set of values — each one replaces "
                f"{'all placeholders at once' if strategy == 'ALL' else 'placeholders one at a time'}."
            )

    elif strategy == "MATRIX":
        if num_sets != num_placeholders:
            raise PayloadError(
                f"MATRIX requires 1 payload set per placeholder. "
                f"Got {num_sets} sets but {num_placeholders} placeholders. "
                f"Pass a list with {num_placeholders} lists of values."
            )

    elif strategy == "PARALLEL":
        if num_sets != num_placeholders:
            raise PayloadError(
                f"PARALLEL requires 1 payload set per placeholder. "
                f"Got {num_sets} sets but {num_placeholders} placeholders. "
                f"Pass a list with {num_placeholders} lists of values."
            )
        if set_lengths and len(set(set_lengths)) > 1:
            raise PayloadError(
                f"PARALLEL requires all payload sets to have the same length. "
                f"Got lengths: {set_lengths}. "
                f"Pad or trim sets so they match."
            )


def validate_payload_config(
    strategy: str,
    num_placeholders: int,
    payload_sets: list[list[str]],
) -> None:
    """Validate a payload configuration before applying it.

    Args:
        strategy: The automate payload strategy.
        num_placeholders: Number of placeholders in the session.
        payload_sets: List of payload value lists.

    Raises:
        PayloadError on any validation failure.
    """
    if not payload_sets:
        raise PayloadError("At least one payload set is required.")

    if num_placeholders == 0:
        raise PayloadError(
            "No placeholders configured. Set placeholders first before adding payloads."
        )

    set_lengths = [len(s) for s in payload_sets]
    if any(length == 0 for length in set_lengths):
        raise PayloadError("Payload sets cannot be empty.")

    _validate_sets_for_strategy(strategy, num_placeholders, len(payload_sets), set_lengths)


def build_payload_input(payload_sets: list[list[str]]) -> list[dict[str, Any]]:
    """Convert payload value lists into AutomatePayloadInput dicts.

    Each set becomes a simpleList payload.

    Args:
        payload_sets: List of lists of string values.

    Returns:
        List of dicts matching the GraphQL AutomatePayloadInput shape.
    """
    return [
        {
            "options": {"simpleList": {"list": values}},
            "preprocessors": [],
        }
        for values in payload_sets
    ]


def build_number_payload(
    start: int,
    end: int,
    increments: int = 1,
    min_length: int = 0,
) -> dict[str, Any]:
    """Build a number range payload input.

    Args:
        start: Range start (inclusive).
        end: Range end (inclusive).
        increments: Step size.
        min_length: Minimum digit length (zero-padded).

    Returns:
        Dict matching the GraphQL AutomatePayloadInput shape.
    """
    return {
        "options": {
            "number": {
                "range": {"start": start, "end": end},
                "increments": increments,
                "minLength": min_length,
            }
        },
        "preprocessors": [],
    }


def add_prefix(payload_input: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Add a prefix preprocessor to a payload.

    Args:
        payload_input: A payload input dict.
        prefix: The prefix string to prepend.

    Returns:
        The modified payload input dict (mutated in place and returned).
    """
    payload_input["preprocessors"].append(
        {"options": {"prefix": {"value": prefix}}}
    )
    return payload_input


def add_suffix(payload_input: dict[str, Any], suffix: str) -> dict[str, Any]:
    """Add a suffix preprocessor to a payload.

    Args:
        payload_input: A payload input dict.
        suffix: The suffix string to append.

    Returns:
        The modified payload input dict (mutated in place and returned).
    """
    payload_input["preprocessors"].append(
        {"options": {"suffix": {"value": suffix}}}
    )
    return payload_input
