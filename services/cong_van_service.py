"""CongVan Service — Quản lý Công văn đến/đi (ROADMAP §2.4).

CRUD + tìm kiếm full-text + gắn tag + phân loại + xuất Excel.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd

import db
from utils import xuat_excel

LOAI_CONG_VAN = {
    "cong_van": "📋 Công văn",
    "quyet_dinh": "📜 Quyết định",
    "thong_bao": "📢 Thông báo",
    "bao_cao": "📊 Báo cáo",
    "huong_dan": "📖 Hướng dẫn",
    "khac": "📁 Khác",
}

TRANG_THAI_CV = {
    "chua_xu_ly": "⏳ Chưa xử lý",
    "dang_xu_ly": "🔄 Đang xử lý",
    "da_xu_ly": "✅ Đã xử lý",
    "luu_tru": "📦 Lưu trữ",
}

TAG_GOP_Y = [
    "TW", "HĐQT", "UBND", "Tín dụng", "Kế toán", "TCCB", "KTNB",
    "KHTD", "NQH", "Ủy thác", "GQVL", "NQ11", "Điện báo",
]


def them_cv(
    so_hieu: str,
    trich_yeu: str,
    ngay_ban_hanh: str,
    ngay_nhan: str,
    loai: str = "cong_van",
    co_quan: str = "",
    nguoi_ky: str = "",
    tag: str = "",
    noi_dung: str = "",
    file_path: str = "",
    onedrive_url: str = "",
    trang_thai: str = "chua_xu_ly",
    username: str = "",
) -> int:
    with db.get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO cong_van (so_hieu, trich_yeu, ngay_ban_hanh, ngay_nhan, loai,
               co_quan_ban_hanh, nguoi_ky, tag, noi_dung_tom_tat, file_path, onedrive_url,
               trang_thai, nguoi_tao)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (so_hieu, trich_yeu, ngay_ban_hanh, ngay_nhan, loai,
             co_quan, nguoi_ky, tag, noi_dung, file_path, onedrive_url, trang_thai, username),
        )
        conn.commit()
        cv_id = cur.lastrowid
    db.ghi_audit(username, "them_cong_van", f"#{cv_id}: {so_hieu} — {trich_yeu[:40]}")
    return cv_id


def cap_nhat_cv(
    cv_id: int,
    so_hieu: str | None = None,
    trich_yeu: str | None = None,
    ngay_ban_hanh: str | None = None,
    ngay_nhan: str | None = None,
    loai: str | None = None,
    co_quan: str | None = None,
    nguoi_ky: str | None = None,
    tag: str | None = None,
    noi_dung: str | None = None,
    file_path: str | None = None,
    onedrive_url: str | None = None,
    trang_thai: str | None = None,
    username: str = "",
) -> bool:
    sets = []
    params = []
    for col, val in [
        ("so_hieu", so_hieu), ("trich_yeu", trich_yeu),
        ("ngay_ban_hanh", ngay_ban_hanh), ("ngay_nhan", ngay_nhan),
        ("loai", loai), ("co_quan_ban_hanh", co_quan),
        ("nguoi_ky", nguoi_ky), ("tag", tag),
        ("noi_dung_tom_tat", noi_dung), ("file_path", file_path),
        ("onedrive_url", onedrive_url), ("trang_thai", trang_thai),
    ]:
        if val is not None:
            sets.append(f"{col} = ?")
            params.append(val)
    if not sets:
        return False
    sets.append("updated_at = datetime('now','localtime')")
    params.append(cv_id)
    with db.get_conn() as conn:
        conn.execute(f"UPDATE cong_van SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
    db.ghi_audit(username, "sua_cong_van", f"#{cv_id}")
    return True


def xoa_cv(cv_id: int, username: str = "") -> bool:
    with db.get_conn() as conn:
        conn.execute("DELETE FROM cong_van WHERE id = ?", (cv_id,))
        conn.commit()
    db.ghi_audit(username, "xoa_cong_van", f"#{cv_id}")
    return True


def doc_cv(cv_id: int) -> dict | None:
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM cong_van WHERE id = ?", (cv_id,)).fetchone()
    return dict(row) if row else None


def tim_kiem_cv(
    keyword: str = "",
    loai: str | None = None,
    tag: str | None = None,
    trang_thai: str | None = None,
    tu_ngay: str | None = None,
    den_ngay: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Tìm kiếm full-text công văn theo từ khóa + bộ lọc."""
    where = ["1=1"]
    params = []

    if keyword.strip():
        kw = f"%{keyword.strip()}%"
        where.append("(so_hieu LIKE ? OR trich_yeu LIKE ? OR noi_dung_tom_tat LIKE ? OR tag LIKE ? OR co_quan_ban_hanh LIKE ?)")
        params.extend([kw, kw, kw, kw, kw])
    if loai:
        where.append("loai = ?")
        params.append(loai)
    if tag:
        where.append("tag LIKE ?")
        params.append(f"%{tag}%")
    if trang_thai:
        where.append("trang_thai = ?")
        params.append(trang_thai)
    if tu_ngay:
        where.append("ngay_ban_hanh >= ?")
        params.append(tu_ngay)
    if den_ngay:
        where.append("ngay_ban_hanh <= ?")
        params.append(den_ngay)

    where_clause = " AND ".join(where)
    params.append(limit)
    sql = f"""SELECT * FROM cong_van
              WHERE {where_clause}
              ORDER BY ngay_ban_hanh DESC, id DESC
              LIMIT ?"""

    with db.get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def ds_cv_theo_tag(tag: str, limit: int = 50) -> list[dict]:
    return tim_kiem_cv(tag=tag, limit=limit)


