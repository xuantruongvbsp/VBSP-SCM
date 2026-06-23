"""Quản lý Mã Nhà đầu tư Địa phương — dành cho Admin/Manager CN."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import normalize_role
from config import (
    CACHE_DIR,
    CACHE_HSTD,
    COT_DU_NO_QH,
    COT_DU_NO_TH,
    COT_MA_CHUONG_TRINH,
    COT_MA_NDT,
    COT_MA_NHA_DAU_TU,
    COT_NGUON_VON,
    COT_TONG_DU_NO,
)
from logger import get_logger
from utils import fmt_so, fmt_ty

logger = get_logger(__name__)

_CAP_OPTS = ["Cấp Tỉnh 🏛️", "Cấp Xã/Khác 🏘️"]
_CAP_TO = {"Cấp Tỉnh 🏛️": "tinh", "Cấp Xã/Khác 🏘️": "xa"}
_CAP_FROM = {"tinh": "Cấp Tỉnh 🏛️", "xa": "Cấp Xã/Khác 🏘️"}
_CT_META = {
    3: {
        "label": "GQVL ĐP",
        "title": "GQVL — Mã NĐT Địa phương",
        "desc": "Áp dụng cho `ma_ct=03`. Dùng để tách `3_DP_TINH` và `3_DP_XA`.",
        "source": str(Path(CACHE_DIR) / "gqvl.parquet"),
    },
    6: {
        "label": "NSVSMT ĐP",
        "title": "NSVSMT — Mã NĐT Địa phương",
        "desc": "Áp dụng cho `ma_ct=06`. Dùng để tách `6_DP_TINH` và `6_DP_XA`.",
        "source": CACHE_HSTD,
    },
}


def _label_ct(ma_ct: int) -> str:
    meta = _CT_META.get(int(ma_ct), {})
    return f"CT {int(ma_ct):02d} — {meta.get('label', ma_ct)}"


def _doc_ds_theo_ct(ma_ct: int) -> list[dict]:
    if int(ma_ct) == 3:
        return db.doc_ndt_dp_list()
    if int(ma_ct) == 6:
        return db.doc_ndt_dp_nsvsmt_list()
    return []


def _luu_ds_theo_ct(ma_ct: int, ds: list[dict], username: str) -> None:
    if int(ma_ct) == 3:
        db.luu_ndt_dp_list(ds, username)
        return
    if int(ma_ct) == 6:
        db.luu_ndt_dp_nsvsmt_list(ds, username)
        return
    raise ValueError(f"Chưa hỗ trợ CT {ma_ct}")


def _action_suffix(ma_ct: int) -> str:
    return "ndt_dp" if int(ma_ct) == 3 else "ndt_dp_nsvsmt"


def _ghi_audit_them_sua_xoa(username: str, ma_ct: int, action: str, detail: str) -> None:
    db.ghi_audit(username, action, f"CT{int(ma_ct):02d} · {detail}")


def _df_rules(ds: list[dict]) -> pd.DataFrame:
    rows = []
    for item in ds:
        cap = str(item.get("cap", "tinh") or "tinh")
        rows.append(
            {
                "Mã CT": f"{int(item.get('ma_ct', 0) or 0):02d}",
                "Chương trình": _CT_META.get(int(item.get("ma_ct", 0) or 0), {}).get("label", ""),
                "Mã NĐT": item.get("ma", ""),
                "Phân loại cấp": _CAP_FROM.get(cap, _CAP_OPTS[0]),
                "Ghi chú": item.get("ghi_chu", "") or "",
            }
        )
    return pd.DataFrame(rows)


def _render_kpi_rules(ds_all: list[dict]) -> None:
    ct03 = [x for x in ds_all if int(x.get("ma_ct", 0) or 0) == 3]
    ct06 = [x for x in ds_all if int(x.get("ma_ct", 0) or 0) == 6]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tổng rule", fmt_so(len(ds_all)))
    c2.metric("CT 03", fmt_so(len(ct03)))
    c3.metric("CT 06", fmt_so(len(ct06)))
    c4.metric("Cấp tỉnh", fmt_so(sum(1 for x in ds_all if x.get("cap", "tinh") == "tinh")))
    c5.metric("Cấp xã/khác", fmt_so(sum(1 for x in ds_all if x.get("cap", "tinh") == "xa")))


def _render_huong_dan() -> None:
    with st.expander("📖 Hướng dẫn sử dụng", expanded=False):
        st.markdown(
            """
