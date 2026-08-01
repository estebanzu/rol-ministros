import csv
import io
import re
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from starlette.requests import Request

from . import schemas
from .csv_parser import parse_csv, parse_masses_csv
from .db import get_session, init_db
from .models import Assignment, Location, Mass, Minister, RosterWeek
from .pdf import build_roster_pdf
from .scheduler import DAY_NAMES, _monday_of, generate_roster, next_monday

BASE_DIR = Path(__file__).resolve().parent

DAY_MIN = {"centro": 4, "filial": 2}
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
TEMPLATE_CSV = (
    "nombre,telefono,lunes,martes,miercoles,jueves,viernes,sabado,domingo\n"
    "Maria Perez,555-1234,si,si,no,si,no,si,si\n"
    "Juan Garcia,555-5678,no,si,si,si,si,no,no\n"
)
MASS_TEMPLATE_CSV = (
    "dia,lugar,tipo,hora,minimo\n"
    "Domingo,Parroquia San Jose,Centro,10:00,4\n"
    "Sabado,Capilla La Paz,Filial,19:00,2\n"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Rol de Ministros de la Comunión", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def _loc_read(loc: Location) -> schemas.LocationRead:
    return schemas.LocationRead(
        id=loc.id,
        name=loc.name,
        kind=loc.kind,
        default_min=loc.default_min,
        active=loc.active,
    )


def _mass_read(mass: Mass) -> schemas.MassRead:
    loc = mass.location
    return schemas.MassRead(
        id=mass.id,
        location_id=mass.location_id,
        location_name=loc.name if loc else "?",
        location_kind=loc.kind if loc else "filial",
        day=mass.day,
        time=mass.time,
        min_ministers=mass.min_ministers,
        active=mass.active,
    )


def _min_read(minister: Minister) -> schemas.MinisterRead:
    return schemas.MinisterRead(
        id=minister.id,
        name=minister.name,
        phone=minister.phone,
        days_available=minister.days_available,
        active=minister.active,
    )


def _build_week_data(session: Session, roster: RosterWeek) -> dict:
    monday = roster.week_start
    by_mass: dict[int, list[Assignment]] = {}
    for a in roster.assignments:
        by_mass.setdefault(a.mass_id, []).append(a)

    mass_ids = set(by_mass.keys())
    masses: dict[int, Mass] = {}
    if mass_ids:
        masses = {m.id: m for m in session.exec(select(Mass).where(Mass.id.in_(mass_ids))).all()}

    days = []
    for d in range(1, 8):
        day_date = monday + timedelta(days=d - 1)
        days.append(
            {
                "day": d,
                "label": DAY_NAMES[d - 1],
                "date": day_date.strftime("%d/%m/%Y"),
                "masses": [],
            }
        )

    for mass_id, assigns in by_mass.items():
        mass = masses.get(mass_id)
        if mass is None:
            continue
        loc = mass.location
        assigns.sort(key=lambda a: a.slot_order)
        ministers = []
        for a in assigns:
            minister = a.minister
            ministers.append(
                {
                    "minister_id": a.minister_id,
                    "name": minister.name if minister else "?",
                    "phone": minister.phone if minister else None,
                    "slot_order": a.slot_order,
                }
            )
        days[mass.day - 1]["masses"].append(
            {
                "mass_id": mass.id,
                "location": loc.name if loc else "?",
                "day": mass.day,
                "time": mass.time,
                "min_ministers": mass.min_ministers,
                "assigned": len(assigns),
                "complete": len(assigns) >= mass.min_ministers,
                "ministers": ministers,
            }
        )

    warnings = [w.strip() for w in (roster.notes or "").split(";") if w.strip()]
    return {
        "week_start": monday.isoformat(),
        "week_start_display": f"{monday:%d/%m/%Y} al {monday + timedelta(days=6):%d/%m/%Y}",
        "status": roster.status,
        "generated_at": roster.generated_at.strftime("%d/%m/%Y %H:%M")
        if roster.generated_at
        else "",
        "warnings": warnings,
        "days": days,
    }


def _resolve_week(week_start: date | None) -> date:
    if week_start is None:
        week_start = next_monday(datetime.now(UTC).date())
    return _monday_of(week_start)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/locations", response_model=list[schemas.LocationRead])
def list_locations(session: Session = Depends(get_session)):
    return [_loc_read(loc) for loc in session.exec(select(Location).order_by(Location.name)).all()]


@app.post("/api/locations", response_model=schemas.LocationRead, status_code=201)
def create_location(payload: schemas.LocationCreate, session: Session = Depends(get_session)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "El nombre es obligatorio.")
    if session.exec(select(Location).where(Location.name == name)).first():
        raise HTTPException(409, "Ya existe un lugar con ese nombre.")
    loc = Location(name=name, kind=payload.kind, default_min=DAY_MIN.get(payload.kind, 2))
    session.add(loc)
    session.commit()
    session.refresh(loc)
    return _loc_read(loc)


@app.put("/api/locations/{location_id}", response_model=schemas.LocationRead)
def update_location(
    location_id: int,
    payload: schemas.LocationCreate,
    session: Session = Depends(get_session),
):
    loc = session.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "Lugar no encontrado.")
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "El nombre es obligatorio.")
    dup = session.exec(
        select(Location).where(Location.name == name, Location.id != location_id)
    ).first()
    if dup:
        raise HTTPException(409, "Ya existe un lugar con ese nombre.")
    loc.name = name
    loc.kind = payload.kind
    loc.default_min = DAY_MIN.get(payload.kind, 2)
    session.add(loc)
    session.commit()
    session.refresh(loc)
    return _loc_read(loc)


