
from pathlib import Path

from scm_platform.database import DEFAULT_DB, connect, init_db


def init_change_db(db_path: str | Path = DEFAULT_DB) -> None:
    init_db(db_path)

    with connect(db_path) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN (
                        'pending', 'approved', 'rejected', 'applied'
                    )),
                reviewer TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                decision_at TEXT,
                applied_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS change_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(request_id)
                    REFERENCES change_requests(id)
            )
        """)


def _required(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} бос болмауы керек")
    return value.strip()


def create_change_request(
    project_id: int,
    title: str,
    description: str = "",
    author: str = "Developer",
    db_path: str | Path = DEFAULT_DB,
) -> int:
    title = _required(title, "Тақырып")
    author = _required(author, "Автор")
    init_change_db(db_path)

    with connect(db_path) as db:
        project = db.execute(
            "SELECT id FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()

        if project is None:
            raise ValueError("Мұндай жоба жоқ")

        cursor = db.execute(
            """INSERT INTO change_requests
               (project_id, title, description)
               VALUES (?, ?, ?)""",
            (project_id, title, description),
        )

        request_id = cursor.lastrowid

        db.execute(
            """INSERT INTO change_events
               (request_id, action, actor)
               VALUES (?, 'created', ?)""",
            (request_id, author),
        )

        return request_id


def get_change_request(
    request_id: int,
    db_path: str | Path = DEFAULT_DB,
) -> dict | None:
    init_change_db(db_path)

    with connect(db_path) as db:
        row = db.execute(
            "SELECT * FROM change_requests WHERE id = ?",
            (request_id,),
        ).fetchone()

    return dict(row) if row is not None else None


def decide_change_request(
    request_id: int,
    approved: bool,
    reviewer: str,
    db_path: str | Path = DEFAULT_DB,
) -> None:
    reviewer = _required(reviewer, "Тексеруші")

    if not isinstance(approved, bool):
        raise ValueError("Шешім True немесе False болуы керек")

    init_change_db(db_path)

    with connect(db_path) as db:
        row = db.execute(
            "SELECT status FROM change_requests WHERE id = ?",
            (request_id,),
        ).fetchone()

        if row is None:
            raise ValueError("Сұрау табылмады")

        if row["status"] != "pending":
            raise ValueError("Бұл сұрау бойынша шешім қабылданған")

        status = "approved" if approved else "rejected"

        db.execute(
            """UPDATE change_requests
               SET status = ?, reviewer = ?,
                   decision_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, reviewer, request_id),
        )

        db.execute(
            """INSERT INTO change_events
               (request_id, action, actor)
               VALUES (?, ?, ?)""",
            (request_id, status, reviewer),
        )


def apply_change_request(
    request_id: int,
    actor: str,
    db_path: str | Path = DEFAULT_DB,
) -> None:
    actor = _required(actor, "Орындаушы")
    init_change_db(db_path)

    with connect(db_path) as db:
        row = db.execute(
            "SELECT status FROM change_requests WHERE id = ?",
            (request_id,),
        ).fetchone()

        if row is None:
            raise ValueError("Сұрау табылмады")

        if row["status"] != "approved":
            raise ValueError("Мақұлданбаған өзгерісті қолдануға болмайды")

        db.execute(
            """UPDATE change_requests
               SET status = 'applied',
                   applied_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (request_id,),
        )

        db.execute(
            """INSERT INTO change_events
               (request_id, action, actor)
               VALUES (?, 'applied', ?)""",
            (request_id, actor),
        )


def list_change_events(
    request_id: int,
    db_path: str | Path = DEFAULT_DB,
) -> list[dict]:
    init_change_db(db_path)

    with connect(db_path) as db:
        rows = db.execute(
            """SELECT * FROM change_events
               WHERE request_id = ?
               ORDER BY id""",
            (request_id,),
        ).fetchall()

    return [dict(row) for row in rows]
