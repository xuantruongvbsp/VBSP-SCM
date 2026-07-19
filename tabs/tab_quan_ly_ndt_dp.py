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
    COT_TEN_CT,
    COT_TEN_NHA_DAU_TU,
    COT_TEN_PGD,
    COT_TONG_DU_NO,
)
from logger import get_logger
from utils import fmt_so, fmt_ty

logger = get_logger(__name__)

_CAP_OPTS = ["Cấp Tỉnh 🏛️", "Cấp Xã/Khác 🏘️"]
_CAP_TO = {"Cấp Tỉnh 🏛️": "tinh", "Cấp Xã/Khác 🏘️": "xa"}
_CAP_FROM = {"tinh": "Cấp Tỉnh 🏛️", "xa": "Cấp Xã/Khác 🏘️"}
_COL_SO_MON = "Số món"
_COL_SO_PGD = "Số PGD"
_COL_TONG_DU_NO = "Tổng dư nợ"
_COL_TEN_CT_VIEW = "Tên CT"
_COL_TEN_NDT_VIEW = "Tên NĐT"
_COL_PGD_PHAT_SINH = "PGD phát sinh"
_COL_DA_CO_RULE = "Đã có rule"
_COL_CHUONG_TRINH_VIEW = "Chương trình"
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


def _text_or_empty(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _first_non_empty(series: pd.Series) -> str:
    for value in series:
        text = _text_or_empty(value)
        if text:
            return text
    return ""


def _join_distinct_short(series: pd.Series, limit: int = 4) -> str:
    values = []
    for value in series:
        text = _text_or_empty(value)
        if text and text not in values:
            values.append(text)
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f" +{len(values) - limit}"


def _normalize_ma_ct(value) -> int | None:
    text = _text_or_empty(value)
    if not text:
        return None
    try:
        number = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    except Exception:
        return None
    if pd.isna(number):
        return None
    return int(number)


def _is_nguon_von_dp(value) -> bool:
    text = _text_or_empty(value).lower()
    if not text:
        return False
    compact = text.replace(" ", "")
    return compact in {"2", "2.0", "đp", "dp", "địaphương", "diaphuong"}


def _tong_du_no_series(df: pd.DataFrame) -> pd.Series:
    if COT_TONG_DU_NO in df.columns:
        return pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").fillna(0)
    du_no_th = (
        pd.to_numeric(df[COT_DU_NO_TH], errors="coerce").fillna(0)
        if COT_DU_NO_TH in df.columns
        else 0
    )
    du_no_qh = (
        pd.to_numeric(df[COT_DU_NO_QH], errors="coerce").fillna(0)
        if COT_DU_NO_QH in df.columns
        else 0
    )
    return du_no_th + du_no_qh


@st.cache_data(show_spinner=False, ttl=300)
def _quet_ma_tu_hstd(_df_full: pd.DataFrame | None, _ds_all: list[dict], ts: float = 0.0) -> pd.DataFrame:
    _ = ts
    df_full = _df_full
    ds_all = _ds_all
    required = {COT_NGUON_VON, COT_MA_CHUONG_TRINH, COT_MA_NHA_DAU_TU}
    if df_full is None or df_full.empty or not required.issubset(df_full.columns):
        return pd.DataFrame()

    cols = [
        col
        for col in (
            COT_NGUON_VON,
            COT_MA_CHUONG_TRINH,
            COT_MA_NHA_DAU_TU,
            COT_TEN_NHA_DAU_TU,
            COT_TEN_CT,
            COT_TEN_PGD,
            COT_TONG_DU_NO,
            COT_DU_NO_TH,
            COT_DU_NO_QH,
        )
        if col in df_full.columns
    ]
    df_work = df_full[cols].copy()
    df_work = df_work[df_work[COT_NGUON_VON].map(_is_nguon_von_dp)]
    if df_work.empty:
        return pd.DataFrame()

    df_work["_ma_ct"] = df_work[COT_MA_CHUONG_TRINH].map(_normalize_ma_ct)
    df_work["_ma_ndt"] = df_work[COT_MA_NHA_DAU_TU].map(_text_or_empty)
    df_work = df_work[
        df_work["_ma_ct"].isin(sorted(_CT_META))
        & df_work["_ma_ndt"].ne("")
    ].copy()
    if df_work.empty:
        return pd.DataFrame()

    df_work["_tong_du_no"] = _tong_du_no_series(df_work)
    agg_dict: dict = {
        _COL_SO_MON: ("_ma_ndt", "size"),
        _COL_SO_PGD: (COT_TEN_PGD, lambda s: len({_text_or_empty(x) for x in s if _text_or_empty(x)}))
        if COT_TEN_PGD in df_work.columns
        else ("_ma_ndt", "size"),
        _COL_TONG_DU_NO: ("_tong_du_no", "sum"),
    }
    if COT_TEN_CT in df_work.columns:
        agg_dict[_COL_TEN_CT_VIEW] = (COT_TEN_CT, _first_non_empty)
    if COT_TEN_NHA_DAU_TU in df_work.columns:
        agg_dict[_COL_TEN_NDT_VIEW] = (COT_TEN_NHA_DAU_TU, _first_non_empty)
    if COT_TEN_PGD in df_work.columns:
        agg_dict[_COL_PGD_PHAT_SINH] = (COT_TEN_PGD, _join_distinct_short)

    df_agg = (
        df_work.groupby(["_ma_ct", "_ma_ndt"], dropna=False)
        .agg(**agg_dict)
        .reset_index()
        .rename(columns={"_ma_ct": "Mã CT", "_ma_ndt": "Mã NĐT"})
    )
    if _COL_TEN_CT_VIEW not in df_agg.columns:
        df_agg[_COL_TEN_CT_VIEW] = df_agg["Mã CT"].map(lambda ma: _CT_META.get(int(ma), {}).get("label", ""))
    if _COL_TEN_NDT_VIEW not in df_agg.columns:
        df_agg[_COL_TEN_NDT_VIEW] = ""
    if _COL_PGD_PHAT_SINH not in df_agg.columns:
        df_agg[_COL_PGD_PHAT_SINH] = ""

    existing_exact = {
        (int(item.get("ma_ct", 0) or 0), _text_or_empty(item.get("ma", "")))
        for item in ds_all
        if item.get("ma_ct") is not None and _text_or_empty(item.get("ma", ""))
    }
    df_agg[_COL_DA_CO_RULE] = df_agg.apply(
        lambda row: (int(row["Mã CT"]), _text_or_empty(row["Mã NĐT"])) in existing_exact,
        axis=1,
    )
    df_agg[_COL_CHUONG_TRINH_VIEW] = df_agg.apply(
        lambda row: f"CT {int(row['Mã CT']):02d} — {_text_or_empty(row[_COL_TEN_CT_VIEW]) or _CT_META.get(int(row['Mã CT']), {}).get('label', '')}",
        axis=1,
    )
    df_agg = df_agg.sort_values(
        by=[_COL_DA_CO_RULE, _COL_TONG_DU_NO, _COL_SO_MON, "Mã CT", "Mã NĐT"],
        ascending=[True, False, False, True, True],
    ).reset_index(drop=True)
    return df_agg


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


def _render_tinh_trang_ma_moi(df_full: pd.DataFrame | None, ds_all: list[dict], ts_hstd: float = 0.0) -> int:
    df_scan = _quet_ma_tu_hstd(df_full, ds_all, ts_hstd)
    if df_scan.empty or _COL_DA_CO_RULE not in df_scan.columns:
        st.caption("Chưa phát hiện mã NĐT ĐP mới từ HSTD hiện tại.")
        return 0

    df_new = df_scan[~df_scan[_COL_DA_CO_RULE]].copy()
    so_ma_moi = len(df_new)
    if so_ma_moi == 0:
        st.success("Tất cả cặp Mã CT + Mã NĐT nguồn ĐP trong HSTD hiện tại đã có rule.")
        return 0

    tong_du_no_moi = float(df_new[_COL_TONG_DU_NO].sum())
    so_mon_moi = int(df_new[_COL_SO_MON].sum())
    so_pgd_anh_huong = int(df_new[_COL_SO_PGD].sum())

    st.warning(
        f"Còn **{fmt_so(so_ma_moi)}** cặp Mã CT + Mã NĐT mới, "
        f"ảnh hưởng **{fmt_ty(tong_du_no_moi)} triệu đồng** dư nợ."
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Mã mới cần gắn rule", fmt_so(so_ma_moi))
    c2.metric("Số món liên quan", fmt_so(so_mon_moi))
    c3.metric("Lượt PGD phát sinh", fmt_so(so_pgd_anh_huong))

    df_ct = (
        df_new.groupby(_COL_CHUONG_TRINH_VIEW, as_index=False)
        .agg(
            **{
                "Mã mới": ("Mã NĐT", "count"),
                "Số món": (_COL_SO_MON, "sum"),
                "Dư nợ (triệu đồng)": (_COL_TONG_DU_NO, "sum"),
            }
        )
        .sort_values("Dư nợ (triệu đồng)", ascending=False)
    )
    df_ct["Dư nợ (triệu đồng)"] = df_ct["Dư nợ (triệu đồng)"].apply(fmt_ty)

    df_top = df_new.head(8)[
        [
            _COL_CHUONG_TRINH_VIEW,
            "Mã NĐT",
            _COL_TEN_NDT_VIEW,
            _COL_PGD_PHAT_SINH,
            _COL_SO_MON,
            _COL_TONG_DU_NO,
        ]
    ].rename(
        columns={
            _COL_CHUONG_TRINH_VIEW: "Chương trình",
            _COL_TEN_NDT_VIEW: "Tên NĐT",
            _COL_PGD_PHAT_SINH: "PGD phát sinh",
            _COL_SO_MON: "Số món",
            _COL_TONG_DU_NO: "Dư nợ (triệu đồng)",
        }
    )
    df_top["Dư nợ (triệu đồng)"] = df_top["Dư nợ (triệu đồng)"].apply(fmt_ty)

    col_ct, col_top = st.columns([1, 2])
    with col_ct:
        st.markdown("###### Theo chương trình")
        st.dataframe(df_ct, hide_index=True, use_container_width=True, height=180)
    with col_top:
        st.markdown("###### Ưu tiên xử lý theo dư nợ")
        st.dataframe(df_top, hide_index=True, use_container_width=True, height=260)

    if st.button("Mở danh sách mã mới để gắn rule", key="btn_open_ndt_dp_new", type="primary"):
        st.session_state["ndt_dp_mode"] = "🆕 Mã mới từ HSTD"
        st.rerun()
    return so_ma_moi


def _render_ma_moi_tu_hstd(df_full: pd.DataFrame | None, ds_all: list[dict], can_edit: bool, username: str, ts_hstd: float = 0.0) -> None:
    st.markdown("##### 🆕 Mã mới từ HSTD chi tiết")
    st.caption("Quét các cặp `Mã CT + Mã NĐT` thuộc nguồn ĐP trong HSTD, hiện chỉ áp dụng cho CT 03 và CT 06.")

    if df_full is None or df_full.empty:
        st.info("Chưa có `df_full` để quét HSTD chi tiết.")
        return

    required = {COT_NGUON_VON, COT_MA_CHUONG_TRINH, COT_MA_NHA_DAU_TU}
    if not required.issubset(df_full.columns):
        st.warning("HSTD hiện tại thiếu một trong các cột: `Nguồn vốn`, `Mã chương trình`, `Mã nhà đầu tư`.")
        return

    df_scan = _quet_ma_tu_hstd(df_full, ds_all, ts_hstd)
    if df_scan.empty:
        st.info("Không tìm thấy dữ liệu nguồn ĐP thuộc CT 03/CT 06 trong HSTD hiện tại.")
        return

    df_new = df_scan[~df_scan[_COL_DA_CO_RULE]].copy()

    c1, c2, c3 = st.columns(3)
    c1.metric("Cặp mã ĐP quét được", fmt_so(len(df_scan)))
    c2.metric("Mã mới chưa cấu hình", fmt_so(len(df_new)))
    c3.metric("Dư nợ mã mới (triệu đồng)", fmt_ty(df_new[_COL_TONG_DU_NO].sum() if not df_new.empty else 0))

    if df_new.empty:
        st.success("Không còn mã NĐT mới nào cần gắn thuộc tính trong HSTD hiện tại.")
        return

    ct_options = ["Tất cả"] + list(dict.fromkeys(df_new[_COL_CHUONG_TRINH_VIEW].tolist()))
    ct_chon = st.selectbox("Lọc theo chương trình", ct_options, key="ndt_dp_hstd_ct")
    df_view = df_new.copy()
    if ct_chon != "Tất cả":
        df_view = df_view[df_view[_COL_CHUONG_TRINH_VIEW] == ct_chon].copy()

    df_view["Phát sinh"] = [
        f"{fmt_so(so_pgd)} PGD · {fmt_so(so_mon)} món · {fmt_ty(tong_du_no)} tr"
        for so_pgd, so_mon, tong_du_no in zip(
            df_view[_COL_SO_PGD],
            df_view[_COL_SO_MON],
            df_view[_COL_TONG_DU_NO],
        )
    ]
    df_view["Chọn"] = False
    df_view["Phân loại cấp"] = _CAP_OPTS[0]
    df_view["Ghi chú"] = df_view[_COL_TEN_NDT_VIEW].astype(str).str.strip()

    editor_cols = [
        "Chọn",
        _COL_CHUONG_TRINH_VIEW,
        "Mã NĐT",
        _COL_TEN_NDT_VIEW,
        "Phát sinh",
        "Phân loại cấp",
        "Ghi chú",
    ]
    df_editor = df_view[editor_cols].copy()

    with st.expander("Chi tiết phát sinh theo PGD", expanded=False):
        st.dataframe(
            df_view[
                [
                    _COL_CHUONG_TRINH_VIEW,
                    "Mã NĐT",
                    _COL_TEN_NDT_VIEW,
                    _COL_PGD_PHAT_SINH,
                    _COL_SO_PGD,
                    _COL_SO_MON,
                    _COL_TONG_DU_NO,
                ]
            ].assign(**{_COL_TONG_DU_NO: lambda x: x[_COL_TONG_DU_NO].apply(fmt_ty)}),
            hide_index=True,
            use_container_width=True,
        )

    if not can_edit:
        st.warning("⚠️ Chỉ Admin CN mới có thể gắn thuộc tính và lưu các mã mới từ HSTD.")
        st.dataframe(
            df_editor.drop(columns=["Chọn", "Phân loại cấp", "Ghi chú"]),
            hide_index=True,
            use_container_width=True,
        )
        return

    edited = st.data_editor(
        df_editor,
        hide_index=True,
        use_container_width=True,
        key="ndt_dp_hstd_editor",
        disabled=[_COL_CHUONG_TRINH_VIEW, "Mã NĐT", _COL_TEN_NDT_VIEW, "Phát sinh"],
        column_config={
            "Chọn": st.column_config.CheckboxColumn("Chọn"),
            "Phân loại cấp": st.column_config.SelectboxColumn("Phân loại cấp", options=_CAP_OPTS, required=True),
            "Ghi chú": st.column_config.TextColumn("Ghi chú", help="Có thể sửa lại tên/diễn giải trước khi lưu"),
        },
    )

    if not st.button("💾 Lưu các mã đã chọn", key="btn_luu_ndt_dp_hstd", type="primary"):
        return

    df_selected = edited[edited["Chọn"] == True].copy()
    if df_selected.empty:
        st.warning("Vui lòng chọn ít nhất 1 mã để lưu.")
        return

    ds_moi = list(ds_all)
    existing_exact = {
        (int(item.get("ma_ct", 0) or 0), _text_or_empty(item.get("ma", "")))
        for item in ds_all
        if item.get("ma_ct") is not None and _text_or_empty(item.get("ma", ""))
    }
    added_labels: list[str] = []

    for _, row in df_selected.iterrows():
        chuong_trinh = _text_or_empty(row[_COL_CHUONG_TRINH_VIEW])
        try:
            ma_ct = int(chuong_trinh[3:5])
        except Exception:
            continue
        ma_ndt = _text_or_empty(row["Mã NĐT"])
        cap_label = _text_or_empty(row["Phân loại cấp"])
        if not ma_ndt or cap_label not in _CAP_TO:
            continue
        if (ma_ct, ma_ndt) in existing_exact:
            continue
        ds_moi.append(
            {
                "ma_ct": ma_ct,
                "ma": ma_ndt,
                "ghi_chu": _text_or_empty(row["Ghi chú"]),
                "cap": _CAP_TO[cap_label],
            }
        )
        existing_exact.add((ma_ct, ma_ndt))
        added_labels.append(f"CT{ma_ct:02d}:{ma_ndt}")

    if not added_labels:
        st.warning("Không có mã mới hợp lệ để lưu. Có thể các mã này đã được cấu hình trước đó.")
        return

    db.luu_ndt_dp_rule_list(ds_moi, username)
    db.ghi_audit(
        username,
        "them_ndt_dp_tu_hstd",
        f"Thêm {len(added_labels)} mã NĐT ĐP từ HSTD: {', '.join(added_labels[:8])}"
        + ("..." if len(added_labels) > 8 else ""),
    )
    st.cache_data.clear()
    st.success(f"✅ Đã lưu {len(added_labels)} mã mới từ HSTD.")
    st.rerun()


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
    st.cache_data.clear()
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
            st.cache_data.clear()
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
            st.cache_data.clear()
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
    df_full = kwargs.get("df_full", kwargs.get("df"))
    ts_hstd = float(kwargs.get("ts_hstd", 0.0))

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

        mode_options = ["📊 Tổng quan", "🆕 Mã mới từ HSTD", "⚙️ Quản lý", "🔎 Phân tích"]
        so_ma_moi = _render_tinh_trang_ma_moi(df_full, ds_all, ts_hstd)
        auto_open_key = "ndt_dp_auto_opened_new"
        if so_ma_moi > 0 and not st.session_state.get(auto_open_key):
            st.session_state["ndt_dp_mode"] = "🆕 Mã mới từ HSTD"
            st.session_state[auto_open_key] = True

        che_do = st.radio(
            "Chế độ",
            mode_options,
            horizontal=True,
            key="ndt_dp_mode",
        )

        if che_do == "📊 Tổng quan":
            _render_tong_quan(ds_all)
        elif che_do == "🆕 Mã mới từ HSTD":
            _render_ma_moi_tu_hstd(df_full, ds_all, can_edit, username, ts_hstd)
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
