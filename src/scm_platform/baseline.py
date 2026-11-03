
import hashlib
import re
from pathlib import Path

from scm_platform.changes import init_change_db
from scm_platform.database import DEFAULT_DB, connect


SEMVER = re.compile(r"\d+\.\d+\.\d+\Z")


def init_baseline_db(db_path: str | Path = DEFAULT_DB) -> None:
    init_change_db(db_path)

    with connect(db_path) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS config_items (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                path TEXT NOT NULL,
                UNIQUE(project_id, path)
            );

            CREATE TABLE IF NOT EXISTS item_versions (
                id INTEGER PRIMARY KEY,
                item_id INTEGER NOT NULL REFERENCES config_items(id),
                version TEXT NOT NULL,
                content TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                change_request_id INTEGER REFERENCES change_requests(id),
                UNIQUE(item_id, version)
            );

            CREATE TABLE IF NOT EXISTS baselines (
                id TEXT PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                approved_by TEXT NOT NULL,
                git_commit_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                sealed INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS baseline_items (
                baseline_id TEXT NOT NULL REFERENCES baselines(id),
                path TEXT NOT NULL,
                version TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                PRIMARY KEY(baseline_id, path)
            );

            CREATE TRIGGER IF NOT EXISTS lock_version_update
            BEFORE UPDATE ON item_versions BEGIN
                SELECT RAISE(ABORT, 'Version is immutable');
            END;

            CREATE TRIGGER IF NOT EXISTS lock_version_delete
            BEFORE DELETE ON item_versions BEGIN
                SELECT RAISE(ABORT, 'Version is immutable');
            END;

            CREATE TRIGGER IF NOT EXISTS lock_baseline_update
            BEFORE UPDATE ON baselines WHEN OLD.sealed = 1 BEGIN
                SELECT RAISE(ABORT, 'Baseline is immutable');
            END;

            CREATE TRIGGER IF NOT EXISTS lock_baseline_delete
            BEFORE DELETE ON baselines BEGIN
                SELECT RAISE(ABORT, 'Baseline is immutable');
            END;

            CREATE TRIGGER IF NOT EXISTS lock_baseline_item_insert
            BEFORE INSERT ON baseline_items
            WHEN (
                SELECT sealed FROM baselines
                WHERE id = NEW.baseline_id
            ) = 1
            BEGIN
                SELECT RAISE(ABORT, 'Baseline is immutable');
            END;

            CREATE TRIGGER IF NOT EXISTS lock_baseline_item_update
            BEFORE UPDATE ON baseline_items BEGIN
                SELECT RAISE(ABORT, 'Baseline is immutable');
            END;

            CREATE TRIGGER IF NOT EXISTS lock_baseline_item_delete
            BEFORE DELETE ON baseline_items BEGIN
                SELECT RAISE(ABORT, 'Baseline is immutable');
            END;
        """)


def register_item_version(
    project_id: int,
    path: str,
    version: str,
    content: str,
    change_request_id: int | None = None,
    db_path: str | Path = DEFAULT_DB,
) -> int:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Файл жолы бос болмауы керек")

    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError("Нұсқа пішімі X.Y.Z болуы керек")

    if not isinstance(content, str):
        raise ValueError("Файл мазмұны мәтін болуы керек")

    path = path.strip().replace("\\", "/")
    init_baseline_db(db_path)

    with connect(db_path) as db:
        project = db.execute(
            "SELECT 1 FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()

        if project is None:
            raise ValueError("Жоба табылмады")

        item = db.execute(
            """SELECT id FROM config_items
               WHERE project_id = ? AND path = ?""",
            (project_id, path),
        ).fetchone()

        last = None

        if item is not None:
            last = db.execute(
                """SELECT version FROM item_versions
                   WHERE item_id = ?
                   ORDER BY id DESC LIMIT 1""",
                (item["id"],),
            ).fetchone()

        has_baseline = db.execute(
            "SELECT 1 FROM baselines WHERE project_id = ? LIMIT 1",
            (project_id,),
        ).fetchone() is not None

        if last is not None or has_baseline:
            if change_request_id is None:
                raise ValueError(
                    "Өзгеріс үшін мақұлданған Change Request керек"
                )

        if change_request_id is not None:
            request = db.execute(
                """SELECT project_id, status
                   FROM change_requests WHERE id = ?""",
                (change_request_id,),
            ).fetchone()

            if request is None or request["project_id"] != project_id:
                raise ValueError(
                    "Change Request бұл жобаға тиесілі емес"
                )

            if request["status"] not in {"approved", "applied"}:
                raise ValueError("Өзгеріс мақұлданбаған")

        if last is not None:
            current = tuple(map(int, last["version"].split(".")))
            incoming = tuple(map(int, version.split(".")))

            if incoming <= current:
                raise ValueError(
                    "Нұсқа алдыңғысынан жоғары болуы керек"
                )

        if item is None:
            item_id = db.execute(
                """INSERT INTO config_items (project_id, path)
                   VALUES (?, ?)""",
                (project_id, path),
            ).lastrowid
        else:
            item_id = item["id"]

        digest = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

        cursor = db.execute(
            """INSERT INTO item_versions
               (item_id, version, content, sha256, change_request_id)
               VALUES (?, ?, ?, ?, ?)""",
            (item_id, version, content, digest, change_request_id),
        )

        return int(cursor.lastrowid)


def create_baseline(
    project_id: int,
    baseline_id: str,
    approved_by: str,
    git_commit_hash: str,
    db_path: str | Path = DEFAULT_DB,
) -> str:
    fields = (baseline_id, approved_by, git_commit_hash)

    if not all(
        isinstance(value, str) and value.strip()
        for value in fields
    ):
        raise ValueError(
            "Baseline ID, бекітуші және Git hash міндетті"
        )

    init_baseline_db(db_path)

    with connect(db_path) as db:
        project = db.execute(
            "SELECT 1 FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()

        if project is None:
            raise ValueError("Жоба табылмады")

        rows = db.execute(
            """SELECT ci.path, iv.version, iv.sha256
               FROM config_items ci
               JOIN item_versions iv ON iv.item_id = ci.id
               WHERE ci.project_id = ?
                 AND iv.id = (
                     SELECT MAX(v.id)
                     FROM item_versions v
                     WHERE v.item_id = ci.id
                 )
               ORDER BY ci.path""",
            (project_id,),
        ).fetchall()

        if not rows:
            raise ValueError(
                "Baseline жасау үшін файл нұсқаларын тіркеңіз"
            )

        db.execute(
            """INSERT INTO baselines
               (id, project_id, approved_by, git_commit_hash)
               VALUES (?, ?, ?, ?)""",
            (baseline_id, project_id, approved_by, git_commit_hash),
        )

        db.executemany(
            """INSERT INTO baseline_items
               (baseline_id, path, version, sha256)
               VALUES (?, ?, ?, ?)""",
            [
                (
                    baseline_id,
                    row["path"],
                    row["version"],
                    row["sha256"],
                )
                for row in rows
            ],
        )

        db.execute(
            "UPDATE baselines SET sealed = 1 WHERE id = ?",
            (baseline_id,),
        )

    return baseline_id


def get_baseline(
    baseline_id: str,
    db_path: str | Path = DEFAULT_DB,
) -> dict | None:
    init_baseline_db(db_path)

    with connect(db_path) as db:
        row = db.execute(
            "SELECT * FROM baselines WHERE id = ?",
            (baseline_id,),
        ).fetchone()

        if row is None:
            return None

        items = db.execute(
            """SELECT path, version, sha256
               FROM baseline_items
               WHERE baseline_id = ?
               ORDER BY path""",
            (baseline_id,),
        ).fetchall()

    return {
        **dict(row),
        "items": [dict(item) for item in items],
    }


def compare_baselines(
    old_id: str,
    new_id: str,
    db_path: str | Path = DEFAULT_DB,
) -> dict:
    old = get_baseline(old_id, db_path)
    new = get_baseline(new_id, db_path)

    if old is None or new is None:
        raise ValueError("Baseline табылмады")

    if old["project_id"] != new["project_id"]:
        raise ValueError(
            "Тек бір жобаның baseline-дарын салыстыруға болады"
        )

    old_items = {
        row["path"]: row for row in old["items"]
    }
    new_items = {
        row["path"]: row for row in new["items"]
    }

    return {
        "added": sorted(
            new_items.keys() - old_items.keys()
        ),
        "removed": sorted(
            old_items.keys() - new_items.keys()
        ),
        "changed": [
            {
                "path": path,
                "old": old_items[path]["version"],
                "new": new_items[path]["version"],
            }
            for path in sorted(
                old_items.keys() & new_items.keys()
            )
            if (
                old_items[path]["sha256"]
                != new_items[path]["sha256"]
                or old_items[path]["version"]
                != new_items[path]["version"]
            )
        ],
    }
