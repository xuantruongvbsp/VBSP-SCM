"""
Tab Quản lý Nhiệm vụ (Tháng / Quý / Năm)
──────────────────────────────────────────
Dành cho:
  - manager / admin / chuyenvien_cn : tổng quan, tạo nhiệm vụ, xem danh sách,
                                      đổi trạng thái, hậu kiểm duyệt kết quả
  - user (CBTD)                     : xem nhiệm vụ được giao, nhập & cập nhật kết quả
"""


from logger import get_logger
logger = get_logger(__name__)

import streamlit as st
import pandas as pd
import plotly.express as px
import db
from datetime import datetime

from auth import la_phan_he_cn, la_executive
from utils import xuat_excel
from config import LOAI_CONG_VIEC, UU_TIEN_CV, TEN_CHI_NHANH_HIEN_THI
from services.upload_service import luu_attachment_nhiem_vu


# ── Ánh xạ nhãn trạng thái ────────────────────────────────────────────────
_NHAN_TRANG_THAI_NV: dict[str, str] = {
    "cho_thuc_hien":  "⏳ Chờ thực hiện",
    "dang_thuc_hien": "🔄 Đang thực hiện",
    "da_hoan_thanh":  "✅ Đã hoàn thành",
    "tam_dung":       "⏸ Tạm dừng",
}
_NHAN_TRANG_THAI_KQ: dict[str, str] = {
    "cho_duyet":   "⏳ Chờ duyệt",
    "da_duyet":    "✅ Đã duyệt",
    "yeu_cau_sua": "🔁 Yêu cầu sửa",
}
_NHAN_CHU_KY: dict[str, str] = {
    "thang": "Tháng",
    "quy":   "Quý",
    "nam":   "Năm",
}


# ── Hàm tiện ích ──────────────────────────────────────────────────────────
def _tao_ky(chu_ky: str, nam: int | None = None) -> list[str]:
    """Tạo danh sách nhãn kỳ tương ứng với chu kỳ đã chọn."""
    if nam is None:
        nam = datetime.now().year
    if chu_ky == "thang":
        return [f"{nam}-T{m:02d}" for m in range(1, 13)]
    if chu_ky == "quy":
        return [f"{nam}-Q{q}" for q in range(1, 5)]
    if chu_ky == "nam":
        return [str(y) for y in range(nam - 1, nam + 2)]
    return []


def _ky_mac_dinh(chu_ky: str, ds_ky: list[str], nam: int | None = None) -> str:
    """Trả về kỳ mặc định phù hợp với tháng / quý / năm hiện tại."""
    if not ds_ky:
        return ""
    nam_ht = datetime.now().year
    # Nếu xem năm khác → về kỳ đầu
    if nam is not None and nam != nam_ht:
        return ds_ky[0]
    thang_hien = datetime.now().month
    if chu_ky == "thang":
        return ds_ky[thang_hien - 1]
    if chu_ky == "quy":
        return ds_ky[(thang_hien - 1) // 3]
    if chu_ky == "nam":
        # Phần tử giữa danh sách 3 năm = năm hiện tại
        return ds_ky[1] if len(ds_ky) >= 2 else ds_ky[0]
    return ds_ky[0]


def _nhan_nv(ts: str) -> str:
    return _NHAN_TRANG_THAI_NV.get(ts, ts)


def _nhan_kq(ts: str) -> str:
    return _NHAN_TRANG_THAI_KQ.get(ts, ts)


# ── Truy vấn DB ───────────────────────────────────────────────────────────
def _doc_nhiem_vu(chu_ky: str, ky: str, pgd: str | None) -> list[dict]:
    """Đọc danh sách nhiệm vụ theo chu kỳ + kỳ + PGD (NULL = tất cả)."""
    with db.get_conn() as conn:
        if pgd:
            rows = conn.execute(
                """SELECT * FROM nhiem_vu
                   WHERE chu_ky=? AND ky=? AND (pgd=? OR pgd IS NULL)
                   ORDER BY id DESC""",
                (chu_ky, ky, pgd),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM nhiem_vu WHERE chu_ky=? AND ky=? ORDER BY id DESC",
                (chu_ky, ky),
            ).fetchall()
    return [dict(r) for r in rows]


def _doc_ket_qua(nhiem_vu_id: int) -> list[dict]:
    """Đọc tất cả kết quả của một nhiệm vụ."""
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM nhiem_vu_ketqua WHERE nhiem_vu_id=? ORDER BY ngay_nhap DESC",
            (nhiem_vu_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _doc_ket_qua_pgd(nhiem_vu_id: int, pgd: str) -> dict | None:
    """Đọc kết quả của một PGD cụ thể cho một nhiệm vụ."""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM nhiem_vu_ketqua WHERE nhiem_vu_id=? AND pgd=?",
            (nhiem_vu_id, pgd),
        ).fetchone()
    return dict(row) if row else None


def _upsert_ket_qua(
    nhiem_vu_id: int,
    pgd: str,
    noi_dung_th: str | None,
    so_lieu: str | None,
    username: str,
    file_path: str | None = None,
    file_name: str | None = None,
) -> None:
    """Chèn mới hoặc cập nhật kết quả theo (nhiem_vu_id, pgd)."""
    now = datetime.now().isoformat()
    with db.get_conn() as conn:
        if file_path:
            conn.execute(
                """INSERT INTO nhiem_vu_ketqua
                   (nhiem_vu_id, pgd, noi_dung_th, so_lieu, trang_thai,
                    nguoi_nhap, ngay_nhap, file_path, file_name)
                   VALUES (?, ?, ?, ?, 'cho_duyet', ?, ?, ?, ?)
                   ON CONFLICT(nhiem_vu_id, pgd) DO UPDATE SET
                     noi_dung_th = excluded.noi_dung_th,
                     so_lieu     = excluded.so_lieu,
                     trang_thai  = 'cho_duyet',
                     nguoi_nhap  = excluded.nguoi_nhap,
                     ngay_nhap   = excluded.ngay_nhap,
                     file_path   = excluded.file_path,
                     file_name   = excluded.file_name""",
                (nhiem_vu_id, pgd, noi_dung_th, so_lieu, username, now, file_path, file_name),
            )
        else:
            conn.execute(
                """INSERT INTO nhiem_vu_ketqua
                   (nhiem_vu_id, pgd, noi_dung_th, so_lieu, trang_thai, nguoi_nhap, ngay_nhap)
                   VALUES (?, ?, ?, ?, 'cho_duyet', ?, ?)
                   ON CONFLICT(nhiem_vu_id, pgd) DO UPDATE SET
                     noi_dung_th = excluded.noi_dung_th,
                     so_lieu     = excluded.so_lieu,
                     trang_thai  = 'cho_duyet',
                     nguoi_nhap  = excluded.nguoi_nhap,
                     ngay_nhap   = excluded.ngay_nhap""",
                (nhiem_vu_id, pgd, noi_dung_th, so_lieu, username, now),
            )
        conn.commit()


def _doi_trang_thai_nhiem_vu(nv_id: int, trang_thai_moi: str, username: str) -> None:
    """Đổi trạng thái một nhiệm vụ và ghi audit."""
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE nhiem_vu SET trang_thai=? WHERE id=?",
            (trang_thai_moi, nv_id),
        )
        conn.commit()
    db.ghi_audit(
        username, "nhiem_vu_doi_trang_thai",
        f"NV id={nv_id} → {trang_thai_moi}",
    )