@app.delete("/api/locations/{location_id}", status_code=204)
def delete_location(location_id: int, session: Session = Depends(get_session)):
    loc = session.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "Lugar no encontrado.")
    session.delete(loc)
    session.commit()
    return Response(status_code=204)


@app.get("/api/masses", response_model=list[schemas.MassRead])
def list_masses(session: Session = Depends(get_session)):
    masses = session.exec(select(Mass).where(Mass.active).order_by(Mass.day, Mass.time)).all()
    return [_mass_read(m) for m in masses]


def _validate_mass_time(time: str):
    if not TIME_RE.fullmatch(time):
        raise HTTPException(400, "La hora debe tener formato HH:MM.")


@app.post("/api/masses", response_model=schemas.MassRead, status_code=201)
def create_mass(payload: schemas.MassCreate, session: Session = Depends(get_session)):
    loc = session.get(Location, payload.location_id)
    if not loc:
        raise HTTPException(404, "Lugar no encontrado.")
    _validate_mass_time(payload.time)
    dup = session.exec(
        select(Mass).where(
            Mass.location_id == payload.location_id,
            Mass.day == payload.day,
            Mass.time == payload.time,
        )
    ).first()
    if dup:
        raise HTTPException(409, "Ya existe esa misa.")
    min_ministers = payload.min_ministers or loc.default_min
    if min_ministers < 1:
        raise HTTPException(400, "El mínimo debe ser al menos 1.")
    mass = Mass(
        location_id=payload.location_id,
        day=payload.day,
        time=payload.time,
        min_ministers=min_ministers,
        active=payload.active,
    )
    session.add(mass)
    session.commit()
    session.refresh(mass)
    return _mass_read(mass)


@app.put("/api/masses/{mass_id}", response_model=schemas.MassRead)
def update_mass(mass_id: int, payload: schemas.MassCreate, session: Session = Depends(get_session)):
    mass = session.get(Mass, mass_id)
    if not mass:
        raise HTTPException(404, "Misa no encontrada.")
    loc = session.get(Location, payload.location_id)
    if not loc:
        raise HTTPException(404, "Lugar no encontrado.")
    _validate_mass_time(payload.time)
    dup = session.exec(
        select(Mass).where(
            Mass.location_id == payload.location_id,
            Mass.day == payload.day,
            Mass.time == payload.time,
            Mass.id != mass_id,
        )
    ).first()
    if dup:
        raise HTTPException(409, "Ya existe esa misa.")
    if payload.min_ministers is not None and payload.min_ministers < 1:
        raise HTTPException(400, "El mínimo debe ser al menos 1.")
    mass.location_id = payload.location_id
    mass.day = payload.day
    mass.time = payload.time
    if payload.min_ministers is not None:
        mass.min_ministers = payload.min_ministers
    mass.active = payload.active
    session.add(mass)
    session.commit()
    session.refresh(mass)
    return _mass_read(mass)


@app.delete("/api/masses/{mass_id}", status_code=204)
def delete_mass(mass_id: int, session: Session = Depends(get_session)):
    mass = session.get(Mass, mass_id)
    if not mass:
        raise HTTPException(404, "Misa no encontrada.")
    session.delete(mass)
    session.commit()
    return Response(status_code=204)


@app.get("/api/ministers", response_model=list[schemas.MinisterRead])
def list_ministers(session: Session = Depends(get_session)):
    ministers = session.exec(select(Minister).where(Minister.active).order_by(Minister.name)).all()
    return [_min_read(m) for m in ministers]


@app.get("/api/masses/template.csv")
def download_masses_template():
    return Response(
        content=MASS_TEMPLATE_CSV,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="misas_semana.csv"'},
    )


