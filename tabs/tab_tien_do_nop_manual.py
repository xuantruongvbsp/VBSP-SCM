"""UI đánh dấu thủ công cho tab Tiến độ nộp báo cáo."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from services.report_submission_service import (
    doc_manual_log_raw,
    luu_manual_override,
    xoa_manual_override,
)


def _fmt_ngay(value) -> str:
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def _fmt_thoi_gian(value) -> str:
    if not value:
        return "—"
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value or "—")


def render_manual_override(
    df: pd.DataFrame,
    ds_pgd_scope: list[str],
    ds_loai: list[str],
    username: str,
    can_config: bool,
) -> None:
    """Render khối đánh dấu thủ công, chỉ hiện với quyền cấu hình CN."""
    if not can_config:
        return

    st.divider()
    st.markdown("### ✏️ Đánh dấu thủ công")
    st.caption("Dùng khi PGD gửi báo cáo ngoài Google Form (email, Zip...)")

    manual_ds = doc_manual_log_raw()
    ds_loai_gsheet = (
        sorted(df["loai_bao_cao"].dropna().unique().tolist())
        if df is not None and not df.empty and "loai_bao_cao" in df.columns
        else []
    )
    ds_loai_manual = sorted(set(ds_loai) | set(ds_loai_gsheet))

    col_pgd, col_loai, col_ngay = st.columns([2, 2, 1.5])
    with col_pgd:
        pgd_manual = st.selectbox("PGD", ds_pgd_scope, key="man_pgd")
    with col_loai:
        loai_manual = st.selectbox("Loại BC", ds_loai_manual, key="man_loai")
    with col_ngay:
        ngay_manual = st.date_input(
            "Ngày nộp",
            value=date.today(),
            format="DD/MM/YYYY",
            key="man_ngay",
        )

    col_note, col_opt = st.columns([4, 2])
    with col_note:
        ghi_chu_manual = st.text_input(
            "Ghi chú (tùy chọn)",
            placeholder="VD: Nộp qua email, thiếu file BCTC",
            key="man_ghi_chu",
        )
    with col_opt:
        st.write("")
        ghi_de_manual = st.checkbox(
            "Ghi đè trạng thái trên ma trận",
            value=True,
            key="man_ghi_de",
            help="Bỏ chọn nếu chỉ muốn lưu ghi chú, không thay đổi trạng thái 🟢/🟡/🔴",
        )

    col_btn, _ = st.columns([1, 5])
    with col_btn:
        if st.button("✅ Đánh dấu", key="man_btn", type="primary", use_container_width=True):
            luu_manual_override(
                {
                    "pgd": pgd_manual,
                    "loai": loai_manual,
                    "ngay_nop": ngay_manual.strftime("%Y-%m-%d"),
                    "ghi_chu": ghi_chu_manual.strip(),
                    "ghi_de": ghi_de_manual,
                },
                username,
                manual_ds,
                ly_do=ghi_chu_manual.strip() or "Đánh dấu thủ công từ UI",
            )
            st.success(f"✅ Đã đánh dấu: **{pgd_manual}** — **{loai_manual}**")
            st.rerun()

    match_form = df[(df["ten_pgd"] == pgd_manual) & (df["loai_bao_cao"] == loai_manual)]
    if not match_form.empty and ghi_de_manual:
        lan_cuoi = match_form.sort_values("thoi_gian").iloc[-1]
        ngay_form = pd.to_datetime(lan_cuoi["thoi_gian"]).strftime("%d/%m/%Y")
        st.warning(
            f"⚠️ **{pgd_manual}** đã nộp **{loai_manual}** qua Google Form "
            f"vào **{ngay_form}**. Đánh dấu sẽ ghi đè trạng thái này trên ma trận."
        )

    if manual_ds:
        st.divider()
        st.caption(f"📌 {len(manual_ds)} đánh dấu thủ công hiện tại:")
        for i, entry in enumerate(manual_ds):
            e_pgd = entry.get("pgd", "?")
            e_loai = entry.get("loai", "?")
            e_note = entry.get("ghi_chu", "")
            e_gde = entry.get("ghi_de", True)
            e_user = entry.get("username_cap_nhat") or entry.get("username_tao") or "?"
            e_luc = entry.get("cap_nhat_luc") or entry.get("tao_luc") or ""
            loai_str = "* ghi đè" if e_gde else "📝 ghi chú"

            c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
            with c1:
                st.write(f"**{e_pgd}**")
            with c2:
                st.write(f"{e_loai} — {_fmt_ngay(entry.get('ngay_nop', '?'))} ({loai_str})")
            with c3:
                st.write(e_note if e_note else "—")
                st.caption(f"{e_user} · {_fmt_thoi_gian(e_luc)}")
            with c4:
                if st.button("↩️ Bỏ", key=f"man_del_{i}", use_container_width=True):
                    xoa_manual_override(i, username, manual_ds, ly_do="Bỏ đánh dấu từ UI")
                    st.success(f"✅ Đã bỏ: **{e_pgd}** — **{e_loai}**")
                    st.rerun()
