"""
Tab Giao KHTD & Điều chỉnh KHTD — lũy kế đợt, Google Sheet, kv_store, duyệt tập trung.
"""
from __future__ import annotations

import socket
from datetime import datetime
import pandas as pd
import streamlit as st

import os

import db
from config import (
    CHUONG_TRINH_KHTD, COT_TEN_PGD, COT_TEN_XA, COT_TEN_CT,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_TONG_DU_NO,
    COT_MA_CHUONG_TRINH, COT_NGUON_VON,
    DON_VI_CHI_NHANH, DS_PGD, GQVL_MA_KEY_GIAO, PGD_XA_MAP,
    tim_ten_xa_trong_hstd,
    baseline_cache_loai, trang_thai_baseline_pgd,
)
from data.pgd import pgd_slug as _pgd_slug
from services import khtd_service
from services.khtd_service import LOAI_DIEU_CHINH, LOAI_GIAO
from utils import fmt_tien, fmt_so, hien_thi_dataframe_phan_trang, xuat_excel
from auth import la_phan_he_pgd, la_quan_ly_cn, normalize_role
from logger import get_logger
from tabs.base_tab import TabContext

logger = get_logger(__name__)

_SS = "khtd_gdc_"

_MAKEY_TO_MACT: dict[str, int] = {mk: mc for mk, mc, _, _, _ in CHUONG_TRINH_KHTD}

_CT_MAP: dict[str, str] = {mk: ten for mk, _, ten, _, _ in CHUONG_TRINH_KHTD}

_SHORT_CT: dict[str, str] = {
    "1_TW": "Hộ nghèo",       "2_TW": "HSSV",           "3_TW_NHCSXH": "GQVL HĐ",
    "3_TW_NSNN": "GQVL NS",  "4_TW": "XKLĐ",            "6_TW": "Nước sạch",
    "7_TW": "Nhà ở HN",       "9_TW": "Mới TN",          "10_TW": "SXKD KK",
    "12_TW": "Nhà ở XH",      "15_TW": "TN KK",          "17_TW": "DTTS 755",
    "19_TW": "Cận nghèo",     "21_TW": "DTTS 2085",      "25_TW": "Vùng DTTS",
    "26_TW": "Chấp hành án",  "99_TW": "Khác TW",
    "1_DP": "HN (ĐP)",        "2_DP": "SV (ĐP)",         "3_DP_TINH": "GQVL tỉnh",
    "3_DP_XA": "GQVL xã",    "6_DP": "NS ĐP",            "9_DP": "Mới TN ĐP",
    "10_DP": "SXKD KK ĐP",   "12_DP": "NOXH ĐP",        "15_DP": "TN KK ĐP",
    "17_DP": "DTTS 755 ĐP",  "19_DP": "Cận nghèo ĐP",   "21_DP": "DTTS 2085 ĐP",
    "25_DP": "Vùng DTTS ĐP", "26_DP": "Chấp hành ĐP",   "99_DP": "Khác ĐP",
}

_ROMAN = [
    "I","II","III","IV","V","VI","VII","VIII","IX","X",
    "XI","XII","XIII","XIV","XV","XVI","XVII","XVIII","XIX","XX","XXI","XXII",
]


def _ten_ngan(ma_key: str) -> str:
    return _SHORT_CT.get(ma_key, ma_key)


def _rows_to_long(rows: list[dict], nguon: str) -> pd.DataFrame:
    """Đưa dữ liệu giao KH về bảng dài, mỗi dòng là một xã × chương trình."""
    if not rows:
        return pd.DataFrame()
    kh_col = "KH giao TW (tr.đ)" if nguon == "TW" else "KH giao ĐP (tr.đ)"
    return pd.DataFrame(
        [
            {
                "Xã/phường": row["Xã"],
                "Chương trình": row["Chương trình"],
                "Mã CT": row["Mã CT"],
                "KH trước (triệu đồng)": row.get("KH trước (tr.đ)", 0.0),
                "Dư nợ TH (triệu đồng)": row.get("Dư nợ TH (tr.đ)", 0.0),
                "Tỷ lệ TH/KH": row.get("% TH/KH", 0.0),
                "KH giao (triệu đồng)": row.get(kh_col, 0.0),
            }
            for row in rows
        ]
    )


def _long_col_config(readonly: bool) -> dict:
    """Cấu hình bảng nhập dài; chỉ cột KH giao được phép sửa."""
    return {
        "Xã/phường": st.column_config.TextColumn(
            disabled=True, width="medium",
        ),
        "Chương trình": st.column_config.TextColumn(
            disabled=True, width="large",
        ),
        "Mã CT": None,
        "KH trước (triệu đồng)": st.column_config.NumberColumn(
            disabled=True, format="%.1f",
        ),
        "Dư nợ TH (triệu đồng)": st.column_config.NumberColumn(
            disabled=True, format="%.1f",
        ),
        "Tỷ lệ TH/KH": st.column_config.NumberColumn(
            disabled=True, format="%.1f%%",
        ),
        "KH giao (triệu đồng)": st.column_config.NumberColumn(
            disabled=readonly,
            format="%.1f",
            min_value=0.0,
            help="Nhập kế hoạch giao, đơn vị triệu đồng.",
        ),
    }


def _long_to_du_lieu(df_tw: pd.DataFrame, df_dp: pd.DataFrame) -> list[dict]:
    """Đổi hai bảng nhập dài về payload chuẩn của khtd_service.luu_dot()."""
    rows: list[dict] = []
    for nguon, df in (("TW", df_tw), ("DP", df_dp)):
        if df.empty:
            continue
        for _, row in df.iterrows():
            kh = float(row.get("KH giao (triệu đồng)", 0) or 0)
            rows.append(
                {
                    "xa": row.get("Xã/phường", ""),
                    "ma_key": row.get("Mã CT", ""),
                    "ten_ct": row.get("Chương trình", ""),
                    "nguon": nguon,
                    "kh_tw": kh if nguon == "TW" else 0.0,
                    "dc_tw": 0.0,
                    "kh_moi_tw": kh if nguon == "TW" else 0.0,
                    "kh_dp": kh if nguon == "DP" else 0.0,
                    "dc_dp": 0.0,
                    "kh_moi_dp": kh if nguon == "DP" else 0.0,
                    "ly_do": "",
                }
            )
    return rows


