from __future__ import annotations

import json
from datetime import date, datetime

import db
from config import DS_PGD, PGD_XA_MAP

_PGD_BIEN_HOA = "Địa bàn Biên Hòa"


def doc_tasks(chi_dang_theo_doi: bool = True) -> list[dict]:
    with db.get_conn() as conn:
        sql = "SELECT * FROM tien_do_task"
        if chi_dang_theo_doi:
            sql += " WHERE trang_thai = 'dang_theo_doi'"
        sql += " ORDER BY ngay_deadline ASC"
        return [dict(r) for r in conn.execute(sql).fetchall()]


def doc_ketqua_task(task_id: int) -> list[dict]:
    with db.get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM tien_do_ketqua WHERE task_id=? ORDER BY pgd, ten_xa",
                (task_id,),
            ).fetchall()
        ]


def khoi_tao_ketqua_task(
    task_id: int,
    ds_pgd_task: list[str],
    cap_theo_doi: str = "xa",
    loai_noi_dung: str = "chi_tiet_xa",
) -> None:
    rows: list[tuple] = []
    if cap_theo_doi == "pgd":
        for pgd in ds_pgd_task:
            rows.append((task_id, pgd, pgd, loai_noi_dung))
    else:
        for pgd in ds_pgd_task:
            for xa in PGD_XA_MAP.get(pgd, []):
                rows.append((task_id, pgd, xa, loai_noi_dung))
    with db.get_conn() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO tien_do_ketqua
               (task_id, pgd, ten_xa, trang_thai, loai_noi_dung)
               VALUES (?, ?, ?, 'chua_thuc_hien', ?)""",
            rows,
        )
        conn.commit()


def sync_bien_hoa_ketqua(task_id: int, cbtd_bien_hoa: str, loai_noi_dung: str) -> None:
    val = str(cbtd_bien_hoa or "").strip()
    with db.get_conn() as conn:
        if val:
            conn.execute(
                """INSERT OR IGNORE INTO tien_do_ketqua
                   (task_id, pgd, ten_xa, trang_thai, loai_noi_dung)
                   VALUES (?, ?, ?, 'chua_thuc_hien', ?)""",
                (task_id, _PGD_BIEN_HOA, _PGD_BIEN_HOA, loai_noi_dung),
            )
        else:
            conn.execute(
                "DELETE FROM tien_do_ketqua WHERE task_id=? AND ten_xa=?",
                (task_id, _PGD_BIEN_HOA),
            )
        conn.commit()


def upsert_ketqua_xa(
    task_id: int,
    ten_xa: str,
    pgd: str,
    trang_thai: str,
    ngay_ht: str | None,
    ghi_chu: str | None,
    username: str,
) -> None:
    now = datetime.now().isoformat()
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO tien_do_ketqua
               (task_id, pgd, ten_xa, trang_thai, ngay_hoan_thanh,
                ghi_chu, nguoi_nhap, ngay_nhap)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(task_id, ten_xa) DO UPDATE SET
                 trang_thai      = excluded.trang_thai,
                 ngay_hoan_thanh = excluded.ngay_hoan_thanh,
                 ghi_chu         = excluded.ghi_chu,
                 nguoi_nhap      = excluded.nguoi_nhap,
                 ngay_nhap       = excluded.ngay_nhap""",
            (task_id, pgd, ten_xa, trang_thai, ngay_ht, ghi_chu, username, now),
        )
        conn.commit()


def cap_nhat_ketqua_bulk(
    task_id: int,
    cap_theo_doi: str,
    pgd_sel: str,
    rows: list[dict],
    username: str,
) -> tuple[int, list[tuple[str, str]]]:
    count = 0
    errors: list[tuple[str, str]] = []
    for r in rows:
        ten_xa_dv = str(r.get("ten_xa") or "").strip()
        if not ten_xa_dv:
            continue
        hoan_thanh = bool(r.get("hoan_thanh"))
        trang_thai = "da_hoan_thanh" if hoan_thanh else "chua_thuc_hien"
        ngay_ht = r.get("ngay_hoan_thanh")
        if isinstance(ngay_ht, date):
            ngay_ht = ngay_ht.isoformat()
        elif ngay_ht:
            try:
                ngay_ht = date.fromisoformat(str(ngay_ht)).isoformat()
            except Exception:
                ngay_ht = None
        ghi_chu = str(r.get("ghi_chu") or "").strip() or None
        pgd_val = ten_xa_dv if cap_theo_doi == "pgd" else pgd_sel
        try:
            upsert_ketqua_xa(task_id, ten_xa_dv, pgd_val, trang_thai, ngay_ht, ghi_chu, username)
            count += 1
        except Exception as e:
            errors.append((ten_xa_dv, str(e)))
    return count, errors


