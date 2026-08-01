from datetime import date, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class Location(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    kind: str = Field(index=True)
    default_min: int = 4
    active: bool = True

    masses: list["Mass"] = Relationship(
        back_populates="location",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Mass(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("location_id", "day", "time", name="uq_mass_location_day_time"),
    )

    id: int | None = Field(default=None, primary_key=True)
    location_id: int = Field(foreign_key="location.id", index=True)
    day: int = Field(index=True)
    time: str
    min_ministers: int = 2
    active: bool = True

    location: Location | None = Relationship(back_populates="masses")
    assignments: list["Assignment"] = Relationship(
        back_populates="mass", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class Minister(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    phone: str | None = None
    days_available: str
    active: bool = True

    assignments: list["Assignment"] = Relationship(
        back_populates="minister",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    def available_days(self) -> list[int]:
        return [int(x) for x in self.days_available.split(",") if x.strip()]


class RosterWeek(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    week_start: date = Field(unique=True, index=True)
    generated_at: datetime
    status: str
    notes: str | None = None

    assignments: list["Assignment"] = Relationship(
        back_populates="roster_week",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Assignment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    roster_week_id: int = Field(foreign_key="rosterweek.id", index=True)
    mass_id: int = Field(foreign_key="mass.id", index=True)
    minister_id: int = Field(foreign_key="minister.id", index=True)
    slot_order: int = 0

    roster_week: RosterWeek | None = Relationship(back_populates="assignments")
    mass: Mass | None = Relationship(back_populates="assignments")
    minister: Minister | None = Relationship(back_populates="assignments")
