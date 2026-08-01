from collections import Counter

from app.scheduler import MassInfo, MinisterInfo, assign


def make_mass(mid, day, time, min_ministers, name="Lugar", kind="filial"):
    return MassInfo(
        id=mid,
        day=day,
        time=time,
        min_ministers=min_ministers,
        location_name=name,
        location_kind=kind,
    )


def make_ministers(n, days):
    return [MinisterInfo(id=i, days=list(days)) for i in range(1, n + 1)]


def test_filial_gets_two():
    masses = [make_mass(1, 1, "10:00", 2)]
    slots, warnings = assign(masses, make_ministers(5, [1]))
    assert len(slots) == 2
    assert not warnings


def test_center_gets_four():
    masses = [make_mass(1, 7, "10:00", 4, name="Centro", kind="centro")]
    slots, warnings = assign(masses, make_ministers(6, [7]))
    assert len(slots) == 4
    assert not warnings


def test_only_available_ministers():
    masses = [make_mass(1, 1, "10:00", 2)]
    ministers = [MinisterInfo(id=1, days=[2]), MinisterInfo(id=2, days=[1])]
    slots, _ = assign(masses, ministers)
    assert {s.minister_id for s in slots} == {2}
    assert len(slots) == 1


def test_equity_with_enough_supply():
    masses = [make_mass(i, i, "10:00", 2) for i in range(1, 6)]
    slots, warnings = assign(masses, make_ministers(10, range(1, 8)))
    assert len(slots) == 10
    assert not warnings
    counts = Counter(s.minister_id for s in slots)
    assert max(counts.values()) - min(counts.values()) <= 1


def test_warning_when_short():
    masses = [make_mass(1, 7, "10:00", 4, name="Centro", kind="centro")]
    slots, warnings = assign(masses, make_ministers(2, [7]))
    assert len(slots) == 2
    assert len(warnings) == 1
    assert "2 de 4" in warnings[0]


def test_no_double_service_same_day_when_possible():
    masses = [make_mass(1, 1, "10:00", 2), make_mass(2, 1, "12:00", 2)]
    slots, _ = assign(masses, make_ministers(4, [1]))
    counts = Counter(s.minister_id for s in slots)
    assert max(counts.values()) == 1


def test_deterministic():
    masses = [make_mass(i, (i % 7) + 1, f"10:0{i}", 2) for i in range(1, 8)]
    ministers = make_ministers(8, range(1, 8))
    s1, _ = assign(masses, ministers)
    s2, _ = assign(masses, ministers)
    assert [(s.mass_id, s.minister_id, s.order) for s in s1] == [
        (s.mass_id, s.minister_id, s.order) for s in s2
    ]


def test_empty_ministers_no_crash():
    masses = [make_mass(1, 1, "10:00", 2)]
    slots, warnings = assign(masses, [])
    assert slots == []
    assert warnings


def test_incomplete_mass_does_not_break_others():
    masses = [
        make_mass(1, 1, "10:00", 4, name="Centro", kind="centro"),
        make_mass(2, 2, "10:00", 2),
    ]
    ministers = [MinisterInfo(id=i, days=[2]) for i in range(1, 4)]
    slots, warnings = assign(masses, ministers)
    by_mass = Counter(s.mass_id for s in slots)
    assert by_mass[2] == 2
    assert by_mass[1] == 0
    assert len(warnings) == 1
