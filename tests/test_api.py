from datetime import date

from sqlmodel import select

from app.models import RosterWeek

MONDAY = date.fromisocalendar(2026, 32, 1)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Ministros" in r.text


def _location(client, name, kind):
    r = client.post("/api/locations", json={"name": name, "kind": kind})
    assert r.status_code == 201, r.text
    return r.json()


def test_location_default_min(client):
    centro = _location(client, "Parroquia San José", "centro")
    filial = _location(client, "Capilla La Paz", "filial")
    assert centro["default_min"] == 4
    assert filial["default_min"] == 2


def test_duplicate_mass_returns_409(client):
    loc = _location(client, "Centro", "centro")
    payload = {"location_id": loc["id"], "day": 7, "time": "10:00"}
    assert client.post("/api/masses", json=payload).status_code == 201
    assert client.post("/api/masses", json=payload).status_code == 409


def test_mass_default_min_from_location(client):
    loc = _location(client, "Filial", "filial")
    r = client.post("/api/masses", json={"location_id": loc["id"], "day": 6, "time": "19:00"})
    assert r.status_code == 201
    assert r.json()["min_ministers"] == 2


def test_mass_invalid_time(client):
    loc = _location(client, "Centro", "centro")
    r = client.post("/api/masses", json={"location_id": loc["id"], "day": 7, "time": "25:99"})
    assert r.status_code == 400


def _csv_bytes(rows):
    header = "nombre,telefono,lunes,martes,miercoles,jueves,viernes,sabado,domingo\n"
    return (header + rows).encode("utf-8")


