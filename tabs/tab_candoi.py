"""Tab Cân đối."""
from __future__ import annotations

import os
import socket
from io import BytesIO
from datetime import datetime
from typing import TYPE_CHECKING, Any

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import *
from utils import (
    fmt_ty,
    fmt_cl,
    fmt_pct,
    xuat_excel,
    ten_file_xuat,
    hien_thi_dataframe_phan_trang,
)
import db
from data import ts_file, doc_dienbao, db_lookup
from data.pgd import duong_dan_pgd, pgd_slug
from services import luu_dienbao
from tabs import tab_kehoach
from logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


def _tao_column_config_candoi(
    nam_prev: str,
    nam_ht: str
) -> dict[str, st.column_config.Column]:
    """
    Tạo column_config cho bảng cân đối.

    Args:
        nam_prev: Năm trước (VD: "2025")
        nam_ht: Năm hiện tại (VD: "2026")

    Returns:
        Dict cấu hình column cho st.dataframe
    """
    return {
        f"31/12/{nam_prev}": st.column_config.NumberColumn(
            f"31/12/{nam_prev}",
            format="%.0f",
            help=f"Số liệu ngày 31/12/{nam_prev}"
        ),
        f"{nam_ht} (HT)": st.column_config.NumberColumn(
            f"{nam_ht} (HT)",
            format="%.0f",
            help=f"Số liệu hiện tại năm {nam_ht}"
        ),
        "Chênh lệch": st.column_config.NumberColumn(
            "Chênh lệch",
            format="%.0f",
            help="Chênh lệch giá trị"
        ),
        "Tỷ lệ %": st.column_config.NumberColumn(
            "Tỷ lệ %",
            format="%.2f%%",
            help="Tỷ lệ thay đổi %"
        ),
        "NQH hiện tại": st.column_config.NumberColumn(
            "NQH hiện tại",
            format="%.0f",
            help="Nợ quá hạn hiện tại"
        ),
        "NQH 31/12": st.column_config.NumberColumn(
            "NQH 31/12",
            format="%.0f",
            help="Nợ quá hạn 31/12"
        ),
    }


# Định nghĩa nhóm chương trình (dùng cho sub-tab + xuất Excel)
_CHUONG_TRINH_CANDOI: list[tuple[str, str | None]] = [
    ("── KẾ HOẠCH A ──",          None),
    ("Hộ nghèo KHA",               "Dư nợ hộ nghèo KHA"),
    ("Hộ cận nghèo KHA",           "Dư nợ hộ cận nghèo KHA"),
    ("Hộ mới thoát nghèo KHA",     "Dư nợ hộ mới thoát nghèo KHA"),
    ("HSSV có HCKK",               "Dư nợ HSSV có HCKK"),
    ("Giải quyết việc làm KHA",    "Dư nợ GQVL KHA"),
    ("NSVSMT nông thôn (KHA+KHB)", "Dư nợ NSVSMT NT"),
    ("SXKD vùng KK",               "Dư nợ SXKD VKK"),
    ("TN vùng KK",                 "Dư nợ TN VKK"),
    ("Nhà ở hộ nghèo",             "Dư nợ hộ nghèo về nhà ở"),
    ("Nhà ở gđ2 KHA",              "Dư nợ nhà ở gđ2 KHA"),
    ("XKLĐ",                       "Dư nợ XKLĐ"),
    ("KFW",                        "Dư nợ KFW"),
    ("DTTS ĐBKK KHA",              "Dư nợ DTTS ĐBKK KHA"),
    ("DTTS 2085 KHA",              "Dư nợ DTTS 2085 KHA"),
    ("NOXH 100% KHA",              "Dư nợ NOXH100 KHA"),
    ("Khác KHA",                   "Dư nợ Khác KHA"),
    ("Nợ quá hạn KHA",             "Dư nợ Quá hạn KHA"),
    ("Nợ khoanh KHA",              "Dư nợ Khoanh KHA"),
    ("── KẾ HOẠCH B ──",          None),
    ("Hộ nghèo KHB",               "Dư nợ hộ nghèo KHB"),
    ("Hộ cận nghèo KHB",           "Dư nợ hộ cận nghèo KHB"),
    ("Hộ mới thoát nghèo KHB",     "Dư nợ hộ mới thoát nghèo KHB"),
    ("Giải quyết việc làm KHB",    "Dư nợ GQVK KHB"),
    ("NSVSMT NT KHB",              "Dư nợ NSVSMT NT KHB"),
    ("DTTS ĐBKK KHB",              "Dư nợ DTTS ĐBKK KHB"),
    ("DTTS 2085 KHB",              "Dư nợ DTTS 2085 KHB"),
    ("NOXH 100% KHB",              "Dư nợ NOXH100 KHB"),
    ("Nhà ở CHSAPT KHB",           "DƯ nợ NCHSAPT KHB"),
    ("Khác KHB",                   "Dư nợ Khác KHB"),
    ("Nợ quá hạn KHB",             "Dư nợ Quá hạn KHB"),
    ("Nợ khoanh KHB",              "Dư nợ Khoanh KHB"),
]


