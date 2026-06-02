def validate_non_empty_string(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Field cannot be blank")
    return v.strip()

def validate_positive_amount(v: float) -> float:
    if v < 0:
        raise ValueError("Amount cannot be negative")
    return v