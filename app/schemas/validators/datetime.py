from datetime import UTC, datetime


def validate_future_datetime(v: datetime) -> datetime:
    if v <= datetime.now(UTC):
        raise ValueError("Datetime must be in the future")

    return v


def validate_slot_alignment(
    v: datetime,
    interval: int = 15,
) -> datetime:
    if v.minute % interval != 0:
        raise ValueError(
            f"Slot time must align to {interval}-minute intervals"
        )

    return v


def validate_slot_time(v: datetime) -> datetime:
    """
    Combined appointment slot validator.
    """

    v = validate_future_datetime(v)
    v = validate_slot_alignment(v)

    return v
