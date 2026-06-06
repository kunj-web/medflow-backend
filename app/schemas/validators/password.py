import re


def validate_password_strength(v: str) -> str:
    """
    Validate strong password rules.

    Requirements:
    - At least 8 characters
    - One uppercase
    - One lowercase
    - One digit
    - One special character
    """

    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")

    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
        raise ValueError("Password must contain at least one special character")

    return v