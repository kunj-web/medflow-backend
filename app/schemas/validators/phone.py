import re
from pydantic import field_validator

def validate_indian_phone(v: str) -> str:
    digits = re.sub(r"[\s\-\+]", "", v)
    if not re.match(r"^[6-9]\d{9}$", digits):
        raise ValueError("Enter a valid 10-digit Indian mobile number")
    return digits