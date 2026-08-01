from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session, select

from .models import Assignment, Mass, Minister, RosterWeek

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


@dataclass
class MassInfo:
    id: int
    day: int
    time: str
    min_ministers: int
    location_name: str
    location_kind: str


@dataclass
class MinisterInfo:
    id: int
    slots: set[str]


@dataclass
class Slot:
    mass_id: int
    minister_id: int
    order: int


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


def make_slot_key(day: int, time: str) -> str:
    return f"{day:02d}-{time}"


def assign(masses: list[MassInfo], ministers: list[MinisterInfo]) -> tuple[list[Slot], list[str]]:
    masses_sorted = sorted(
        masses,
        key=lambda m: (
            -m.min_ministers,
            0 if m.location_kind == "centro" else 1,
            m.day,
            m.time,
        ),
    )
    ministers = sorted(ministers, key=lambda m: m.id)

    load: dict[int, int] = {m.id: 0 for m in ministers}
    slot_load: dict[str, int] = {s: 0 for m in ministers for s in m.slots}

    slots: list[Slot] = []
    warnings: list[str] = []

    for mass in masses_sorted:
        slot = make_slot_key(mass.day, mass.time)
        candidates = [m for m in ministers if slot in m.slots]
        candidates.sort(key=lambda m: (load[m.id], slot_load.get(slot, 0), m.id))

        chosen: list[MinisterInfo] = []
        for m in candidates:
            if len(chosen) >= mass.min_ministers:
                break
            chosen.append(m)

        for i, m in enumerate(chosen):
            load[m.id] += 1
            slot_load[slot] = slot_load.get(slot, 0) + 1
            slots.append(Slot(mass_id=mass.id, minister_id=m.id, order=i))

        if len(chosen) < mass.min_ministers:
            warnings.append(
                f"{mass.location_name}: {DAY_NAMES[mass.day - 1]} {mass.time} — "
                f"{len(chosen)} de {mass.min_ministers} ministros"
            )

    return slots, warnings


def generate_roster(session: Session, week_start: date) -> RosterWeek:
    week_start = _monday_of(week_start)

    ministers = session.exec(select(Minister).where(Minister.active)).all()
    masses = session.exec(select(Mass).where(Mass.active)).all()

    minister_infos = [
        MinisterInfo(id=m.id, slots=m.available_slots()) for m in ministers if m.available_slots()
    ]
    mass_infos = []
    for mass in masses:
        location = mass.location
        mass_infos.append(
            MassInfo(
                id=mass.id,
                day=mass.day,
                time=mass.time,
                min_ministers=mass.min_ministers,
                location_name=location.name if location else "?",
                location_kind=location.kind if location else "filial",
            )
        )

    slots, warnings = assign(mass_infos, minister_infos)

    roster = session.exec(select(RosterWeek).where(RosterWeek.week_start == week_start)).first()
    if roster is None:
        roster = RosterWeek(week_start=week_start, generated_at=datetime.now(UTC), status="ok")
        session.add(roster)
        session.flush()
    else:
        for a in list(roster.assignments):
            session.delete(a)

    roster.generated_at = datetime.now(UTC)
    roster.status = "con_faltantes" if warnings else "ok"
    roster.notes = "; ".join(warnings) if warnings else None

    for slot in slots:
        session.add(
            Assignment(
                roster_week_id=roster.id,
                mass_id=slot.mass_id,
                minister_id=slot.minister_id,
                slot_order=slot.order,
            )
        )

    session.commit()
    session.refresh(roster)
    return roster
