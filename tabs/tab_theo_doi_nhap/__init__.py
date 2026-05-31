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

from auth import normalize_role
from logger import get_logger
from utils import get_tab_context

from .data import (
    tim_credentials,
    doc_sheet,
    phan_nhom_pgd,
    tinh_tien_do,
    doc_ds_sheet,
    cleanup_snapshots_cu,
)
from .ui_overview import render_tong_quan
from .ui_detail import render_chi_tiet
from .ui_settings import render_cai_dat
from .ui_guide import render_huong_dan

logger = get_logger(__name__)


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

    ctx = get_tab_context(tab)
    with ctx:
        ok, msg = _kiem_tra_ket_noi()
        if not ok:
            st.error(f"🔴 **GSheet lỗi:** {msg}")
        else:
            st.success(f"🟢 **GSheet OK** — {msg}")

        st.subheader("📋 Theo dõi tiến trình nhập liệu PGD")

        ds_sheet = doc_ds_sheet()
        can_config = role_n in ("admin_cn", "manager_cn", "admin", "manager")

        # Cleanup stale session_state keys
        n_sheets = len(ds_sheet)
        for i in range(n_sheets, n_sheets + 50):
            for suffix in ("_ct_count",):
                st.session_state.pop(f"cd_{i}{suffix}", None)
            for sk in (f"cd_mig_{i}", f"cd_mig_{i}_ten"):
                st.session_state.pop(sk, None)

        # ── Chọn sheet ────────────────────────────────────────────────────
        df_td = pd.DataFrame()
        ds_ct: list[dict] = []
        ten_sheet = ""
        groups: dict[str, list[list]] = {}
        name_col_idx = 1
        sheet_id = ""
        sheet_tab = ""

        if not ds_sheet:
            st.info("⚙️ Chưa có sheet nào. Vào tab **⚙️ Cài đặt** để thêm.")
        else:
            labels = [
                cfg.get("ten_hien_thi") or cfg.get("sheet_tab", f"Sheet {i+1}")
                for i, cfg in enumerate(ds_sheet)
            ]
            col_sel, col_ref = st.columns([5, 1])
            with col_sel:
                idx = st.selectbox(
                    "📂 Chọn sheet theo dõi",
                    range(len(labels)),
                    format_func=lambda i: labels[i],
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

            cfg_sel = ds_sheet[idx]
            ten_sheet = labels[idx]
            ds_ct = cfg_sel.get("ds_chuong_trinh", [])

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

        # ── Tabs ───────────────────────────────────────────────────────────
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