def _lay_nqh_con(rows: list[dict], ten_cha: str) -> float:
    """Tìm giá trị dòng NQH con ngay sau ten_cha."""
    for r in rows:
        if r["la_nqh_con"] and r["cha"] == ten_cha:
            return r["val"]
    return 0.0


from tabs.base_tab import TabContext


def render(tab: DeltaGenerator | None = None, **kwargs: dict) -> None:
    ctx = TabContext(tab, **kwargs)
    df        = kwargs.get("df")
    df_full   = ctx.df_full if ctx.df_full is not None and not ctx.df_full.empty else df
    role      = ctx.role_norm
    pgd_user  = ctx.pgd_user
    username  = ctx.username
    df_nq11   = kwargs.get("df_nq11")
    pgd_mode  = kwargs.get("pgd_mode", False)

    if pgd_mode and not pgd_user:
        with ctx:
            st.error("Không xác định được PGD.")
        return

    key_sfx   = f"_{pgd_slug(pgd_user)}" if pgd_mode else ""

    path_dien_ht = (
        duong_dan_pgd(pgd_user, "dienbao_ht") if pgd_mode else None
    )
    path_dien_prev = (
        duong_dan_pgd(pgd_user, "dienbao_prev") if pgd_mode else None
    )
    store_ht = path_dien_ht if pgd_mode else DB_HT_CACHE
    store_prev = path_dien_prev if pgd_mode else DB_PREV_CACHE

    with ctx:
        nam_ht   = str(datetime.today().year)
        nam_prev = str(datetime.today().year - 1)

        if pgd_mode:
            st.subheader(f"📌 Số liệu {pgd_user} từ file Điện báo PGD")
        else:
            st.subheader("📌 Số liệu toàn Chi nhánh từ file Điện báo")
        st.caption("⚖️ Cân đối Nguồn vốn & Sử dụng vốn")

        with st.expander("📖 Hướng dẫn Điện báo", expanded=False):
            from pathlib import Path

            path = Path(__file__).resolve().parent.parent / "docs" / "HUONG_DAN_DIEN_BAO.md"
            if path.exists():
                st.markdown(path.read_text(encoding="utf-8"))

        def vfmt_cd(x, d=1):
            try:
                x = float(x)
                s = f"{x:,.{d}f}".replace(",","X").replace(".",",").replace("X",".")
                return s.rstrip("0").rstrip(",") if "," in s else s
            except: return "—"

        def fmt_pct(x):
            try:
                x = float(x)
                return (f"+{vfmt_cd(x,1)}%" if x > 0 else f"{vfmt_cd(x,1)}%") if x != 0 else "0%"
            except: return "—"

        if pgd_mode:
            path_ht = path_dien_ht if os.path.exists(path_dien_ht) else None
            path_prev = path_dien_prev if os.path.exists(path_dien_prev) else None
        else:
            path_ht = DB_HT_CACHE if os.path.exists(DB_HT_CACHE) else FILE_PATH_DB
            path_prev = DB_PREV_CACHE if os.path.exists(DB_PREV_CACHE) else FILE_PATH_DB_PREV

        db_ht_rows   = None
        db_prev_rows = None

        if path_ht and os.path.exists(path_ht):
            try:
                db_ht_rows = doc_dienbao(path_ht, ts_file(path_ht))
            except Exception as e:
                logger.error("Lỗi đọc file Điện báo hiện tại: %s", e, exc_info=True)
                st.error(f"Lỗi đọc file Điện báo hiện tại: {e}")

        if path_prev and os.path.exists(path_prev):
            try:
                db_prev_rows = doc_dienbao(path_prev, ts_file(path_prev))
            except Exception as e:
                logger.error("Lỗi đọc file Điện báo 31/12: %s", e, exc_info=True)
                st.error(f"Lỗi đọc file Điện báo 31/12: {e}")

        def build_row(ten_hien: str, val_ht: float, val_pv: float, la_con: bool = False) -> dict[str, Any]:
            cl = val_ht - val_pv if db_prev_rows is not None else None
            tl = (cl / val_pv * 100) if (cl is not None and val_pv and val_pv != 0) else None
            indent = "　　" if la_con else ""
            return {
                "Chỉ tiêu":          indent + ten_hien,
                f"31/12/{nam_prev}": val_pv if db_prev_rows else 0,
                f"{nam_ht} (HT)":    val_ht,
                "Chênh lệch":        cl if cl is not None else 0,
                "Tỷ lệ %":           tl if tl is not None else 0,
                "_ht": val_ht, "_pv": val_pv or 0, "_cl": cl or 0,
            }

        cd_tab1, cd_tab2, cd_tab3, cd_tab4, cd_tab5 = st.tabs([
            "📊 Tổng quan",
            "🎯 KH vs Thực hiện",
            "📋 Toàn bộ chỉ tiêu",
            "📌 Theo chương trình",
            "📊 Biểu đồ so sánh",
        ])

        with cd_tab1:
            if db_ht_rows is None:
                st.info("Chưa có file Điện báo hiện tại — vui lòng **upload ở cuối trang**.")
            else:
                tong_dn_ht   = db_lookup(db_ht_rows,   "Tổng dư nợ")
                nguon_tw_ht  = db_lookup(db_ht_rows,   "Nguồn vốn cân đối từ TW (KHA)")
                huy_dong_ht  = db_lookup(db_ht_rows,   "Tổng huy động vốn")
                utdt_ht      = db_lookup(db_ht_rows,   "Nguồn vốn nhận UTĐT tại ĐP")
                nqh_ht       = db_lookup(db_ht_rows,   "Dư nợ Quá hạn KHA") + db_lookup(db_ht_rows, "Dư nợ Quá hạn KHB")
                kha_ht       = db_lookup(db_ht_rows,   "Dư nợ Kế hoạch A")
                khb_ht       = db_lookup(db_ht_rows,   "Dư nợ Kế hoạch B")

                if pgd_mode:
                    st.markdown(f"### 📊 Tổng quan — {pgd_user} — {nam_ht}")
                else:
                    st.markdown(f"### 📊 Tổng quan toàn Chi nhánh — {nam_ht}")
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                if db_prev_rows:
                    label_so_sanh = f"so 31/12/{nam_prev}"
                    tong_dn_pv  = db_lookup(db_prev_rows, "Tổng dư nợ")
                    nguon_tw_pv = db_lookup(db_prev_rows, "Nguồn vốn cân đối từ TW (KHA)")
                    huy_dong_pv = db_lookup(db_prev_rows, "Tổng huy động vốn")
                    utdt_pv     = db_lookup(db_prev_rows, "Nguồn vốn nhận UTĐT tại ĐP")
                    nqh_pv      = db_lookup(db_prev_rows, "Dư nợ Quá hạn KHA") + db_lookup(db_prev_rows, "Dư nợ Quá hạn KHB")
                    kha_pv      = db_lookup(db_prev_rows, "Dư nợ Kế hoạch A")
                    khb_pv      = db_lookup(db_prev_rows, "Dư nợ Kế hoạch B")
                    m1.metric(f"Tổng dư nợ\n({label_so_sanh})",   fmt_ty(tong_dn_ht),  delta=fmt_cl(tong_dn_ht - tong_dn_pv))
                    m2.metric(f"Vốn TW (KHA)\n({label_so_sanh})",  fmt_ty(nguon_tw_ht), delta=fmt_cl(nguon_tw_ht - nguon_tw_pv))
                    m3.metric(f"Huy động vốn\n({label_so_sanh})",  fmt_ty(huy_dong_ht), delta=fmt_cl(huy_dong_ht - huy_dong_pv))
                    m4.metric(f"Vốn UTĐT ĐP\n({label_so_sanh})",   fmt_ty(utdt_ht),     delta=fmt_cl(utdt_ht - utdt_pv))
                    m5.metric(f"Dư nợ KHA\n({label_so_sanh})",     fmt_ty(kha_ht),      delta=fmt_cl(kha_ht - kha_pv))
                    tl_nqh = nqh_ht / tong_dn_ht * 100 if tong_dn_ht else 0
                    m6.metric(
                        "NQH (KHA+KHB)",
                        fmt_ty(nqh_ht),
                        delta=f"{tl_nqh:.3f}% tổng DN",
                        delta_color="inverse",
                        help=f"Tỷ lệ NQH/Tổng dư nợ tại thời điểm hiện tại · So sánh: 31/12/{nam_prev}",
                    )
                else:
                    tl_nqh = nqh_ht / tong_dn_ht * 100 if tong_dn_ht else 0
                    m1.metric("Tổng dư nợ",  fmt_ty(tong_dn_ht))
                    m2.metric("Vốn TW (KHA)",fmt_ty(nguon_tw_ht))
                    m3.metric("Huy động vốn",fmt_ty(huy_dong_ht))
                    m4.metric("Vốn UTĐT ĐP", fmt_ty(utdt_ht))
                    m5.metric("Dư nợ KHA",   fmt_ty(kha_ht))
                    m6.metric("NQH (KHA+KHB)",fmt_ty(nqh_ht),
                              delta=f"{tl_nqh:.3f}% tổng DN", delta_color="inverse")

        with cd_tab2:
            tab_kehoach.render(
                cd_tab2,
                **{
                    **kwargs,
                    "pgd_mode": pgd_mode,
                    "khtd_mode": (
                        f"candoi_pgd_{pgd_slug(pgd_user)}"
                        if pgd_mode
                        else "candoi_cn_kh"
                    ),
                },
            )

        with cd_tab3:
            if db_ht_rows is None:
                st.info("Chưa có dữ liệu — upload Điện báo hiện tại ở cuối trang.")
            else:
                nhom_loc = st.radio("Lọc nhóm",
                    ["Tất cả","Nguồn vốn","Dư nợ KHA","Dư nợ KHB","Vốn an toàn & quỹ"],
                    horizontal=True, key=f"cd_nhom{key_sfx}")

                NHOM_KEYS_LOC = {
                    "Nguồn vốn":       ["Nguồn vốn","Tổng huy động","Tiền gửi","UTĐT"],
                    "Dư nợ KHA":       ["KHA","Kế hoạch A","GQVL KHA","NSVSMT NT","HSSV",
                                        "hộ nghèo KHA","cận nghèo KHA","thoát nghèo KHA",
                                        "SXKD VKK","XKLĐ","KFW","nhà ở","DTTS","NOXH"],
                    "Dư nợ KHB":       ["KHB","Kế hoạch B","GQVK KHB","NSVSMT NT KHB",
                                        "hộ nghèo KHB","cận nghèo KHB","thoát nghèo KHB",
                                        "DTTS ĐBKK KHB","NOXH100 KHB","NCHSAPT"],
                    "Vốn an toàn & quỹ":["Vốn An toàn","Tồn quỹ","Tiền gửi tại NHNN"],
                }

                rows_tab1 = []
                for r in db_ht_rows:
                    ten_r = r["ten"]
                    val_ht_r = r["val"]
                    val_pv_r = 0.0
                    if db_prev_rows:
                        for rp in db_prev_rows:
                            if rp["la_nqh_con"] == r["la_nqh_con"] and rp["cha"] == r["cha"] and rp["ten"] == ten_r:
                                val_pv_r = rp["val"]
                                break
                            if not r["la_nqh_con"] and not rp["la_nqh_con"] and rp["ten"] == ten_r:
                                val_pv_r = rp["val"]
                                break

                    if nhom_loc != "Tất cả":
                        kws = NHOM_KEYS_LOC.get(nhom_loc, [])
                        ten_check = (r["cha"] or ten_r) if r["la_nqh_con"] else ten_r
                        if not any(kw.lower() in ten_check.lower() for kw in kws):
                            continue

                    ten_hien = ten_r.replace("  NQH: ", "  └ NQH: ")
                    rows_tab1.append(build_row(ten_hien, val_ht_r, val_pv_r, r["la_nqh_con"]))

                if rows_tab1:
                    cols_s = ["Chỉ tiêu", f"31/12/{nam_prev}", f"{nam_ht} (HT)", "Chênh lệch", "Tỷ lệ %"]
                    hien_thi_dataframe_phan_trang(
                        pd.DataFrame(rows_tab1)[cols_s],
                        key=f"candoi_ss_chitieu{key_sfx}",
                        column_config=_tao_column_config_candoi(nam_prev, nam_ht),
                        height=520,
                    )

        with cd_tab4:
            if db_ht_rows is None:
                st.info("Chưa có dữ liệu — upload Điện báo hiện tại ở cuối trang.")
            else:
                st.markdown(f"**So sánh dư nợ từng chương trình: 31/12/{nam_prev} vs {nam_ht} (HT)**")

                rows_ct = []
                for ten_hien, key in _CHUONG_TRINH_CANDOI:
                    if key is None:
                        rows_ct.append({
                            "Chương trình":      ten_hien,
                            f"31/12/{nam_prev}": float('nan'),
                            f"{nam_ht} (HT)":    float('nan'),
                            "Chênh lệch":        float('nan'),
                            "Tỷ lệ %":           float('nan'),
                            "NQH hiện tại":      float('nan'),
                            "NQH 31/12":         float('nan'),
                            "_is_header": True,
                            "_ht": 0, "_pv": 0,
                        })
                        continue

                    val_ht_ct = db_lookup(db_ht_rows, key)
                    val_pv_ct = db_lookup(db_prev_rows, key) if db_prev_rows else 0.0
                    nqh_ht_ct = _lay_nqh_con(db_ht_rows, key)
                    nqh_pv_ct = _lay_nqh_con(db_prev_rows, key) if db_prev_rows else 0.0

                    cl = val_ht_ct - val_pv_ct
                    tl = (cl / val_pv_ct * 100) if val_pv_ct else None

                    rows_ct.append({
                        "Chương trình":      ten_hien,
                        f"31/12/{nam_prev}": val_pv_ct,
                        f"{nam_ht} (HT)":    val_ht_ct,
                        "Chênh lệch":        cl,
                        "Tỷ lệ %":           tl if tl is not None else 0,
                        "NQH hiện tại":      nqh_ht_ct,
                        "NQH 31/12":         nqh_pv_ct,
                        "_is_header": False,
                        "_ht": val_ht_ct, "_pv": val_pv_ct,
                    })

                df_ct = pd.DataFrame(rows_ct)
                cols_ct = ["Chương trình", f"31/12/{nam_prev}", f"{nam_ht} (HT)",
                           "Chênh lệch", "Tỷ lệ %", "NQH hiện tại", "NQH 31/12"]
                hien_thi_dataframe_phan_trang(
                    df_ct[cols_ct],
                    key=f"candoi_ct_chuong_trinh{key_sfx}",
                    column_config=_tao_column_config_candoi(nam_prev, nam_ht),
                    height=560,
                )

                if db_prev_rows:
                    st.divider()
                    df_ct_loc = df_ct[~df_ct["_is_header"] & (df_ct["_ht"] > 0)]
                    c_tang, c_giam = st.columns(2)
                    with c_tang:
                        st.markdown("**📈 Tăng mạnh nhất (top 8)**")
                        top_tang = df_ct_loc[df_ct_loc["_ht"] > df_ct_loc["_pv"]]\
                            .assign(_cl=lambda x: x["_ht"] - x["_pv"])\
                            .nlargest(8, "_cl")
                        if not top_tang.empty:
                            top_tang["_tl"] = (top_tang["_cl"] / top_tang["_pv"] * 100).round(1)
                            fig_t = px.bar(top_tang, x="_cl", y="Chương trình", orientation="h",
                                text=top_tang["_tl"].apply(lambda x: f"+{x:.1f}%"),
                                color="_cl", color_continuous_scale="Blues")
                            fig_t.update_traces(textposition="outside")
                            fig_t.update_layout(height=300, margin=dict(l=0,r=60,t=5,b=5),
                                xaxis_title="", yaxis=dict(title="",autorange="reversed"),
                                coloraxis_showscale=False,
                                plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)")
                            st.plotly_chart(fig_t, use_container_width=True)
                    with c_giam:
                        st.markdown("**📉 Giảm mạnh nhất (top 8)**")
                        top_giam = df_ct_loc[df_ct_loc["_ht"] < df_ct_loc["_pv"]]\
                            .assign(_cl=lambda x: x["_ht"] - x["_pv"])\
                            .nsmallest(8, "_cl")
                        if not top_giam.empty:
                            top_giam["_tl"] = (top_giam["_cl"] / top_giam["_pv"] * 100).round(1)
                            fig_g = px.bar(top_giam, x="_cl", y="Chương trình", orientation="h",
                                text=top_giam["_tl"].apply(lambda x: f"{x:.1f}%"),
                                color="_cl", color_continuous_scale="Reds_r")
                            fig_g.update_traces(textposition="outside")
                            fig_g.update_layout(height=300, margin=dict(l=0,r=60,t=5,b=5),
                                xaxis_title="", yaxis=dict(title="",autorange="reversed"),
                                coloraxis_showscale=False,
                                plot_bgcolor="rgba(0,0,0,0)",paper_bgcolor="rgba(0,0,0,0)")
                            st.plotly_chart(fig_g, use_container_width=True)

        with cd_tab5:
            if db_ht_rows is None:
                st.info("Chưa có dữ liệu — upload Điện báo hiện tại ở cuối trang.")
            elif not db_prev_rows:
                st.info("Upload file Điện báo 31/12 để xem biểu đồ so sánh.")
            else:
                BD_GROUPS = {
                    "Nguồn vốn": [
                        ("Vốn TW (KHA)",  "Nguồn vốn cân đối từ TW (KHA)"),
                        ("Huy động vốn",  "Tổng huy động vốn"),
                        ("Vốn UTĐT ĐP",  "Nguồn vốn nhận UTĐT tại ĐP"),
                    ],
                    "Dư nợ tổng & phân kỳ": [
                        ("Tổng dư nợ",    "Tổng dư nợ"),
                        ("Dư nợ KHA",     "Dư nợ Kế hoạch A"),
                        ("Dư nợ KHB",     "Dư nợ Kế hoạch B"),
                    ],
                    "Chương trình lớn nhất": [
                        ("GQVL KHA",      "Dư nợ GQVL KHA"),
                        ("NSVSMT NT",     "Dư nợ NSVSMT NT"),
                        ("HSSV HCKK",     "Dư nợ HSSV có HCKK"),
                        ("SXKD VKK",      "Dư nợ SXKD VKK"),
                        ("GQVK KHB",      "Dư nợ GQVK KHB"),
                        ("NOXH KHA",      "Dư nợ NOXH100 KHA"),
                        ("NOXH KHB",      "Dư nợ NOXH100 KHB"),
                        ("Hộ MTN KHA",    "Dư nợ hộ mới thoát nghèo KHA"),
                        ("Cận nghèo KHA", "Dư nợ hộ cận nghèo KHA"),
                    ],
                }
                chon_bd = st.radio("Nhóm biểu đồ", list(BD_GROUPS.keys()),
                    horizontal=True, key=f"cd_bd_nhom{key_sfx}")
                items = BD_GROUPS[chon_bd]
                ten_ng   = [i[0] for i in items]
                val_ht_b = [db_lookup(db_ht_rows,   i[1])/1e6 for i in items]
                val_pv_b = [db_lookup(db_prev_rows, i[1])/1e6 for i in items]

                fig_bd = go.Figure()
                fig_bd.add_bar(name=f"31/12/{nam_prev}", x=ten_ng, y=val_pv_b,
                    marker_color="#90CAF9",
                    text=[f"{v:,.1f}".replace(",","X").replace(".",",").replace("X",".") for v in val_pv_b],
                    textposition="outside")
                fig_bd.add_bar(name=f"{nam_ht} (HT)", x=ten_ng, y=val_ht_b,
                    marker_color="#1565C0",
                    text=[f"{v:,.1f}".replace(",","X").replace(".",",").replace("X",".") for v in val_ht_b],
                    textposition="outside")
                fig_bd.update_layout(
                    barmode="group", height=420, yaxis_title="Tỷ đồng",
                    margin=dict(l=0,r=20,t=10,b=10),
                    legend=dict(orientation="h", y=1.08),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_bd, use_container_width=True)

        st.divider()

        st.markdown("**📤 Upload file Điện báo**")
        up_col1, up_col2 = st.columns(2)

        with up_col1:
            st.caption(f"📅 File Điện báo **hiện tại** (năm {nam_ht})")
            f_db_ht = st.file_uploader(
                "Chọn file Điện báo hiện tại",
                type=["xlsx", "xls"],
                key=f"up_db_ht{key_sfx}",
            )

            if f_db_ht:
                try:
                    with st.spinner("⏳ Đang xử lý..."):
                        kq_ht = luu_dienbao(
                            "ht",
                            f_db_ht.read(),
                            f_db_ht.name,
                            ten_pgd=pgd_user if pgd_mode else None,
                        )
                    kq_ht.hien_thi()
                    if kq_ht.thanh_cong:
                        st.success("✅ Hoàn thành — Điện báo hiện tại đã sẵn sàng!")
                        st.cache_data.clear()
                except Exception as e:
                    logger.error("Upload điện báo hiện tại: %s", e, exc_info=True)
                    u = st.session_state.get("username", "unknown")
                    db.ghi_audit(
                        u,
                        "loi_he_thong",
                        f"[{socket.gethostname()}] upload điện báo ht: {e}",
                    )
                    st.error(f"❌ Lỗi upload Điện báo hiện tại: {e}")
            elif os.path.exists(store_ht):
                st.info(
                    f"📂 Đã có file — cập nhật lúc: "
                    f"{pd.Timestamp(os.path.getmtime(store_ht), unit='s').strftime('%d/%m/%Y %H:%M')}"
                )
            else:
                st.warning("⚠️ Chưa có file — vui lòng upload")

        with up_col2:
            st.caption(f"📅 File Điện báo **31/12 năm trước** ({nam_prev})")
            f_db_prev = st.file_uploader(
                "Chọn file Điện báo 31/12 năm trước",
                type=["xlsx", "xls"],
                key=f"up_db_prev{key_sfx}",
            )

            if f_db_prev:
                try:
                    with st.spinner("⏳ Đang xử lý..."):
                        kq_prev = luu_dienbao(
                            "prev",
                            f_db_prev.read(),
                            f_db_prev.name,
                            ten_pgd=pgd_user if pgd_mode else None,
                        )
                    kq_prev.hien_thi()
                    if kq_prev.thanh_cong:
                        st.success("✅ Hoàn thành — Điện báo 31/12 đã sẵn sàng!")
                        st.cache_data.clear()
                except Exception as e:
                    logger.error("Upload điện báo 31/12: %s", e, exc_info=True)
                    u = st.session_state.get("username", "unknown")
                    db.ghi_audit(
                        u,
                        "loi_he_thong",
                        f"[{socket.gethostname()}] upload điện báo prev: {e}",
                    )
                    st.error(f"❌ Lỗi upload Điện báo 31/12: {e}")
            elif os.path.exists(store_prev):
                st.info(
                    f"📂 Đã có file — cập nhật lúc: "
                    f"{pd.Timestamp(os.path.getmtime(store_prev), unit='s').strftime('%d/%m/%Y %H:%M')}"
                )
            else:
                st.warning("⚠️ Chưa có file — vui lòng upload")

        st.divider()
        if db_ht_rows is None:
            st.caption("Xuất Excel: cần có file Điện báo hiện tại.")
        elif st.button("📥 Xuất so sánh cân đối ra Excel", key=f"btn_xuat_cd{key_sfx}"):
            buf = BytesIO()
            rows_ex1, rows_ex2 = [], []
            for r in db_ht_rows:
                val_pv_e = 0.0
                if db_prev_rows:
                    for rp in db_prev_rows:
                        if rp["la_nqh_con"] == r["la_nqh_con"] and rp["ten"] == r["ten"]:
                            val_pv_e = rp["val"]; break
                cl_e = r["val"] - val_pv_e
                rows_ex1.append({
                    "Chỉ tiêu":          r["ten"],
                    "Loại":              "NQH (dòng con)" if r["la_nqh_con"] else "Chỉ tiêu chính",
                    f"31/12/{nam_prev}":  val_pv_e,
                    f"{nam_ht} (HT)":     r["val"],
                    "Chênh lệch":         cl_e,
                    "Tỷ lệ %":            round(cl_e/val_pv_e*100,2) if val_pv_e else 0,
                })
            for ten_hien, key in _CHUONG_TRINH_CANDOI:
                if key is None: continue
                val_ht_e  = db_lookup(db_ht_rows,   key)
                val_pv_e  = db_lookup(db_prev_rows, key) if db_prev_rows else 0
                nqh_ht_e  = _lay_nqh_con(db_ht_rows,   key)
                nqh_pv_e  = _lay_nqh_con(db_prev_rows, key) if db_prev_rows else 0
                cl_e = val_ht_e - val_pv_e
                rows_ex2.append({
                    "Chương trình":       ten_hien,
                    f"DN 31/12/{nam_prev}":val_pv_e,
                    f"DN {nam_ht} (HT)":   val_ht_e,
                    "Chênh lệch":          cl_e,
                    "Tỷ lệ %":             round(cl_e/val_pv_e*100,2) if val_pv_e else 0,
                    f"NQH 31/12/{nam_prev}":nqh_pv_e,
                    f"NQH {nam_ht}":        nqh_ht_e,
                })
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                pd.DataFrame(rows_ex1).to_excel(w, index=False, sheet_name="Tổng hợp chỉ tiêu")
                pd.DataFrame(rows_ex2).to_excel(w, index=False, sheet_name="Theo chương trình")
            st.session_state[f"_bytes_cd{key_sfx}"] = buf.getvalue()
            st.session_state[f"_file_cd{key_sfx}"] = f"CanDoi_{nam_prev}_vs_{nam_ht}_{datetime.today().strftime('%d%m%Y')}.xlsx"

        if st.session_state.get(f"_bytes_cd{key_sfx}"):
            st.download_button("⬇ Tải Excel", data=st.session_state[f"_bytes_cd{key_sfx}"],
                file_name=st.session_state[f"_file_cd{key_sfx}"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_cd_excel{key_sfx}")
