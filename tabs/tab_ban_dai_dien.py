"""
tab_ban_dai_dien.py — Ban Đại Diện HĐQT
4 sub-tab:
  1. Tổng hợp số liệu   — bảng KPI + export Excel/PDF
  2. Dự báo nguồn vốn   — tốc độ GN/thu nợ + "X ngày hết room"
  3. Họp BĐD            — lịch họp, biên bản, kết luận (lưu kv_store)
  4. Lưu trữ văn bản    — upload & quản lý file văn bản (lưu kv_store)
"""



from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

import base64
import os
from datetime import datetime, date
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

import db
from auth import normalize_role
from config import (
    COT_TEN_PGD,
    COT_MA_KH,
    COT_TONG_DU_NO,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_NGAY_SL,
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_GIAI_NGAN_TRONG_NAM,
    TEN_CHI_NHANH_HIEN_THI,
    NAM_HT,
    CACHE_HSTD,
)
from data.core import ts_file
from utils import (
    fmt_ty,
    fmt_bang_ty,
    fmt_so,
    fmt_pct,
    vn,
    xuat_excel,
    ten_file_xuat,
)
from tabs.base_tab import TabContext



_KV_HOP = "bdd_hop_list"
_KV_VBAN = "bdd_van_ban_list"
_MAX_FILE = 5 * 1024 * 1024

_GN_NAM_ALIASES = (COT_GIAI_NGAN_TRONG_NAM, "Giải ngân Năm", "Giải ngân năm")
_THU_NO_TH_NAM = ("Thu nợ TH Năm", "Thu nợ TH trong năm")
_THU_NO_QH_NAM = ("Thu nợ QH Năm", "Thu nợ QH trong năm")


@st.cache_data(show_spinner=False)
def _doc_hstd(_ts: float = 0) -> pd.DataFrame | None:
    """Đọc HSTD từ cache parquet. _ts dùng để bust cache khi file thay đổi."""
    try:
        return pd.read_parquet(CACHE_HSTD)
    except Exception:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        return None


def _find_col(df: pd.DataFrame, aliases: tuple) -> str | None:
    for a in aliases:
        if a in df.columns:
            return a
    return None


def _ngay_so_lieu(df: pd.DataFrame) -> datetime | None:
    if COT_NGAY_SL not in df.columns:
        return None
    sl = df[COT_NGAY_SL].dropna()
    if sl.empty:
        return None
    try:
        return datetime.strptime(str(sl.iloc[0]), "%d/%m/%Y")
    except Exception:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        return None


def _tong_hop_kpi(df: pd.DataFrame) -> dict:
    """Tính các chỉ tiêu tổng hợp từ HSTD."""

    def _sum(col):
        if not col or col not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())

    tdn = _sum(COT_TONG_DU_NO)
    dth = _sum(COT_DU_NO_TH)
    dqh = _sum(COT_DU_NO_QH)

    gn_col = _find_col(df, _GN_NAM_ALIASES)
    gn_nam = _sum(gn_col) if gn_col else 0.0

    thu_th_col = _find_col(df, _THU_NO_TH_NAM)
    thu_qh_col = _find_col(df, _THU_NO_QH_NAM)
    thu_nam = (_sum(thu_th_col) if thu_th_col else 0.0) + (_sum(thu_qh_col) if thu_qh_col else 0.0)

    n_kh = int(df[COT_MA_KH].nunique()) if COT_MA_KH in df.columns else 0
    tlqh = dqh / tdn * 100 if tdn > 0 else 0.0

    return {
        "tdn": tdn,
        "dth": dth,
        "dqh": dqh,
        "gn_nam": gn_nam,
        "thu_nam": thu_nam,
        "n_kh": n_kh,
        "tlqh": tlqh,
    }


