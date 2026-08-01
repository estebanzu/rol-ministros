from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from . import models  # noqa: F401

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_DIR / 'rol.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if session.exec(select(models.Mass)).first():
            return
        location = models.Location(name="Centro Parroquial", kind="centro", default_min=4)
        session.add(location)
        session.commit()
        session.refresh(location)
        for day, time in [
            (1, "08:00"),
            (1, "18:00"),
            (2, "08:00"),
            (2, "18:00"),
            (3, "08:00"),
            (3, "18:00"),
            (4, "08:00"),
            (4, "18:00"),
            (5, "08:00"),
            (5, "18:00"),
            (6, "17:00"),
            (7, "08:00"),
            (7, "11:00"),
            (7, "16:00"),
        ]:
            session.add(
                models.Mass(
                    location_id=location.id,
                    day=day,
                    time=time,
                    min_ministers=4,
                    active=True,
                )
            )
        session.commit()


def get_session():
    with Session(engine) as session:
        yield session