# ── Xuất Excel nhiệm vụ ───────────────────────────────────────────────────
def _xuat_excel_nhiem_vu(ds_nv: list[dict]) -> bytes:
    """Xuất danh sách nhiệm vụ + kết quả PGD ra Excel (2 sheet)."""
    rows_nv = []
    rows_kq = []
    for nv in ds_nv:
        rows_nv.append({
            "ID":            nv["id"],
            "Tiêu đề":       nv["tieu_de"],
            "Mô tả":         nv.get("mo_ta") or "",
            "Chu kỳ":        _NHAN_CHU_KY.get(nv["chu_ky"], nv["chu_ky"]),
            "Kỳ":            nv["ky"],
            "PGD được giao": nv.get("pgd") or "Tất cả PGD",
            "Trạng thái":    _nhan_nv(nv["trang_thai"]),
            "Người tạo":     nv["nguoi_tao"],
            "Ngày tạo":      nv["ngay_tao"][:10],
            "Deadline":      nv.get("ngay_deadline") or "",
            "Ghi chú KH":    nv.get("ghi_chu_kh") or "",
        })
        for kq in _doc_ket_qua(nv["id"]):
            rows_kq.append({
                "ID NV":          nv["id"],
                "Tiêu đề NV":     nv["tieu_de"],
                "PGD":            kq["pgd"],
                "Nội dung TH":    kq.get("noi_dung_th") or "",
                "Số liệu":        kq.get("so_lieu") or "",
                "Trạng thái KQ":  _nhan_kq(kq["trang_thai"]),
                "Người nhập":     kq["nguoi_nhap"],
                "Ngày nhập":      kq["ngay_nhap"][:10],
                "Người duyệt":    kq.get("nguoi_duyet") or "",
                "Ngày duyệt":     (kq.get("ngay_duyet") or "")[:10],
                "Ý kiến duyệt":   kq.get("y_kien_duyet") or "",
            })

    df_nv = pd.DataFrame(rows_nv) if rows_nv else pd.DataFrame()
    df_kq = pd.DataFrame(rows_kq) if rows_kq else pd.DataFrame()
    return xuat_excel({"Danh sách nhiệm vụ": df_nv, "Kết quả PGD": df_kq})


# ── Widget lọc năm / chu kỳ / kỳ / PGD (dùng chung) ──────────────────────
def _bo_loc_ky(key_prefix: str, hien_pgd: bool = False, ds_pgd: list | None = None):
    """Render bộ lọc năm + chu_ky + ky (+ pgd tuỳ chọn).
    Trả về (chu_ky, ky, pgd|None)."""
    nam_ht = datetime.now().year
    ds_nam = list(range(nam_ht - 1, nam_ht + 2))

    col_count = 4 if hien_pgd else 3
    cols = st.columns(col_count)

    with cols[0]:
        nam = st.selectbox(
            "Năm",
            ds_nam,
            index=ds_nam.index(nam_ht),
            key=f"{key_prefix}_nam",
        )

    with cols[1]:
        chu_ky = st.selectbox(
            "Chu kỳ",
            ["thang", "quy", "nam"],
            format_func=lambda x: _NHAN_CHU_KY[x],
            key=f"{key_prefix}_chu_ky",
        )

    ds_ky = _tao_ky(chu_ky, nam)
    ky_default = _ky_mac_dinh(chu_ky, ds_ky, nam)
    idx_default = ds_ky.index(ky_default) if ky_default in ds_ky else 0

    with cols[2]:
        ky = st.selectbox("Kỳ", ds_ky, index=idx_default, key=f"{key_prefix}_ky")

    pgd_chon = None
    if hien_pgd and ds_pgd is not None:
        with cols[3]:
            pgd_sel = st.selectbox(
                "PGD", ["Tất cả PGD"] + ds_pgd, key=f"{key_prefix}_pgd"
            )
        pgd_chon = None if pgd_sel == "Tất cả PGD" else pgd_sel

    return chu_ky, ky, pgd_chon


