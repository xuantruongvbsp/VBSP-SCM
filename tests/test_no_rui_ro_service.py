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

