from datetime import datetime, timezone

def validate_future_datetime(v: datetime) -> datetime:
    if v <= datetime.now(timezone.utc):
        raise ValueError("Slot time must be in the future")
    return v

def validate_slot_alignment(v: datetime, interval: int = 15) -> datetime:
    if v.minute % interval != 0:
        raise ValueError(f"Slot time must align to {interval}-minute intervals")
    return v