# ══════════════════════════════════════════════════════════════════════════
# NHÓM MANAGER / ADMIN / CHUYENVIEN_CN
# ══════════════════════════════════════════════════════════════════════════

def _render_tong_quan_manager(tab, **kwargs):
    """📊 Tổng quan nhiệm vụ — KPI metrics, ma trận PGD, biểu đồ trạng thái."""
    ds_pgd_all: list = kwargs.get("ds_pgd_all", [])

    _tab_ctx = TabContext(tab, **kwargs)
    with _tab_ctx:
        st.subheader("📊 Tổng quan nhiệm vụ")

        chu_ky, ky, _ = _bo_loc_ky("tq")

        ds_nv = _doc_nhiem_vu(chu_ky, ky, None)
        if not ds_nv:
            st.info("Chưa có nhiệm vụ nào trong kỳ này.")
            return

        # ── KPI ─────────────────────────────────────────────────────────
        tong    = len(ds_nv)
        da_ht   = sum(1 for nv in ds_nv if nv["trang_thai"] == "da_hoan_thanh")
        dang_th = sum(1 for nv in ds_nv if nv["trang_thai"] == "dang_thuc_hien")

        all_kq: dict[int, list] = {}
        cho_duyet_total = 0
        for nv in ds_nv:
            kq_list = _doc_ket_qua(nv["id"])
            all_kq[nv["id"]] = kq_list
            cho_duyet_total += sum(1 for kq in kq_list if kq["trang_thai"] == "cho_duyet")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📋 Tổng nhiệm vụ", tong)
        c2.metric(
            "✅ Đã hoàn thành", da_ht,
            f"{round(da_ht / tong * 100) if tong else 0}%",
        )
        c3.metric("🔄 Đang thực hiện", dang_th)
        c4.metric("⏳ Chờ duyệt KQ", cho_duyet_total, delta_color="inverse")

        # ── Ma trận PGD × Nhiệm vụ ──────────────────────────────────────
        if ds_pgd_all:
            st.markdown("#### 🗺️ Ma trận PGD × Nhiệm vụ")
            st.caption("Ô = Trạng thái kết quả PGD đã nhập. — = chưa nhập.")
            bang_rows = []
            for pgd in ds_pgd_all:
                row: dict = {"Đơn vị": pgd}
                for nv in ds_nv:
                    kq_pgd = [kq for kq in all_kq.get(nv["id"], [])
                              if kq.get("pgd") == pgd]
                    col_name = nv["tieu_de"][:16]
                    if not kq_pgd:
                        row[col_name] = "—"
                    else:
                        row[col_name] = _nhan_kq(kq_pgd[0]["trang_thai"])
                bang_rows.append(row)
            df_ma_tran = pd.DataFrame(bang_rows)
            st.dataframe(df_ma_tran, use_container_width=True, hide_index=True, height=400)

        # ── Biểu đồ trạng thái ──────────────────────────────────────────
        st.markdown("#### 📈 Phân bố trạng thái nhiệm vụ")
        ts_counter: dict[str, int] = {}
        for nv in ds_nv:
            label = _nhan_nv(nv["trang_thai"])
            ts_counter[label] = ts_counter.get(label, 0) + 1
        df_ts = pd.DataFrame(
            [{"Trạng thái": k, "Số lượng": v} for k, v in ts_counter.items()]
        )
        color_map = {
            "⏳ Chờ thực hiện":  "#f59e0b",
            "🔄 Đang thực hiện": "#3b82f6",
            "✅ Đã hoàn thành":  "#22c55e",
            "⏸ Tạm dừng":       "#94a3b8",
        }
        fig = px.bar(
            df_ts, x="Trạng thái", y="Số lượng",
            color="Trạng thái",
            color_discrete_map=color_map,
            text="Số lượng",
            height=280,
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, key="nv_chart_tq")


