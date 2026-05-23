from __future__ import annotations

from datetime import datetime

import pytest

import db as db_module
from data.pgd import pgd_slug
from services import no_rui_ro_service


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("VBSP_SCM_DB_PATH", db_file)
    db_module.reset_conn()
    db_module.init_db()
    yield db_module
    db_module.reset_conn()


def test_tao_kv_key_thang_format(test_db):
    ten_pgd = "PGD Long Thành"
    key = no_rui_ro_service.tao_kv_key_thang(ten_pgd, 2026, 5)
    assert key == f"no_rui_ro_{pgd_slug(ten_pgd)}_2026_05"


def test_tao_kv_key_now(test_db):
    ten_pgd = "PGD Long Thành"
    key = no_rui_ro_service.tao_kv_key(ten_pgd, now=datetime(2026, 5, 21, 10, 0, 0))
    assert key == f"no_rui_ro_{pgd_slug(ten_pgd)}_2026_05"


def test_luu_va_xoa_ho_so(test_db):
    ten_pgd = "PGD Long Thành"
    kv_key = no_rui_ro_service.tao_kv_key_thang(ten_pgd, 2026, 5)

    ds = [{"ten_kh": "A", "so_ku": "KU1", "du_no": 1_000_000, "bien_phap": "Khoanh nợ"}]
    no_rui_ro_service.luu_ho_so(kv_key, ds, username="tester", ten_pgd=ten_pgd)

    val = no_rui_ro_service.doc_ho_so(kv_key)
    assert isinstance(val, dict)
    assert val.get("danh_sach") == ds
    assert isinstance(val.get("ngay_tao"), str)

    no_rui_ro_service.xoa_ho_so(kv_key, username="tester", ten_pgd=ten_pgd, so_ho_so=len(ds))
    val2 = no_rui_ro_service.doc_ho_so(kv_key)
    assert val2 == {}


# ── additional edge cases ─────────────────────────────────────────────────────

def test_tao_kv_key_thang_pads_month(test_db):
    key = no_rui_ro_service.tao_kv_key_thang("PGD Long Thành", 2026, 1)
    assert "_2026_01" in key


def test_tao_kv_key_thang_double_digit_month(test_db):
    key = no_rui_ro_service.tao_kv_key_thang("PGD Long Thành", 2026, 12)
    assert "_2026_12" in key


def test_doc_ho_so_returns_empty_dict_when_key_missing(test_db):
    result = no_rui_ro_service.doc_ho_so("no_rui_ro_nonexistent_2026_99")
    assert result == {}


def test_luu_ho_so_empty_list(test_db):
    ten_pgd = "PGD Trảng Bom"
    key = no_rui_ro_service.tao_kv_key_thang(ten_pgd, 2026, 6)
    no_rui_ro_service.luu_ho_so(key, [], username="tester", ten_pgd=ten_pgd)
    val = no_rui_ro_service.doc_ho_so(key)
    assert val["danh_sach"] == []


def test_luu_ho_so_audit_logged(test_db):
    ten_pgd = "PGD Long Khánh"
    key = no_rui_ro_service.tao_kv_key_thang(ten_pgd, 2026, 7)
    ds = [{"ten_kh": "B", "so_ku": "KU99"}]
    no_rui_ro_service.luu_ho_so(key, ds, username="auditor", ten_pgd=ten_pgd)

    with test_db.get_conn() as conn:
        rows = conn.execute(
            "SELECT action FROM audit_log WHERE username='auditor' ORDER BY id DESC LIMIT 1"
        ).fetchall()
    assert rows and rows[0][0] == "luu_no_rui_ro"


def test_xoa_ho_so_audit_logged(test_db):
    ten_pgd = "PGD Xuân Lộc"
    key = no_rui_ro_service.tao_kv_key_thang(ten_pgd, 2026, 8)
    no_rui_ro_service.xoa_ho_so(key, username="auditor2", ten_pgd=ten_pgd, so_ho_so=3)

    with test_db.get_conn() as conn:
        rows = conn.execute(
            "SELECT action FROM audit_log WHERE username='auditor2' ORDER BY id DESC LIMIT 1"
        ).fetchall()
    assert rows and rows[0][0] == "xoa_no_rui_ro"


def test_multiple_pgd_keys_independent(test_db):
    pgd1, pgd2 = "PGD Long Thành", "PGD Trảng Bom"
    key1 = no_rui_ro_service.tao_kv_key_thang(pgd1, 2026, 5)
    key2 = no_rui_ro_service.tao_kv_key_thang(pgd2, 2026, 5)
    assert key1 != key2

    ds1 = [{"ten_kh": "KH1"}]
    ds2 = [{"ten_kh": "KH2"}, {"ten_kh": "KH3"}]
    no_rui_ro_service.luu_ho_so(key1, ds1, "tester", pgd1)
    no_rui_ro_service.luu_ho_so(key2, ds2, "tester", pgd2)

    assert len(no_rui_ro_service.doc_ho_so(key1)["danh_sach"]) == 1
    assert len(no_rui_ro_service.doc_ho_so(key2)["danh_sach"]) == 2

