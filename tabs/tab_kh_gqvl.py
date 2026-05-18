"""
Tab Kế hoạch GQVL Chi nhánh — nhập KH GQVL theo năm, phân tầng TW/ĐP.
Lưu vào kv_store key "kh_gqvl_cn_{nam}".
"""
from __future__ import annotations

import subprocess
from datetime import datetime

import streamlit as st

import db
from auth import la_phan_he_cn, normalize_role
from config import DS_PGD
from data.pgd import pgd_slug


def render(role: str = None, **kwargs) -> None:
    username = st.session_state.get("username", "unknown")

    st.markdown("## 📋 Kế hoạch GQVL Chi nhánh")
    st.caption("Nhập kế hoạch GQVL toàn Chi nhánh theo nguồn vốn TW và ĐP.")

    nam = st.selectbox(
        "Năm kế hoạch",
        [datetime.now().year, datetime.now().year + 1],
        key="kh_gqvl_nam",
    )

    role_n = normalize_role(str(role or "user"))
    co_quyen = la_phan_he_cn(role_n) and role_n != "executive"
    kh_data = db.doc_kv(f"kh_gqvl_cn_{nam}") or {"pgd": {}}

    if not co_quyen:
        st.info("Bạn chỉ có quyền xem.")
        _hien_thi_bang_readonly(kh_data, nam)
        return

    with st.form(f"form_kh_gqvl_{nam}"):
        st.markdown("##### Nhập kế hoạch theo PGD (triệu đồng)")

        col_labels = st.columns([3, 2, 2, 2])
        col_labels[0].markdown("**Tên PGD**")
        col_labels[1].markdown("**KH TW**")
        col_labels[2].markdown("**KH ĐP**")
        col_labels[3].markdown("**Tổng**")

        tong_tw_all = 0
        tong_dp_all = 0

        for ten_pgd in DS_PGD:
            slug = pgd_slug(ten_pgd)
            kh_pgd = kh_data.get("pgd", {}).get(ten_pgd, {})
            val_tw_trieu = int(kh_pgd.get("kh_tw", 0)) // 1_000_000
            val_dp_trieu = int(kh_pgd.get("kh_dp", 0)) // 1_000_000

            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
            with col1:
                st.text(ten_pgd)
            with col2:
                kh_tw = st.number_input(
                    "KH TW",
                    min_value=0,
                    step=100,
                    format="%d",
                    key=f"kh_tw_{slug}_{nam}",
                    value=val_tw_trieu,
                    label_visibility="collapsed",
                )
            with col3:
                kh_dp = st.number_input(
                    "KH ĐP",
                    min_value=0,
                    step=100,
                    format="%d",
                    key=f"kh_dp_{slug}_{nam}",
                    value=val_dp_trieu,
                    label_visibility="collapsed",
                )
            with col4:
                st.metric("Tổng", f"{kh_tw + kh_dp:,}", label_visibility="collapsed")

            tong_tw_all += kh_tw
            tong_dp_all += kh_dp

        st.divider()
        tc1, tc2, tc3, tc4 = st.columns([3, 2, 2, 2])
        with tc1:
            st.markdown("**TỔNG CỘNG**")
        with tc2:
            st.markdown(f"**{tong_tw_all:,}**")
        with tc3:
            st.markdown(f"**{tong_dp_all:,}**")
        with tc4:
            st.markdown(f"**{tong_tw_all + tong_dp_all:,}**")

        submitted = st.form_submit_button("💾 Lưu kế hoạch GQVL", type="primary")

    if submitted:
        pgd_map = {}
        for ten_pgd in DS_PGD:
            slug = pgd_slug(ten_pgd)
            val_tw = st.session_state.get(f"kh_tw_{slug}_{nam}", 0) * 1_000_000
            val_dp = st.session_state.get(f"kh_dp_{slug}_{nam}", 0) * 1_000_000
            pgd_map[ten_pgd] = {"kh_tw": int(val_tw), "kh_dp": int(val_dp)}

        kh_new = {
            "pgd": pgd_map,
            "updated_by": username,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "nam": nam,
        }
        db.ghi_kv(f"kh_gqvl_cn_{nam}", kh_new, username)
        db.ghi_audit(username, "luu_kh_gqvl_cn", f"Năm {nam}, {len(pgd_map)} PGD")
        st.success(f"✅ Đã lưu kế hoạch GQVL năm {nam}.")
        st.cache_data.clear()

    st.divider()
    st.subheader("📤 Đẩy lên Google Sheet")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📊 Push TH lên GSheet", key="btn_push_th_gqvl"):
            subprocess.Popen(["python", "gen_dcgiam_sheet.py", "--th"])
            st.info("Đang push TH... Kiểm tra terminal để xem kết quả.")
    with col_b:
        if st.button("📋 Push KH lên GSheet", key="btn_push_kh_gqvl"):
            subprocess.Popen(["python", "gen_dcgiam_sheet.py", "--kh", "--nam", str(nam)])
            st.info("Đang push KH... Kiểm tra terminal để xem kết quả.")


def _hien_thi_bang_readonly(kh_data: dict, nam: int) -> None:
    st.markdown(f"##### 📊 Kế hoạch GQVL năm {nam} (chỉ đọc)")
    pgd_map = kh_data.get("pgd", {})
    if not pgd_map:
        st.info(f"Chưa có kế hoạch GQVL năm {nam}.")
        return

    rows = []
    tong_tw = 0
    tong_dp = 0
    for ten_pgd in DS_PGD:
        info = pgd_map.get(ten_pgd, {})
        kh_tw = int(info.get("kh_tw", 0)) // 1_000_000
        kh_dp = int(info.get("kh_dp", 0)) // 1_000_000
        rows.append({"Tên PGD": ten_pgd, "KH TW (tr)": kh_tw, "KH ĐP (tr)": kh_dp, "Tổng (tr)": kh_tw + kh_dp})
        tong_tw += kh_tw
        tong_dp += kh_dp

    import pandas as pd
    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        width='stretch',
        hide_index=True,
        column_config={
            "KH TW (tr)": st.column_config.NumberColumn(format=",.0f"),
            "KH ĐP (tr)": st.column_config.NumberColumn(format=",.0f"),
            "Tổng (tr)": st.column_config.NumberColumn(format=",.0f"),
        },
    )

    updated_by = kh_data.get("updated_by", "—")
    updated_at = kh_data.get("updated_at", "—")
    st.caption(f"📅 Cập nhật: {updated_at} · Người cập nhật: {updated_by}")
