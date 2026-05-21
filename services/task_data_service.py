"""Database access functions cho module Tiến độ Công việc.

Các hàm này là thin wrapper gọi qua services.tien_do_service,
giữ nguyên tên có underscore prefix để call sites trong tab_tien_do.py
không cần thay đổi.
"""
from __future__ import annotations

from services import tien_do_service

_PGD_BIEN_HOA = "Địa bàn Biên Hòa"


def _doc_tasks(chi_dang_theo_doi: bool = True) -> list[dict]:
    return tien_do_service.doc_tasks(chi_dang_theo_doi)


def _doc_ketqua_task(task_id: int) -> list[dict]:
    return tien_do_service.doc_ketqua_task(task_id)


def _khoi_tao_ketqua_task(
    task_id: int,
    ds_pgd_task: list[str],
    cap_theo_doi: str = "xa",
    loai_noi_dung: str = "chi_tiet_xa",
) -> None:
    tien_do_service.khoi_tao_ketqua_task(task_id, ds_pgd_task, cap_theo_doi, loai_noi_dung)


def _sync_bien_hoa_ketqua(task_id: int, cbtd_bien_hoa: str, loai_noi_dung: str) -> None:
    tien_do_service.sync_bien_hoa_ketqua(task_id, cbtd_bien_hoa, loai_noi_dung)


def _upsert_ketqua_xa(
    task_id: int,
    ten_xa: str,
    pgd: str,
    trang_thai: str,
    ngay_ht: str | None,
    ghi_chu: str | None,
    username: str,
) -> None:
    tien_do_service.upsert_ketqua_xa(task_id, ten_xa, pgd, trang_thai, ngay_ht, ghi_chu, username)