def test_upload_with_error_saves_nothing(client):
    bad = _csv_bytes("Maria,111,si,si,si,si,si,si,si\nJuan,222,quizas,si,si,si,si,si,si\n")
    r = client.post("/api/ministers/upload", files={"file": ("m.csv", bad, "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 0
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 3
    assert client.get("/api/ministers").json() == []


def test_upload_valid_and_replace(client):
    first = _csv_bytes("Maria,111,si,si,si,si,si,si,si\nJuan,222,si,si,si,si,si,si,si\n")
    r1 = client.post("/api/ministers/upload", files={"file": ("m.csv", first, "text/csv")})
    assert r1.json()["imported"] == 2

    second = _csv_bytes("Ana,333,si,si,si,si,si,si,si\n")
    r2 = client.post("/api/ministers/upload", files={"file": ("m.csv", second, "text/csv")})
    assert r2.json()["imported"] == 1

    names = [m["name"] for m in client.get("/api/ministers").json()]
    assert names == ["Ana"]


def test_download_template(client):
    r = client.get("/api/ministers/template.csv")
    assert r.status_code == 200
    assert r.text.startswith("nombre,telefono")


def _setup_full(client):
    centro = _location(client, "Parroquia San José", "centro")
    filial = _location(client, "Capilla La Paz", "filial")
    client.post("/api/masses", json={"location_id": centro["id"], "day": 7, "time": "10:00"})
    client.post("/api/masses", json={"location_id": filial["id"], "day": 6, "time": "19:00"})
    rows = "".join(f"Ministro {i},55{i},si,si,si,si,si,si,si\n" for i in range(1, 7))
    r = client.post(
        "/api/ministers/upload", files={"file": ("m.csv", _csv_bytes(rows), "text/csv")}
    )
    assert r.json()["imported"] == 6


def test_generate_and_get_roster(client):
    _setup_full(client)
    r = client.post("/api/roster/generate", params={"week_start": MONDAY.isoformat()})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["week_start"] == MONDAY.isoformat()
    assert len(data["days"]) == 7

    sunday = data["days"][6]
    assert any(
        m["location"] == "Parroquia San José" and len(m["ministers"]) == 4 for m in sunday["masses"]
    )
    saturday = data["days"][5]
    assert any(
        m["location"] == "Capilla La Paz" and len(m["ministers"]) == 2 for m in saturday["masses"]
    )

    g = client.get("/api/roster", params={"week_start": MONDAY.isoformat()})
    assert g.status_code == 200
    assert g.json()["week_start"] == MONDAY.isoformat()


def test_roster_persisted_in_db(client, session):
    _setup_full(client)
    client.post("/api/roster/generate", params={"week_start": MONDAY.isoformat()})
    roster = session.exec(select(RosterWeek).where(RosterWeek.week_start == MONDAY)).first()
    assert roster is not None
    assert roster.status == "ok"
    assert len(roster.assignments) == 6


def test_roster_con_faltantes(client):
    centro = _location(client, "Centro", "centro")
    client.post("/api/masses", json={"location_id": centro["id"], "day": 7, "time": "10:00"})
    rows = _csv_bytes("A,1,si,si,si,si,si,si,si\nB,2,si,si,si,si,si,si,si\n")
    client.post("/api/ministers/upload", files={"file": ("m.csv", rows, "text/csv")})
    r = client.post("/api/roster/generate", params={"week_start": MONDAY.isoformat()})
    assert r.status_code == 200
    assert r.json()["status"] == "con_faltantes"
    assert len(r.json()["warnings"]) == 1


def test_download_csv(client):
    _setup_full(client)
    client.post("/api/roster/generate", params={"week_start": MONDAY.isoformat()})
    r = client.get("/api/roster/download.csv", params={"week_start": MONDAY.isoformat()})
    assert r.status_code == 200
    lines = r.text.strip().splitlines()
    assert lines[0] == "dia,fecha,lugar,hora,ministros"
    assert len(lines) == 3


def test_print_page(client):
    _setup_full(client)
    client.post("/api/roster/generate", params={"week_start": MONDAY.isoformat()})
    r = client.get("/roster/print", params={"week_start": MONDAY.isoformat()})
    assert r.status_code == 200
    assert "Semana del" in r.text


def test_get_missing_roster_404(client):
    r = client.get("/api/roster", params={"week_start": MONDAY.isoformat()})
    assert r.status_code == 404


MASSES_CSV_HEADER = "dia,lugar,tipo,hora,minimo\n"


def _masses_csv(rows):
    return (MASSES_CSV_HEADER + rows).encode("utf-8")


def test_masses_template_download(client):
    r = client.get("/api/masses/template.csv")
    assert r.status_code == 200
    assert r.text.startswith("dia,lugar,tipo,hora,minimo")


def test_upload_masses_creates_locations_and_masses(client):
    rows = (
        "Domingo,Parroquia San Jose,Centro,10:00,4\n"
        "Sabado,Capilla La Paz,Filial,19:00,2\n"
        "Viernes,Parroquia San Jose,Centro,20:00,4\n"
    )
    r = client.post("/api/masses/upload", files={"file": ("m.csv", _masses_csv(rows), "text/csv")})
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 3
    assert data["errors"] == []

    locations = {loc["name"]: loc for loc in client.get("/api/locations").json()}
    assert locations["Parroquia San Jose"]["kind"] == "centro"
    assert locations["Parroquia San Jose"]["default_min"] == 4
    assert locations["Capilla La Paz"]["kind"] == "filial"
    assert locations["Capilla La Paz"]["default_min"] == 2

    masses = client.get("/api/masses").json()
    assert len(masses) == 3
    sunday = [m for m in masses if m["day"] == 7]
    assert sunday[0]["min_ministers"] == 4


def test_upload_masses_defaults_minimo(client):
    rows = "Domingo,Parroquia San Jose,Centro,10:00,\nSabado,Capilla La Paz,,19:00,\n"
    r = client.post("/api/masses/upload", files={"file": ("m.csv", _masses_csv(rows), "text/csv")})
    assert r.json()["imported"] == 2
    masses = client.get("/api/masses").json()
    by_key = {(m["location_name"], m["day"]): m for m in masses}
    assert by_key[("Parroquia San Jose", 7)]["min_ministers"] == 4
    assert by_key[("Capilla La Paz", 6)]["min_ministers"] == 2


def test_upload_masses_with_error_saves_nothing(client):
    rows = "Domingo,Parroquia San Jose,Centro,10:00,4\nSabado,Capilla La Paz,Filial,25:99,2\n"
    r = client.post("/api/masses/upload", files={"file": ("m.csv", _masses_csv(rows), "text/csv")})
    data = r.json()
    assert data["imported"] == 0
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 3
    assert client.get("/api/masses").json() == []
    assert client.get("/api/locations").json() == []


def test_upload_masses_replaces_previous(client):
    first = "Domingo,Parroquia San Jose,Centro,10:00,4\n"
    client.post("/api/masses/upload", files={"file": ("m.csv", _masses_csv(first), "text/csv")})

    second = "Sabado,Capilla La Paz,Filial,19:00,2\n"
    r = client.post(
        "/api/masses/upload", files={"file": ("m.csv", _masses_csv(second), "text/csv")}
    )
    assert r.json()["imported"] == 1

    masses = client.get("/api/masses").json()
    assert len(masses) == 1
    assert masses[0]["location_name"] == "Capilla La Paz"
    assert masses[0]["day"] == 6


def test_upload_masses_reupload_same_schedule(client):
    rows = "Domingo,Parroquia San Jose,Centro,10:00,4\nSabado,Capilla La Paz,Filial,19:00,2\n"
    client.post("/api/masses/upload", files={"file": ("m.csv", _masses_csv(rows), "text/csv")})
    r = client.post("/api/masses/upload", files={"file": ("m.csv", _masses_csv(rows), "text/csv")})
    assert r.status_code == 200
    assert r.json()["imported"] == 2
    assert len(client.get("/api/masses").json()) == 2