@app.post("/api/masses/upload", response_model=schemas.UploadResult)
async def upload_masses(file: UploadFile = File(...), session: Session = Depends(get_session)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "El archivo está vacío.")

    result = parse_masses_csv(data)
    if result.errors:
        return schemas.UploadResult(
            imported=0,
            errors=[
                schemas.CsvIssue(row=e.row, column=e.column, message=e.message)
                for e in result.errors
            ],
            warnings=[
                schemas.CsvIssue(row=e.row, column=e.column, message=e.message)
                for e in result.warnings
            ],
        )

    existing = session.exec(select(Mass)).all()
    existing_by_key: dict[tuple[str, int, str], Mass] = {}
    for mass in existing:
        loc = mass.location
        if loc is not None:
            existing_by_key[(loc.name.casefold(), mass.day, mass.time)] = mass

    matched_ids: set[int] = set()
    for pm in result.masses:
        loc = session.exec(select(Location).where(Location.name == pm.location_name)).first()
        if loc is None:
            kind = pm.kind or "filial"
            loc = Location(name=pm.location_name, kind=kind, default_min=DAY_MIN.get(kind, 2))
            session.add(loc)
            session.flush()

        mass = existing_by_key.get((pm.location_name.casefold(), pm.day, pm.time))
        min_ministers = pm.min_ministers or loc.default_min
        if mass is None:
            session.add(
                Mass(
                    location_id=loc.id,
                    day=pm.day,
                    time=pm.time,
                    min_ministers=min_ministers,
                    active=True,
                )
            )
        else:
            matched_ids.add(mass.id)
            mass.active = True
            mass.location_id = loc.id
            mass.min_ministers = min_ministers
            session.add(mass)

    for mass in existing:
        if mass.id in matched_ids:
            continue
        if mass.assignments:
            mass.active = False
            session.add(mass)
        else:
            session.delete(mass)
    session.commit()

    return schemas.UploadResult(
        imported=len(result.masses),
        errors=[],
        warnings=[
            schemas.CsvIssue(row=e.row, column=e.column, message=e.message) for e in result.warnings
        ],
    )


@app.delete("/api/ministers", status_code=204)
def delete_ministers(session: Session = Depends(get_session)):
    for m in session.exec(select(Minister)).all():
        session.delete(m)
    session.commit()
    return Response(status_code=204)


@app.get("/api/ministers/template.csv")
def download_template():
    return Response(
        content=TEMPLATE_CSV,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ministros.csv"'},
    )


@app.post("/api/ministers/upload", response_model=schemas.UploadResult)
async def upload_ministers(file: UploadFile = File(...), session: Session = Depends(get_session)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "El archivo está vacío.")

    result = parse_csv(data)
    if result.errors:
        return schemas.UploadResult(
            imported=0,
            errors=[
                schemas.CsvIssue(row=e.row, column=e.column, message=e.message)
                for e in result.errors
            ],
            warnings=[
                schemas.CsvIssue(row=e.row, column=e.column, message=e.message)
                for e in result.warnings
            ],
        )

    old = session.exec(select(Minister)).all()
    to_delete = [m for m in old if not m.assignments]
    to_keep = [m for m in old if m.assignments]
    for m in to_delete:
        session.delete(m)
    for m in to_keep:
        m.active = False

    for pm in result.ministers:
        session.add(
            Minister(
                name=pm.name,
                phone=pm.phone or None,
                days_available=",".join(str(d) for d in pm.days),
            )
        )
    session.commit()

    return schemas.UploadResult(
        imported=len(result.ministers),
        errors=[],
        warnings=[
            schemas.CsvIssue(row=e.row, column=e.column, message=e.message) for e in result.warnings
        ],
    )


@app.post("/api/roster/generate", response_model=schemas.RosterRead)
def generate(week_start: date | None = None, session: Session = Depends(get_session)):
    week_start = _resolve_week(week_start)
    roster = generate_roster(session, week_start)
    return _build_week_data(session, roster)


@app.get("/api/roster", response_model=schemas.RosterRead)
def get_roster(week_start: date | None = None, session: Session = Depends(get_session)):
    week_start = _resolve_week(week_start)
    roster = session.exec(select(RosterWeek).where(RosterWeek.week_start == week_start)).first()
    if not roster:
        raise HTTPException(404, "No hay rol generado para esa semana.")
    return _build_week_data(session, roster)


@app.get("/api/roster/pdf")
def download_roster_pdf(week_start: date | None = None, session: Session = Depends(get_session)):
    week_start = _resolve_week(week_start)
    roster = session.exec(select(RosterWeek).where(RosterWeek.week_start == week_start)).first()
    if not roster:
        raise HTTPException(404, "No hay rol generado para esa semana.")
    data = _build_week_data(session, roster)
    filename = f"rol_{week_start.isoformat()}.pdf"
    return Response(
        content=build_roster_pdf(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/roster/download.csv")
def download_roster(week_start: date | None = None, session: Session = Depends(get_session)):
    week_start = _resolve_week(week_start)
    roster = session.exec(select(RosterWeek).where(RosterWeek.week_start == week_start)).first()
    if not roster:
        raise HTTPException(404, "No hay rol generado para esa semana.")

    data = _build_week_data(session, roster)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["dia", "fecha", "lugar", "hora", "ministros"])
    for day in data["days"]:
        for m in day["masses"]:
            names = ", ".join(x["name"] for x in m["ministers"]) or "(falta cubrir)"
            writer.writerow([day["label"], day["date"], m["location"], m["time"], names])

    filename = f"rol_{week_start.isoformat()}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/roster/print", response_class=HTMLResponse)
def print_page(
    request: Request,
    week_start: date | None = None,
    session: Session = Depends(get_session),
):
    week_start = _resolve_week(week_start)
    roster = session.exec(select(RosterWeek).where(RosterWeek.week_start == week_start)).first()
    if not roster:
        raise HTTPException(404, "No hay rol generado para esa semana.")
    data = _build_week_data(session, roster)
    return templates.TemplateResponse(
        request=request, name="roster_print.html", context={"week": data}
    )
