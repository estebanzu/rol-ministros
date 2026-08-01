import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field

DAY_HEADERS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
DAY_NAME_TO_NUM = {name: i + 1 for i, name in enumerate(DAY_HEADERS)}
TRUE_VALUES = {"si", "s", "x", "1", "verdadero", "true", "yes", "disponible"}
FALSE_VALUES = {"no", "n", "0", "falso", "false", ""}
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _normalize_header(h: str) -> str:
    h = unicodedata.normalize("NFKD", h)
    h = "".join(c for c in h if not unicodedata.combining(c))
    return h.strip().lower().replace(" ", "")


@dataclass
class CsvError:
    row: int
    column: str
    message: str


@dataclass
class ParsedMinister:
    name: str
    phone: str
    days: list[int]
    slots: list[str]


@dataclass
class ParseResult:
    ministers: list[ParsedMinister] = field(default_factory=list)
    errors: list[CsvError] = field(default_factory=list)
    warnings: list[CsvError] = field(default_factory=list)


@dataclass
class ParsedMass:
    day: int
    location_name: str
    kind: str | None
    time: str
    min_ministers: int | None


@dataclass
class MassParseResult:
    masses: list[ParsedMass] = field(default_factory=list)
    errors: list[CsvError] = field(default_factory=list)
    warnings: list[CsvError] = field(default_factory=list)


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _detect_delimiter(first_line: str) -> str:
    return ";" if first_line.count(";") > first_line.count(",") else ","


def _parse_day(raw: str) -> int | None:
    norm = _normalize_header(raw)
    if norm in DAY_NAME_TO_NUM:
        return DAY_NAME_TO_NUM[norm]
    if norm in {"1", "2", "3", "4", "5", "6", "7"}:
        return int(norm)
    return None


SLOT_TIME_MAP = {
    "lunes_manana": "08:00",
    "lunes_tarde": "18:00",
    "martes_manana": "08:00",
    "martes_tarde": "18:00",
    "miercoles_manana": "08:00",
    "miercoles_tarde": "18:00",
    "jueves_manana": "08:00",
    "jueves_tarde": "18:00",
    "viernes_manana": "08:00",
    "viernes_tarde": "18:00",
    "sabado_tarde": "17:00",
    "domingo_manana": "08:00",
    "domingo_noche": "16:00",
}


def parse_csv(data: bytes) -> ParseResult:
    text = _decode(data)
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        return ParseResult(errors=[CsvError(row=1, column="", message="El archivo está vacío.")])

    delimiter = _detect_delimiter(lines[0])
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))

    header = [_normalize_header(h) for h in rows[0]]
    header_idx = {h: i for i, h in enumerate(header)}

    slot_pairs = [
        ("lunes", "manana", "lunes_manana"),
        ("lunes", "tarde", "lunes_tarde"),
        ("martes", "manana", "martes_manana"),
        ("martes", "tarde", "martes_tarde"),
        ("miercoles", "manana", "miercoles_manana"),
        ("miercoles", "tarde", "miercoles_tarde"),
        ("jueves", "manana", "jueves_manana"),
        ("jueves", "tarde", "jueves_tarde"),
        ("viernes", "manana", "viernes_manana"),
        ("viernes", "tarde", "viernes_tarde"),
        ("sabado", "tarde", "sabado_tarde"),
        ("domingo", "manana", "domingo_manana"),
        ("domingo", "noche", "domingo_noche"),
    ]
    required = ["nombre", "telefono"] + [col for _, _, col in slot_pairs]
    missing = [h for h in required if h not in header_idx]
    if missing:
        return ParseResult(
            errors=[
                CsvError(
                    row=1,
                    column=", ".join(missing),
                    message=f"Faltan columnas requeridas: {', '.join(missing)}",
                )
            ]
        )

    result = ParseResult()
    for row_no, row in enumerate(rows[1:], start=2):
        if all(cell.strip() == "" for cell in row):
            continue

        def val(row, col: str) -> str:
            i = header_idx.get(col)
            if i is None or i >= len(row):
                return ""
            return row[i].strip()

        name = val(row, "nombre")
        if not name:
            result.errors.append(
                CsvError(row=row_no, column="nombre", message="El nombre es obligatorio.")
            )
            continue

        phone = val(row, "telefono")
        days: list[int] = []
        slots: list[str] = []

        valid_row = True
        for day_name, _slot_name, col in slot_pairs:
            raw = val(row, col).strip().lower()
            if raw in TRUE_VALUES:
                day_num = DAY_NAME_TO_NUM[day_name]
                days.append(day_num)
                slots.append(f"{day_num:02d}-{SLOT_TIME_MAP[col]}")
            elif raw in FALSE_VALUES:
                continue
            else:
                result.errors.append(
                    CsvError(
                        row=row_no,
                        column=col,
                        message=f"Valor '{val(row, col)}' no válido. Usa si/no.",
                    )
                )
                valid_row = False
        if not valid_row:
            continue
        if not phone:
            result.warnings.append(CsvError(row=row_no, column="telefono", message="Sin teléfono."))
        if not slots:
            result.warnings.append(
                CsvError(row=row_no, column="", message="No disponible ningún horario.")
            )
        result.ministers.append(ParsedMinister(name=name, phone=phone, days=days, slots=slots))

    return result


