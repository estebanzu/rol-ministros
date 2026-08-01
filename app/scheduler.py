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
    days: list[int]


@dataclass
class Slot:
    mass_id: int
    minister_id: int
    order: int


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)


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
    day_load: dict[int, dict[int, int]] = {m.id: {d: 0 for d in m.days} for m in ministers}

    slots: list[Slot] = []
    warnings: list[str] = []

    for mass in masses_sorted:
        candidates = [m for m in ministers if mass.day in day_load[m.id]]
        candidates.sort(key=lambda m: (load[m.id], day_load[m.id].get(mass.day, 0), m.id))

        chosen: list[MinisterInfo] = []
        for m in candidates:
            if day_load[m.id].get(mass.day, 0) == 0:
                chosen.append(m)
                if len(chosen) >= mass.min_ministers:
                    break
        if len(chosen) < mass.min_ministers:
            for m in candidates:
                if m not in chosen:
                    chosen.append(m)
                if len(chosen) >= mass.min_ministers:
                    break

        for i, m in enumerate(chosen):
            load[m.id] += 1
            day_load[m.id][mass.day] = day_load[m.id].get(mass.day, 0) + 1
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
        MinisterInfo(id=m.id, days=m.available_days()) for m in ministers if m.available_days()
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
