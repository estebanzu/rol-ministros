from pydantic import BaseModel, Field


class LocationCreate(BaseModel):
    name: str
    kind: str = "filial"


class LocationRead(BaseModel):
    id: int
    name: str
    kind: str
    default_min: int
    active: bool


class MassCreate(BaseModel):
    location_id: int
    day: int = Field(ge=1, le=7)
    time: str
    min_ministers: int | None = None
    active: bool = True


class MassRead(BaseModel):
    id: int
    location_id: int
    location_name: str
    location_kind: str
    day: int
    time: str
    min_ministers: int
    active: bool


class MinisterRead(BaseModel):
    id: int
    name: str
    phone: str | None = None
    slots_available: str
    active: bool


class CsvIssue(BaseModel):
    row: int
    column: str
    message: str


class UploadResult(BaseModel):
    imported: int
    errors: list[CsvIssue] = []
    warnings: list[CsvIssue] = []


class MinisterSlot(BaseModel):
    minister_id: int
    name: str
    phone: str | None = None
    slot_order: int


class MassSlot(BaseModel):
    mass_id: int
    location: str
    day: int
    time: str
    min_ministers: int
    assigned: int
    complete: bool
    ministers: list[MinisterSlot]


class DaySlots(BaseModel):
    day: int
    label: str
    date: str
    masses: list[MassSlot]


class RosterRead(BaseModel):
    week_start: str
    week_start_display: str
    status: str
    generated_at: str
    warnings: list[str] = []
    days: list[DaySlots] = []