def _html_bdd_table(nam: int, thang: str, dot: str, nguon: str) -> str:
    """HTML pivot table dạng BĐD: hàng = PGD/xã phân cấp, cột = nhóm chương trình."""
    df_raw = khtd_service.tong_hop(nam, thang, dot)
    if df_raw.empty:
        return "<p style='color:var(--text-color);padding:12px'>⚠️ Chưa có dữ liệu KHTD cho đợt này.</p>"

    df = df_raw[df_raw["nguon"] == nguon].copy()
    if df.empty:
        return f"<p style='color:var(--text-color);padding:12px'>⚠️ Không có dữ liệu nguồn {nguon}.</p>"

    kh_c = "kh_tw" if nguon == "TW" else "kh_dp"
    dc_c = "dc_tw" if nguon == "TW" else "dc_dp"
    km_c = "kh_moi_tw" if nguon == "TW" else "kh_moi_dp"
    for c in (kh_c, dc_c, km_c):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0) / 1e6

    active_mk: list[str] = []
    mk_set: set[str] = set()
    for mk in df["ma_key"]:
        if mk not in mk_set:
            active_mk.append(mk)
            mk_set.add(mk)

    data: dict[tuple, tuple] = {
        (r["pgd_slug"], r.get("xa", ""), r["ma_key"]): (float(r[kh_c]), float(r[dc_c]), float(r[km_c]))
        for _, r in df.iterrows()
    }

    xas_per_pgd: dict[str, list[str]] = {}
    for pgd_slug, xa, _ in data.keys():
        xas_per_pgd.setdefault(pgd_slug, [])
        if xa and xa not in xas_per_pgd[pgd_slug]:
            xas_per_pgd[pgd_slug].append(xa)

    def fn(v: float) -> str:
        return "" if v == 0 else f"{v:,.1f}".replace(",", ".")

    def fdc(v: float) -> str:
        if v == 0:
            return ""
        s = f"{abs(v):,.1f}".replace(",", ".")
        return f"+{s}" if v > 0 else f"−{s}"

    td = "border:1px solid #e2e8f0;padding:3px 7px"
    th_hdr = "border:1px solid #1e40af;padding:5px 8px;background:rgba(30,64,175,0.85);color:#fff;text-align:center;font-size:11px;white-space:nowrap"
    th_sub = "border:1px solid #2563eb;padding:3px 6px;background:rgba(37,99,235,0.75);color:#fff;text-align:center;font-size:10px;white-space:nowrap"
    th_base = "border:1px solid #e2e8f0;padding:4px 8px;background:rgba(239,246,255,0.9);text-align:center;font-size:11px;font-weight:600;white-space:nowrap"

    html: list[str] = [
        "<div style='overflow-x:auto;font-size:12px;margin-top:8px'>",
        "<table style='border-collapse:collapse;white-space:nowrap'>",
        "<thead>",
        "<tr>",
        f'<th rowspan="2" style="{th_base}">STT</th>',
        f'<th rowspan="2" style="{th_base}">Tên đơn vị</th>',
    ]
    for mk in active_mk:
        html.append(f'<th colspan="3" style="{th_hdr}">{_ten_ngan(mk)}</th>')
    html += ["</tr>", "<tr>"]
    for _ in active_mk:
        html += [
            f'<th style="{th_sub}">KH đã giao</th>',
            f'<th style="{th_sub}">Điều chỉnh</th>',
            f'<th style="{th_sub}">KH năm {nam}</th>',
        ]
    html += ["</tr>", "</thead>", "<tbody>"]

    totals: dict[str, list[float]] = {mk: [0.0, 0.0, 0.0] for mk in active_mk}
    pgd_order = [("hoi_so", DON_VI_CHI_NHANH)] + [
        (_pgd_slug(p), p) for p in DS_PGD
    ]
    pgd_idx = 0

    for pgd_slug, pgd_name in pgd_order:
        if pgd_slug not in xas_per_pgd:
            continue
        pgd_idx += 1
        roman = _ROMAN[pgd_idx - 1] if pgd_idx <= len(_ROMAN) else str(pgd_idx)
        xas = xas_per_pgd[pgd_slug]

        html.append("<tr style='background:rgba(219,234,254,0.6);font-weight:700'>")
        html.append(f'<td style="{td};text-align:center">{roman}</td>')
        html.append(f'<td style="{td}">{pgd_name}</td>')
        for mk in active_mk:
            kh = sum(data.get((pgd_slug, xa, mk), (0, 0, 0))[0] for xa in xas)
            dc = sum(data.get((pgd_slug, xa, mk), (0, 0, 0))[1] for xa in xas)
            km = sum(data.get((pgd_slug, xa, mk), (0, 0, 0))[2] for xa in xas)
            totals[mk][0] += kh; totals[mk][1] += dc; totals[mk][2] += km
            cc = "#059669" if dc > 0 else ("#dc2626" if dc < 0 else "inherit")
            html += [
                f'<td style="{td};text-align:right">{fn(kh)}</td>',
                f'<td style="{td};text-align:right;color:{cc}">{fdc(dc)}</td>',
                f'<td style="{td};text-align:right">{fn(km)}</td>',
            ]
        html.append("</tr>")

        for stt_xa, xa in enumerate(xas, 1):
            html.append("<tr>")
            html.append(f'<td style="{td};text-align:center;opacity:.5">{stt_xa}</td>')
            html.append(f'<td style="{td};padding-left:20px">{xa}</td>')
            for mk in active_mk:
                kh, dc, km = data.get((pgd_slug, xa, mk), (0, 0, 0))
                cc = "#059669" if dc > 0 else ("#dc2626" if dc < 0 else "inherit")
                html += [
                    f'<td style="{td};text-align:right">{fn(kh)}</td>',
                    f'<td style="{td};text-align:right;color:{cc}">{fdc(dc)}</td>',
                    f'<td style="{td};text-align:right">{fn(km)}</td>',
                ]
            html.append("</tr>")

    html.append("<tr style='background:rgba(240,253,244,0.8);font-weight:700'>")
    html.append(f'<td style="{td}" colspan="2">Tổng cộng</td>')
    for mk in active_mk:
        kh, dc, km = totals[mk]
        cc = "#059669" if dc > 0 else ("#dc2626" if dc < 0 else "inherit")
        html += [
            f'<td style="{td};text-align:right">{fn(kh)}</td>',
            f'<td style="{td};text-align:right;color:{cc}">{fdc(dc)}</td>',
            f'<td style="{td};text-align:right">{fn(km)}</td>',
        ]
    html += [
        "</tr>", "</tbody>", "</table>",
        "<p style='font-size:11px;margin-top:4px;color:var(--text-color)'>Đơn vị: triệu đồng</p>",
        "</div>",
    ]
    return "\n".join(html)


def _hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "unknown"


def _slug_to_ten(slug: str) -> str:
    if slug == "hoi_so":
        return DON_VI_CHI_NHANH
    for ten in DS_PGD:
        if _pgd_slug(ten) == slug:
            return ten
    return slug


def _ds_slug_label() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for s in khtd_service.ds_slug():
        out.append((_slug_to_ten(s), s))
    return out


def _doc_kv_dot(
    pgd_slug_s: str, nam: int | str, thang: str, dot: str
) -> dict | None:
    key = khtd_service.kv_key_dot(pgd_slug_s, nam, thang, dot)
    raw = db.doc_kv(key)
    return raw if isinstance(raw, dict) else None


def _badge_trang_thai(raw: dict | None) -> str:
    if not raw or not raw.get("du_lieu"):
        return "⬜ Chưa tải"
    tt = raw.get("trang_thai") or "cho_duyet"
    if tt == "cho_duyet":
        return "🔵 Chờ duyệt"
    if tt == "da_duyet":
        return "🟢 Đã duyệt"
    if tt == "tu_choi":
        return "🔴 Từ chối"
    return "🔵 Chờ duyệt"


def _chon_dot() -> tuple[int, str, str]:
    with st.container(border=True):
        st.caption("📅 Chọn đợt làm việc")
        c1, c2, c3 = st.columns(3)
        with c1:
            nam = int(
                st.number_input(
                    "Năm",
                    min_value=2000,
                    max_value=2100,
                    value=int(st.session_state.get(_SS + "nam", 2026)),
                    key=_SS + "nam",
                )
            )
        with c2:
            thang_opts = [f"{i:02d}" for i in range(1, 13)]
            default_th = str(st.session_state.get(_SS + "thang", "01")).zfill(2)
            idx = (
                thang_opts.index(default_th)
                if default_th in thang_opts
                else 0
            )
            thang = st.selectbox(
                "Tháng",
                thang_opts,
                index=idx,
                key=_SS + "thang",
            )
        with c3:
            dot = st.text_input(
                "Số đợt",
                value=st.session_state.get(_SS + "dot", "Dot1"),
                key=_SS + "dot",
                help="Ví dụ: Dot1, Dot2…",
            )
    return nam, thang, dot


