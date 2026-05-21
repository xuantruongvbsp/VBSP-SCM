from __future__ import annotations

from datetime import datetime

import db
from data.pgd import pgd_slug


def tao_kv_key_thang(ten_pgd: str, nam: int, thang: int) -> str:
    return f"no_rui_ro_{pgd_slug(ten_pgd)}_{int(nam)}_{int(thang):02d}"


def tao_kv_key(ten_pgd: str, now: datetime | None = None) -> str:
    now_val = now or datetime.now()
    return tao_kv_key_thang(ten_pgd, now_val.year, now_val.month)


def doc_ho_so(kv_key: str) -> dict:
    val = db.doc_kv(kv_key)
    return val if isinstance(val, dict) else {}


def luu_ho_so(kv_key: str, danh_sach: list[dict], username: str, ten_pgd: str) -> None:
    payload = {"danh_sach": danh_sach, "ngay_tao": datetime.now().isoformat()}
    db.ghi_kv(kv_key, payload, username)
    db.ghi_audit(username, "luu_no_rui_ro", f"{len(danh_sach)} hồ sơ — {ten_pgd or 'unknown'}")


def xoa_ho_so(kv_key: str, username: str, ten_pgd: str, so_ho_so: int) -> None:
    db.ghi_kv(kv_key, {}, username)
    db.ghi_audit(username, "xoa_no_rui_ro", f"Xóa {int(so_ho_so)} hồ sơ — {ten_pgd or 'unknown'}")