def _render_danh_sach_manager(tab, **kwargs):
    """📥 Danh sách nhiệm vụ — lọc/tìm kiếm, xuất Excel/PDF, đổi trạng thái."""
    ds_pgd_all: list = kwargs.get("ds_pgd_all", [])
    username: str    = kwargs.get("username", "")

    _tab_ctx = TabContext(tab, **kwargs)
    with _tab_ctx:
        st.subheader("📥 Danh sách nhiệm vụ")
        chu_ky, ky, pgd_loc = _bo_loc_ky("mgr_ds", hien_pgd=True, ds_pgd=ds_pgd_all)

        ds_nv = _doc_nhiem_vu(chu_ky, ky, pgd_loc)
        if not ds_nv:
            st.info("Chưa có nhiệm vụ nào trong kỳ này.")
            return

        # ── Lọc / Tìm kiếm ──────────────────────────────────────────────
        c_search, c_ts, c_ut, c_loai_f = st.columns([3, 1, 1, 1])
        with c_search:
            tu_khoa = st.text_input(
                "🔍 Tìm kiếm tiêu đề",
                placeholder="Nhập từ khoá...",
                key="mgr_ds_search",
                label_visibility="collapsed",
            )
        with c_ts:
            ts_options = ["Tất cả"] + list(_NHAN_TRANG_THAI_NV.values())
            ts_loc = st.selectbox(
                "Trạng thái", ts_options,
                key="mgr_ds_ts",
                label_visibility="collapsed",
            )
        with c_ut:
            ut_options = ["Tất cả"] + list(UU_TIEN_CV.values())
            ut_loc = st.selectbox(
                "Ưu tiên", ut_options,
                key="mgr_ds_ut",
                label_visibility="collapsed",
            )
        with c_loai_f:
            loai_options = ["Tất cả"] + list(LOAI_CONG_VIEC.values())
            loai_loc = st.selectbox(
                "Loại", loai_options,
                key="mgr_ds_loai",
                label_visibility="collapsed",
            )

        ds_hien = ds_nv
        if tu_khoa:
            ds_hien = [nv for nv in ds_hien
                       if tu_khoa.lower() in nv["tieu_de"].lower()]
        if ts_loc != "Tất cả":
            ts_key = next(
                (k for k, v in _NHAN_TRANG_THAI_NV.items() if v == ts_loc), None
            )
            if ts_key:
                ds_hien = [nv for nv in ds_hien if nv["trang_thai"] == ts_key]
        if ut_loc != "Tất cả":
            ut_key = next((k for k, v in UU_TIEN_CV.items() if v == ut_loc), None)
            if ut_key:
                ds_hien = [nv for nv in ds_hien if nv.get("uu_tien") == ut_key]
        if loai_loc != "Tất cả":
            loai_key = next((k for k, v in LOAI_CONG_VIEC.items() if v == loai_loc), None)
            if loai_key:
                ds_hien = [nv for nv in ds_hien if nv.get("loai") == loai_key]

        st.caption(f"Hiển thị: **{len(ds_hien)}** / {len(ds_nv)} nhiệm vụ")

        # ── Xuất báo cáo ────────────────────────────────────────────────
        col_pdf, col_excel, _ = st.columns([1, 1, 4])
        with col_pdf:
            if st.button(
                "📥 Xuất PDF", key="btn_xuat_pdf_nv",
                use_container_width=True, type="primary",
            ):
                pdf_bytes = _xuat_pdf_nhiem_vu(ds_hien, chu_ky, ky)
                st.session_state["_pdf_nv_bytes"] = pdf_bytes
                st.session_state["_pdf_nv_ten"] = f"danh_sach_nhiem_vu_{chu_ky}_{ky}.pdf"
        with col_excel:
            if st.button(
                "📊 Xuất Excel", key="btn_xuat_excel_nv",
                use_container_width=True,
            ):
                st.session_state["_excel_nv_bytes"] = _xuat_excel_nhiem_vu(ds_hien)
                st.session_state["_excel_nv_ten"] = f"nhiem_vu_{chu_ky}_{ky}.xlsx"

        if st.session_state.get("_pdf_nv_bytes"):
            st.download_button(
                "⬇ Tải PDF",
                data=st.session_state["_pdf_nv_bytes"],
                file_name=st.session_state["_pdf_nv_ten"],
                mime="application/pdf",
                key="dl_pdf_nv",
            )
        if st.session_state.get("_excel_nv_bytes"):
            st.download_button(
                "⬇ Tải Excel",
                data=st.session_state["_excel_nv_bytes"],
                file_name=st.session_state["_excel_nv_ten"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_excel_nv",
            )

        st.divider()

        # ── Danh sách nhiệm vụ ───────────────────────────────────────────
        _TS_BUTTONS = [
            ("cho_thuc_hien",  "⏳ Chờ"),
            ("dang_thuc_hien", "▶️ Bắt đầu"),
            ("da_hoan_thanh",  "✅ Hoàn thành"),
            ("tam_dung",       "⏸ Tạm dừng"),
        ]

        for nv in ds_hien:
            pgd_nhan = nv["pgd"] if nv["pgd"] else "Tất cả PGD"
            deadline = f" · ⏰ {nv['ngay_deadline']}" if nv.get("ngay_deadline") else ""
            nhan_ts  = _nhan_nv(nv["trang_thai"])

            with st.expander(
                f"**{nv['tieu_de']}** — {nhan_ts} · {pgd_nhan}{deadline}",
                expanded=False,
            ):
                if nv.get("mo_ta"):
                    st.markdown(f"_{nv['mo_ta']}_")
                st.caption(
                    f"Người tạo: **{nv['nguoi_tao']}** · Ngày tạo: {nv['ngay_tao'][:10]}"
                )
                if nv.get("ghi_chu_kh"):
                    st.info(nv["ghi_chu_kh"])

                # ── Đổi trạng thái ──────────────────────────────────────
                ts_hien = nv["trang_thai"]
                btn_cols = st.columns(4)
                for (ts_key, ts_label), col in zip(_TS_BUTTONS, btn_cols):
                    with col:
                        is_active = ts_hien == ts_key
                        if st.button(
                            ts_label,
                            key=f"nv_ts_{nv['id']}_{ts_key}",
                            type="primary" if is_active else "secondary",
                            disabled=is_active,
                            use_container_width=True,
                        ):
                            try:
                                _doi_trang_thai_nhiem_vu(nv["id"], ts_key, username)
                                st.toast(f"✅ Đã cập nhật: {ts_label}")
                                st.rerun()
                            except Exception as e:
                                logger.error("Lỗi đổi trạng thái NV: %s", e, exc_info=True)
                                st.error(f"Lỗi: {e}")

                # ── Kết quả PGD ─────────────────────────────────────────
                ds_kq = _doc_ket_qua(nv["id"])
                if ds_kq:
                    st.markdown("**Kết quả các PGD đã nhập:**")
                    for kq in ds_kq:
                        icon = _nhan_kq(kq["trang_thai"])
                        y_kien = (
                            f" — _{kq['y_kien_duyet']}_"
                            if kq.get("y_kien_duyet") else ""
                        )
                        st.markdown(
                            f"- **{kq['pgd']}** · {icon} · "
                            f"Nội dung: *{kq.get('noi_dung_th') or 'chưa nhập'}* · "
                            f"Số liệu: **{kq.get('so_lieu') or '—'}** · "
                            f"Ngày nhập: {kq['ngay_nhap'][:10]}"
                            + y_kien
                        )
                else:
                    st.info("Chưa có PGD nào nhập kết quả.")


def _render_nhap_moi(tab, **kwargs):
    """➕ Nhập nhiệm vụ mới — manager / admin tạo nhiệm vụ cho PGD."""
    username: str    = kwargs.get("username", "")
    ds_pgd_all: list = kwargs.get("ds_pgd_all", [])

    _tab_ctx = TabContext(tab, **kwargs)
    with _tab_ctx:
        st.subheader("➕ Nhập nhiệm vụ mới")

        # Năm + chu_ky đặt NGOÀI form để kỳ cập nhật động khi người dùng đổi
        nam_ht  = datetime.now().year
        ds_nam  = list(range(nam_ht - 1, nam_ht + 2))
        c_nam, c_ck = st.columns(2)
        with c_nam:
            nam_chon = st.selectbox(
                "Năm *", ds_nam, index=ds_nam.index(nam_ht), key="nhap_moi_nam"
            )
        with c_ck:
            chu_ky = st.selectbox(
                "Chu kỳ *",
                ["thang", "quy", "nam"],
                format_func=lambda x: _NHAN_CHU_KY[x],
                key="nhap_moi_chu_ky",
            )
        ds_ky = _tao_ky(chu_ky, nam_chon)
        ky_default = _ky_mac_dinh(chu_ky, ds_ky, nam_chon)

        with st.form("form_nhap_nhiem_vu_moi"):
            tieu_de = st.text_area(
                "Tiêu đề nhiệm vụ *",
                placeholder="Ví dụ: Tổng hợp dư nợ NOXH tháng 4",
                height=68,
                key="nhiem_vu_tieu_de",
            )
            mo_ta = st.text_area(
                "Mô tả chi tiết",
                placeholder="Nêu rõ yêu cầu, nội dung cần thực hiện...",
            )

            c1, c2 = st.columns(2)
            with c1:
                ky = st.selectbox(
                    "Kỳ *",
                    ds_ky,
                    index=ds_ky.index(ky_default) if ky_default in ds_ky else 0,
                    key="nhap_moi_ky",
                )
            with c2:
                pgd_chon = st.selectbox(
                    "Giao cho PGD",
                    ["Tất cả PGD"] + ds_pgd_all,
                    key="nhap_moi_pgd",
                )

            c3, c4 = st.columns(2)
            with c3:
                uu_tien_chon = st.selectbox(
                    "Ưu tiên",
                    list(UU_TIEN_CV.keys()),
                    format_func=lambda x: UU_TIEN_CV[x],
                    index=2,
                    key="nhap_moi_uu_tien",
                )
            with c4:
                loai_chon = st.selectbox(
                    "Loại công việc",
                    list(LOAI_CONG_VIEC.keys()),
                    format_func=lambda x: LOAI_CONG_VIEC[x],
                    key="nhap_moi_loai",
                )

            c5, c6 = st.columns(2)
            with c5:
                ngay_deadline = st.date_input(
                    "Ngày deadline", value=None, format="DD/MM/YYYY",
                    key="nhap_moi_deadline",
                )
            with c6:
                st.markdown("<br>", unsafe_allow_html=True)

            ghi_chu = st.text_area("Ghi chú kế hoạch (tuỳ chọn)")
            submitted = st.form_submit_button("💾 Lưu nhiệm vụ", type="primary")

        if submitted:
            if not tieu_de.strip():
                st.error("⚠️ Vui lòng nhập tiêu đề nhiệm vụ!")
            else:
                pgd_luu = None if pgd_chon == "Tất cả PGD" else pgd_chon
                deadline_str = str(ngay_deadline) if ngay_deadline else None
                try:
                    with db.get_conn() as conn:
                        conn.execute(
                            """INSERT INTO nhiem_vu
                               (tieu_de, mo_ta, chu_ky, ky, pgd, trang_thai,
                                nguoi_tao, ngay_tao, ngay_deadline, ghi_chu_kh,
                                uu_tien, loai)
                               VALUES (?, ?, ?, ?, ?, 'cho_thuc_hien', ?, ?, ?, ?, ?, ?)""",
                            (
                                tieu_de.strip(),
                                mo_ta.strip() or None,
                                chu_ky, ky,
                                pgd_luu,
                                username,
                                datetime.now().isoformat(),
                                deadline_str,
                                ghi_chu.strip() or None,
                                uu_tien_chon,
                                loai_chon,
                            ),
                        )
                        conn.commit()
                    db.ghi_audit(
                        username, "nhiem_vu_tao",
                        f"Tạo NV: '{tieu_de}' · chu_ky={chu_ky} · ky={ky} · pgd={pgd_luu} · uu_tien={uu_tien_chon} · loai={loai_chon}",
                    )
                    st.toast(f"✅ Đã tạo nhiệm vụ: {tieu_de}")
                    st.rerun()
                except Exception as e:
                    logger.error("Lỗi tạo nhiệm vụ: %s", e, exc_info=True)
                    st.error(f"Lỗi khi lưu nhiệm vụ: {e}")


def _render_hau_kiem(tab, **kwargs):
    """🔍 Hậu kiểm kết quả — manager duyệt hoặc yêu cầu sửa kết quả PGD."""
    username: str    = kwargs.get("username", "")
    ds_pgd_all: list = kwargs.get("ds_pgd_all", [])

    _tab_ctx = TabContext(tab, **kwargs)
    with _tab_ctx:
        st.subheader("🔍 Hậu kiểm kết quả")
        chu_ky, ky, pgd_loc = _bo_loc_ky("hk", hien_pgd=True, ds_pgd=ds_pgd_all)

        ds_nv = _doc_nhiem_vu(chu_ky, ky, pgd_loc)
        if not ds_nv:
            st.info("Không có nhiệm vụ nào trong kỳ này.")
            return

        co_cho_duyet = False

        for nv in ds_nv:
            ds_kq_cho_duyet = [
                kq for kq in _doc_ket_qua(nv["id"])
                if kq["trang_thai"] == "cho_duyet"
            ]
            if not ds_kq_cho_duyet:
                continue
            co_cho_duyet = True

            with st.expander(
                f"**{nv['tieu_de']}** · {len(ds_kq_cho_duyet)} kết quả chờ duyệt",
                expanded=True,
            ):
                for kq in ds_kq_cho_duyet:
                    st.markdown(f"**PGD: {kq['pgd']}**")
                    st.markdown(
                        f"- Nội dung: *{kq.get('noi_dung_th') or 'chưa nhập'}*\n"
                        f"- Số liệu: **{kq.get('so_lieu') or '—'}**"
                    )
                    if kq.get("file_name"):
                        st.caption(f"📎 File đính kèm: **{kq['file_name']}**")
                    st.caption(
                        f"Người nhập: {kq['nguoi_nhap']} · "
                        f"Ngày nhập: {kq['ngay_nhap'][:10]}"
                    )

                    with st.form(key=f"form_duyet_{kq['id']}"):
                        y_kien = st.text_area(
                            "Ý kiến duyệt (tuỳ chọn)",
                            key=f"yk_{kq['id']}",
                            placeholder="Nhập ý kiến hoặc để trống...",
                        )
                        col_d, col_s = st.columns(2)
                        with col_d:
                            btn_duyet = st.form_submit_button("✅ Duyệt", type="primary")
                        with col_s:
                            btn_sua = st.form_submit_button("🔁 Yêu cầu sửa")

                    if btn_duyet or btn_sua:
                        ts_moi = "da_duyet" if btn_duyet else "yeu_cau_sua"
                        try:
                            with db.get_conn() as conn:
                                conn.execute(
                                    """UPDATE nhiem_vu_ketqua SET
                                       trang_thai=?, nguoi_duyet=?,
                                       ngay_duyet=?, y_kien_duyet=?
                                       WHERE id=?""",
                                    (
                                        ts_moi, username,
                                        datetime.now().isoformat(),
                                        y_kien.strip() or None,
                                        kq["id"],
                                    ),
                                )
                                conn.commit()
                            db.ghi_audit(
                                username, f"nhiem_vu_ketqua_{ts_moi}",
                                f"KQ id={kq['id']} · NV '{nv['tieu_de']}' · PGD {kq['pgd']}",
                            )
                            st.toast(f"✅ Đã cập nhật: {_nhan_kq(ts_moi)}")
                            st.rerun()
                        except Exception as e:
                            logger.error("Lỗi duyệt kết quả: %s", e, exc_info=True)
                            st.error(f"Lỗi cập nhật: {e}")

                    st.divider()

        if not co_cho_duyet:
            st.success("✅ Không có kết quả nào đang chờ duyệt trong kỳ này.")


# ══════════════════════════════════════════════════════════════════════════
# NHÓM USER (CBTD)
# ══════════════════════════════════════════════════════════════════════════

def _render_nhiem_vu_duoc_giao(tab, **kwargs):
    """📥 Nhiệm vụ được giao — CBTD xem nhiệm vụ và trạng thái kết quả."""
    pgd_user: str = kwargs.get("pgd_user") or ""

    _tab_ctx = TabContext(tab, **kwargs)
    with _tab_ctx:
        st.subheader("📥 Nhiệm vụ được giao")
        if not pgd_user:
            st.warning("Tài khoản chưa được gán PGD. Liên hệ quản trị viên.")
            return

        chu_ky, ky, _ = _bo_loc_ky("user_ds")
        ds_nv = _doc_nhiem_vu(chu_ky, ky, pgd_user)

        if not ds_nv:
            st.info("Chưa có nhiệm vụ nào được giao trong kỳ này.")
            return

        st.caption(f"Tổng cộng: **{len(ds_nv)}** nhiệm vụ")
        st.divider()

        for nv in ds_nv:
            kq = _doc_ket_qua_pgd(nv["id"], pgd_user)
            ts_kq   = _nhan_kq(kq["trang_thai"]) if kq else "📝 Chưa nhập"
            deadline = f" · ⏰ {nv['ngay_deadline']}" if nv.get("ngay_deadline") else ""

            with st.expander(
                f"**{nv['tieu_de']}** — {ts_kq}{deadline}", expanded=False
            ):
                if nv.get("mo_ta"):
                    st.markdown(f"_{nv['mo_ta']}_")
                st.caption(
                    f"Kỳ: {nv['ky']} · "
                    f"Giao cho: {nv['pgd'] or 'Tất cả PGD'}"
                )

                if kq:
                    st.markdown("**Kết quả đã nhập:**")
                    st.markdown(
                        f"- Nội dung: *{kq.get('noi_dung_th') or 'chưa nhập'}*\n"
                        f"- Số liệu: **{kq.get('so_lieu') or '—'}**\n"
                        f"- Ngày nhập: {kq['ngay_nhap'][:10]}"
                    )
                    if kq.get("file_name"):
                        st.caption(f"📎 File đính kèm: **{kq['file_name']}**")
                    if kq.get("y_kien_duyet"):
                        if kq["trang_thai"] == "yeu_cau_sua":
                            st.warning(f"🔁 Ý kiến duyệt: _{kq['y_kien_duyet']}_")
                        else:
                            st.success(f"✅ Ý kiến duyệt: _{kq['y_kien_duyet']}_")
                else:
                    st.info("Chưa nhập kết quả. Vào tab **✏️ Nhập kết quả** để thực hiện.")


def _render_nhap_ket_qua(tab, **kwargs):
    """✏️ Nhập kết quả — CBTD nhập / sửa kết quả thực hiện nhiệm vụ."""
    username: str = kwargs.get("username", "")
    pgd_user: str = kwargs.get("pgd_user") or ""

    _tab_ctx = TabContext(tab, **kwargs)
    with _tab_ctx:
        st.subheader("✏️ Nhập kết quả nhiệm vụ")
        if not pgd_user:
            st.warning("Tài khoản chưa được gán PGD. Liên hệ quản trị viên.")
            return

        chu_ky, ky, _ = _bo_loc_ky("user_nkq")
        ds_nv = _doc_nhiem_vu(chu_ky, ky, pgd_user)

        if not ds_nv:
            st.info("Chưa có nhiệm vụ nào được giao trong kỳ này.")
            return

        for nv in ds_nv:
            nv_id = nv["id"]
            kq    = _doc_ket_qua_pgd(nv_id, pgd_user)
            ts_hien = kq["trang_thai"] if kq else None

            with st.expander(
                f"**{nv['tieu_de']}** — {_nhan_kq(ts_hien) if ts_hien else '📝 Chưa nhập'}",
                expanded=(ts_hien == "yeu_cau_sua"),
            ):
                if nv.get("mo_ta"):
                    st.markdown(f"_{nv['mo_ta']}_")

                # Đã duyệt → chỉ đọc
                if ts_hien == "da_duyet":
                    st.success("✅ Kết quả đã được duyệt — không thể chỉnh sửa.")
                    st.markdown(
                        f"- Nội dung: *{kq.get('noi_dung_th') or '—'}*\n"
                        f"- Số liệu: **{kq.get('so_lieu') or '—'}**"
                    )
                else:
                    if ts_hien == "yeu_cau_sua":
                        st.warning(
                            f"🔁 **Yêu cầu sửa:** "
                            f"_{kq.get('y_kien_duyet') or 'Không có ý kiến cụ thể'}_"
                        )

                    val_noi_dung = kq.get("noi_dung_th") or "" if kq else ""
                    val_so_lieu  = kq.get("so_lieu") or "" if kq else ""

                    # File uploader ngoài form (Streamlit form không hỗ trợ tốt)
                    attach_key = f"attach_file_{nv_id}"
                    uploaded_file = st.file_uploader(
                        "📎 Đính kèm file (Excel/PDF/Word, tối đa 5 MB)",
                        type=["xlsx", "xls", "pdf", "docx", "doc"],
                        key=attach_key,
                        help="Tuỳ chọn — tải lên bằng chứng / số liệu thực hiện.",
                    )
                    if kq and kq.get("file_name"):
                        st.caption(f"📎 File hiện tại: **{kq['file_name']}**")

                    with st.form(key=f"form_{nv_id}"):
                        noi_dung_th = st.text_area(
                            "Nội dung đã thực hiện",
                            value=val_noi_dung,
                        )
                        so_lieu = st.text_input(
                            "Số liệu kết quả",
                            value=val_so_lieu,
                            placeholder="Ví dụ: 1,250 triệu đồng / 45 hộ",
                            key=f"nv_so_lieu_{nv_id}",
                        )
                        submitted = st.form_submit_button(
                            "💾 Lưu kết quả", type="primary"
                        )

                    if submitted:
                        try:
                            f_path, f_name = None, None
                            if uploaded_file is not None:
                                ket_qua_up = luu_attachment_nhiem_vu(
                                    pgd_user, nv_id,
                                    uploaded_file.name,
                                    uploaded_file.read(),
                                    username,
                                )
                                if ket_qua_up.thanh_cong:
                                    f_path = ket_qua_up.duong_dan
                                    f_name = uploaded_file.name
                                else:
                                    st.warning(ket_qua_up.thong_bao)
                            _upsert_ket_qua(
                                nv_id, pgd_user,
                                noi_dung_th.strip() or None,
                                so_lieu.strip() or None,
                                username,
                                file_path=f_path,
                                file_name=f_name,
                            )
                            db.ghi_audit(
                                username, "nhiem_vu_nhap_ketqua",
                                f"NV id={nv_id} '{nv['tieu_de']}' · PGD {pgd_user}"
                                + (f" · attach={f_name}" if f_name else ""),
                            )
                            st.toast("✅ Đã lưu kết quả — đang chờ duyệt.")
                            st.rerun()
                        except Exception as e:
                            logger.error("Lỗi nhập kết quả: %s", e, exc_info=True)
                            st.error(f"Lỗi khi lưu kết quả: {e}")


# ══════════════════════════════════════════════════════════════════════════
# HÀM RENDER CHÍNH
# ══════════════════════════════════════════════════════════════════════════

from tabs.base_tab import TabContext


def render(tab, **kwargs):
    """Render tab Quản lý Nhiệm vụ — phân nhánh theo role."""
    ctx = TabContext(tab, **kwargs)
    role = ctx.role_norm

    with ctx:
        # Phân nhánh: CN không phải executive → dùng giao diện manager
        is_manager = la_phan_he_cn(role) and not la_executive(role)

        if is_manager:
            t1, t2, t3, t4 = st.tabs([
                "📊 Tổng quan",
                "📥 Danh sách nhiệm vụ",
                "➕ Nhập nhiệm vụ mới",
                "🔍 Hậu kiểm kết quả",
            ])
            _render_tong_quan_manager(t1, **kwargs)
            _render_danh_sach_manager(t2, **kwargs)
            _render_nhap_moi(t3, **kwargs)
            _render_hau_kiem(t4, **kwargs)
        else:
            t1, t2 = st.tabs([
                "📥 Nhiệm vụ được giao",
                "✏️ Nhập kết quả",
            ])
            _render_nhiem_vu_duoc_giao(t1, **kwargs)
            _render_nhap_ket_qua(t2, **kwargs)


# ══════════════════════════════════════════════════════════════════════════
# XUẤT PDF
# ══════════════════════════════════════════════════════════════════════════

def _xuat_pdf_nhiem_vu(ds_nv: list, chu_ky: str, ky: str) -> bytes:
    """Tạo PDF báo cáo danh sách nhiệm vụ. Trả về bytes."""
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    buf = io.BytesIO()

    font_dir = "C:/Windows/Fonts"
    try:
        pdfmetrics.registerFont(TTFont("TimesVN",        os.path.join(font_dir, "times.ttf")))
        pdfmetrics.registerFont(TTFont("TimesVN-Bold",   os.path.join(font_dir, "timesbd.ttf")))
        pdfmetrics.registerFont(TTFont("TimesVN-Italic", os.path.join(font_dir, "timesi.ttf")))
        base_font      = "TimesVN"
        base_font_bold = "TimesVN-Bold"
        base_font_ital = "TimesVN-Italic"
    except Exception as e:  # conv: skip
        logger.warning("Không tải được font TimesVN, dùng Helvetica: %s", e)
        base_font      = "Helvetica"
        base_font_bold = "Helvetica-Bold"
        base_font_ital = "Helvetica-Oblique"

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    s_co_quan = ParagraphStyle(
        "co_quan", fontName=base_font, fontSize=10, leading=14, alignment=1
    )
    s_tieu_de = ParagraphStyle(
        "tieu_de", fontName=base_font_bold, fontSize=13,
        leading=18, alignment=1, spaceBefore=10, spaceAfter=4
    )
    s_phu_de = ParagraphStyle(
        "phu_de", fontName=base_font_ital, fontSize=10,
        leading=14, alignment=1, spaceAfter=14,
        textColor=colors.HexColor("#444444")
    )
    s_normal = ParagraphStyle(
        "normal", fontName=base_font, fontSize=9, leading=13
    )
    s_footer = ParagraphStyle(
        "footer", fontName=base_font_ital, fontSize=8,
        leading=12, textColor=colors.grey
    )

    story = []
    story.append(Paragraph("NGÂN HÀNG CHÍNH SÁCH XÃ HỘI", s_co_quan))
    story.append(Paragraph(TEN_CHI_NHANH_HIEN_THI, s_co_quan))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=colors.HexColor("#185FA5")))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("BÁO CÁO TÌNH HÌNH THỰC HIỆN NHIỆM VỤ", s_tieu_de))
    story.append(Paragraph(
        f"{_NHAN_CHU_KY.get(chu_ky, chu_ky).upper()} {ky}", s_phu_de
    ))
    story.append(Paragraph(
        f"Ngày xuất báo cáo: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        f"  &nbsp;&nbsp;|&nbsp;&nbsp;  Tổng số nhiệm vụ: <b>{len(ds_nv)}</b>",
        s_normal,
    ))
    story.append(Spacer(1, 0.4*cm))

    header = [
        Paragraph("<b>STT</b>", s_normal),
        Paragraph("<b>Tiêu đề nhiệm vụ</b>", s_normal),
        Paragraph("<b>PGD</b>", s_normal),
        Paragraph("<b>Trạng thái</b>", s_normal),
        Paragraph("<b>Deadline</b>", s_normal),
    ]
    data = [header]
    for i, nv in enumerate(ds_nv, 1):
        ten_nv = nv["tieu_de"]
        ten_nv = ten_nv[:80] + "..." if len(ten_nv) > 80 else ten_nv
        data.append([
            Paragraph(str(i), s_normal),
            Paragraph(ten_nv, s_normal),
            Paragraph(nv["pgd"] or "Tất cả PGD", s_normal),
            Paragraph(
                _NHAN_TRANG_THAI_NV.get(nv["trang_thai"], nv["trang_thai"]),
                s_normal,
            ),
            Paragraph(
                datetime.strptime(nv["ngay_deadline"], "%Y-%m-%d")
                        .strftime("%d/%m/%Y")
                if nv.get("ngay_deadline") else "—",
                s_normal,
            ),
        ])

    tbl = Table(
        data,
        colWidths=[1*cm, 8.5*cm, 3.5*cm, 3.5*cm, 2.5*cm],
        repeatRows=1,
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#185FA5")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F1EFE8")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#AAAAAA")),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.8, colors.HexColor("#0C447C")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (0, 0), (0, -1), "CENTER"),
        ("ALIGN",         (4, 0), (4, -1), "CENTER"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.6*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Tài liệu được tạo tự động từ Hệ thống Quản trị Tín dụng Nội bộ VBSP-SCM",
        s_footer,
    ))

    doc.build(story)
    return buf.getvalue()
