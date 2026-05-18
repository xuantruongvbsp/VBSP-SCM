"""
tab_trang_thai_nguon.py
───────────────────────
Trạng thái Nguồn dữ liệu — Health Check toàn diện hệ thống VBSP-SCM.

Hiển thị trong:
  - ws_management : toàn bộ 22 đơn vị + health check CN
  - ws_operation  : chỉ PGD được phân công + audit cá nhân

Sub-tabs:
  1. 📂 Tệp nguồn       — Trạng thái upload 22 đơn vị (HSTD / NQ11 / GQVL)
  2. 🔗 Merge & Cache   — merge_meta + parquet integrity (columns, duplicate)
  3. 📸 Snapshot        — Danh sách kỳ snapshot HSTD
  4. 👥 Người dùng      — User PGD thiếu pgd, tổng số tài khoản
  5. 💾 Hệ thống        — Dung lượng ổ đĩa, quyền ghi thư mục
  6. 📋 Audit log       — 100 thao tác gần nhất (có lọc)
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from auth import la_phan_he_cn, la_phan_he_pgd, normalize_role
from config import (
    CACHE_DIR,
    CACHE_GQVL,
    CACHE_HSTD,
    CACHE_NQ11,
    COT_MA_KH,
    COT_NGAY_SL,
    COT_SO_KU,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
    DS_PGD,
    FILE_PATH,
    FILE_PATH_GQVL,
    FILE_PATH_NQ11,
    GQVL_PGD_DIR,
    PGD_DATA_DIR,
)
from tabs.base_tab import TabContext

# ── Hằng số nội bộ ─────────────────────────────────────────────────────────
_DS_LOAI_FILE = ["hstd", "nq11", "gqvl"]

_REQUIRED_COLS_HSTD = [
    COT_TEN_PGD,
    COT_MA_KH,
    COT_SO_KU,
    COT_TONG_DU_NO,
    COT_NGAY_SL,
]

_CACHE_MAP = {
    "HSTD": CACHE_HSTD,
    "NQ11": CACHE_NQ11,
    "GQVL": CACHE_GQVL,
}

_SOURCE_MAP = {
    "HSTD": FILE_PATH,
    "NQ11": FILE_PATH_NQ11,
    "GQVL": FILE_PATH_GQVL,
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _ts_fmt(fp: str | Path) -> str:
    """Trả về chuỗi thời gian sửa đổi file, hoặc '—' nếu không tồn tại."""
    try:
        ts = os.path.getmtime(str(fp))
        return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "—"


def _size_fmt(fp: str | Path) -> str:
    """Trả về dung lượng file dạng KB/MB, hoặc '—'."""
    try:
        sz = os.path.getsize(str(fp))
        if sz >= 1_048_576:
            return f"{sz / 1_048_576:.1f} MB"
        return f"{sz / 1024:.0f} KB"
    except Exception:
        return "—"


def _pgd_slug_local(ten_pgd: str) -> str:
    """Slug đơn giản không phụ thuộc import vòng."""
    try:
        from data.pgd import pgd_slug
        return pgd_slug(ten_pgd)
    except Exception:
        import re, unicodedata
        s = unicodedata.normalize("NFD", ten_pgd.lower())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _pgd_hstd_path(ten_pgd: str) -> Path:
    return PGD_DATA_DIR / _pgd_slug_local(ten_pgd) / "hstd_latest.xlsx"


def _pgd_nq11_path(ten_pgd: str) -> Path:
    slug = _pgd_slug_local(ten_pgd)
    return PGD_DATA_DIR / slug / "nq11_latest.xlsx"


def _pgd_gqvl_path(ten_pgd: str) -> Path:
    slug = _pgd_slug_local(ten_pgd)
    return GQVL_PGD_DIR / f"gqvl_{slug}.xlsx"


# ── Sub-tab 1: Tệp nguồn ─────────────────────────────────────────────────
def _render_tep_nguon(la_cn: bool, pgd_user: str | None) -> None:
    st.subheader("📂 Trạng thái tệp nguồn")

    if la_cn:
        # ── File toàn CN (data/) ──────────────────────────────────────────
        st.markdown("#### 📁 File trung tâm (Phòng KH-NV upload)")
        rows_cn = []
        for loai, fp in _SOURCE_MAP.items():
            exists = os.path.exists(fp)
            rows_cn.append({
                "Loại": loai,
                "Đường dẫn": os.path.basename(fp),
                "Trạng thái": "✅ Có" if exists else "❌ Thiếu",
                "Cập nhật lần cuối": _ts_fmt(fp) if exists else "—",
                "Dung lượng": _size_fmt(fp) if exists else "—",
            })
        df_cn = pd.DataFrame(rows_cn)
        st.dataframe(df_cn, use_container_width=True, hide_index=True)

        st.markdown("#### 🏢 Upload riêng từng đơn vị (22 đơn vị)")
        ds_all = [DON_VI_CHI_NHANH] + DS_PGD
    else:
        ds_all = [pgd_user] if pgd_user else []

    rows_pgd = []
    for dv in ds_all:
        p_hstd = _pgd_hstd_path(dv)
        p_nq11 = _pgd_nq11_path(dv)
        p_gqvl = _pgd_gqvl_path(dv)
        rows_pgd.append({
            "Đơn vị": dv,
            "HSTD": "✅" if p_hstd.exists() else "❌",
            "HSTD cập nhật": _ts_fmt(p_hstd) if p_hstd.exists() else "—",
            "NQ11": "✅" if p_nq11.exists() else "❌",
            "NQ11 cập nhật": _ts_fmt(p_nq11) if p_nq11.exists() else "—",
            "GQVL": "✅" if p_gqvl.exists() else "❌",
            "GQVL cập nhật": _ts_fmt(p_gqvl) if p_gqvl.exists() else "—",
        })

    df_pgd = pd.DataFrame(rows_pgd)

    if la_cn:
        co_hstd = (df_pgd["HSTD"] == "✅").sum()
        co_nq11 = (df_pgd["NQ11"] == "✅").sum()
        co_gqvl = (df_pgd["GQVL"] == "✅").sum()
        total = len(ds_all)
        c1, c2, c3 = st.columns(3)
        c1.metric("HSTD có file", f"{co_hstd}/{total}")
        c2.metric("NQ11 có file", f"{co_nq11}/{total}")
        c3.metric("GQVL có file", f"{co_gqvl}/{total}")

    st.dataframe(df_pgd, use_container_width=True, hide_index=True)

    # ── Kiểm tra đồng nhất ngày số liệu ──────────────────────────────────
    if la_cn and os.path.exists(CACHE_HSTD):
        st.markdown("#### 📅 Kiểm tra Ngày số liệu")
        try:
            import duckdb
            con = duckdb.connect()
            rows = con.execute(f"""
                SELECT "{COT_TEN_PGD}", MAX("{COT_NGAY_SL}") as ngay_sl
                FROM read_parquet('{CACHE_HSTD}')
                GROUP BY "{COT_TEN_PGD}"
                ORDER BY ngay_sl DESC
            """).fetchall()
            con.close()
            if rows:
                dates = [r[1] for r in rows if r[1]]
                unique_dates = set(dates)
                if len(unique_dates) <= 1:
                    st.success(f"✅ Toàn bộ PGD đồng nhất ngày số liệu: **{dates[0] if dates else '—'}**")
                else:
                    st.warning(
                        f"⚠️ Ngày số liệu không đồng nhất — "
                        f"có **{len(unique_dates)}** mốc khác nhau"
                    )
                    df_dates = pd.DataFrame(rows, columns=["Đơn vị", "Ngày số liệu"])
                    st.dataframe(df_dates, use_container_width=True, hide_index=True, height=250)
        except Exception as e:
            st.error(f"Lỗi kiểm tra ngày số liệu: {e}")


# ── Sub-tab 2: Merge & Cache ──────────────────────────────────────────────
def _render_merge_cache(la_cn: bool) -> None:
    st.subheader("🔗 Merge & Parquet Cache")

    # ── Trạng thái merge_meta ────────────────────────────────────────────
    st.markdown("#### ⚙️ Trạng thái Merge")
    loai_merge = ["hstd", "nq11", "gqvl"]
    rows_merge = []
    for loai in loai_merge:
        meta = db.doc_kv(f"merge_meta_{loai}")
        if meta:
            rows_merge.append({
                "Loại": loai.upper(),
                "Trạng thái": "✅ Đã merge",
                "Thời gian merge": meta.get("thoi_gian", "—"),
                "Số PGD": meta.get("so_pgd", "—"),
                "Người thực hiện": meta.get("updated_by", meta.get("nguoi_dung", "—")),
            })
        else:
            rows_merge.append({
                "Loại": loai.upper(),
                "Trạng thái": "❌ Chưa merge",
                "Thời gian merge": "—",
                "Số PGD": "—",
                "Người thực hiện": "—",
            })
    st.dataframe(pd.DataFrame(rows_merge), use_container_width=True, hide_index=True)

    if not la_cn:
        return

    # ── Kiểm tra đồng bộ cấu hình DS_PGD ────────────────────────────────
    st.markdown("#### 🔄 Đồng bộ cấu hình DS_PGD")
    try:
        from utils import lay_config
        ds_kv = lay_config("ds_pgd", [])
        if not ds_kv:
            st.info("ℹ️ kv_store chưa có ds_pgd — đang dùng config.py mặc định.")
        elif set(ds_kv) != set(DS_PGD):
            only_kv = set(ds_kv) - set(DS_PGD)
            only_cfg = set(DS_PGD) - set(ds_kv)
            msg = []
            if only_kv:
                msg.append(f"Chỉ trong kv_store: {sorted(only_kv)}")
            if only_cfg:
                msg.append(f"Chỉ trong config.py: {sorted(only_cfg)}")
            st.warning("⚠️ DS_PGD không đồng bộ — " + " | ".join(msg))
        else:
            st.success(f"✅ DS_PGD đồng bộ — {len(DS_PGD)} đơn vị")
    except Exception as e:
        st.error(f"Lỗi kiểm tra cấu hình: {e}")

    # ── Kiểm tra parquet integrity ───────────────────────────────────────
    st.markdown("#### 📦 Kiểm tra Parquet Cache")
    try:
        import duckdb

        for ten, path in _CACHE_MAP.items():
            with st.expander(f"{ten} — `{os.path.basename(path)}`", expanded=(ten == "HSTD")):
                if not os.path.exists(path):
                    st.warning(f"⚠️ File cache chưa tồn tại: `{path}`")
                    continue

                st.caption(f"Cập nhật: {_ts_fmt(path)}  |  Dung lượng: {_size_fmt(path)}")

                try:
                    con = duckdb.connect()
                    # Kiểm tra cột bắt buộc (chỉ HSTD)
                    if ten == "HSTD":
                        actual_cols = con.execute(
                            f"SELECT * FROM read_parquet('{path}') LIMIT 0"
                        ).df().columns.tolist()
                        missing = [c for c in _REQUIRED_COLS_HSTD if c not in actual_cols]
                        if missing:
                            st.error(f"❌ Thiếu cột bắt buộc: {missing}")
                        else:
                            st.success(f"✅ Đủ {len(_REQUIRED_COLS_HSTD)} cột bắt buộc")

                        # Kiểm tra duplicate (Mã KH + Số khế ước)
                        dup_count = con.execute(f"""
                            SELECT COUNT(*) FROM (
                                SELECT "{COT_MA_KH}", "{COT_SO_KU}", COUNT(*) as cnt
                                FROM read_parquet('{path}')
                                GROUP BY "{COT_MA_KH}", "{COT_SO_KU}"
                                HAVING COUNT(*) > 1
                            )
                        """).fetchone()[0]
                        if dup_count > 0:
                            st.warning(
                                f"⚠️ Có **{dup_count:,}** cặp (Mã KH, Số khế ước) "
                                f"xuất hiện nhiều hơn 1 lần"
                            )
                        else:
                            st.success("✅ Không có bản ghi trùng lặp")

                    # Số dòng tổng
                    total_rows = con.execute(
                        f"SELECT COUNT(*) FROM read_parquet('{path}')"
                    ).fetchone()[0]
                    st.info(f"📊 Tổng số dòng: **{total_rows:,}**")
                    con.close()

                except Exception as e:
                    st.error(f"Lỗi đọc parquet: {e}")

    except ImportError:
        st.warning("⚠️ Cần cài `duckdb` để kiểm tra parquet integrity.")


# ── Sub-tab 3: Snapshot ───────────────────────────────────────────────────
def _render_snapshot() -> None:
    st.subheader("📸 Snapshot HSTD")
    try:
        conn = db.get_conn()
        rows = conn.execute(
            """
            SELECT ky, COUNT(DISTINCT ten_pgd) as so_pgd,
                   SUM(tong_du_no) as tong_du_no,
                   MIN(created_at) as tao_luc
            FROM hstd_snapshot
            GROUP BY ky
            ORDER BY ky DESC
            LIMIT 24
            """
        ).fetchall()

        if not rows:
            st.warning("❌ Chưa có snapshot nào. Dữ liệu lịch sử sẽ trống trước khi upload lần đầu.")
            return

        st.success(f"✅ Snapshot mới nhất: **{rows[0][0]}** ({rows[0][1]} đơn vị)")

        df_snap = pd.DataFrame(rows, columns=["Kỳ", "Số đơn vị", "Tổng dư nợ (VND)", "Tạo lúc"])
        df_snap["Tổng dư nợ (tỷ đ)"] = (df_snap["Tổng dư nợ (VND)"] / 1e12).round(1)
        df_snap = df_snap.drop(columns=["Tổng dư nợ (VND)"])
        st.dataframe(df_snap, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Lỗi đọc snapshot: {e}")


# ── Sub-tab 4: Người dùng ─────────────────────────────────────────────────
def _render_nguoi_dung() -> None:
    st.subheader("👥 Trạng thái Tài khoản")
    try:
        conn = db.get_conn()

        # Tổng hợp theo role
        rows_role = conn.execute(
            "SELECT role, COUNT(*) as so_luong FROM users GROUP BY role ORDER BY role"
        ).fetchall()
        if rows_role:
            df_role = pd.DataFrame(rows_role, columns=["Role", "Số tài khoản"])
            c1, c2 = st.columns([1, 2])
            with c1:
                st.metric("Tổng tài khoản", sum(r[1] for r in rows_role))
            with c2:
                st.dataframe(df_role, use_container_width=True, hide_index=True)

        # User PGD role nhưng không có pgd gán
        rows_no_pgd = conn.execute(
            """
            SELECT username, role, ho_ten
            FROM users
            WHERE role IN ('user_pgd','admin_pgd','manager_pgd','user')
              AND (pgd IS NULL OR pgd = '')
            ORDER BY username
            """
        ).fetchall()

        st.markdown("#### ⚠️ User PGD chưa được gán đơn vị")
        if rows_no_pgd:
            df_no_pgd = pd.DataFrame(rows_no_pgd, columns=["Username", "Role", "Họ tên"])
            st.warning(
                f"Có **{len(rows_no_pgd)}** tài khoản PGD chưa có đơn vị — "
                "sẽ không thể truy cập dữ liệu."
            )
            st.dataframe(df_no_pgd, use_container_width=True, hide_index=True)
        else:
            st.success("✅ Tất cả tài khoản PGD đã được gán đơn vị")

        # Kiểm tra tài khoản mới tạo chưa đổi mật khẩu (ngay_doi_mk IS NULL)
        try:
            rows_chua_doi = conn.execute(
                """
                SELECT COUNT(*) FROM users
                WHERE ngay_doi_mk IS NULL
                  AND role NOT IN ('executive')
                """
            ).fetchone()
            if rows_chua_doi and rows_chua_doi[0] > 0:
                st.warning(
                    f"⚠️ Có **{rows_chua_doi[0]}** tài khoản chưa đổi mật khẩu lần đầu."
                )
            else:
                st.success("✅ Tất cả tài khoản đã đổi mật khẩu ít nhất 1 lần")
        except Exception:
            pass  # Bảng users có thể chưa có cột ngay_doi_mk — bỏ qua

    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu người dùng: {e}")


# ── Sub-tab 5: Hệ thống ──────────────────────────────────────────────────
def _render_he_thong(la_cn: bool = False) -> None:
    st.subheader("💾 Tài nguyên Hệ thống")

    # ── Dung lượng ổ đĩa ─────────────────────────────────────────────────
    st.markdown("#### 💿 Dung lượng ổ đĩa")
    try:
        from config import BASE_DIR
        total, used, free = shutil.disk_usage(str(BASE_DIR))
        pct_used = used / total * 100

        c1, c2, c3 = st.columns(3)
        c1.metric("Tổng", f"{total / 1e9:.1f} GB")  # noqa
        c2.metric("Đã dùng", f"{used / 1e9:.1f} GB", f"{pct_used:.0f}%")  # noqa
        c3.metric("Còn trống", f"{free / 1e9:.1f} GB")  # noqa

        if pct_used > 90:
            st.error("❌ Ổ đĩa gần đầy (>90%) — cần dọn dẹp ngay!")
        elif pct_used > 75:
            st.warning(f"⚠️ Ổ đĩa đã dùng {pct_used:.0f}% — nên theo dõi")
        else:
            st.success(f"✅ Ổ đĩa còn {free / 1e9:.1f} GB trống")  # noqa
    except Exception as e:
        st.error(f"Lỗi đọc dung lượng: {e}")

    # ── Quyền ghi thư mục ────────────────────────────────────────────────
    st.markdown("#### 🔐 Quyền ghi thư mục")
    try:
        from config import BASE_DIR, TEMPLATES_DIR
        dirs_to_check = {
            "Cache": CACHE_DIR,
            "PGD Data": PGD_DATA_DIR,
            "GQVL PGD": GQVL_PGD_DIR,
            "Templates": TEMPLATES_DIR,
        }
        rows_perm = []
        for ten, d in dirs_to_check.items():
            exists = os.path.exists(str(d))
            writable = os.access(str(d), os.W_OK) if exists else False
            rows_perm.append({
                "Thư mục": ten,
                "Đường dẫn": str(d),
                "Tồn tại": "✅" if exists else "❌",
                "Quyền ghi": "✅" if writable else "❌",
            })
        st.dataframe(
            pd.DataFrame(rows_perm),
            use_container_width=True,
            hide_index=True,
        )
    except Exception as e:
        st.error(f"Lỗi kiểm tra quyền thư mục: {e}")

    # ── Kích thước audit_log ──────────────────────────────────────────────
    st.markdown("#### 📝 Audit Log")
    try:
        conn = db.get_conn()
        total_audit = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        if total_audit > 50_000:
            st.warning(
                f"⚠️ Audit log có **{total_audit:,}** dòng — "
                "có thể ảnh hưởng hiệu năng, nên cân nhắc archive."
            )
        else:
            st.success(f"✅ Audit log: **{total_audit:,}** dòng")
    except Exception as e:
        st.error(f"Lỗi đọc audit log: {e}")

    # ── Kiểm tra credentials Google Sheets ───────────────────────────────
    st.markdown("#### 🔑 Tích hợp Google Sheets")
    try:
        from config import BASE_DIR as _bd
        creds_path = _bd / "credentials.json"
        if creds_path.exists():
            st.success(f"✅ `credentials.json` tồn tại ({_size_fmt(creds_path)})")
        else:
            st.info("ℹ️ Không tìm thấy `credentials.json` — tính năng Google Sheets bị tắt hoặc chưa cấu hình.")
    except Exception:
        pass

    # ── Kiểm tra nhiệm vụ quá hạn ────────────────────────────────────────
    st.markdown("#### ⏰ Nhiệm vụ quá hạn")
    try:
        from datetime import date
        hom_nay = date.today().strftime("%Y-%m-%d")
        conn = db.get_conn()

        qh_nv = conn.execute("""
            SELECT id, tieu_de, pgd, ngay_deadline, trang_thai
            FROM nhiem_vu
            WHERE ngay_deadline IS NOT NULL
              AND ngay_deadline < ?
              AND trang_thai != 'hoan_thanh'
            ORDER BY ngay_deadline ASC
            LIMIT 20
        """, (hom_nay,)).fetchall()

        qh_td = conn.execute("""
            SELECT id, ten_task, ngay_deadline, trang_thai
            FROM tien_do_task
            WHERE ngay_deadline < ?
              AND trang_thai NOT IN ('hoan_thanh', 'da_bao_cao')
            ORDER BY ngay_deadline ASC
            LIMIT 20
        """, (hom_nay,)).fetchall()

        if not qh_nv and not qh_td:
            st.success("✅ Không có nhiệm vụ hoặc tiến độ nào quá hạn")
        else:
            if qh_nv:
                st.warning(f"⚠️ **{len(qh_nv)}** nhiệm vụ quá hạn")
                df_nv = pd.DataFrame(qh_nv, columns=["ID", "Tiêu đề", "PGD", "Deadline", "Trạng thái"])
                st.dataframe(df_nv, use_container_width=True, hide_index=True, height=200)
            if qh_td:
                st.warning(f"⚠️ **{len(qh_td)}** tiến độ task quá hạn")
                df_td = pd.DataFrame(qh_td, columns=["ID", "Tên task", "Deadline", "Trạng thái"])
                st.dataframe(df_td, use_container_width=True, hide_index=True, height=200)
    except Exception as e:
        st.error(f"Lỗi kiểm tra nhiệm vụ quá hạn: {e}")

    # ── Backup thủ công ──────────────────────────────────────────────────────
    st.markdown("#### 🗄️ Backup dữ liệu")

    if la_cn:
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            if st.button("🗄️ Backup ngay", key="btn_backup_now",
                         type="primary"):
                with st.spinner("Đang backup..."):
                    try:
                        from backup_service import chay_backup
                        ket_qua = chay_backup()
                        db.ghi_audit(
                            st.session_state.get("username", "unknown"),
                            "manual_backup",
                            f"ky={ket_qua['ky']} "
                            f"db={'ok' if ket_qua['db_ok'] else 'loi'} "
                            f"parquet={ket_qua['parquet']} "
                            f"pgd={ket_qua['pgd_xlsx']}",
                        )
                        if ket_qua["db_ok"]:
                            st.success(
                                f"✅ Backup thành công — kỳ **{ket_qua['ky']}**\n\n"
                                f"DB ✅ · Parquet: {ket_qua['parquet']} file"
                                f" · PGD: {ket_qua['pgd_xlsx']} file"
                            )
                        else:
                            st.error("❌ Backup DB thất bại — xem backup.log")
                    except Exception as e:
                        st.error(f"❌ Lỗi backup: {e}")
        with col_info:
            st.caption(
                "Backup gồm: SQLite DB · Parquet cache · File xlsx PGD\n\n"
                "Lưu vào: `backups/YYYYMMDD_HHMMSS/` · Giữ 7 bản gần nhất"
            )
    else:
        st.info("ℹ️ Chỉ Admin/Manager Chi nhánh mới có thể thực hiện backup.")

    # ── Danh sách backup đã có ───────────────────────────────────────────
    st.markdown("##### 📁 Các bản backup hiện có")
    try:
        from backup_service import BACKUP_DIR
        from pathlib import Path
        bk_dir = Path(BACKUP_DIR)
        if not bk_dir.exists():
            st.info("Chưa có bản backup nào.")
        else:
            ds_bk = sorted(
                [d for d in bk_dir.iterdir()
                 if d.is_dir() and len(d.name) == 15
                 and d.name[8] == "_"],
                reverse=True,
            )
            if not ds_bk:
                st.info("Chưa có bản backup nào.")
            else:
                rows = []
                for d in ds_bk:
                    # Tính tổng dung lượng thư mục
                    total = sum(
                        f.stat().st_size
                        for f in d.rglob("*") if f.is_file()
                    )
                    size_str = (
                        f"{total/1e6:.1f} MB" if total >= 1e6
                        else f"{total/1e3:.0f} KB"
                    )
                    # Parse tên thư mục YYYYMMDD_HHMMSS
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(d.name, "%Y%m%d_%H%M%S")
                        ngay = dt.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        ngay = d.name
                    # Đếm số file
                    n_files = sum(1 for _ in d.rglob("*") if _.is_file())
                    rows.append({
                        "Kỳ backup": ngay,
                        "Thư mục": d.name,
                        "Số file": n_files,
                        "Dung lượng": size_str,
                        "DB": "✅" if (d / "vbsp_scm.db").exists() else "❌",
                        "Parquet": "✅" if (d / "cache").exists() else "❌",
                        "PGD xlsx": "✅" if (d / "pgd_data").exists() else "❌",
                    })
                df_bk = pd.DataFrame(rows)
                st.caption(f"Tổng cộng **{len(ds_bk)}** bản backup")
                st.dataframe(
                    df_bk,
                    use_container_width=True,
                    hide_index=True,
                )
    except Exception as e:
        st.error(f"Lỗi đọc danh sách backup: {e}")


# ── Sub-tab 6: Audit Log ──────────────────────────────────────────────────
def _render_audit(la_cn: bool, username: str | None) -> None:
    st.subheader("📋 Audit Log")

    try:
        conn = db.get_conn()

        # Bộ lọc
        col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
        with col_f1:
            filter_user = st.text_input(
                "Lọc theo username",
                value="" if la_cn else (username or ""),
                placeholder="Để trống = tất cả",
                key="audit_filter_user",
                disabled=(not la_cn),
            )
        with col_f2:
            filter_action = st.text_input(
                "Lọc theo action",
                placeholder="Ví dụ: upload, ghi_kv...",
                key="audit_filter_action",
            )
        with col_f3:
            limit = st.selectbox("Số dòng", [50, 100, 200, 500], key="audit_limit")

        # Build query
        wheres = []
        params: list = []
        if filter_user.strip():
            wheres.append("username LIKE ?")
            params.append(f"%{filter_user.strip()}%")
        if filter_action.strip():
            wheres.append("action LIKE ?")
            params.append(f"%{filter_action.strip()}%")
        if not la_cn and username:
            wheres.append("username = ?")
            params.append(username)

        where_clause = f"WHERE {' AND '.join(wheres)}" if wheres else ""
        rows = conn.execute(
            f"SELECT ts, username, action, detail FROM audit_log "
            f"{where_clause} ORDER BY ts DESC LIMIT ?",
            params + [limit],
        ).fetchall()

        if rows:
            df_audit = pd.DataFrame(rows, columns=["Thời gian", "Username", "Action", "Chi tiết"])
            st.caption(f"Hiển thị {len(df_audit):,} dòng gần nhất")
            st.dataframe(df_audit, use_container_width=True, hide_index=True, height=420)
        else:
            st.info("Không có kết quả phù hợp.")

    except Exception as e:
        st.error(f"Lỗi đọc audit log: {e}")


# ── Entry point ──────────────────────────────────────────────────────────────
def render(tab=None, **kwargs) -> None:
    """
    render(tab, role=..., username=..., pgd_user=...)

    Parameters
    ----------
    tab      : st.tab context hoặc None (fallback st.container)
    role     : chuỗi role người dùng
    username : username đang đăng nhập
    pgd_user : tên PGD (chỉ dành cho PGD role)
    """
    ctx = get_tab_context(tab)
    with ctx:
        role = normalize_role(str(kwargs.get("role") or "user"))
        username: str = kwargs.get("username") or st.session_state.get("username", "unknown")
        pgd_user: str | None = kwargs.get("pgd_user") or st.session_state.get(
            "user_info", {}
        ).get("pgd")

        la_cn = la_phan_he_cn(role)

        st.title("🔍 Trạng thái Nguồn dữ liệu")
        if la_cn:
            st.caption("Giám sát toàn diện 22 đơn vị · Merge · Parquet · Snapshot · Người dùng · Hệ thống")
        else:
            dv_hien_thi = pgd_user or "PGD của bạn"
            st.caption(f"Trạng thái upload và hoạt động — {dv_hien_thi}")

        # ── Xác định sub-tabs theo role ──────────────────────────────────
        if la_cn:
            tab_labels = [
                "📂 Tệp nguồn",
                "🔗 Merge & Cache",
                "📸 Snapshot",
                "👥 Người dùng",
                "💾 Hệ thống",
                "📋 Audit Log",
            ]
            tabs = st.tabs(tab_labels)
            with tabs[0]:
                _render_tep_nguon(la_cn=True, pgd_user=None)
            with tabs[1]:
                _render_merge_cache(la_cn=True)
            with tabs[2]:
                _render_snapshot()
            with tabs[3]:
                _render_nguoi_dung()
            with tabs[4]:
                _render_he_thong(la_cn=la_cn)
            with tabs[5]:
                _render_audit(la_cn=True, username=username)
        else:
            # PGD chỉ thấy tệp nguồn của mình + audit cá nhân
            tab_labels = [
                "📂 Tệp nguồn",
                "🔗 Merge",
                "📋 Audit Log",
            ]
            tabs = st.tabs(tab_labels)
            with tabs[0]:
                _render_tep_nguon(la_cn=False, pgd_user=pgd_user)
            with tabs[1]:
                _render_merge_cache(la_cn=False)
            with tabs[2]:
                _render_audit(la_cn=False, username=username)
