from __future__ import annotations

from datetime import date

import pytest

import db as db_module
from services import tien_do_service


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("VBSP_SCM_DB_PATH", db_file)
    db_module.reset_conn()
    db_module.init_db()
    yield db_module
    db_module.reset_conn()


def test_tao_task_tao_ketqua_pgd(test_db):
    task_id = tien_do_service.tao_task(
        tieu_de="Test task",
        mo_ta=None,
        deadline=date.today(),
        ds_pgd=["PGD Long Thành"],
        loai="chung",
        uu_tien="binh_thuong",
        username="tester",
        cap_theo_doi="pgd",
        ngay_bat_dau=date.today(),
        nguoi_phu_trach=None,
        nguoi_thuc_hien_cn="",
        cbtd_bien_hoa="",
    )
    tasks = tien_do_service.doc_tasks(chi_dang_theo_doi=False)
    assert any(t["id"] == task_id for t in tasks)

    kq = tien_do_service.doc_ketqua_task(task_id)
    assert len(kq) == 1
    assert kq[0]["pgd"] == "PGD Long Thành"
    assert kq[0]["ten_xa"] == "PGD Long Thành"


def test_sync_bien_hoa_ketqua_on_off(test_db):
    task_id = tien_do_service.tao_task(
        tieu_de="Test BH",
        mo_ta=None,
        deadline=date.today(),
        ds_pgd=["PGD Long Thành"],
        loai="chung",
        uu_tien="binh_thuong",
        username="tester",
        cap_theo_doi="pgd",
        ngay_bat_dau=date.today(),
        nguoi_phu_trach=None,
        nguoi_thuc_hien_cn="",
        cbtd_bien_hoa="CB BH",
    )
    kq = tien_do_service.doc_ketqua_task(task_id)
    assert any(r["ten_xa"] == "Địa bàn Biên Hòa" for r in kq)

    tien_do_service.cap_nhat_task(
        task_id=task_id,
        tieu_de="Test BH",
        mo_ta=None,
        deadline=date.today(),
        loai="chung",
        uu_tien="binh_thuong",
        ghi_chu=None,
        cap_theo_doi="pgd",
        ngay_bat_dau=date.today(),
        nguoi_phu_trach=None,
        nguoi_thuc_hien_cn="",
        cbtd_bien_hoa="",
    )
    kq2 = tien_do_service.doc_ketqua_task(task_id)
    assert not any(r["ten_xa"] == "Địa bàn Biên Hòa" for r in kq2)


def test_cap_nhat_ketqua_bulk(test_db):
    task_id = tien_do_service.tao_task(
        tieu_de="Bulk",
        mo_ta=None,
        deadline=date.today(),
        ds_pgd=["PGD Long Thành", "PGD Trảng Bom"],
        loai="chung",
        uu_tien="binh_thuong",
        username="tester",
        cap_theo_doi="pgd",
        ngay_bat_dau=date.today(),
        nguoi_phu_trach=None,
        nguoi_thuc_hien_cn="",
        cbtd_bien_hoa="",
    )
    count, errors = tien_do_service.cap_nhat_ketqua_bulk(
        task_id=task_id,
        cap_theo_doi="pgd",
        pgd_sel="__ALL__",
        rows=[
            {"ten_xa": "PGD Long Thành", "hoan_thanh": True, "ngay_hoan_thanh": date.today(), "ghi_chu": "x"},
            {"ten_xa": "PGD Trảng Bom", "hoan_thanh": False, "ngay_hoan_thanh": None, "ghi_chu": ""},
        ],
        username="tester",
    )
    assert count == 2
    assert errors == []
    kq = tien_do_service.doc_ketqua_task(task_id)
    m = {r["ten_xa"]: r for r in kq}
    assert m["PGD Long Thành"]["trang_thai"] == "da_hoan_thanh"
    assert m["PGD Trảng Bom"]["trang_thai"] == "chua_thuc_hien"

