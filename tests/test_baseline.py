
import hashlib
import sqlite3

import pytest

from scm_platform.baseline import (
    compare_baselines,
    create_baseline,
    get_baseline,
    register_item_version,
)
from scm_platform.changes import (
    create_change_request,
    decide_change_request,
)
from scm_platform.database import connect
from scm_platform.projects import create_project


@pytest.fixture
def project_db(tmp_path):
    db = tmp_path / "test.db"
    project_id = create_project("Demo", db_path=db)
    return db, project_id


def test_register_version(project_db):
    db, project_id = project_db

    version_id = register_item_version(
        project_id, "main.py", "1.0.0", "print(1)", db_path=db
    )

    assert version_id > 0


def test_sha256(project_db):
    db, project_id = project_db

    register_item_version(
        project_id, "main.py", "1.0.0", "abc", db_path=db
    )
    create_baseline(
        project_id, "BL-001", "Admin", "abc123", db
    )

    result = get_baseline("BL-001", db)

    assert result["items"][0]["sha256"] == hashlib.sha256(
        b"abc"
    ).hexdigest()


def test_missing_project(tmp_path):
    with pytest.raises(ValueError):
        register_item_version(
            999, "x.py", "1.0.0", "abc",
            db_path=tmp_path / "test.db",
        )


def test_empty_baseline(project_db):
    db, project_id = project_db

    with pytest.raises(ValueError):
        create_baseline(
            project_id, "BL-001", "Admin", "abc123", db
        )


def test_baseline_snapshot(project_db):
    db, project_id = project_db

    register_item_version(
        project_id, "main.py", "1.0.0", "abc", db_path=db
    )
    create_baseline(
        project_id, "BL-001", "Admin", "abc123", db
    )

    result = get_baseline("BL-001", db)

    assert result["items"][0]["version"] == "1.0.0"


def test_duplicate_baseline(project_db):
    db, project_id = project_db

    register_item_version(
        project_id, "main.py", "1.0.0", "abc", db_path=db
    )
    create_baseline(
        project_id, "BL-001", "Admin", "abc123", db
    )

    with pytest.raises(sqlite3.IntegrityError):
        create_baseline(
            project_id, "BL-001", "Admin", "abc123", db
        )


def test_unauthorized_update(project_db):
    db, project_id = project_db

    register_item_version(
        project_id, "main.py", "1.0.0", "abc", db_path=db
    )

    with pytest.raises(ValueError, match="Change Request"):
        register_item_version(
            project_id, "main.py", "1.1.0", "abcd",
            db_path=db,
        )


def test_rejected_update(project_db):
    db, project_id = project_db

    register_item_version(
        project_id, "main.py", "1.0.0", "abc", db_path=db
    )

    request_id = create_change_request(
        project_id, "Update main.py", db_path=db
    )
    decide_change_request(request_id, False, "Admin", db)

    with pytest.raises(ValueError, match="мақұлданбаған"):
        register_item_version(
            project_id, "main.py", "1.1.0", "abcd",
            request_id, db,
        )


def test_compare_and_old_snapshot(project_db):
    db, project_id = project_db

    register_item_version(
        project_id, "main.py", "1.0.0", "abc", db_path=db
    )
    create_baseline(
        project_id, "BL-001", "Admin", "abc123", db
    )

    request_id = create_change_request(
        project_id, "Update files", db_path=db
    )
    decide_change_request(request_id, True, "Admin", db)

    register_item_version(
        project_id, "main.py", "1.1.0",
        "abcd", request_id, db,
    )
    register_item_version(
        project_id, "new.py", "1.0.0",
        "new", request_id, db,
    )

    create_baseline(
        project_id, "BL-002", "Admin", "def456", db
    )

    result = compare_baselines("BL-001", "BL-002", db)

    assert result["added"] == ["new.py"]
    assert result["changed"] == [
        {"path": "main.py", "old": "1.0.0", "new": "1.1.0"}
    ]

    old = get_baseline("BL-001", db)
    assert old["items"][0]["version"] == "1.0.0"


def test_immutable_baseline(project_db):
    db, project_id = project_db

    register_item_version(
        project_id, "main.py", "1.0.0", "abc", db_path=db
    )
    create_baseline(
        project_id, "BL-001", "Admin", "abc123", db
    )

    with pytest.raises(sqlite3.IntegrityError):
        with connect(db) as connection:
            connection.execute(
                "DELETE FROM baseline_items WHERE baseline_id = ?",
                ("BL-001",),
            )
