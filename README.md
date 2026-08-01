# Rol de Ministros de la Comunión

Aplicación web para generar el rol semanal de ministros de la comunión de una
parroquia. Se sube un CSV con los ministros y su disponibilidad por día de la
semana, se configuran los lugares y las misas, y la aplicación asigna los
ministros automáticamente.

## Características

- Sin login, un solo coordinador local.
- Sube el CSV de ministros y reemplaza la lista (validando errores con número de fila).
- Sube el CSV de misas de la semana y reemplaza el horario completo (los lugares se crean automáticamente).
- Configura lugares (centro parroquial o filiales) y misas (día + hora + mínimo de ministros).
- El mínimo por defecto es **4 ministros en el centro parroquial** y **2 en cada filial** (editable por misa).
- Genera el rol de cualquier semana (lunes a domingo), determinista y equitativo.
- Avisa con un banner rojo cuando faltan ministros para cubrir una misa.
- Vista imprimible y descarga del rol en CSV (para enviar por WhatsApp).

## Requisitos

- Python 3.11 o 3.12
- La base de datos es un archivo local: `data/rol.db` (haz copias de seguridad copiando ese archivo).

## Puesta en marcha

### Linux / macOS

```bash
./run.sh
```

### Windows

```
run.bat
```

Luego abre <http://localhost:8000>.

Para probar sin esperar a tus datos reales, usa las plantillas de ejemplo:
`sample-data/misas_semana.csv` (pestaña Misas) y `sample-data/ministros_ejemplo.csv`.

## Formato del CSV

```csv
nombre,telefono,lunes,martes,miercoles,jueves,viernes,sabado,domingo
Maria Perez,555-1234,si,si,no,si,no,si,si
Juan Garcia,555-5678,no,si,si,si,si,no,no
```

- Columnas requeridas: `nombre`, `telefono`, y los 7 días de la semana (se aceptan acentos: `miércoles`, `sábado`).
- Disponible: `si`, `s`, `x`, `1`, `verdadero` (da igual mayúsculas). No disponible: `no`, `n`, `0`, celda vacía.
- El separador puede ser `,` o `;` (se detecta solo). Acepta archivos de Excel (UTF-8 con BOM o Latin-1).
- El teléfono es opcional (se avisa si falta).

### CSV de misas (pestaña Misas)

```csv
dia,lugar,tipo,hora,minimo
Domingo,Parroquia San Jose,Centro,10:00,4
Sabado,Capilla La Paz,,19:00,
```

- Columnas requeridas: `dia`, `lugar`, `hora`. Opcionales: `tipo`, `minimo`.
- Días: nombres en español con o sin acento (`Domingo`, `Sábado`, `Sabado`) o números del 1 al 7 (1 = lunes, 7 = domingo).
- `tipo`: `centro` o `filial` (vacío → la misa no recibe un lugar nuevo, se usa el mínimo 2).
- `minimo`: número mínimo de ministros (vacío → mínimo por defecto del lugar: 4 centro, 2 filial).
- Los lugares se crean automáticamente a partir de la columna `lugar` (el primer tipo no vacío define centro/filial). Subir un CSV reemplaza todo el horario de misas y los roles ya generados.

## Uso

1. **Misas**: sube el CSV de la semana (descarga la plantilla desde la pestaña Misas) o agrega misas manualmente; los lugares se crean automáticamente.
2. **Ministros**: descarga la plantilla CSV, complétala y súbela.
3. **Rol**: elige la semana (por defecto el próximo lunes), genera el rol, imprímelo o descárgalo en CSV.

## Desarrollo

Instalar dependencias y ejecutar los tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

### Estructura

```
app/
  main.py          rutas y API
  models.py        tablas SQLite (SQLModel)
  csv_parser.py    importación y validación de CSVs (ministros y misas)
  scheduler.py     algoritmo de asignación
  templates/       páginas (índice + rol imprimible)
  static/          CSS y JavaScript
tests/             tests (pytest)
sample-data/       CSV de ejemplo
data/              base de datos local (no versionada)
```