def _tong_hop_theo_pgd(df: pd.DataFrame) -> pd.DataFrame:
    """Tổng hợp các chỉ tiêu theo PGD."""
    if COT_TEN_PGD not in df.columns:
        return pd.DataFrame()

    agg_kwargs: dict[str, tuple[str, str]] = {}
    if COT_TONG_DU_NO in df.columns:
        agg_kwargs["du_no"] = (COT_TONG_DU_NO, "sum")
    if COT_DU_NO_TH in df.columns:
        agg_kwargs["dth"] = (COT_DU_NO_TH, "sum")
    if COT_DU_NO_QH in df.columns:
        agg_kwargs["dqh"] = (COT_DU_NO_QH, "sum")
    if COT_MA_KH in df.columns:
        agg_kwargs["nkh"] = (COT_MA_KH, "nunique")

    gn_col = _find_col(df, _GN_NAM_ALIASES)
    if gn_col and gn_col in df.columns:
        agg_kwargs["gn_nam"] = (gn_col, "sum")

    if not agg_kwargs:
        return pd.DataFrame()

    g = df.groupby(COT_TEN_PGD, dropna=False).agg(**agg_kwargs).reset_index()

    def _num(col):
        return pd.to_numeric(g[col], errors="coerce").fillna(0)

    out = pd.DataFrame()
    out[COT_TEN_PGD] = g[COT_TEN_PGD].astype(str)
    if "du_no" in g.columns:
        out["Dư nợ (triệu đồng)"] = _num("du_no") / 1e6
    if "dth" in g.columns:
        out["Trong hạn (triệu đồng)"] = _num("dth") / 1e6
    if "dqh" in g.columns:
        out["Quá hạn (triệu đồng)"] = _num("dqh") / 1e6
    if "nkh" in g.columns:
        out["Số KH"] = _num("nkh").astype(int)
    if "gn_nam" in g.columns:
        out["GN năm (triệu đồng)"] = _num("gn_nam") / 1e6

    if "Quá hạn (triệu đồng)" in out.columns and "Dư nợ (triệu đồng)" in out.columns:
        out["NQH%"] = (
            out["Quá hạn (triệu đồng)"] / out["Dư nợ (triệu đồng)"].replace(0, float("nan")) * 100
        ).round(3).fillna(0)
    else:
        out["NQH%"] = 0.0

    return out.sort_values("Dư nợ (triệu đồng)", ascending=False).reset_index(drop=True)


