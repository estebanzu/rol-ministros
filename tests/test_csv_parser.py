from app.csv_parser import parse_csv, parse_masses_csv

CSV_HEADER = "nombre,telefono,lunes,martes,miercoles,jueves,viernes,sabado,domingo\n"
MASSES_HEADER = "dia,lugar,tipo,hora,minimo\n"


def test_semicolon_detected():
    text = (
        "nombre;telefono;lunes;martes;miercoles;jueves;viernes;sabado;domingo\n"
        "Maria;111;si;no;si;no;no;si;si\n"
    )
    result = parse_csv(text.encode("utf-8"))
    assert not result.errors
    assert result.ministers[0].name == "Maria"
    assert result.ministers[0].days == [1, 3, 6, 7]


def test_utf8_bom():
    result = parse_csv(("\ufeff" + CSV_HEADER + "Maria,111,si,no,no,no,no,no,no\n").encode("utf-8"))
    assert not result.errors
    assert result.ministers[0].name == "Maria"


def test_latin1_encoding():
    text = CSV_HEADER + "María Pérez,111,si,no,no,no,no,no,no\n"
    result = parse_csv(text.encode("latin-1"))
    assert not result.errors
    assert result.ministers[0].name == "María Pérez"


def test_day_value_variants():
    text = CSV_HEADER + "Ana,111,S,x,1,verdadero,no,0,\n"
    result = parse_csv(text.encode("utf-8"))
    assert not result.errors
    assert result.ministers[0].days == [1, 2, 3, 4]


def test_invalid_value_error_with_row_and_column():
    text = CSV_HEADER + "Ana,111,quizas,no,no,no,no,no,no\n"
    result = parse_csv(text.encode("utf-8"))
    assert len(result.errors) == 1
    assert result.errors[0].row == 2
    assert result.errors[0].column == "lunes"


def test_missing_phone_column_is_error():
    text = "nombre,lunes,martes,miercoles,jueves,viernes,sabado,domingo\nAna,si,no,no,no,no,no,no\n"
    result = parse_csv(text.encode("utf-8"))
    assert result.errors
    assert "telefono" in result.errors[0].message


def test_accented_day_headers_accepted():
    text = (
        "nombre,telefono,lunes,martes,miércoles,jueves,viernes,sábado,domingo\n"
        "Ana,111,si,no,si,no,no,si,no\n"
    )
    result = parse_csv(text.encode("utf-8"))
    assert not result.errors
    assert result.ministers[0].days == [1, 3, 6]


def test_empty_name_is_error():
    text = CSV_HEADER + ",111,si,no,no,no,no,no,no\n"
    result = parse_csv(text.encode("utf-8"))
    assert result.errors
    assert result.errors[0].column == "nombre"


def test_missing_phone_is_warning_not_error():
    text = CSV_HEADER + "Ana,,si,no,no,no,no,no,no\n"
    result = parse_csv(text.encode("utf-8"))
    assert not result.errors
    assert any(w.column == "telefono" for w in result.warnings)


def test_empty_file():
    result = parse_csv(b"")
    assert result.errors


def test_error_keeps_valid_rows_separate():
    text = CSV_HEADER + "Ana,111,si,si,si,si,si,si,si\nJuan,222,quizas,no,no,no,no,no,no\n"
    result = parse_csv(text.encode("utf-8"))
    assert len(result.ministers) == 1
    assert result.ministers[0].name == "Ana"
    assert len(result.errors) == 1
    assert result.errors[0].row == 3


def test_masses_valid():
    text = (
        MASSES_HEADER
        + "Domingo,Parroquia San Jose,Centro,10:00,4\nSabado,Capilla La Paz,Filial,19:00,2\n"
    )
    result = parse_masses_csv(text.encode("utf-8"))
    assert not result.errors
    assert len(result.masses) == 2
    assert result.masses[0].day == 7
    assert result.masses[0].location_name == "Parroquia San Jose"
    assert result.masses[0].kind == "centro"
    assert result.masses[0].min_ministers == 4
    assert result.masses[1].day == 6
    assert result.masses[1].min_ministers == 2


def test_masses_accented_days_and_numbers():
    text = MASSES_HEADER + "Miércoles,Lugar Uno,,19:30,\n4,Otro Lugar,,08:00,3\n"
    result = parse_masses_csv(text.encode("utf-8"))
    assert not result.errors
    days = {m.day for m in result.masses}
    assert days == {3, 4}
    assert result.masses[0].min_ministers is None
    assert result.masses[1].min_ministers == 3


def test_masses_missing_minimo_defaults_none():
    text = MASSES_HEADER + "Viernes,Capilla,,19:30,\n"
    result = parse_masses_csv(text.encode("utf-8"))
    assert not result.errors
    assert result.masses[0].min_ministers is None


def test_masses_invalid_day():
    text = MASSES_HEADER + "Cualquierdia,Lugar,,\n"
    result = parse_masses_csv(text.encode("utf-8"))
    assert len(result.errors) == 1
    assert result.errors[0].column == "dia"
    assert result.masses == []


def test_masses_invalid_time():
    text = MASSES_HEADER + "Domingo,Lugar,,25:99,\n"
    result = parse_masses_csv(text.encode("utf-8"))
    assert len(result.errors) == 1
    assert result.errors[0].column == "hora"


def test_masses_missing_required_column():
    text = "dia,lugar,minimo\nDomingo,Lugar,4\n"
    result = parse_masses_csv(text.encode("utf-8"))
    assert result.errors
    assert "hora" in result.errors[0].message


def test_masses_duplicate_in_csv():
    text = MASSES_HEADER + "Domingo,Lugar,,10:00,\nDomingo,Lugar,,10:00,\n"
    result = parse_masses_csv(text.encode("utf-8"))
    assert len(result.masses) == 1
    assert len(result.errors) == 1


def test_masses_invalid_tipo():
    text = MASSES_HEADER + "Domingo,Lugar,Capilla,10:00,\n"
    result = parse_masses_csv(text.encode("utf-8"))
    assert len(result.errors) == 1
    assert result.errors[0].column == "tipo"


def test_masses_invalid_minimo():
    text = MASSES_HEADER + "Domingo,Lugar,,10:00,0\n"
    result = parse_masses_csv(text.encode("utf-8"))
    assert len(result.errors) == 1
    assert result.errors[0].column == "minimo"


def test_masses_empty_file():
    result = parse_masses_csv(b"")
    assert result.errors
