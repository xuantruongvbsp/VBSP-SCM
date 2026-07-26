"""Theo dõi tiến trình nhập liệu của PGD trên nhiều Google Sheet phân cấp.

Sheet có cấu trúc:
  - PGD header row: Col STT = Số La Mã (I, II, III...), Col tên = "PGD X"
  - Xã/phường row:  Col STT = số thập phân (1.0, 2.0...), Col tên = "Phường Y"
Admin cấu hình nhiều sheet, mỗi sheet có tên hiển thị riêng.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from auth import la_quan_ly_cn, normalize_role
from logger import get_logger
from tabs.base_tab import TabContext

from .data import (
    tim_credentials,
    doc_sheet,
    phan_nhom_pgd,
    tinh_tien_do,
    doc_ds_sheet,
    doc_builtin_visibility,
    cleanup_snapshots_cu,
)
from .constants import BUILTIN_MODULES
from .ui_overview import render_tong_quan
from .ui_detail import render_chi_tiet
from .ui_settings import render_cai_dat, render_quan_ly_danh_sach
from .ui_guide import render_huong_dan
from .ui_dieu_chinh import render_dieu_chinh_tang_truong
from .ui_trang_thai_chot import render_trang_thai_chot

logger = get_logger(__name__)

_SHEET_OPTIONS_STATE_KEY = "_ttdn_sheet_option_ids"


def _selection_needs_reset(
    selected: object,
    previous_option_ids: object,
    current_option_ids: tuple[str, ...],
) -> bool:
    """True khi state dropdown không còn khớp danh sách lựa chọn hiện tại."""
    if previous_option_ids != current_option_ids:
        return True
    return (
        not isinstance(selected, int)
        or selected < 0
        or selected >= len(current_option_ids)
    )


def _visible_sheet_entries(
    ds_sheet: list[dict],
) -> list[tuple[int, dict]]:
    """Giữ index gốc khi lọc các sheet đang bật."""
    return [
        (index, cfg)
        for index, cfg in enumerate(ds_sheet)
        if cfg.get("enabled", True)
    ]


def _deadline_badge(cfg: dict) -> str:
    from datetime import date as _date
    dl = cfg.get("deadline", "")
    if not dl:
        return ""
    try:
        d = _date.fromisoformat(dl)
        days = (d - _date.today()).days
        if days < 0:
            return f" 🔴 QH {abs(days)}d"
        if days <= 3:
            return f" 🟡 còn {days}d"
        return f" 📅 {d.strftime('%d/%m')}"
    except Exception:
        return ""


def _kiem_tra_ket_noi() -> tuple[bool, str]:
    try:
        cred_path = tim_credentials()
    except FileNotFoundError as e:
        return False, str(e)
    try:
        import gspread  # noqa: F401
    except ImportError:
        return False, "Thiếu thư viện gspread"
    return True, f"credentials.json tìm thấy ({cred_path.name})"


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role_n = normalize_role(role_raw)
    username = kwargs.get("username", st.session_state.get("username", "unknown"))

    ctx = TabContext(tab, **kwargs)
    with ctx:
        ok, msg = _kiem_tra_ket_noi()
        if not ok:
            st.error(f"🔴 **GSheet lỗi:** {msg}")
        else:
            st.success(f"🟢 **GSheet OK** — {msg}")

        st.subheader("📋 Theo dõi tiến trình nhập liệu PGD")

        ds_sheet = doc_ds_sheet()
        can_config = la_quan_ly_cn(role_n)

        # ── Chọn sheet — lọc module tích hợp theo visibility ─────────────
        vis = doc_builtin_visibility()
        visible_builtins = [m for m in BUILTIN_MODULES if vis.get(m["id"], True)]
        n_builtins = len(visible_builtins)
        visible_sheets = _visible_sheet_entries(ds_sheet)

        sheet_labels = [
            (
                cfg.get("ten_hien_thi")
                or cfg.get("sheet_tab", f"Sheet {original_index + 1}")
            )
            + _deadline_badge(cfg)
            for original_index, cfg in visible_sheets
        ]
        all_labels = [m["label"] for m in visible_builtins] + sheet_labels
        current_option_ids = tuple(
            [f"builtin:{m['id']}" for m in visible_builtins]
            + [
                (
                    f"sheet:{original_index}:"
                    f"{cfg.get('sheet_id', '')}:"
                    f"{cfg.get('sheet_tab', '')}"
                )
                for original_index, cfg in visible_sheets
            ]
        )

        if not all_labels:
            st.info(
                "⚙️ Chưa có module hoặc sheet nào đang bật. "
                "Bật lại module tích hợp hoặc thêm sheet theo dõi trong Cài đặt."
            )
            if can_config:
                with st.expander(
                    "⚙️ Quản lý danh sách theo dõi",
                    expanded=True,
                ):
                    render_quan_ly_danh_sach(ds_sheet, username, role_n)
                with st.expander(
                    "⚙️ Cài đặt sheet theo dõi nhập liệu",
                    expanded=True,
                ):
                    render_cai_dat(ds_sheet, username)
            return

        # Reset index nếu danh sách sheet thay đổi (vd: xóa sheet, ẩn module)
        _sel = st.session_state.get("ttdn_sheet_sel", 0)
        previous_option_ids = st.session_state.get(_SHEET_OPTIONS_STATE_KEY)
        if _selection_needs_reset(
            _sel,
            previous_option_ids,
            current_option_ids,
        ):
            st.session_state["ttdn_sheet_sel"] = 0
        st.session_state[_SHEET_OPTIONS_STATE_KEY] = current_option_ids

        if can_config:
            col_sel, col_ref, col_manage = st.columns([6, 1, 2])
        else:
            col_sel, col_ref = st.columns([5, 1])
        with col_sel:
            idx = st.selectbox(
                "📂 Chọn báo cáo để xem",
                range(len(all_labels)),
                format_func=lambda i: all_labels[i],
                key="ttdn_sheet_sel",
            )
        with col_ref:
            st.write("")
            if st.button(
                "🔄", key="ttdn_refresh", help="Làm mới dữ liệu",
                use_container_width=True,
            ):
                doc_sheet.clear()
                st.rerun()

        if can_config:
            with col_manage:
                st.write("")
                with st.popover("⚙️ Quản lý", use_container_width=True):
                    render_quan_ly_danh_sach(ds_sheet, username, role_n)

        # ── Nhánh module tích hợp sẵn ────────────────────────────────────
        if idx < n_builtins:
            module_id = visible_builtins[idx]["id"]

            if module_id == "khao_sat":
                from tabs import tab_theo_doi_khao_sat as _ks
                _ks.render(None, **kwargs)
            elif module_id == "dctt":
                render_dieu_chinh_tang_truong(username=username)
            elif module_id == "trang_thai_chot":
                render_trang_thai_chot(username=username)

            return

        # ── Nhánh sheet thông thường (offset = số module tích hợp) ───────
        # Cleanup stale session_state keys
        n_sheets = len(ds_sheet)
        for i in range(n_sheets, n_sheets + 50):
            for suffix in ("_ct_count",):
                st.session_state.pop(f"cd_{i}{suffix}", None)
            for sk in (f"cd_mig_{i}", f"cd_mig_{i}_ten"):
                st.session_state.pop(sk, None)

        df_td = pd.DataFrame()
        ds_ct: list[dict] = []
        ten_sheet = ""
        groups: dict[str, list[list]] = {}
        name_col_idx = 1
        sheet_id = ""
        sheet_tab = ""

        if not visible_sheets:
            st.info("⚙️ Chưa có sheet nào. Vào tab **⚙️ Cài đặt** để thêm.")
        else:
            _, cfg_sel = visible_sheets[idx - n_builtins]
            ten_sheet = all_labels[idx]
            ds_ct = cfg_sel.get("ds_chuong_trinh", [])
            deadline_str = cfg_sel.get("deadline", "")

            sheet_id = cfg_sel.get("sheet_id", "").strip()
            sheet_tab = cfg_sel.get("sheet_tab", "")
            name_col_idx = cfg_sel.get("name_col", 2) - 1

            if sheet_id:
                try:
                    with st.spinner(f"Đang đọc **{ten_sheet}**..."):
                        raw = doc_sheet(
                            sheet_id,
                            sheet_tab,
                            cfg_sel.get("header_row", 10),
                        )
                    groups = phan_nhom_pgd(
                        raw,
                        stt_idx=cfg_sel.get("stt_col", 1) - 1,
                        name_idx=name_col_idx,
                        loai=cfg_sel.get("loai_cau_truc", "phan_cap_stt"),
                        pgd_col_idx=cfg_sel.get("pgd_col", 1) - 1,
                    )
                    df_td = tinh_tien_do(groups, ds_ct)
                    n_con = sum(len(v) for v in groups.values())
                    from .constants import LOAI_LABEL
                    loai_label = LOAI_LABEL.get(
                        cfg_sel.get("loai_cau_truc", ""), "",
                    )
                    st.caption(
                        f"📅 Cache 5 phút · {len(groups)} đơn vị · "
                        f"{n_con} hàng · {loai_label}"
                    )
                except Exception as e:
                    logger.error(
                        "tab_theo_doi_nhap: %s", e, exc_info=True,
                    )
                    st.error(f"❌ Lỗi đọc sheet: {e}")
            else:
                st.warning(
                    "Sheet này chưa có Sheet ID. Vào Cài đặt để nhập."
                )

        # ── Tabs nội dung ──────────────────────────────────────────────────
        if can_config:
            t0, t1, t2, t3 = st.tabs([
                "📊 Tổng quan", "📋 Chi tiết", "⚙️ Cài đặt", "📖 Hướng dẫn",
            ])
        else:
            t0, t1, t3 = st.tabs([
                "📊 Tổng quan", "📋 Chi tiết", "📖 Hướng dẫn",
            ])
            t2 = None

        with t0:
            render_tong_quan(
                df_td, ds_ct, ten_sheet,
                pgd_groups=groups,
                name_idx=name_col_idx,
                sheet_id=sheet_id,
                sheet_tab=sheet_tab,
                username=username,
                deadline=deadline_str,
            )

        with t1:
            render_chi_tiet(
                df_td, ds_ct, username,
                pgd_groups=groups,
                name_idx=name_col_idx,
            )

        if t2 is not None:
            with t2:
                render_cai_dat(ds_sheet, username)

        with t3:
            render_huong_dan()

        # ── Cleanup định kỳ snapshot cũ (1 lần/session) ─────────────────────
        if not st.session_state.get("_ttdn_cleanup_done"):
            try:
                cleanup_snapshots_cu(90)
            except Exception:
                pass
            st.session_state["_ttdn_cleanup_done"] = True