def parse_masses_csv(data: bytes) -> MassParseResult:
    text = _decode(data)
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        return MassParseResult(
            errors=[CsvError(row=1, column="", message="El archivo está vacío.")]
        )

    delimiter = _detect_delimiter(lines[0])
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))

    header = [_normalize_header(h) for h in rows[0]]
    header_idx = {h: i for i, h in enumerate(header)}

    required = ["dia", "lugar", "hora"]
    missing = [h for h in required if h not in header_idx]
    if missing:
        return MassParseResult(
            errors=[
                CsvError(
                    row=1,
                    column=", ".join(missing),
                    message=f"Faltan columnas requeridas: {', '.join(missing)}",
                )
            ]
        )

    result = MassParseResult()
    seen: set[tuple[str, int, str]] = set()
    for row_no, row in enumerate(rows[1:], start=2):
        if all(cell.strip() == "" for cell in row):
            continue

        def val(row, col: str) -> str:
            i = header_idx.get(col)
            if i is None or i >= len(row):
                return ""
            return row[i].strip()

        day_raw = val(row, "dia")
        day = _parse_day(day_raw)
        if day is None:
            result.errors.append(
                CsvError(
                    row=row_no,
                    column="dia",
                    message=f"Día '{day_raw}' no válido. Usa lunes a domingo o 1-7.",
                )
            )
            continue

        location_name = val(row, "lugar")
        if not location_name:
            result.errors.append(
                CsvError(row=row_no, column="lugar", message="El lugar es obligatorio.")
            )
            continue

        time = val(row, "hora")
        if not TIME_RE.fullmatch(time):
            result.errors.append(
                CsvError(
                    row=row_no,
                    column="hora",
                    message="La hora debe tener formato HH:MM.",
                )
            )
            continue

        kind_raw = val(row, "tipo")
        kind = kind_raw.strip().lower() if kind_raw else None
        if kind is not None and kind not in ("centro", "filial"):
            result.errors.append(
                CsvError(
                    row=row_no,
                    column="tipo",
                    message="El tipo debe ser 'centro' o 'filial'.",
                )
            )
            continue

        min_ministers = None
        min_raw = val(row, "minimo")
        if min_raw:
            try:
                min_ministers = int(min_raw)
                if min_ministers < 1:
                    raise ValueError
            except ValueError:
                result.errors.append(
                    CsvError(
                        row=row_no,
                        column="minimo",
                        message="El mínimo debe ser un número entero mayor o igual a 1.",
                    )
                )
                continue

        key = (location_name.casefold(), day, time)
        if key in seen:
            result.errors.append(
                CsvError(
                    row=row_no,
                    column="dia",
                    message=f"Misa duplicada: {location_name} el {day} a las {time}.",
                )
            )
            continue
        seen.add(key)

        result.masses.append(
            ParsedMass(
                day=day,
                location_name=location_name,
                kind=kind,
                time=time,
                min_ministers=min_ministers,
            )
        )

    return result