def _bang_chi_tiet_pgd(slug: str, nam: int, thang: str, dot: str) -> pd.DataFrame:
    raw = db.doc_kv(khtd_service.kv_key_dot(slug, nam, thang, dot))
    if not raw or not raw.get("du_lieu"):
        return pd.DataFrame(
            columns=[
                "Xã",
                "Chương trình",
                "Mã CT",
                "KH đã giao TW",
                "ĐC TW",
                "KH mới TW",
                "KH đã giao ĐP",
                "ĐC ĐP",
                "KH mới ĐP",
                "Lý do",
            ]
        )
    loai_dot = raw.get("loai")
    rows: list[dict] = []
    for r in raw["du_lieu"]:
        if not isinstance(r, dict):
            continue
        rows.append(
            {
                "Xã": r.get("xa", ""),
                "Chương trình": r.get("ten_ct", ""),
                "Mã CT": r.get("ma_key", ""),
                "KH đã giao TW": r.get("kh_tw", 0),
                "ĐC TW": r.get("dc_tw", 0),
                "KH mới TW": r.get("kh_moi_tw", 0),
                "KH đã giao ĐP": r.get("kh_dp", 0),
                "ĐC ĐP": r.get("dc_dp", 0),
                "KH mới ĐP": r.get("kh_moi_dp", 0),
                "Lý do": r.get("ly_do", ""),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    disp = df.copy()
    money_cols = [
        "KH đã giao TW",
        "ĐC TW",
        "KH mới TW",
        "KH đã giao ĐP",
        "ĐC ĐP",
        "KH mới ĐP",
    ]
    for c in money_cols:
        if c in disp.columns:
            disp[c] = disp[c].map(fmt_tien)
    if loai_dot == LOAI_GIAO:
        drop_c = ["ĐC TW", "ĐC ĐP", "Lý do"]
        disp = disp.drop(columns=[c for c in drop_c if c in disp.columns])
    return disp


def _section_a(
    username: str, nam: int, thang: str, dot: str, df_hstd: pd.DataFrame | None
) -> None:
    _ = df_hstd
    nam_baseline = nam - 1
    cache_path = baseline_cache_loai(nam_baseline, "hstd")
    co_cache = os.path.exists(cache_path)

    # Đếm file per-PGD đã upload (chỉ khi chưa có cache để tránh I/O thừa)
    so_co_file = 0
    if not co_cache:
        tt = trang_thai_baseline_pgd(nam_baseline)
        so_co_file = sum(1 for v in tt.values() if v)

    # ── Nguồn dữ liệu HSTD 31/12 ──────────────────────────────────────────────
    with st.expander(
        "📂 Dữ liệu HSTD 31/12 (dùng cho đợt đầu năm)",
        expanded=not co_cache,
    ):
        if co_cache:
            st.success(
                f"✅ Đã có cache baseline HSTD 31/12/{nam_baseline} — "
                "không cần upload lại."
            )
            st.caption(
                "Dữ liệu được tổng hợp từ mục **Upload → Mốc 31/12**. "
                "Nhấn **Khởi tạo đợt đầu năm** bên dưới để tiếp tục."
            )
        else:
            if so_co_file > 0:
                st.warning(
                    f"⚠️ Có {so_co_file}/22 đơn vị đã upload file HSTD 31/12/{nam_baseline} "
                    "nhưng chưa tổng hợp cache."
                )
                st.caption(
                    "Vào **Tab Upload → Mốc 31/12** → nhấn **Tổng hợp baseline** "
                    "để tạo cache, sau đó quay lại đây."
                )
                st.divider()
            st.caption(
                "Hoặc upload thủ công file HSTD xuất tại ngày 31/12 năm trước "
                "để dùng ngay trong phiên này."
            )
            f_up = st.file_uploader(
                "Chọn file HSTD 31/12",
                type=["xlsx", "xls"],
                key=_SS + "hstd_upload",
            )
            if f_up:
                try:
                    df_31_12 = pd.read_excel(f_up)
                    st.session_state["khtd_df_hstd_31_12"] = df_31_12
                    st.success(
                        f"✅ Đã tải {len(df_31_12):,} dòng từ file HSTD 31/12"
                    )
                    db.ghi_audit(
                        username,
                        "upload_khtd_hstd_3112",
                        f"[{_hostname()}] session · {len(df_31_12)} dòng",
                    )
                except Exception as e:
                    logger.error("Không đọc được file HSTD 31/12: %s", e, exc_info=True)
                    db.ghi_audit(
                        username,
                        "upload_khtd_hstd_3112_loi",
                        f"[{_hostname()}] {e}",
                    )
                    st.error(f"❌ Không đọc được file: {e}")

    # ── Khởi tạo đợt đầu năm ──────────────────────────────────────────────────
    with st.expander("🚀 Khởi tạo đợt đầu năm", expanded=False):
        # Xác định nguồn: cache disk > session state
        if co_cache:
            parquet_to_use: str | None = cache_path
            df_to_use: pd.DataFrame | None = None
            st.info(
                f"Nguồn: cache baseline HSTD 31/12/{nam_baseline}  \n"
                f"Sẽ khởi tạo đợt giao đầu năm **{nam}** cho 22 đơn vị."
            )
        else:
            parquet_to_use = None
            df_to_use = st.session_state.get("khtd_df_hstd_31_12")
            if df_to_use is None:
                st.warning(
                    "⚠️ Chưa có dữ liệu HSTD 31/12. "
                    "Tổng hợp baseline trong Tab Upload hoặc upload thủ công ở mục trên."
                )
                return
            st.info(
                f"Nguồn: file upload phiên này ({len(df_to_use):,} dòng)  \n"
                f"Sẽ khởi tạo đợt giao đầu năm **{nam}** cho 22 đơn vị."
            )

        if st.button(
            f"🚀 Khởi tạo đợt giao {nam}_01_Dot1",
            key=_SS + "btn_khoi_tao",
        ):
            with st.spinner("Đang khởi tạo…"):
                ket_qua = khtd_service.tao_dot_giao_dau_nam(
                    nam, username, df_to_use, parquet_path=parquet_to_use
                )
            rows = [
                {
                    "Đơn vị": _slug_to_ten(s),
                    "Kết quả": (
                        "✅ ok"
                        if kq.thanh_cong
                        else f"❌ {kq.thong_bao[:100]}"
                    ),
                }
                for s, kq in ket_qua.items()
            ]
            hien_thi_dataframe_phan_trang(
                pd.DataFrame(rows), key=_SS + "khoi_tao_result"
            )
            db.ghi_audit(
                username,
                "khoi_tao_dot_giao_dau_nam",
                f"[{_hostname()}] nam={nam} · nguon={'cache' if co_cache else 'session'} · {len(ket_qua)} đơn vị",
            )

    loai_hien_tai = st.session_state.get(_SS + "loai", LOAI_DIEU_CHINH)
    if loai_hien_tai == LOAI_DIEU_CHINH:
        with st.expander("⬆️ Push KH lên GSheet", expanded=False):
            st.caption(
                "Điền KH kỳ trước vào cột F/I của GSheet "
                "trước khi PGD nhập điều chỉnh."
            )
            ds = _ds_slug_label()
            labels = [x[0] for x in ds]
            slugs = [x[1] for x in ds]
            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    "⬆️ Push tất cả 22 đơn vị",
                    key=_SS + "btn_push_all",
                ):
                    with st.spinner("Đang push…"):
                        for slug in slugs:
                            khtd_service.push_kh_len_sheet(
                                slug, nam, thang, dot, username
                            )
                    st.success("✅ Đã push KH lên GSheet cho tất cả.")
                    db.ghi_audit(
                        username,
                        "push_khtd_sheet_tat_ca",
                        f"[{_hostname()}] {nam}/{thang}/{dot}",
                    )
            with c2:
                idx = st.selectbox(
                    "Push riêng 1 đơn vị",
                    range(len(labels)),
                    format_func=lambda i: labels[i],
                    key=_SS + "sel_push_mot",
                )
                if st.button("⬆️ Push 1 đơn vị", key=_SS + "btn_push_mot"):
                    kq = khtd_service.push_kh_len_sheet(
                        slugs[idx], nam, thang, dot, username
                    )
                    kq.hien_thi()

        with st.expander("⬇️ Tải từ Google Sheet", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                if st.button(
                    "⬇️ Tải tất cả 22 đơn vị",
                    key=_SS + "btn_tai_all",
                ):
                    with st.spinner("Đang tải…"):
                        ket = khtd_service.tai_tat_ca(
                            nam, thang, dot, username
                        )
                    df_k = pd.DataFrame(
                        [
                            {
                                "PGD": _slug_to_ten(s),
                                "Trạng thái": (
                                    "✅ ok" if v == "ok" else "⚠️ Cần xem"
                                ),
                                "Ghi chú": v,
                            }
                            for s, v in ket.items()
                        ]
                    )
                    hien_thi_dataframe_phan_trang(
                        df_k, key=_SS + "tai_all_status"
                    )
            with c2:
                ds = _ds_slug_label()
                labels = [x[0] for x in ds]
                slugs = [x[1] for x in ds]
                idx = st.selectbox(
                    "Tải riêng 1 đơn vị",
                    range(len(labels)),
                    format_func=lambda i: labels[i],
                    key=_SS + "sel_tai_mot",
                )
                if st.button("⬇️ Tải riêng", key=_SS + "btn_tai_mot"):
                    kq = khtd_service.tai_va_luu_pgd(
                        slugs[idx], nam, thang, dot, username
                    )
                    kq.hien_thi()


def _build_du_no_map(
    df_hstd: pd.DataFrame | None, ten_pgd: str
) -> dict[tuple[str, int, int], float]:
    """Trả về {(xa, ma_ct_int, nguon_int): du_no_trieu} = TH + QH + Khoanh.

    Join theo mã số CT + nguồn vốn số (1=TW, 2=ĐP) — stable, không phụ thuộc
    chuỗi tên chương trình (tránh mismatch TW vs ĐP, tên hiển thị khác tên HSTD).
    Dùng COT_TONG_DU_NO (validated = TH+QH+Khoanh khi upload).
    """
    if df_hstd is None or df_hstd.empty:
        return {}
    required = (COT_TEN_PGD, COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON)
    if not all(c in df_hstd.columns for c in required):
        return {}
    df_pgd = df_hstd[df_hstd[COT_TEN_PGD] == ten_pgd].copy()
    if df_pgd.empty:
        return {}

    # Chuẩn hóa mã CT → int, nguồn vốn → int (1=TW, 2=ĐP)
    df_pgd["_ma_ct"] = (
        pd.to_numeric(df_pgd[COT_MA_CHUONG_TRINH], errors="coerce").fillna(-1).astype(int)
    )
    df_pgd["_nguon"] = (
        pd.to_numeric(df_pgd[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)
    )

    if COT_TONG_DU_NO in df_pgd.columns:
        df_pgd["_dn"] = pd.to_numeric(df_pgd[COT_TONG_DU_NO], errors="coerce").fillna(0)
    else:
        cols = [c for c in (COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH) if c in df_pgd.columns]
        for c in cols:
            df_pgd[c] = pd.to_numeric(df_pgd[c], errors="coerce").fillna(0)
        df_pgd["_dn"] = df_pgd[cols].sum(axis=1)

    # PGD_XA_MAP lưu tên đầy đủ ("Xã ...", "Phường ..."), trong khi HSTD
    # thường bỏ tiền tố hành chính. Chuẩn hóa cùng một khóa trước khi group/lookup.
    df_pgd["_xa_key"] = df_pgd[COT_TEN_XA].map(
        lambda value: tim_ten_xa_trong_hstd(str(value).strip()).casefold()
        if pd.notna(value)
        else ""
    )
    agg = df_pgd.groupby(["_xa_key", "_ma_ct", "_nguon"])["_dn"].sum().reset_index()
    return {
        (row["_xa_key"], int(row["_ma_ct"]), int(row["_nguon"])): row["_dn"] / 1e6
        for _, row in agg.iterrows()
    }


def _section_b_giao(
    nam: int, thang: str, dot: str, role: str, username: str,
    df_hstd: pd.DataFrame | None = None,
) -> None:
    ds = _ds_slug_label()
    labels = [x[0] for x in ds]
    slugs = [x[1] for x in ds]
    j = st.selectbox(
        "Chọn đơn vị",
        range(len(labels)),
        format_func=lambda i: labels[i],
        key=_SS + "sel_giao_pgd",
    )
    slug_chon = slugs[j]
    ten_chon = labels[j]

    kh_truoc = khtd_service.lay_kh_dot_truoc(slug_chon, nam, thang, dot)
    ds_xa = PGD_XA_MAP.get(ten_chon, [])
    if not ds_xa:
        st.warning(f"⚠️ {ten_chon} chưa có danh sách xã trong cấu hình. Liên hệ Admin.")
        return

    # Tiến độ nhập per-xã
    tt_xa = khtd_service.trang_thai_xa(slug_chon, nam, thang, dot)
    so_da_nhap = sum(1 for v in tt_xa.values() if v)
    st.caption(f"📊 Tiến độ nhập KH: **{so_da_nhap}/{len(ds_xa)}** xã")

    # Chọn xã để nhập
    xa_chon_idx = st.selectbox(
        "Chọn xã/phường để nhập KH",
        range(len(ds_xa)),
        format_func=lambda i: (
            f"{'✅' if tt_xa.get(ds_xa[i]) else '⬜'} {ds_xa[i]}"
        ),
        key=_SS + f"sel_xa_{slug_chon}",
    )
    xa_chon = ds_xa[xa_chon_idx]
    xa_key_widget = _pgd_slug(xa_chon)

    du_no_map = _build_du_no_map(df_hstd, ten_chon)

    rows_nhap: list[dict] = []
    for xa in [xa_chon]:
        for ma_key, _ma_ct, ten_ct, nguon, _ in CHUONG_TRINH_KHTD:
            if ma_key.startswith("3_") and ma_key not in GQVL_MA_KEY_GIAO:
                continue
            kh_prev = kh_truoc.get(ma_key, {})
            kh_prev_trieu = (
                kh_prev.get("kh_moi_tw", 0) / 1e6
                if nguon == "TW"
                else kh_prev.get("kh_moi_dp", 0) / 1e6
            )
            nguon_int = 1 if nguon == "TW" else 2
            xa_key = tim_ten_xa_trong_hstd(str(xa).strip()).casefold()
            du_no_trieu = du_no_map.get((xa_key, int(_ma_ct), nguon_int), 0.0)
            pct_th = (
                round(du_no_trieu / kh_prev_trieu * 100, 1)
                if kh_prev_trieu
                else 0.0
            )
            rows_nhap.append(
                {
                    "Xã": xa,
                    "Chương trình": ten_ct,
                    "Mã CT": ma_key,
                    "Nguồn": nguon,
                    "KH trước (tr.đ)": round(kh_prev_trieu, 1),
                    "Dư nợ TH (tr.đ)": round(du_no_trieu, 1),
                    "% TH/KH": pct_th,
                    "KH giao TW (tr.đ)": 0.0,
                    "KH giao ĐP (tr.đ)": 0.0,
                }
            )

    rows_tw = [r for r in rows_nhap if r["Nguồn"] == "TW"]
    rows_dp = [r for r in rows_nhap if r["Nguồn"] == "DP"]
    df_long_tw = _rows_to_long(rows_tw, "TW")
    df_long_dp = _rows_to_long(rows_dp, "DP")

    readonly = normalize_role(role) == "executive"

    tab_tw, tab_dp = st.tabs(["🏦 Nguồn TW", "🏙️ Nguồn ĐP"])
    df_edited_tw = df_long_tw.copy()
    df_edited_dp = df_long_dp.copy()

    if not readonly:
        with tab_tw:
            st.caption(f"Nhập KH cho **{xa_chon}** · Đơn vị: triệu đồng")
            if not df_long_tw.empty:
                df_edited_tw = st.data_editor(
                    df_long_tw,
                    column_config=_long_col_config(readonly=False),
                    key=_SS + f"editor_tw_{slug_chon}_{xa_key_widget}",
                    hide_index=True,
                    disabled=[
                        "Xã/phường", "Chương trình", "Mã CT",
                        "KH trước (triệu đồng)", "Dư nợ TH (triệu đồng)",
                        "Tỷ lệ TH/KH",
                    ],
                    column_order=[
                        "Xã/phường", "Chương trình",
                        "KH trước (triệu đồng)", "Dư nợ TH (triệu đồng)",
                        "Tỷ lệ TH/KH", "KH giao (triệu đồng)",
                    ],
                    use_container_width=True,
                    height=520,
                )
            else:
                st.info("Không có chương trình TW.")
        with tab_dp:
            st.caption(f"Nhập KH cho **{xa_chon}** · Đơn vị: triệu đồng")
            if not df_long_dp.empty:
                df_edited_dp = st.data_editor(
                    df_long_dp,
                    column_config=_long_col_config(readonly=False),
                    key=_SS + f"editor_dp_{slug_chon}_{xa_key_widget}",
                    hide_index=True,
                    disabled=[
                        "Xã/phường", "Chương trình", "Mã CT",
                        "KH trước (triệu đồng)", "Dư nợ TH (triệu đồng)",
                        "Tỷ lệ TH/KH",
                    ],
                    column_order=[
                        "Xã/phường", "Chương trình",
                        "KH trước (triệu đồng)", "Dư nợ TH (triệu đồng)",
                        "Tỷ lệ TH/KH", "KH giao (triệu đồng)",
                    ],
                    use_container_width=True,
                    height=520,
                )
            else:
                st.info("Không có chương trình ĐP.")
    else:
        with tab_tw:
            if not df_long_tw.empty:
                hien_thi_dataframe_phan_trang(df_long_tw, key=_SS + "view_tw")
            else:
                st.info("Không có chương trình TW.")
        with tab_dp:
            if not df_long_dp.empty:
                hien_thi_dataframe_phan_trang(df_long_dp, key=_SS + "view_dp")
            else:
                st.info("Không có chương trình ĐP.")
        st.caption("*(Chế độ xem — không thực hiện nhập.)*")
        return

    kh_col = "KH giao (triệu đồng)"
    tong_tw = float(pd.to_numeric(df_edited_tw.get(kh_col), errors="coerce").fillna(0).sum()) if kh_col in df_edited_tw else 0.0
    tong_dp = float(pd.to_numeric(df_edited_dp.get(kh_col), errors="coerce").fillna(0).sum()) if kh_col in df_edited_dp else 0.0
    c1, c2 = st.columns(2)
    c1.metric("Tổng KH giao TW (triệu đồng)", f"{tong_tw:,.0f}".replace(",", "."))
    c2.metric("Tổng KH giao ĐP (triệu đồng)", f"{tong_dp:,.0f}".replace(",", "."))

    if st.button(
        f"💾 Lưu KH giao — {xa_chon} ({ten_chon})",
        key=_SS + f"btn_luu_giao_{slug_chon}_{xa_key_widget}",
        type="primary",
    ):
        du_lieu = _long_to_du_lieu(df_edited_tw, df_edited_dp)
        kq = khtd_service.luu_dot_xa(
            slug_chon, xa_chon, nam, thang, dot, LOAI_GIAO, du_lieu, username,
        )
        kq.hien_thi()
        if kq.thanh_cong:
            st.cache_data.clear()


def _section_c_tong_hop(nam: int, thang: str, dot: str) -> None:
    c_tw, c_dp = st.tabs(["🏦 Tổng hợp TW", "🏙️ Tổng hợp ĐP"])
    with c_tw:
        st.html(_html_bdd_table(nam, thang, dot, "TW"))
    with c_dp:
        st.html(_html_bdd_table(nam, thang, dot, "DP"))
    st.caption(
        "ℹ️ Tổng KH không bao gồm các chương trình chỉ thu hồi, không giao kế hoạch: "
        "mã 24 — Cơ sở giáo dục mầm non, tiểu học ngoài công lập; "
        "mã 7 nguồn ĐP — Hộ nghèo về nhà ở. Vì vậy Tổng KH có thể thấp hơn dư nợ thực hiện."
    )

    df_raw = khtd_service.tong_hop(nam, thang, dot)
    if not df_raw.empty:
        st.divider()
        df_x = df_raw.copy()
        df_x = df_x.rename(
            columns={
                "kh_tw": "KH đã giao TW",
                "dc_tw": "Tăng/Giảm TW",
                "kh_moi_tw": f"KH TH năm {nam} (TW)",
                "kh_dp": "KH đã giao ĐP",
                "dc_dp": "Tăng/Giảm ĐP",
                "kh_moi_dp": f"KH TH năm {nam} (ĐP)",
            }
        )
        for c in [
            "KH đã giao TW",
            "Tăng/Giảm TW",
            f"KH TH năm {nam} (TW)",
            "KH đã giao ĐP",
            "Tăng/Giảm ĐP",
            f"KH TH năm {nam} (ĐP)",
        ]:
            if c in df_x.columns:
                df_x[c] = df_x[c].map(fmt_tien)
        if st.button("📥 Tạo Excel tổng hợp", key=_SS + "btn_gen_xlsx"):
            try:
                st.session_state[_SS + "xls_bytes"] = xuat_excel(
                    {f"KHTD_{nam}_{thang}_{dot}": df_x}
                )
                st.session_state[_SS + "xls_fname"] = (
                    f"KHTD_{nam}_{thang}_{dot}_"
                    f"{datetime.now().strftime('%Y%m%d')}.xlsx"
                )
            except Exception as e:
                logger.error("tab_khtd_giao_dc xuat_excel: %s", e, exc_info=True)
                st.error(f"❌ Lỗi xuất Excel: {e}")
        if st.session_state.get(_SS + "xls_bytes"):
            st.download_button(
                "📥 Tải Excel tổng hợp",
                data=st.session_state[_SS + "xls_bytes"],
                file_name=st.session_state.get(_SS + "xls_fname", "KHTD.xlsx"),
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                key=_SS + "dl_xlsx",
            )


def _section_d_user(
    pgd_user: str | None, nam: int, thang: str, dot: str
) -> None:
    st.markdown("#### D — Trạng thái PGD của tôi")
    if not pgd_user:
        st.warning("Không xác định được PGD. Liên hệ Admin.")
        return
    slug = _pgd_slug(pgd_user)
    raw = db.doc_kv(khtd_service.kv_key_dot(slug, nam, thang, dot))
    loai = raw.get("loai", "") if raw else ""
    st.markdown(f"**Đơn vị:** {pgd_user}")
    st.markdown(
        "**Loại đợt:** "
        f"{'📋 Giao' if loai == LOAI_GIAO else '📉 Điều chỉnh'}"
    )
    st.markdown(f"**Trạng thái:** {_badge_trang_thai(raw)}")
    if raw and raw.get("trang_thai") == "tu_choi":
        st.error(
            f"Ý kiến từ chối: {raw.get('y_kien_duyet', '—')} "
            f"— {raw.get('nguoi_duyet', '')} "
            f"· {raw.get('thoi_gian_duyet', '')}"
        )
    hien_thi_dataframe_phan_trang(
        _bang_chi_tiet_pgd(slug, nam, thang, dot),
        key=_SS + "chi_tiet_user",
        height=400,
    )


def _tinh_so_sanh_kh_th(
    nam: int, thang: str, dot: str, df_hstd: pd.DataFrame | None
) -> pd.DataFrame:
    """Trả về DataFrame so sánh KH vs TH theo (PGD, mã CT, nguồn), đơn vị triệu đồng."""
    df_kh_raw = khtd_service.tong_hop(nam, thang, dot)
    if df_kh_raw.empty:
        return pd.DataFrame()

    df_kh_raw = df_kh_raw.copy()
    df_kh_raw["ten_pgd"] = df_kh_raw["pgd_slug"].apply(_slug_to_ten)
    df_kh_raw["ma_ct"] = df_kh_raw["ma_key"].map(_MAKEY_TO_MACT).fillna(-1).astype(int)
    for c in ("kh_moi_tw", "kh_moi_dp"):
        df_kh_raw[c] = pd.to_numeric(df_kh_raw[c], errors="coerce").fillna(0)

    kh_grp = (
        df_kh_raw.groupby(["ten_pgd", "ma_ct", "nguon"], as_index=False)
        .agg(ten_ct=("ten_ct", "first"), kh_tw=("kh_moi_tw", "sum"), kh_dp=("kh_moi_dp", "sum"))
    )
    kh_grp["kh_tw"] = kh_grp["kh_tw"] / 1e6
    kh_grp["kh_dp"] = kh_grp["kh_dp"] / 1e6

    th_map: dict = {}
    if df_hstd is not None and not df_hstd.empty:
        req = (COT_TEN_PGD, COT_MA_CHUONG_TRINH, COT_NGUON_VON)
        if all(c in df_hstd.columns for c in req):
            dh = df_hstd.copy()
            dh["_mc"] = pd.to_numeric(dh[COT_MA_CHUONG_TRINH], errors="coerce").fillna(-1).astype(int)
            dh["_nv"] = pd.to_numeric(dh[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)
            if COT_TONG_DU_NO in dh.columns:
                dh["_dn"] = pd.to_numeric(dh[COT_TONG_DU_NO], errors="coerce").fillna(0)
            else:
                cols_dn = [c for c in (COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH) if c in dh.columns]
                for c in cols_dn:
                    dh[c] = pd.to_numeric(dh[c], errors="coerce").fillna(0)
                dh["_dn"] = dh[cols_dn].sum(axis=1)
            agg = dh.groupby([COT_TEN_PGD, "_mc", "_nv"])["_dn"].sum().reset_index()
            th_map = {
                (r[COT_TEN_PGD], int(r["_mc"]), int(r["_nv"])): r["_dn"] / 1e6
                for _, r in agg.iterrows()
            }

    rows = []
    for _, r in kh_grp.iterrows():
        nguon_int = 1 if r["nguon"] == "TW" else 2
        kh = float(r["kh_tw"] if r["nguon"] == "TW" else r["kh_dp"])
        th = th_map.get((r["ten_pgd"], int(r["ma_ct"]), nguon_int), 0.0)
        cl = th - kh
        pct = round(th / kh * 100, 1) if kh else 0.0
        rows.append({
            "PGD": r["ten_pgd"],
            "Mã CT": int(r["ma_ct"]) if int(r["ma_ct"]) >= 0 else "?",
            "Chương trình": r["ten_ct"] or "",
            "Nguồn": r["nguon"],
            "KH (triệu đ)": round(kh, 1),
            "TH (triệu đ)": round(th, 1),
            "Chênh lệch": round(cl, 1),
            "% TH/KH": pct,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _tinh_so_sanh_kh_th_xa(
    nam: int, thang: str, dot: str, df_hstd: pd.DataFrame | None
) -> pd.DataFrame:
    """So sánh KH vs TH theo (PGD, xã, mã CT, nguồn), đơn vị triệu đồng."""
    df_kh_raw = khtd_service.tong_hop(nam, thang, dot)
    if df_kh_raw.empty or "xa" not in df_kh_raw.columns:
        return pd.DataFrame()

    df_kh_raw = df_kh_raw.copy()
    df_kh_raw["ten_pgd"] = df_kh_raw["pgd_slug"].apply(_slug_to_ten)
    df_kh_raw["ma_ct"] = df_kh_raw["ma_key"].map(_MAKEY_TO_MACT).fillna(-1).astype(int)
    for c in ("kh_moi_tw", "kh_moi_dp"):
        df_kh_raw[c] = pd.to_numeric(df_kh_raw[c], errors="coerce").fillna(0)

    kh_grp = (
        df_kh_raw.groupby(["ten_pgd", "xa", "ma_ct", "nguon"], as_index=False)
        .agg(ten_ct=("ten_ct", "first"), kh_tw=("kh_moi_tw", "sum"), kh_dp=("kh_moi_dp", "sum"))
    )
    kh_grp["kh_tw"] = kh_grp["kh_tw"] / 1e6
    kh_grp["kh_dp"] = kh_grp["kh_dp"] / 1e6

    th_map: dict = {}
    if df_hstd is not None and not df_hstd.empty:
        req = (COT_TEN_PGD, COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON)
        if all(c in df_hstd.columns for c in req):
            dh = df_hstd.copy()
            dh["_mc"] = pd.to_numeric(dh[COT_MA_CHUONG_TRINH], errors="coerce").fillna(-1).astype(int)
            dh["_nv"] = pd.to_numeric(dh[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)
            if COT_TONG_DU_NO in dh.columns:
                dh["_dn"] = pd.to_numeric(dh[COT_TONG_DU_NO], errors="coerce").fillna(0)
            else:
                cols_dn = [c for c in (COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH) if c in dh.columns]
                for c in cols_dn:
                    dh[c] = pd.to_numeric(dh[c], errors="coerce").fillna(0)
                dh["_dn"] = dh[cols_dn].sum(axis=1)
            agg = dh.groupby([COT_TEN_PGD, COT_TEN_XA, "_mc", "_nv"])["_dn"].sum().reset_index()
            th_map = {
                (r[COT_TEN_PGD], r[COT_TEN_XA], int(r["_mc"]), int(r["_nv"])): r["_dn"] / 1e6
                for _, r in agg.iterrows()
            }

    rows = []
    for _, r in kh_grp.iterrows():
        nguon_int = 1 if r["nguon"] == "TW" else 2
        kh = float(r["kh_tw"] if r["nguon"] == "TW" else r["kh_dp"])
        th = th_map.get((r["ten_pgd"], r["xa"], int(r["ma_ct"]), nguon_int), 0.0)
        cl = th - kh
        pct = round(th / kh * 100, 1) if kh else 0.0
        rows.append({
            "PGD": r["ten_pgd"],
            "Xã": r["xa"],
            "Mã CT": int(r["ma_ct"]) if int(r["ma_ct"]) >= 0 else "?",
            "Chương trình": r["ten_ct"] or "",
            "Nguồn": r["nguon"],
            "KH (triệu đ)": round(kh, 1),
            "TH (triệu đ)": round(th, 1),
            "Chênh lệch": round(cl, 1),
            "% TH/KH": pct,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _dinh_dang_so_sanh(df: pd.DataFrame) -> pd.DataFrame:
    """Chuyển cột số → string theo quy ước VN trước khi hiển thị."""
    disp = df.copy()
    for c in ("KH (triệu đ)", "TH (triệu đ)", "Chênh lệch"):
        if c in disp.columns:
            disp[c] = disp[c].apply(
                lambda x: f"{round(x):,}".replace(",", ".") if pd.notna(x) else "0"
            )
    if "% TH/KH" in disp.columns:
        disp["% TH/KH"] = disp["% TH/KH"].apply(
            lambda x: f"{x:.1f}".replace(".", ",") + "%" if pd.notna(x) else "0%"
        )
    return disp


def _section_e_so_sanh_kh_th(
    nam: int, thang: str, dot: str, df_hstd: pd.DataFrame | None
) -> None:
    if df_hstd is None or df_hstd.empty:
        st.info("ℹ️ Chưa có dữ liệu HSTD — cột Thực hiện sẽ = 0.")

    try:
        df = _tinh_so_sanh_kh_th(nam, thang, dot, df_hstd)
    except Exception as e:
        logger.error("_section_e_so_sanh_kh_th: %s", e, exc_info=True)
        st.error(f"❌ Lỗi tính toán: {e}")
        return

    if df.empty:
        st.warning("⚠️ Chưa có dữ liệu KHTD đã giao cho đợt này.")
        return

    df_tw = df[df["Nguồn"] == "TW"]
    df_dp = df[df["Nguồn"] == "DP"]
    tong_kh_tw = df_tw["KH (triệu đ)"].sum()
    tong_th_tw = df_tw["TH (triệu đ)"].sum()
    tong_kh_dp = df_dp["KH (triệu đ)"].sum()
    tong_th_dp = df_dp["TH (triệu đ)"].sum()
    pct_tw = round(tong_th_tw / tong_kh_tw * 100, 1) if tong_kh_tw else 0.0
    pct_dp = round(tong_th_dp / tong_kh_dp * 100, 1) if tong_kh_dp else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("KH Trung ương (triệu đ)", f"{round(tong_kh_tw):,}".replace(",", "."))
    c2.metric("TH Trung ương (triệu đ)", f"{round(tong_th_tw):,}".replace(",", "."), delta=f"{pct_tw:.1f}%".replace(".", ","))
    c3.metric("KH Địa phương (triệu đ)", f"{round(tong_kh_dp):,}".replace(",", "."))
    c4.metric("TH Địa phương (triệu đ)", f"{round(tong_th_dp):,}".replace(",", "."), delta=f"{pct_dp:.1f}%".replace(".", ","))

    xem = st.radio(
        "Xem theo",
        ["🏢 Tổng hợp Chi nhánh", "📍 Chi tiết PGD", "📋 Danh sách xã theo PGD"],
        horizontal=True,
        key=_SS + "ss_xem",
    )

    ds = _ds_slug_label()
    labels = [x[0] for x in ds]

    if "Tổng hợp" in xem:
        df_cn = (
            df.groupby(["Mã CT", "Chương trình", "Nguồn"], as_index=False)
            .agg({"KH (triệu đ)": "sum", "TH (triệu đ)": "sum", "Chênh lệch": "sum"})
        )
        df_cn["% TH/KH"] = df_cn.apply(
            lambda r: round(r["TH (triệu đ)"] / r["KH (triệu đ)"] * 100, 1) if r["KH (triệu đ)"] else 0.0,
            axis=1,
        )
        hien_thi_dataframe_phan_trang(
            _dinh_dang_so_sanh(df_cn),
            key=_SS + "ss_cn_tbl",
            height=500,
        )
    elif "Chi tiết PGD" in xem:
        idx = st.selectbox(
            "Chọn PGD",
            range(len(labels)),
            format_func=lambda i: labels[i],
            key=_SS + "ss_pgd_sel",
        )
        ten_chon = labels[idx]
        df_pgd = df[df["PGD"] == ten_chon].drop(columns=["PGD"])
        hien_thi_dataframe_phan_trang(
            _dinh_dang_so_sanh(df_pgd),
            key=_SS + "ss_pgd_tbl",
            height=400,
        )
    else:
        idx_xa = st.selectbox(
            "Chọn PGD",
            range(len(labels)),
            format_func=lambda i: labels[i],
            key=_SS + "ss_xa_pgd_sel",
        )
        ten_chon_xa = labels[idx_xa]
        try:
            df_xa_all = _tinh_so_sanh_kh_th_xa(nam, thang, dot, df_hstd)
        except Exception as e:
            logger.error("_tinh_so_sanh_kh_th_xa: %s", e, exc_info=True)
            st.error(f"❌ Lỗi: {e}")
            df_xa_all = pd.DataFrame()
        if df_xa_all.empty:
            st.warning("⚠️ Không có dữ liệu xã.")
        else:
            df_xa = df_xa_all[df_xa_all["PGD"] == ten_chon_xa].drop(columns=["PGD"])
            if df_xa.empty:
                st.info(f"Không có dữ liệu xã cho {ten_chon_xa}.")
            else:
                hien_thi_dataframe_phan_trang(
                    _dinh_dang_so_sanh(df_xa),
                    key=_SS + "ss_xa_tbl",
                    height=500,
                )

    if st.button("📥 Xuất Excel So sánh", key=_SS + "ss_export"):
        try:
            df_cn_exp = (
                df.groupby(["Mã CT", "Chương trình", "Nguồn"], as_index=False)
                .agg({"KH (triệu đ)": "sum", "TH (triệu đ)": "sum", "Chênh lệch": "sum"})
            )
            df_cn_exp["% TH/KH"] = df_cn_exp.apply(
                lambda r: round(r["TH (triệu đ)"] / r["KH (triệu đ)"] * 100, 1) if r["KH (triệu đ)"] else 0.0,
                axis=1,
            )
            try:
                df_xa_exp = _tinh_so_sanh_kh_th_xa(nam, thang, dot, df_hstd)
            except Exception:
                df_xa_exp = pd.DataFrame()
            sheets = {
                f"Tổng hợp CN {nam}.{thang} {dot}": df_cn_exp,
                "Chi tiết PGD": df,
            }
            if not df_xa_exp.empty:
                sheets["Chi tiết xã"] = df_xa_exp
            xls_bytes = xuat_excel(sheets)
            st.download_button(
                "📥 Tải file Excel",
                data=xls_bytes,
                file_name=f"SoSanh_KHTD_{nam}_{thang}_{dot}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=_SS + "ss_dl",
            )
        except Exception as e:
            logger.error("_section_e export: %s", e, exc_info=True)
            st.error(f"❌ Lỗi xuất Excel: {e}")


# ── Section F: Theo dõi thực hiện per xã (3 cấp drill-down) ──────────────────


def _build_th_map_toan_cn(
    df_hstd: pd.DataFrame | None,
) -> dict[tuple[str, str, int, int], float]:
    """Trả về {(ten_pgd, xa_key, ma_ct_int, nguon_int): du_no_trieu}."""
    if df_hstd is None or df_hstd.empty:
        return {}
    required = (COT_TEN_PGD, COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON)
    if not all(c in df_hstd.columns for c in required):
        return {}
    dh = df_hstd.copy()
    dh["_mc"] = pd.to_numeric(dh[COT_MA_CHUONG_TRINH], errors="coerce").fillna(-1).astype(int)
    dh["_nv"] = pd.to_numeric(dh[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)
    if COT_TONG_DU_NO in dh.columns:
        dh["_dn"] = pd.to_numeric(dh[COT_TONG_DU_NO], errors="coerce").fillna(0)
    else:
        cols_dn = [c for c in (COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH) if c in dh.columns]
        for c in cols_dn:
            dh[c] = pd.to_numeric(dh[c], errors="coerce").fillna(0)
        dh["_dn"] = dh[cols_dn].sum(axis=1)
    dh["_xa_key"] = dh[COT_TEN_XA].map(
        lambda v: tim_ten_xa_trong_hstd(str(v).strip()).casefold() if pd.notna(v) else ""
    )
    agg = dh.groupby([COT_TEN_PGD, "_xa_key", "_mc", "_nv"])["_dn"].sum().reset_index()
    return {
        (r[COT_TEN_PGD], r["_xa_key"], int(r["_mc"]), int(r["_nv"])): r["_dn"] / 1e6
        for _, r in agg.iterrows()
    }


def _tinh_pivot_kh_th(
    nam: int, thang: str, dot: str,
    nguon: str,
    df_hstd: pd.DataFrame | None,
    th_map: dict[tuple[str, str, int, int], float] | None = None,
) -> tuple[dict, list[str], dict[str, list[str]]]:
    """
    Tính pivot KH/TH per (pgd_slug, xa, ma_key).
    Trả về: (data_dict, active_mk_list, xas_per_pgd_dict)
      data_dict: {(pgd_slug, xa, ma_key): (kh_trieu, th_trieu, cl_trieu, pct)}
    """
    df_kh = khtd_service.tong_hop(nam, thang, dot)
    if df_kh.empty:
        return {}, [], {}

    df_kh = df_kh[df_kh["nguon"] == nguon].copy()
    km_c = "kh_moi_tw" if nguon == "TW" else "kh_moi_dp"
    df_kh[km_c] = pd.to_numeric(df_kh[km_c], errors="coerce").fillna(0)

    if th_map is None:
        th_map = _build_th_map_toan_cn(df_hstd)

    active_mk: list[str] = []
    mk_set: set[str] = set()
    for mk in df_kh["ma_key"]:
        if mk not in mk_set:
            active_mk.append(mk)
            mk_set.add(mk)

    data: dict[tuple, tuple] = {}
    xas_per_pgd: dict[str, list[str]] = {}

    for _, r in df_kh.iterrows():
        pgd_s = r["pgd_slug"]
        xa = r.get("xa", "")
        mk = r["ma_key"]
        kh_trieu = float(r[km_c]) / 1e6

        # Lookup TH
        ma_ct = _MAKEY_TO_MACT.get(mk, -1)
        nguon_int = 1 if nguon == "TW" else 2
        ten_pgd = _slug_to_ten(pgd_s)
        xa_key = tim_ten_xa_trong_hstd(str(xa).strip()).casefold() if xa else ""
        th_trieu = th_map.get((ten_pgd, xa_key, ma_ct, nguon_int), 0.0)

        cl = th_trieu - kh_trieu
        pct = round(th_trieu / kh_trieu * 100, 1) if kh_trieu else 0.0
        data[(pgd_s, xa, mk)] = (kh_trieu, th_trieu, cl, pct)

        if xa:
            xas_per_pgd.setdefault(pgd_s, [])
            if xa not in xas_per_pgd[pgd_s]:
                xas_per_pgd[pgd_s].append(xa)

    return data, active_mk, xas_per_pgd


def _mau_pct(pct: float) -> str:
    if pct >= 95:
        return "#059669"
    if pct >= 80:
        return "#d97706"
    return "#dc2626"


def _mau_cl(cl: float) -> str:
    if cl > 0:
        return "#059669"
    if cl < 0:
        return "#dc2626"
    return "inherit"


def _html_pivot_kh_th(
    nam: int, thang: str, dot: str,
    nguon: str,
    df_hstd: pd.DataFrame | None,
    pivot_data: tuple[dict, list[str], dict[str, list[str]]] | None = None,
) -> str:
    """Render HTML bảng pivot Cấp 1: PGD × CT × (KH, TH, CL, %)."""
    if pivot_data is None:
        pivot_data = _tinh_pivot_kh_th(nam, thang, dot, nguon, df_hstd)
    data, active_mk, xas_per_pgd = pivot_data
    if not data:
        return "<p style='color:var(--text-color);padding:12px'>⚠️ Chưa có dữ liệu KHTD cho đợt này.</p>"

    def fn(v: float) -> str:
        return "" if v == 0 else f"{v:,.1f}".replace(",", ".")

    def fpct(v: float) -> str:
        return f"{v:.1f}%".replace(".", ",") if v else "—"

    td = "border:1px solid #e2e8f0;padding:3px 6px"
    th_hdr = "border:1px solid #1e40af;padding:4px 6px;background:rgba(30,64,175,0.85);color:#fff;text-align:center;font-size:10px;white-space:nowrap"
    th_sub = "border:1px solid #2563eb;padding:2px 5px;background:rgba(37,99,235,0.75);color:#fff;text-align:center;font-size:9px;white-space:nowrap"
    th_base = "border:1px solid #e2e8f0;padding:4px 8px;background:rgba(239,246,255,0.9);text-align:center;font-size:11px;font-weight:600;white-space:nowrap"

    html: list[str] = [
        "<div style='overflow-x:auto;max-width:100%;font-size:11px;margin-top:8px'>",
        f"<table style='border-collapse:collapse;white-space:nowrap;min-width:{max(960, 260 + len(active_mk) * 220)}px'>",
        "<thead>",
        "<tr>",
        f'<th rowspan="2" style="{th_base}">STT</th>',
        f'<th rowspan="2" style="{th_base}">Tên đơn vị</th>',
    ]
    for mk in active_mk:
        html.append(f'<th colspan="4" style="{th_hdr}">{_ten_ngan(mk)}</th>')
    html += ["</tr>", "<tr>"]
    for _ in active_mk:
        html += [
            f'<th style="{th_sub}">KH</th>',
            f'<th style="{th_sub}">TH</th>',
            f'<th style="{th_sub}">CL</th>',
            f'<th style="{th_sub}">%</th>',
        ]
    html += ["</tr>", "</thead>", "<tbody>"]

    totals: dict[str, list[float]] = {mk: [0.0, 0.0, 0.0] for mk in active_mk}
    pgd_order = [("hoi_so", DON_VI_CHI_NHANH)] + [
        (_pgd_slug(p), p) for p in DS_PGD
    ]
    pgd_idx = 0

    for pgd_slug, pgd_name in pgd_order:
        if pgd_slug not in xas_per_pgd:
            continue
        pgd_idx += 1
        roman = _ROMAN[pgd_idx - 1] if pgd_idx <= len(_ROMAN) else str(pgd_idx)
        xas = xas_per_pgd[pgd_slug]

        # Row PGD (tổng)
        html.append("<tr style='background:rgba(219,234,254,0.6);font-weight:700'>")
        html.append(f'<td style="{td};text-align:center">{roman}</td>')
        html.append(f'<td style="{td}">{pgd_name}</td>')
        for mk in active_mk:
            kh = sum(data.get((pgd_slug, xa, mk), (0, 0, 0, 0))[0] for xa in xas)
            th = sum(data.get((pgd_slug, xa, mk), (0, 0, 0, 0))[1] for xa in xas)
            cl = th - kh
            pct = round(th / kh * 100, 1) if kh else 0.0
            totals[mk][0] += kh
            totals[mk][1] += th
            totals[mk][2] += cl
            html += [
                f'<td style="{td};text-align:right">{fn(kh)}</td>',
                f'<td style="{td};text-align:right">{fn(th)}</td>',
                f'<td style="{td};text-align:right;color:{_mau_cl(cl)}">{fn(cl)}</td>',
                f'<td style="{td};text-align:right;color:{_mau_pct(pct)}">{fpct(pct)}</td>',
            ]
        html.append("</tr>")

        # Rows xã
        for stt_xa, xa in enumerate(xas, 1):
            html.append("<tr>")
            html.append(f'<td style="{td};text-align:center;opacity:.5">{stt_xa}</td>')
            html.append(f'<td style="{td};padding-left:20px">{xa}</td>')
            for mk in active_mk:
                kh, th, cl, pct = data.get((pgd_slug, xa, mk), (0, 0, 0, 0))
                html += [
                    f'<td style="{td};text-align:right">{fn(kh)}</td>',
                    f'<td style="{td};text-align:right">{fn(th)}</td>',
                    f'<td style="{td};text-align:right;color:{_mau_cl(cl)}">{fn(cl)}</td>',
                    f'<td style="{td};text-align:right;color:{_mau_pct(pct)}">{fpct(pct)}</td>',
                ]
            html.append("</tr>")

    # Row tổng cộng
    html.append("<tr style='background:rgba(240,253,244,0.8);font-weight:700'>")
    html.append(f'<td style="{td}" colspan="2">Tổng cộng</td>')
    for mk in active_mk:
        kh, th, cl = totals[mk]
        pct = round(th / kh * 100, 1) if kh else 0.0
        html += [
            f'<td style="{td};text-align:right">{fn(kh)}</td>',
            f'<td style="{td};text-align:right">{fn(th)}</td>',
            f'<td style="{td};text-align:right;color:{_mau_cl(cl)}">{fn(cl)}</td>',
            f'<td style="{td};text-align:right;color:{_mau_pct(pct)}">{fpct(pct)}</td>',
        ]
    html += [
        "</tr>", "</tbody>", "</table>",
        "<p style='font-size:11px;margin-top:4px;color:var(--text-color)'>"
        "Đơn vị: triệu đồng · 🟢 ≥95% · 🟡 80–95% · 🔴 &lt;80%</p>",
        "</div>",
    ]
    return "\n".join(html)


def _build_rows_ct_theo_xa(
    data_tw: dict[tuple, tuple],
    data_dp: dict[tuple, tuple],
    slug_chon: str,
    xa_chon: str,
) -> list[dict]:
    rows_ct: list[dict] = []
    for nguon_label, source_data in (("TW", data_tw), ("ĐP", data_dp)):
        for (pgd_s, xa, ma_key), (kh, th, cl, pct) in source_data.items():
            if pgd_s != slug_chon or xa != xa_chon:
                continue
            rows_ct.append({
                "_sort": (_MAKEY_TO_MACT.get(ma_key, 999), nguon_label, ma_key),
                "Chương trình": _CT_MAP.get(ma_key, ma_key),
                "Nguồn": nguon_label,
                "KH (tr.đ)": round(kh, 1),
                "TH (tr.đ)": round(th, 1),
                "CL": round(cl, 1),
                "% TH/KH": pct,
            })
    rows_ct.sort(key=lambda r: r["_sort"])
    for row in rows_ct:
        row.pop("_sort", None)
    return rows_ct


def _section_f_theo_doi(
    nam: int, thang: str, dot: str, df_hstd: pd.DataFrame | None
) -> None:
    """Section theo dõi thực hiện: 3 cấp drill-down (PGD → xã → CT)."""
    th_map = _build_th_map_toan_cn(df_hstd)
    pivot_tw = _tinh_pivot_kh_th(nam, thang, dot, "TW", df_hstd, th_map)
    pivot_dp = _tinh_pivot_kh_th(nam, thang, dot, "DP", df_hstd, th_map)
    data_tw = pivot_tw[0]
    data_dp = pivot_dp[0]

    tab_tw, tab_dp = st.tabs(["🏦 Nguồn TW", "🏙️ Nguồn ĐP"])

    with tab_tw:
        st.html(_html_pivot_kh_th(nam, thang, dot, "TW", df_hstd, pivot_tw))
    with tab_dp:
        st.html(_html_pivot_kh_th(nam, thang, dot, "DP", df_hstd, pivot_dp))

    # ── Drill-down: chọn PGD → KPI cards xã ──
    st.divider()
    st.markdown("##### 🔍 Xem chi tiết theo đơn vị")
    ds = _ds_slug_label()
    labels = [x[0] for x in ds]
    slugs = [x[1] for x in ds]

    idx_pgd = st.selectbox(
        "Chọn PGD",
        range(len(labels)),
        format_func=lambda i: labels[i],
        key=_SS + "f_pgd_sel",
    )
    slug_chon = slugs[idx_pgd]
    ten_chon = labels[idx_pgd]

    # KPI cards per xã
    tt_xa = khtd_service.trang_thai_xa(slug_chon, nam, thang, dot)
    ds_xa = list(tt_xa.keys())
    if not ds_xa:
        st.info(f"{ten_chon} chưa có danh sách xã.")
        return

    so_da_nhap = sum(1 for v in tt_xa.values() if v)
    st.caption(f"Tiến độ nhập KH: **{so_da_nhap}/{len(ds_xa)}** xã")

    xa_kpi: dict[str, dict] = {}
    for xa in ds_xa:
        kh_t = sum(v[0] for k, v in data_tw.items() if k[0] == slug_chon and k[1] == xa)
        th_t = sum(v[1] for k, v in data_tw.items() if k[0] == slug_chon and k[1] == xa)
        kh_d = sum(v[0] for k, v in data_dp.items() if k[0] == slug_chon and k[1] == xa)
        th_d = sum(v[1] for k, v in data_dp.items() if k[0] == slug_chon and k[1] == xa)
        kh = kh_t + kh_d
        th = th_t + th_d
        pct = round(th / kh * 100, 1) if kh else 0.0
        xa_kpi[xa] = {"kh": kh, "th": th, "pct": pct, "da_nhap": tt_xa.get(xa, False)}

    # Render KPI cards (tối đa 5 cột)
    cols_per_row = min(5, len(ds_xa))
    for row_start in range(0, len(ds_xa), cols_per_row):
        cols = st.columns(cols_per_row)
        for ci, xa in enumerate(ds_xa[row_start:row_start + cols_per_row]):
            info = xa_kpi[xa]
            badge = "✅" if info["da_nhap"] else "⬜"
            mau = _mau_pct(info["pct"])
            with cols[ci]:
                st.markdown(
                    f"<div style='border:1px solid #e2e8f0;border-radius:8px;"
                    f"padding:10px;text-align:center;margin-bottom:6px'>"
                    f"<div style='font-weight:600;font-size:12px'>{badge} {xa}</div>"
                    f"<div style='font-size:11px;color:var(--text-color)'>"
                    f"KH: {info['kh']:,.0f}</div>"
                    f"<div style='font-size:11px;color:var(--text-color)'>"
                    f"TH: {info['th']:,.0f}</div>"
                    f"<div style='font-size:14px;font-weight:700;color:{mau}'>"
                    f"{info['pct']:.1f}%</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ── Drill-down cấp 3: chọn xã → bảng chi tiết CT ──
    st.divider()
    idx_xa = st.selectbox(
        "Chọn xã xem chi tiết",
        range(len(ds_xa)),
        format_func=lambda i: ds_xa[i],
        key=_SS + f"f_xa_sel_{slug_chon}",
    )
    xa_chon = ds_xa[idx_xa]

    rows_ct = _build_rows_ct_theo_xa(data_tw, data_dp, slug_chon, xa_chon)

    if rows_ct:
        df_ct = pd.DataFrame(rows_ct)
        # Thêm dòng tổng
        tong_kh = df_ct["KH (tr.đ)"].sum()
        tong_th = df_ct["TH (tr.đ)"].sum()
        tong_cl = tong_th - tong_kh
        tong_pct = round(tong_th / tong_kh * 100, 1) if tong_kh else 0.0
        df_ct.loc[len(df_ct)] = {
            "Chương trình": "TỔNG CỘNG",
            "Nguồn": "",
            "KH (tr.đ)": round(tong_kh, 1),
            "TH (tr.đ)": round(tong_th, 1),
            "CL": round(tong_cl, 1),
            "% TH/KH": tong_pct,
        }
        st.markdown(f"**Xã {xa_chon}** — {ten_chon}")
        hien_thi_dataframe_phan_trang(df_ct, key=_SS + "f_ct_tbl", height=450)
    else:
        st.info(f"Chưa có dữ liệu KHTD cho xã {xa_chon}.")


def render(tab=None, **kwargs) -> None:
    username = st.session_state.get("username", "unknown")
    role = kwargs.get("role", "user")
    pgd_user = kwargs.get("pgd_user")
    df_hstd = kwargs.get("df_full")

    ctx = TabContext(tab, **kwargs)
    with ctx:
        st.subheader("📋 Giao & Điều chỉnh KHTD")
        st.caption(
            "Lưu theo đợt · Lũy kế giữa các đợt · Duyệt tập trung"
        )

        with st.expander("📖 Hướng dẫn sử dụng", expanded=False):
            st.markdown(
                """
**Quy trình:**
1. Admin upload file HSTD 31/12 → Khởi tạo đợt giao đầu năm
2. Các đợt tiếp theo:
   - Loại **Giao**: Admin/Manager nhập KH giao cho từng PGD
   - Loại **Điều chỉnh**: Admin push KH lên GSheet → PGD nhập +/-
3. Admin tải về → Kiểm tra → Duyệt hoặc Từ chối

---
**Lũy kế:**
- KH_giao đợt hiện tại = KH_mới của đợt liền trước
- Các đợt giao và điều chỉnh có thể xen kẽ tự do

---
### Quy tắc nhập GSheet (Điều chỉnh)
- ✅ Số **dương (+)** = tăng · Số **âm (-)** = giảm
- ✅ Đơn vị: **triệu đồng**
- ⚠️ ĐC ≠ 0 → **bắt buộc nhập Lý do**
- 🔒 Chỉ nhập cột **ĐC_TW (G)**, **ĐC_ĐP (J)**, **Lý do (L)**
- 🚫 Không thêm/xóa dòng · Không đổi tên tab GSheet

---

### Trạng thái đợt
| | Ý nghĩa |
|---|---|
| ⬜ Chưa tải | Chưa có dữ liệu |
| 🔵 Chờ duyệt | Đã nhập, chờ Admin xét |
| 🟢 Đã duyệt | Hoàn tất |
| 🔴 Từ chối | Cần sửa và tải lại |

---

### Phân quyền
| Vai trò | Quyền |
|---|---|
| **Admin** | Toàn quyền: khởi tạo, giao, tải GSheet, duyệt |
| **Manager** | Giao KH, xem tổng hợp, duyệt |
| **Executive** | Chỉ xem, không nhập |
| **User (PGD)** | Nhập ĐC vào GSheet, xem trạng thái PGD mình |
            """
            )

        nam, thang, dot = _chon_dot()

        if la_quan_ly_cn(role):
            loai_radio = st.radio(
                "Loại đợt",
                ["📋 Giao KHTD", "📉 Điều chỉnh KHTD"],
                horizontal=True,
                key=_SS + "loai_radio",
            )
            loai_val = (
                LOAI_GIAO if "Giao" in loai_radio else LOAI_DIEU_CHINH
            )
            st.session_state[_SS + "loai"] = loai_val
        else:
            loai_val = st.session_state.get(_SS + "loai", LOAI_DIEU_CHINH)

        if la_phan_he_pgd(role):
            _section_d_user(pgd_user, nam, thang, dot)
            return

        is_admin = normalize_role(role) in ("admin_cn", "admin")

        tab_labels: list[str] = []
        if is_admin:
            tab_labels.append("⚙️ Khởi tạo")
        if loai_val == LOAI_GIAO:
            tab_labels.append("📝 Nhập KH Giao")
        tab_labels += ["📊 Tổng hợp KH", "📈 So sánh KH/TH", "📍 Theo dõi Xã"]

        tabs_ui = st.tabs(tab_labels)
        t_idx = 0

        if is_admin:
            with tabs_ui[t_idx]:
                _section_a(username, nam, thang, dot, df_hstd)
            t_idx += 1

        if loai_val == LOAI_GIAO:
            with tabs_ui[t_idx]:
                _section_b_giao(nam, thang, dot, role, username, df_hstd)
            t_idx += 1

        with tabs_ui[t_idx]:
            _section_c_tong_hop(nam, thang, dot)
        t_idx += 1

        with tabs_ui[t_idx]:
            _section_e_so_sanh_kh_th(nam, thang, dot, df_hstd)
        t_idx += 1

        with tabs_ui[t_idx]:
            _section_f_theo_doi(nam, thang, dot, df_hstd)
