from __future__ import annotations

import pytest

import db as db_module
from services import khnv_noi_bo_service


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("VBSP_SCM_DB_PATH", db_file)
    db_module.reset_conn()
    db_module.init_db()
    yield db_module
    db_module.reset_conn()


def test_doc_ds_default_empty(test_db):
    assert khnv_noi_bo_service.doc_ds("khnv_test_list") == []


def test_ghi_ds_roundtrip_and_audit(test_db):
    key = "khnv_test_list"
    ds = [{"id": "1", "x": 1}]
    khnv_noi_bo_service.ghi_ds(key, ds, username="tester", action="khnv_test_write", mo_ta="write")
    assert khnv_noi_bo_service.doc_ds(key) == ds

    with db_module.get_conn() as conn:
        rows = conn.execute(
            "SELECT username, action, detail FROM audit_log WHERE username=? ORDER BY id DESC LIMIT 1",
            ("tester",),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["action"] == "khnv_test_write"

