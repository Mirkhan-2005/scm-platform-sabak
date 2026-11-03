
import pytest

from scm_platform.changes import (
    apply_change_request,
    create_change_request,
    decide_change_request,
    get_change_request,
    list_change_events,
)
from scm_platform.projects import create_project


@pytest.fixture
def project_db(tmp_path):
    db = tmp_path / "test.db"
    project_id = create_project("Demo", db_path=db)
    return db, project_id


def test_create_change(project_db):
    db, project_id = project_db
    request_id = create_change_request(
        project_id, "Add feature", db_path=db
    )
    assert get_change_request(request_id, db)["status"] == "pending"


def test_missing_project(tmp_path):
    with pytest.raises(ValueError):
        create_change_request(
            999, "Invalid", db_path=tmp_path / "test.db"
        )


def test_approve_change(project_db):
    db, project_id = project_db
    request_id = create_change_request(
        project_id, "Feature", db_path=db
    )
    decide_change_request(request_id, True, "Admin", db)
    assert get_change_request(request_id, db)["status"] == "approved"


def test_reject_change(project_db):
    db, project_id = project_db
    request_id = create_change_request(
        project_id, "Feature", db_path=db
    )
    decide_change_request(request_id, False, "Admin", db)
    assert get_change_request(request_id, db)["status"] == "rejected"


def test_cannot_apply_pending(project_db):
    db, project_id = project_db
    request_id = create_change_request(
        project_id, "Feature", db_path=db
    )

    with pytest.raises(ValueError):
        apply_change_request(request_id, "Developer", db)


def test_cannot_apply_rejected(project_db):
    db, project_id = project_db
    request_id = create_change_request(
        project_id, "Feature", db_path=db
    )
    decide_change_request(request_id, False, "Admin", db)

    with pytest.raises(ValueError):
        apply_change_request(request_id, "Developer", db)


def test_apply_approved(project_db):
    db, project_id = project_db
    request_id = create_change_request(
        project_id, "Feature", db_path=db
    )
    decide_change_request(request_id, True, "Admin", db)
    apply_change_request(request_id, "Developer", db)

    assert get_change_request(request_id, db)["status"] == "applied"


def test_cannot_approve_twice(project_db):
    db, project_id = project_db
    request_id = create_change_request(
        project_id, "Feature", db_path=db
    )
    decide_change_request(request_id, True, "Admin", db)

    with pytest.raises(ValueError):
        decide_change_request(request_id, False, "Admin", db)


def test_change_history(project_db):
    db, project_id = project_db
    request_id = create_change_request(
        project_id, "Feature", db_path=db
    )
    decide_change_request(request_id, True, "Admin", db)
    apply_change_request(request_id, "Developer", db)

    events = list_change_events(request_id, db)

    assert [event["action"] for event in events] == [
        "created", "approved", "applied"
    ]


def test_change_persistence(project_db):
    db, project_id = project_db
    request_id = create_change_request(
        project_id, "Persisted", db_path=db
    )
    assert get_change_request(request_id, db)["title"] == "Persisted"