### Mục đích

Danh mục này quản lý rule phân loại theo cặp **Mã CT + Mã NĐT**:

| Trường | Ý nghĩa |
|---|---|
| **Mã CT** | Chương trình áp dụng, ví dụ `03` = GQVL, `06` = NSVSMT |
| **Mã NĐT** | Lấy chính xác từ cột `Mã nhà đầu tư` trong file dữ liệu |
| **Phân loại cấp** | `Cấp tỉnh` hoặc `Cấp xã/khác` |

### Cách dùng

1. Chọn chương trình cần quản lý ở mục `⚙️ Quản lý`
2. Thêm mã mới hoặc chỉnh sửa trực tiếp từng dòng
3. Hệ thống dùng rule `(Mã CT, Mã NĐT)` trước, rồi mới fallback rule chung nếu có

### Gợi ý vận hành

- `CT 03` dùng cho GQVL ĐP
- `CT 06` dùng cho NSVSMT ĐP
- Cùng một `Mã NĐT` có thể xuất hiện ở nhiều CT, nên phải quản lý tách theo CT
"""
        )


def _render_tong_quan(ds_all: list[dict]) -> None:
    st.markdown("##### 📋 Danh mục tổng hợp")
    df = _df_rules(ds_all)
    if df.empty:
        st.info("Chưa có rule nào.")
        return

    f1, f2, f3 = st.columns([2, 2, 3])
    ct_chon = f1.selectbox(
        "Chương trình",
        ["Tất cả"] + [f"CT {ma_ct:02d} — {meta['label']}" for ma_ct, meta in _CT_META.items()],
        key="ndt_dp_tq_ct",
    )
    cap_chon = f2.selectbox(
        "Phân loại cấp",
        ["Tất cả"] + _CAP_OPTS,
        key="ndt_dp_tq_cap",
    )
    tu_khoa = f3.text_input(
        "Tìm mã / ghi chú",
        placeholder="VD: INV080214... hoặc UBND tỉnh",
        key="ndt_dp_tq_kw",
    ).strip().lower()

    df_loc = df.copy()
    if ct_chon != "Tất cả":
        df_loc = df_loc[df_loc["Chương trình"] == ct_chon.split(" — ", 1)[1]]
    if cap_chon != "Tất cả":
        df_loc = df_loc[df_loc["Phân loại cấp"] == cap_chon]
    if tu_khoa:
        mask = (
            df_loc["Mã NĐT"].astype(str).str.lower().str.contains(tu_khoa, na=False)
            | df_loc["Ghi chú"].astype(str).str.lower().str.contains(tu_khoa, na=False)
        )
        df_loc = df_loc[mask]

    st.dataframe(df_loc, hide_index=True, use_container_width=True)


def _render_danh_sach_theo_cap(ds: list[dict], ma_ct: int) -> None:
    ds_tinh = [x for x in ds if x.get("cap", "tinh") == "tinh"]
    ds_xa = [x for x in ds if x.get("cap", "tinh") == "xa"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng rule", fmt_so(len(ds)))
    c2.metric("Cấp tỉnh", fmt_so(len(ds_tinh)))
    c3.metric("Cấp xã/khác", fmt_so(len(ds_xa)))

    left, right = st.columns(2)
    with left:
        st.markdown("###### 🏛️ Cấp Tỉnh")
        if ds_tinh:
            st.dataframe(_df_rules(ds_tinh), hide_index=True, use_container_width=True)
        else:
            st.info(f"CT {ma_ct:02d} chưa có rule cấp tỉnh.")
    with right:
        st.markdown("###### 🏘️ Cấp Xã/Khác")
        if ds_xa:
            st.dataframe(_df_rules(ds_xa), hide_index=True, use_container_width=True)
        else:
            st.info(f"CT {ma_ct:02d} chưa có rule cấp xã/khác.")


def _render_them_moi(ds: list[dict], ma_ct: int, can_edit: bool, username: str) -> None:
    if not can_edit:
        st.warning("⚠️ Chỉ Admin CN mới có thể thêm rule.")
        return

    with st.form(f"form_them_ndt_ct_{ma_ct}", clear_on_submit=True):
        st.caption(f"Thêm rule mới cho `{_label_ct(ma_ct)}`")
        ma_them = st.text_input(
            "Mã NĐT",
            placeholder="VD: INV0802140002662",
            key=f"ndt_ma_them_ct_{ma_ct}",
        )
        ghi_chu_them = st.text_input(
            "Ghi chú",
            placeholder="VD: UBND tỉnh Đồng Nai",
            key=f"ndt_gc_them_ct_{ma_ct}",
        )
        cap_them = st.selectbox(
            "Phân loại cấp",
            _CAP_OPTS,
            key=f"ndt_cap_them_ct_{ma_ct}",
        )
        submitted = st.form_submit_button("➕ Thêm rule", type="primary")

    if not submitted:
        return

    ma_them = ma_them.strip()
    if not ma_them:
        st.error("Vui lòng nhập mã NĐT.")
        return
    if any(str(x.get("ma", "")).strip() == ma_them for x in ds):
        st.warning(f"Mã **{ma_them}** đã tồn tại trong `{_label_ct(ma_ct)}`.")
        return

    ds_moi = list(ds) + [
        {
            "ma_ct": int(ma_ct),
            "ma": ma_them,
            "ghi_chu": ghi_chu_them.strip(),
            "cap": _CAP_TO[cap_them],
        }
    ]
    _luu_ds_theo_ct(ma_ct, ds_moi, username)
    _ghi_audit_them_sua_xoa(
        username,
        ma_ct,
        f"them_{_action_suffix(ma_ct)}",
        f"Thêm mã {ma_them} ({cap_them})",
    )
    st.success(f"✅ Đã thêm mã **{ma_them}** cho `{_label_ct(ma_ct)}`.")
    st.rerun()


def _render_chinh_sua(ds: list[dict], ma_ct: int, can_edit: bool, username: str) -> None:
    if not can_edit:
        st.warning("⚠️ Chỉ Admin CN mới có thể chỉnh sửa / xóa rule.")
        return
    if not ds:
        st.info("Chưa có rule nào.")
        return

    st.caption("Chỉnh sửa ghi chú hoặc đổi phân loại cấp, nhấn 💾 để lưu từng dòng.")
    for i, item in enumerate(ds):
        cols = st.columns([3, 3, 2, 1, 1])
        cols[0].code(item["ma"])
        gc_edit = cols[1].text_input(
            "Ghi chú",
            value=item.get("ghi_chu", "") or "",
            key=f"ndt_gc_{ma_ct}_{i}",
            label_visibility="collapsed",
        )
        cap_current = _CAP_FROM.get(item.get("cap", "tinh"), _CAP_OPTS[0])
        cap_edit = cols[2].selectbox(
            "Cấp",
            _CAP_OPTS,
            index=_CAP_OPTS.index(cap_current),
            key=f"ndt_cap_{ma_ct}_{i}",
            label_visibility="collapsed",
        )
        if cols[3].button("💾", key=f"luu_ndt_{ma_ct}_{i}", help="Lưu thay đổi"):
            ds_moi = [dict(x) for x in ds]
            ds_moi[i]["ma_ct"] = int(ma_ct)
            ds_moi[i]["ghi_chu"] = (gc_edit or "").strip()
            ds_moi[i]["cap"] = _CAP_TO[cap_edit]
            _luu_ds_theo_ct(ma_ct, ds_moi, username)
            _ghi_audit_them_sua_xoa(
                username,
                ma_ct,
                f"sua_{_action_suffix(ma_ct)}",
                f"Sửa mã {item['ma']} → ghi chú: {gc_edit}, cấp: {cap_edit}",
            )
            st.rerun()
        if cols[4].button(
            "🗑️",
            key=f"xoa_ndt_{ma_ct}_{i}",
            disabled=(len(ds) <= 1),
            help="Không thể xóa khi chỉ còn 1 rule",
        ):
            ds_moi = [x for j, x in enumerate(ds) if j != i]
            _luu_ds_theo_ct(ma_ct, ds_moi, username)
            _ghi_audit_them_sua_xoa(
                username,
                ma_ct,
                f"xoa_{_action_suffix(ma_ct)}",
                f"Xóa mã {item['ma']}",
            )
            st.rerun()


def _render_quan_ly_ct(ma_ct: int, can_edit: bool, username: str) -> None:
    meta = _CT_META[int(ma_ct)]
    ds = _doc_ds_theo_ct(ma_ct)

    st.markdown(f"##### {meta['title']}")
    st.caption(f"{meta['desc']} Nguồn dữ liệu phân tích: `{meta['source']}`")

    tab_ds, tab_them, tab_sua = st.tabs(["📋 Danh sách", "➕ Thêm mới", "✏️ Chỉnh sửa / Xóa"])
    with tab_ds:
        _render_danh_sach_theo_cap(ds, ma_ct)
    with tab_them:
        _render_them_moi(ds, ma_ct, can_edit, username)
    with tab_sua:
        _render_chinh_sua(ds, ma_ct, can_edit, username)


def _phan_tich_gqvl(ds: list[dict]) -> None:
    try:
        gqvl_path = Path(CACHE_DIR) / "gqvl.parquet"
        if not gqvl_path.exists():
            st.info("Chưa có dữ liệu GQVL. Upload file để xem phân tích.")
            return

        df_gqvl = pd.read_parquet(gqvl_path)
        if (COT_NGUON_VON not in df_gqvl.columns) or (COT_MA_NDT not in df_gqvl.columns):
            st.warning("File GQVL không có đủ cột để phân tích.")
            return
        if df_gqvl[COT_NGUON_VON].isna().all():
            st.warning("⚠️ Cột 'Nguồn vốn' trong cache GQVL toàn NaN — dữ liệu cũ bị lỗi. Vui lòng upload lại file GQVL.")
            return

        df_dp = df_gqvl[df_gqvl[COT_NGUON_VON] == "ĐP"].copy()
        if df_dp.empty:
            st.info("Không có món GQVL ĐP trong cache hiện tại.")
            return

        ma_ndt = df_dp[COT_MA_NDT].astype(str).str.strip()
        cap_s = ma_ndt.map(lambda ma: db.phan_loai_ndt_dp_cap(3, ma))
        p1, p2, p3 = st.columns(3)
        p1.metric("Tổng món ĐP", fmt_so(len(df_dp)))
        p2.metric("→ Cấp tỉnh", fmt_so(int(cap_s.eq("tinh").sum())))
        p3.metric("→ Cấp xã/khác", fmt_so(int(cap_s.ne("tinh").sum())))

        agg_kw: dict = {"Số món": (COT_MA_NDT, "count")}
        if COT_DU_NO_TH in df_dp.columns:
            agg_kw["Dư nợ TH (tỷ)"] = (COT_DU_NO_TH, "sum")
        if COT_DU_NO_QH in df_dp.columns:
            agg_kw["Dư nợ QH (tỷ)"] = (COT_DU_NO_QH, "sum")

        df_pv = (
            df_dp.assign(Nhóm=cap_s.map(lambda x: "Cấp Tỉnh 🏛️" if x == "tinh" else "Cấp Xã/Khác 🏘️"))
            .groupby("Nhóm")
            .agg(**agg_kw)
            .reset_index()
        )
        for col in ("Dư nợ TH (tỷ)", "Dư nợ QH (tỷ)"):
            if col in df_pv.columns:
                df_pv[col] = df_pv[col].apply(fmt_ty)
        st.dataframe(df_pv, hide_index=True, use_container_width=True)
    except Exception as e:
        logger.error("tab_quan_ly_ndt_dp _phan_tich_gqvl: %s", e, exc_info=True)
        st.warning(f"Không thể phân tích tác động GQVL: {e}")


def _phan_tich_nsvsmt(ds: list[dict]) -> None:
    try:
        hstd_path = Path(CACHE_HSTD)
        if not hstd_path.exists():
            st.info("Chưa có dữ liệu HSTD. Upload file để xem phân tích.")
            return

        df_hstd = pd.read_parquet(hstd_path)
        required = {COT_MA_CHUONG_TRINH, COT_NGUON_VON, COT_MA_NHA_DAU_TU}
        if not required.issubset(df_hstd.columns):
            st.warning("File HSTD không có đủ cột để phân tích NSVSMT ĐP.")
            return

        col_dn = COT_TONG_DU_NO if COT_TONG_DU_NO in df_hstd.columns else (
            COT_DU_NO_TH if COT_DU_NO_TH in df_hstd.columns else None
        )
        if not col_dn:
            st.warning("HSTD thiếu cột dư nợ để phân tích.")
            return

        df_work = df_hstd.copy()
        df_work[COT_MA_CHUONG_TRINH] = pd.to_numeric(df_work[COT_MA_CHUONG_TRINH], errors="coerce").fillna(0).astype(int)
        df_work[COT_NGUON_VON] = pd.to_numeric(df_work[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)
        df_work[col_dn] = pd.to_numeric(df_work[col_dn], errors="coerce").fillna(0)
        df_work = df_work[(df_work[COT_MA_CHUONG_TRINH] == 6) & (df_work[COT_NGUON_VON] == 2)]
        if df_work.empty:
            st.info("Không có món NSVSMT ĐP trong HSTD hiện tại.")
            return

        ma_ndt = df_work[COT_MA_NHA_DAU_TU].astype(str).str.strip()
        cap_s = ma_ndt.map(lambda ma: db.phan_loai_ndt_dp_cap(6, ma))
        p1, p2, p3 = st.columns(3)
        p1.metric("Tổng món ĐP", fmt_so(len(df_work)))
        p2.metric("→ Cấp tỉnh", fmt_so(int(cap_s.eq("tinh").sum())))
        p3.metric("→ Cấp xã/khác", fmt_so(int(cap_s.ne("tinh").sum())))

        df_pv = (
            df_work.assign(Nhóm=cap_s.map(lambda x: "Cấp Tỉnh 🏛️" if x == "tinh" else "Cấp Xã/Khác 🏘️"))
            .groupby("Nhóm")
            .agg(
                **{
                    "Số món": (COT_MA_NHA_DAU_TU, "count"),
                    "Tổng dư nợ (tỷ)": (col_dn, "sum"),
                }
            )
            .reset_index()
        )
        df_pv["Tổng dư nợ (tỷ)"] = df_pv["Tổng dư nợ (tỷ)"].apply(fmt_ty)
        st.dataframe(df_pv, hide_index=True, use_container_width=True)
    except Exception as e:
        logger.error("tab_quan_ly_ndt_dp _phan_tich_nsvsmt: %s", e, exc_info=True)
        st.warning(f"Không thể phân tích tác động NSVSMT: {e}")


def _render_phan_tich() -> None:
    st.markdown("##### 🔎 Phân tích tác động")
    tab_gqvl, tab_ns = st.tabs(["CT 03 — GQVL ĐP", "CT 06 — NSVSMT ĐP"])
    with tab_gqvl:
        _phan_tich_gqvl(_doc_ds_theo_ct(3))
    with tab_ns:
        _phan_tich_nsvsmt(_doc_ds_theo_ct(6))


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    """CRUD Mã NĐT địa phương — quản lý theo Mã CT + Mã NĐT."""
    role = kwargs.get("role", "user")
    username = kwargs.get("username", "unknown")

    ctx = tab if tab is not None else st.container()
    with ctx:
        st.subheader("🏦 Mã Nhà đầu tư Địa phương")
        st.info(
            "ℹ️ Danh mục này quản lý rule theo cặp **Mã CT + Mã NĐT**. "
            "Một mã có thể tồn tại ở nhiều chương trình ĐP với phân loại khác nhau. "
            "Hệ thống ưu tiên match đúng `(Mã CT, Mã NĐT)` khi phân loại."
        )

        can_edit = normalize_role(str(role or "user")) == "admin_cn"
        ds_all = db.doc_ndt_dp_rule_list()

        _render_huong_dan()
        _render_kpi_rules(ds_all)

        che_do = st.radio(
            "Chế độ",
            ["📊 Tổng quan", "⚙️ Quản lý", "🔎 Phân tích"],
            horizontal=True,
            key="ndt_dp_mode",
        )

        if che_do == "📊 Tổng quan":
            _render_tong_quan(ds_all)
        elif che_do == "⚙️ Quản lý":
            ct_label = st.radio(
                "Chương trình",
                options=[_label_ct(3), _label_ct(6)],
                horizontal=True,
                key="ndt_dp_manage_ct",
            )
            ma_ct = 3 if "CT 03" in str(ct_label) else 6
            _render_quan_ly_ct(ma_ct, can_edit, username)
        else:
            _render_phan_tich()

        st.divider()
        col_xl, col_rf = st.columns([3, 1])
        with col_xl:
            df_export = _df_rules(ds_all)
            buf = BytesIO()
            df_export.to_excel(buf, index=False)
            st.download_button(
                "📥 Xuất danh sách Excel",
                data=buf.getvalue(),
                file_name="danh_sach_ndt_dp.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_ndt_dp_all",
            )
        with col_rf:
            if st.button(
                "🔄 Làm mới",
                key="btn_refresh_ndt_dp",
                use_container_width=True,
                help="Xóa cache và tải lại dữ liệu liên quan",
            ):
                st.cache_data.clear()
                st.rerun()
