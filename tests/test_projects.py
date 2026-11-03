
import pytest

from scm_platform.projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    update_project,
)


def test_create_project(tmp_path):
    db = tmp_path / "test.db"
    project_id = create_project("Test", "Description", db)
    assert get_project(project_id, db)["name"] == "Test"


def test_list_projects(tmp_path):
    db = tmp_path / "test.db"
    create_project("First", db_path=db)
    create_project("Second", db_path=db)
    assert len(list_projects(db)) == 2


def test_duplicate_name(tmp_path):
    db = tmp_path / "test.db"
    create_project("Same", db_path=db)

    with pytest.raises(ValueError):
        create_project("Same", db_path=db)


def test_empty_name(tmp_path):
    with pytest.raises(ValueError):
        create_project("   ", db_path=tmp_path / "test.db")


def test_update_project(tmp_path):
    db = tmp_path / "test.db"
    project_id = create_project("Old", db_path=db)

    assert update_project(project_id, "New", "Changed", db)
    assert get_project(project_id, db)["description"] == "Changed"


def test_delete_project(tmp_path):
    db = tmp_path / "test.db"
    project_id = create_project("Delete me", db_path=db)

    assert delete_project(project_id, db)
    assert get_project(project_id, db) is None


def test_persistence(tmp_path):
    db = tmp_path / "test.db"
    create_project("Saved", db_path=db)

    assert list_projects(db)[0]["name"] == "Saved"
