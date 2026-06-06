import re


def validate_non_empty_string(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Field cannot be blank")

    return v.strip()


def validate_positive_amount(v: float) -> float:
    if v < 0:
        raise ValueError("Amount cannot be negative")

    return v


def validate_hex_color(v: str) -> str:
    """
    Validate HEX color codes like:
    #FFFFFF
    #000000
    """

    if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
        raise ValueError("Invalid HEX color format")

    return v


def validate_cancellation_reason(v: str) -> str:
    """
    Ensure cancellation reason is meaningful.
    """

    v = validate_non_empty_string(v)

    if len(v) < 5:
        raise ValueError(
            "Cancellation reason must be at least 5 characters long"
        )

    return v
