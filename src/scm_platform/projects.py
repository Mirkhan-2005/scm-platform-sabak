
import sqlite3
from pathlib import Path

from scm_platform.database import DEFAULT_DB, connect, init_db


def _valid_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Жоба атауы бос болмауы керек")
    return name.strip()


def create_project(
    name: str, description: str = "", db_path: str | Path = DEFAULT_DB
) -> int:
    name = _valid_name(name)
    init_db(db_path)

    with connect(db_path) as connection:
        try:
            cursor = connection.execute(
                "INSERT INTO projects (name, description) VALUES (?, ?)",
                (name, description),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("Бұл атаудағы жоба бұрын тіркелген") from error

        return int(cursor.lastrowid)


def get_project(
    project_id: int, db_path: str | Path = DEFAULT_DB
) -> dict | None:
    init_db(db_path)

    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def list_projects(db_path: str | Path = DEFAULT_DB) -> list[dict]:
    init_db(db_path)

    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM projects ORDER BY id"
        ).fetchall()

    return [dict(row) for row in rows]


def update_project(
    project_id: int,
    name: str,
    description: str,
    db_path: str | Path = DEFAULT_DB,
) -> bool:
    name = _valid_name(name)
    init_db(db_path)

    with connect(db_path) as connection:
        try:
            cursor = connection.execute(
                """UPDATE projects
                   SET name = ?, description = ?
                   WHERE id = ?""",
                (name, description, project_id),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("Бұл атаудағы жоба бұрын тіркелген") from error

        return cursor.rowcount > 0


def delete_project(
    project_id: int, db_path: str | Path = DEFAULT_DB
) -> bool:
    init_db(db_path)

    with connect(db_path) as connection:
        cursor = connection.execute(
            "DELETE FROM projects WHERE id = ?",
            (project_id,),
        )
        return cursor.rowcount > 0