def _render_tong_hop(df: pd.DataFrame, username: str) -> None:
    st.subheader("📊 Tổng hợp số liệu tín dụng chính sách")

    ngay = _ngay_so_lieu(df)
    if ngay:
        st.caption(
            f"Số liệu ngày **{ngay.strftime('%d/%m/%Y')}** · "
            f"{TEN_CHI_NHANH_HIEN_THI}"
        )

    kpi = _tong_hop_kpi(df)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tổng dư nợ", fmt_ty(kpi["tdn"]))
    c2.metric("Dư nợ trong hạn", fmt_ty(kpi["dth"]))
    c3.metric("Dư nợ quá hạn", fmt_ty(kpi["dqh"]))
    c4.metric("Tỷ lệ NQH", f"{vn(kpi['tlqh'], 3)}%")
    c5.metric("Số hộ vay", fmt_so(kpi["n_kh"]))

    st.divider()
    c6, c7 = st.columns(2)
    c6.metric("Giải ngân trong năm", fmt_ty(kpi["gn_nam"]))
    c7.metric("Thu nợ trong năm", fmt_ty(kpi["thu_nam"]))

    st.divider()
    st.markdown("**Bảng tổng hợp theo PGD**")
    df_pgd = _tong_hop_theo_pgd(df)
    if df_pgd.empty:
        st.info("Không đủ dữ liệu để tổng hợp theo PGD.")
        return

    st.dataframe(df_pgd, use_container_width=True, hide_index=True)

    col_xl, col_pdf = st.columns([1, 1])
    with col_xl:
        df_cn = pd.DataFrame(
            [
                {"Chỉ tiêu": "Tổng dư nợ", "Giá trị": round(kpi["tdn"] / 1e6, 3)},
                {"Chỉ tiêu": "Dư nợ trong hạn", "Giá trị": round(kpi["dth"] / 1e6, 3)},
                {"Chỉ tiêu": "Dư nợ quá hạn", "Giá trị": round(kpi["dqh"] / 1e6, 3)},
                {"Chỉ tiêu": "Tỷ lệ NQH (%)", "Giá trị": round(kpi["tlqh"], 3)},
                {"Chỉ tiêu": "Giải ngân trong năm", "Giá trị": round(kpi["gn_nam"] / 1e6, 3)},
                {"Chỉ tiêu": "Thu nợ trong năm", "Giá trị": round(kpi["thu_nam"] / 1e6, 3)},
                {"Chỉ tiêu": "Số hộ vay", "Giá trị": kpi["n_kh"]},
            ]
        )
        xl_bytes = xuat_excel(
            {
                "Tổng hợp CN": df_cn,
                "Chi tiết PGD": df_pgd,
            }
        )
        st.download_button(
            "📥 Xuất Excel",
            data=xl_bytes,
            file_name=ten_file_xuat("BDD_TONGHOP"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with col_pdf:
        try:
            from pdf_service import xuat_pdf


            if st.button("📄 Xuất PDF", use_container_width=True, key="bdd_xuat_pdf", type="primary"):
                pdf_bytes = xuat_pdf(
                    df_pgd,
                    tieu_de=f"Tổng hợp tín dụng chính sách — {TEN_CHI_NHANH_HIEN_THI}",
                    nguoi_xuat=username,
                    cols_tien=["Dư nợ (triệu đồng)", "Trong hạn (triệu đồng)", "Quá hạn (triệu đồng)"],
                    prefix_file="BDD_TONGHOP",
                )
                st.download_button(
                    "⬇️ Tải PDF",
                    data=pdf_bytes,
                    file_name=ten_file_xuat("BDD_TONGHOP", "pdf"),
                    mime="application/pdf",
                    use_container_width=True,
                    key="bdd_dl_pdf",
                )
        except Exception as e:
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            st.caption(f"PDF: {e}")


def _render_du_bao_von(df: pd.DataFrame) -> None:
    st.subheader("📈 Dự báo Nguồn vốn")
    st.caption("Tốc độ giải ngân & thu nợ hiện tại → ước tính đến cuối năm")

    ngay_sl = _ngay_so_lieu(df)
    if ngay_sl is None:
        st.warning("⚠️ Không xác định được ngày số liệu.")
        return

    nam = ngay_sl.year
    dau_nam = datetime(nam, 1, 1)
    cuoi_nam = datetime(nam, 12, 31)
    so_ngay_da_qua = max((ngay_sl - dau_nam).days + 1, 1)
    so_ngay_con_lai = (cuoi_nam - ngay_sl).days

    kpi = _tong_hop_kpi(df)
    gn_nam = kpi["gn_nam"]
    thu_nam = kpi["thu_nam"]
    tdn_hien = kpi["tdn"]

    toc_do_gn = gn_nam / so_ngay_da_qua
    toc_do_thu = thu_nam / so_ngay_da_qua

    gn_du_bao = gn_nam + toc_do_gn * so_ngay_con_lai
    thu_du_bao = thu_nam + toc_do_thu * so_ngay_con_lai
    tdn_du_bao = tdn_hien + (gn_du_bao - gn_nam) - (thu_du_bao - thu_nam)

    st.info(
        f"📅 Số liệu ngày **{ngay_sl.strftime('%d/%m/%Y')}** · "
        f"Đã qua **{so_ngay_da_qua}** ngày · Còn lại **{so_ngay_con_lai}** ngày"
    )

    st.markdown("##### Tốc độ bình quân ngày")
    c1, c2 = st.columns(2)
    c1.metric("Giải ngân/ngày", fmt_ty(toc_do_gn))
    c2.metric("Thu nợ/ngày", fmt_ty(toc_do_thu))

    st.markdown("##### Dự báo lũy kế cả năm")
    c3, c4, c5 = st.columns(3)
    c3.metric("GN dự báo cả năm", fmt_ty(gn_du_bao), delta=fmt_ty(gn_du_bao - gn_nam))
    c4.metric("Thu nợ dự báo", fmt_ty(thu_du_bao), delta=fmt_ty(thu_du_bao - thu_nam))
    c5.metric("Dư nợ cuối năm DK", fmt_ty(tdn_du_bao))

    st.divider()
    st.markdown("##### Dự báo room giải ngân theo chương trình (GQVL)")
    st.caption("Ước tính số ngày còn lại đến khi hết room — dựa trên tốc độ GN hiện tại")

    kh_cn = db.doc_kv("khtd_cn") or {}
    if not kh_cn:
        st.info("Chưa có dữ liệu KHTD. Vào tab **KH Tín dụng Năm** để nhập trước.")
        return

    rows_room = []
    gn_col = _find_col(df, _GN_NAM_ALIASES)
    if not gn_col:
        st.info("Không có cột giải ngân năm trong HSTD.")
        return

    for ma_key, kh_vnd in kh_cn.items():
        kh_vnd = float(kh_vnd or 0)
        if kh_vnd <= 0:
            continue

        try:
            parts = str(ma_key).split("_")
            ma_ct = int(parts[0])
            nv = int(parts[1])
        except Exception:
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            continue

        if COT_MA_CHUONG_TRINH not in df.columns or COT_NGUON_VON not in df.columns:
            continue

        mask_ct = pd.to_numeric(df[COT_MA_CHUONG_TRINH], errors="coerce") == ma_ct
        mask_nv = pd.to_numeric(df[COT_NGUON_VON], errors="coerce") == nv
        df_ct = df[mask_ct & mask_nv]

        gn_ct = float(pd.to_numeric(df_ct[gn_col], errors="coerce").fillna(0).sum()) if not df_ct.empty else 0.0
        room_con_lai = max(kh_vnd - gn_ct, 0)
        toc_do_ct = gn_ct / so_ngay_da_qua if so_ngay_da_qua > 0 else 0

        if toc_do_ct > 0:
            ngay_het_room = room_con_lai / toc_do_ct
            canh_bao = "🔴" if ngay_het_room < 30 else ("🟡" if ngay_het_room < 90 else "🟢")
        else:
            ngay_het_room = None
            canh_bao = "⚪"

        rows_room.append(
            {
                "Mã key": ma_key,
                "KH (triệu đồng)": round(kh_vnd / 1e6, 3),
                "Đã GN (triệu đồng)": round(gn_ct / 1e6, 3),
                "Room còn (triệu đồng)": round(room_con_lai / 1e6, 3),
                "Tốc độ GN/ngày (tr)": round(toc_do_ct / 1e6, 1),
                "Ngày hết room": f"{canh_bao} {round(ngay_het_room)} ngày" if ngay_het_room is not None else "— (chưa GN)",
            }
        )

    if rows_room:
        st.dataframe(pd.DataFrame(rows_room), use_container_width=True, hide_index=True)
    else:
        st.info("Không có dữ liệu để dự báo room.")


def _co_quyen_ghi(role: str) -> bool:
    r = normalize_role(role or "")
    return r in ("admin_cn", "manager_cn", "admin_pgd", "manager_pgd")


def _render_hop_bdd(role: str, username: str) -> None:
    st.subheader("📅 Họp Ban Đại Diện")

    ds_hop: list[dict] = db.doc_kv(_KV_HOP) or []
    co_quyen = _co_quyen_ghi(role)

    if co_quyen:
        with st.expander("➕ Thêm cuộc họp mới", expanded=False):
            with st.form("form_them_hop_bdd"):
                c1, c2 = st.columns(2)
                ngay_hop = c1.date_input("Ngày họp", value=date.today(), key="hop_ngay")
                loai_hop = c2.selectbox(
                    "Loại",
                    ["Họp định kỳ quý", "Họp bất thường", "Họp cuối năm"],
                    key="hop_loai",
                )
                noi_dung = st.text_area("Nội dung / Kết luận chính", height=100, key="hop_nd")
                nguoi_chu_tri = st.text_input("Người chủ trì", key="hop_nct")
                so_vb = st.text_input("Số biên bản / văn bản", placeholder="VD: 05/BB-BDD", key="hop_sovb")
                submitted = st.form_submit_button("💾 Lưu cuộc họp", type="primary")
                if submitted:
                    if not noi_dung.strip():
                        st.error("Vui lòng nhập nội dung cuộc họp.")
                    else:
                        muc_hop = {
                            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                            "ngay_hop": str(ngay_hop),
                            "loai_hop": loai_hop,
                            "noi_dung": noi_dung.strip(),
                            "nguoi_chu_tri": nguoi_chu_tri.strip(),
                            "so_vb": so_vb.strip(),
                            "nguoi_tao": username,
                            "ngay_tao": datetime.now().isoformat(),
                        }
                        ds_hop.insert(0, muc_hop)
                        db.ghi_kv(_KV_HOP, ds_hop, username)
                        db.ghi_audit(username, "bdd_them_hop", f"Thêm họp {ngay_hop} — {loai_hop}")
                        st.success("✅ Đã lưu cuộc họp.")
                        st.rerun()

    if not ds_hop:
        st.info("Chưa có cuộc họp nào được ghi nhận.")
        return

    st.markdown(f"**{len(ds_hop)} cuộc họp đã ghi nhận**")
    for i, h in enumerate(ds_hop):
        label = (
            f"📌 {h.get('ngay_hop','—')} — {h.get('loai_hop','—')} "
            f"{('· ' + h['so_vb']) if h.get('so_vb') else ''}"
        )
        with st.expander(label):
            st.markdown(f"**Người chủ trì:** {h.get('nguoi_chu_tri') or '—'}")
            st.markdown("**Kết luận / Nội dung:**")
            st.write(h.get("noi_dung", ""))
            st.caption(f"Ghi nhận bởi {h.get('nguoi_tao','—')} lúc {str(h.get('ngay_tao','—'))[:16]}")
            if co_quyen:
                if st.button("🗑 Xóa", key=f"del_hop_{h.get('id', i)}"):
                    ds_hop.pop(i)
                    db.ghi_kv(_KV_HOP, ds_hop, username)
                    db.ghi_audit(username, "bdd_xoa_hop", f"Xóa họp id={h.get('id')}")
                    st.rerun()


def _render_van_ban(role: str, username: str) -> None:
    st.subheader("📁 Lưu trữ Văn bản BĐD")
    st.caption("Văn bản chỉ đạo, kết luận họp, nghị quyết BĐD. Lưu metadata + file (tối đa 5MB).")

    ds_vb: list[dict] = db.doc_kv(_KV_VBAN) or []
    co_quyen = _co_quyen_ghi(role)

    if co_quyen:
        with st.expander("➕ Thêm văn bản", expanded=False):
            with st.form("form_them_vb_bdd"):
                c1, c2 = st.columns(2)
                so_vb = c1.text_input("Số hiệu văn bản", placeholder="VD: 12/NQ-BDD", key="vb_so")
                ngay_vb = c2.date_input("Ngày ban hành", value=date.today(), key="vb_ngay")
                loai_vb = st.selectbox(
                    "Loại văn bản",
                    [
                        "Nghị quyết BĐD",
                        "Kết luận họp",
                        "Văn bản chỉ đạo",
                        "Thông báo BĐD",
                        "Khác",
                    ],
                    key="vb_loai",
                )
                trich_yeu = st.text_area("Trích yếu nội dung", height=80, key="vb_ty")
                ghi_chu = st.text_input("Ghi chú", key="vb_gc")
                file_vb = st.file_uploader(
                    "Tải file văn bản (pdf/doc/docx/xlsx/xls) — tối đa 5MB",
                    type=["pdf", "doc", "docx", "xlsx", "xls"],
                    key="vb_file",
                )
                submitted = st.form_submit_button("💾 Lưu", type="primary")
                if submitted:
                    if not trich_yeu.strip():
                        st.error("Vui lòng nhập trích yếu.")
                    else:
                        file_payload = None
                        if file_vb is not None:
                            file_bytes = file_vb.getvalue() or b""
                            if len(file_bytes) > _MAX_FILE:
                                st.error("File vượt quá 5MB.")
                                return
                            file_payload = {
                                "filename": file_vb.name,
                                "mime": file_vb.type or "",
                                "size": len(file_bytes),
                                "data_b64": base64.b64encode(file_bytes).decode("ascii"),
                            }

                        muc = {
                            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                            "so_vb": so_vb.strip(),
                            "ngay_vb": str(ngay_vb),
                            "loai_vb": loai_vb,
                            "trich_yeu": trich_yeu.strip(),
                            "ghi_chu": ghi_chu.strip(),
                            "file": file_payload,
                            "nguoi_tao": username,
                            "ngay_tao": datetime.now().isoformat(),
                        }
                        ds_vb.insert(0, muc)
                        db.ghi_kv(_KV_VBAN, ds_vb, username)
                        db.ghi_audit(username, "bdd_them_vb", f"Thêm VB {so_vb} — {loai_vb}")
                        st.success("✅ Đã lưu.")
                        st.rerun()

    if not ds_vb:
        st.info("Chưa có văn bản nào được lưu trữ.")
        return

    col_f1, col_f2 = st.columns(2)
    ds_loai = sorted({v.get("loai_vb", "") for v in ds_vb if v.get("loai_vb")})
    loc_loai = col_f1.selectbox("Loại", ["Tất cả"] + ds_loai, key="vb_loc_loai")
    loc_kw = col_f2.text_input("Tìm theo trích yếu / số hiệu", key="vb_loc_kw")

    hien_thi = ds_vb
    if loc_loai != "Tất cả":
        hien_thi = [v for v in hien_thi if v.get("loai_vb") == loc_loai]
    if loc_kw.strip():
        kw = loc_kw.strip().lower()
        hien_thi = [
            v
            for v in hien_thi
            if kw in v.get("trich_yeu", "").lower() or kw in v.get("so_vb", "").lower()
        ]

    st.markdown(f"**{len(hien_thi)} văn bản**")

    for i, v in enumerate(hien_thi):
        label = f"📄 {v.get('so_vb') or '—'}  ·  {v.get('ngay_vb','—')}  ·  {v.get('loai_vb','—')}"
        with st.expander(label):
            st.markdown(f"**Trích yếu:** {v.get('trich_yeu','')}")
            if v.get("ghi_chu"):
                st.caption(f"Ghi chú: {v['ghi_chu']}")
            f = v.get("file") or None
            if isinstance(f, dict) and f.get("data_b64"):
                try:
                    data = base64.b64decode(f["data_b64"].encode("ascii"))
                    st.download_button(
                        "⬇️ Tải file",
                        data=data,
                        file_name=f.get("filename") or "van_ban",
                        mime=f.get("mime") or "application/octet-stream",
                        key=f"vb_dl_{v.get('id', i)}",
                        use_container_width=True,
                    )
                except Exception:
                    logger.error("Lỗi trong khối except: %s", e, exc_info=True)
                    st.caption("Không đọc được file đã lưu.")
            st.caption(f"Lưu bởi {v.get('nguoi_tao','—')} lúc {str(v.get('ngay_tao','—'))[:16]}")
            if co_quyen:
                idx_thuc = ds_vb.index(v) if v in ds_vb else -1
                if idx_thuc >= 0 and st.button("🗑 Xóa", key=f"del_vb_{v.get('id', i)}"):
                    ds_vb.pop(idx_thuc)
                    db.ghi_kv(_KV_VBAN, ds_vb, username)
                    db.ghi_audit(username, "bdd_xoa_vb", f"Xóa VB {v.get('so_vb')}")
                    st.rerun()

    df_export = pd.DataFrame(
        [
            {
                "Số hiệu": v.get("so_vb", ""),
                "Ngày": v.get("ngay_vb", ""),
                "Loại": v.get("loai_vb", ""),
                "Trích yếu": v.get("trich_yeu", ""),
                "Ghi chú": v.get("ghi_chu", ""),
                "File": (v.get("file") or {}).get("filename", ""),
            }
            for v in ds_vb
        ]
    )
    st.download_button(
        "📥 Xuất danh mục Excel",
        data=xuat_excel({"Danh mục VB BĐD": df_export}),
        file_name=ten_file_xuat("BDD_VANBAN"),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def render(tab, cap: str = "xa", **kwargs) -> None:
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")
    v = kwargs.get("df_full")
    df_full = v if v is not None and not getattr(v, "empty", True) else kwargs.get("df")

    ctx = TabContext(tab, **kwargs)
    with ctx:
        cap_hien = "tỉnh" if cap == "tinh" else "huyện"
        st.header(f"🏛️ Ban Đại Diện HĐQT cấp {cap_hien}")
        st.caption("Tổng hợp số liệu · Dự báo vốn · Quản lý họp · Lưu trữ văn bản")

        df = df_full if df_full is not None and not getattr(df_full, "empty", True) else _doc_hstd(ts_file(CACHE_HSTD))
        if df is None or df.empty:
            st.warning("⚠️ Chưa có dữ liệu HSTD. Vui lòng merge HSTD để sử dụng các chức năng tổng hợp/dự báo.")
            return

        sub1, sub2, sub3, sub4 = st.tabs(
            [
                "📊 Tổng hợp số liệu",
                "📈 Dự báo nguồn vốn",
                "📅 Họp BĐD",
                "📁 Lưu trữ văn bản",
            ]
        )
        with sub1:
            _render_tong_hop(df, username)
        with sub2:
            _render_du_bao_von(df)
        with sub3:
            _render_hop_bdd(role, username)
        with sub4:
            _render_van_ban(role, username)