def tao_task(
    tieu_de: str,
    mo_ta: str | None,
    deadline: date,
    ds_pgd: list[str] | None,
    loai: str,
    uu_tien: str,
    username: str,
    cap_theo_doi: str,
    ngay_bat_dau: date | None = None,
    nguoi_phu_trach: str | None = None,
    nguoi_thuc_hien_cn: str = "",
    cbtd_bien_hoa: str = "",
    ghi_chu: str | None = None,
) -> int:
    pgd_luu = ds_pgd or DS_PGD
    ds_pgd_json = json.dumps(pgd_luu, ensure_ascii=False)
    ngay_bd = ngay_bat_dau or date.today()
    with db.get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO tien_do_task
               (tieu_de, mo_ta, ngay_deadline, ds_pgd, loai,
                uu_tien, nguoi_tao, ngay_tao, trang_thai, ghi_chu,
                cap_theo_doi, ngay_bat_dau, nguoi_phu_trach, nguoi_thuc_hien_cn,
                cbtd_bien_hoa)
               VALUES (?,?,?,?,?,?,?,?,'dang_theo_doi',?,?,?,?,?,?)""",
            (
                str(tieu_de).strip(),
                str(mo_ta).strip() or None if mo_ta is not None else None,
                deadline.isoformat(),
                ds_pgd_json,
                loai,
                uu_tien,
                username,
                datetime.now().isoformat(),
                str(ghi_chu).strip() or None if ghi_chu is not None else None,
                cap_theo_doi,
                ngay_bd.isoformat(),
                str(nguoi_phu_trach).strip() or None if nguoi_phu_trach is not None else None,
                str(nguoi_thuc_hien_cn).strip(),
                str(cbtd_bien_hoa).strip(),
            ),
        )
        task_id = int(cur.lastrowid)
        conn.commit()

    loai_noi_dung = "chung_pgd" if cap_theo_doi == "pgd" else "chi_tiet_xa"
    khoi_tao_ketqua_task(task_id, pgd_luu, cap_theo_doi, loai_noi_dung)
    sync_bien_hoa_ketqua(task_id, cbtd_bien_hoa, loai_noi_dung)
    return task_id


def cap_nhat_task(
    task_id: int,
    tieu_de: str,
    mo_ta: str | None,
    deadline: date,
    loai: str,
    uu_tien: str,
    ghi_chu: str | None,
    cap_theo_doi: str,
    ngay_bat_dau: date,
    nguoi_phu_trach: str | None,
    nguoi_thuc_hien_cn: str,
    cbtd_bien_hoa: str,
) -> None:
    with db.get_conn() as conn:
        conn.execute(
            """UPDATE tien_do_task
               SET tieu_de=?, mo_ta=?, ngay_deadline=?, loai=?,
                   uu_tien=?, ghi_chu=?,
                   cap_theo_doi=?, ngay_bat_dau=?, nguoi_phu_trach=?,
                   nguoi_thuc_hien_cn=?,
                   cbtd_bien_hoa=?
               WHERE id=?""",
            (
                str(tieu_de).strip(),
                str(mo_ta).strip() or None if mo_ta is not None else None,
                deadline.isoformat(),
                loai,
                uu_tien,
                str(ghi_chu).strip() or None if ghi_chu is not None else None,
                cap_theo_doi,
                ngay_bat_dau.isoformat(),
                str(nguoi_phu_trach).strip() or None if nguoi_phu_trach is not None else None,
                str(nguoi_thuc_hien_cn).strip(),
                str(cbtd_bien_hoa).strip(),
                task_id,
            ),
        )
        conn.commit()
    loai_noi_dung = "chung_pgd" if cap_theo_doi == "pgd" else "chi_tiet_xa"
    sync_bien_hoa_ketqua(task_id, cbtd_bien_hoa, loai_noi_dung)


def doi_trang_thai_task(task_id: int, trang_thai: str) -> None:
    with db.get_conn() as conn:
        conn.execute("UPDATE tien_do_task SET trang_thai=? WHERE id=?", (trang_thai, task_id))
        conn.commit()


def xoa_task(task_id: int) -> None:
    with db.get_conn() as conn:
        conn.execute("DELETE FROM tien_do_ketqua WHERE task_id=?", (task_id,))
        conn.execute("DELETE FROM tien_do_task WHERE id=?", (task_id,))
        conn.commit()