def ds_cv_sap_den_han(ngay_canh_bao: str | None = None) -> list[dict]:
    """Công văn chưa xử lý đã NHẬN quá N ngày (lọc theo ngay_nhan, không phải ngay_ban_hanh)."""
    if ngay_canh_bao is None:
        from datetime import date, timedelta
        ngay_canh_bao = (date.today() - timedelta(days=7)).isoformat()
    with db.get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM cong_van
               WHERE trang_thai = 'chua_xu_ly' AND ngay_nhan <= ?
               ORDER BY ngay_nhan ASC
               LIMIT 50""",
            (ngay_canh_bao,),
        ).fetchall()
    return [dict(r) for r in rows]


def thong_ke_cv_theo_loai() -> pd.DataFrame:
    with db.get_conn() as conn:
        rows = conn.execute(
            """SELECT loai, COUNT(*) as so_luong FROM cong_van GROUP BY loai ORDER BY so_luong DESC"""
        ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if not df.empty:
        df["Tên loại"] = df["loai"].map(LOAI_CONG_VAN)
    return df


def thong_ke_cv_theo_trang_thai() -> pd.DataFrame:
    with db.get_conn() as conn:
        rows = conn.execute(
            """SELECT trang_thai, COUNT(*) as so_luong FROM cong_van GROUP BY trang_thai ORDER BY so_luong DESC"""
        ).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if not df.empty:
        df["Tên trạng thái"] = df["trang_thai"].map(TRANG_THAI_CV)
    return df


def xuat_danh_sach_cv(
    keyword: str = "",
    loai: str | None = None,
    tag: str | None = None,
    trang_thai: str | None = None,
) -> bytes:
    ds = tim_kiem_cv(keyword=keyword, loai=loai, tag=tag, trang_thai=trang_thai, limit=500)
    if not ds:
        return xuat_excel({"Danh sách": pd.DataFrame()})

    rows = []
    for r in ds:
        rows.append({
            "Số hiệu": r.get("so_hieu", ""),
            "Trích yếu": r.get("trich_yeu", ""),
            "Ngày BH": r.get("ngay_ban_hanh", "")[:10],
            "Ngày nhận": r.get("ngay_nhan", "")[:10],
            "Loại": LOAI_CONG_VAN.get(r.get("loai", ""), r.get("loai", "")),
            "Cơ quan": r.get("co_quan_ban_hanh", ""),
            "Người ký": r.get("nguoi_ky", ""),
            "Tag": r.get("tag", ""),
            "Trạng thái": TRANG_THAI_CV.get(r.get("trang_thai", ""), r.get("trang_thai", "")),
            "Nội dung": r.get("noi_dung_tom_tat", ""),
            "OneDrive URL": r.get("onedrive_url", ""),
        })

    df = pd.DataFrame(rows)
    stats = thong_ke_cv_theo_loai()
    stats_tt = thong_ke_cv_theo_trang_thai()
    return xuat_excel({
        "Danh sách công văn": df,
        "Theo loại": stats,
        "Theo trạng thái": stats_tt,
    })
