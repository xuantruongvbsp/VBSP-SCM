"""Quản lý danh sách nợ đến hạn phân kỳ nhà ở xã hội (SKKU/NSVC/GQVL)."""
from __future__ import annotations

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import pandas as pd

import db
from auth import la_phan_he_cn, normalize_role
from config import PGD_XA_MAP
from data.phan_ky_nxh import doc_phan_ky_nxh, luu_phan_ky_nxh
from utils import fmt_ty, fmt_so


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")

    ctx = tab if tab is not None else st.container()
    with ctx:
        if not la_phan_he_cn(role):
            st.warning("⚠️ Chức năng dành riêng cho cán bộ Chi nhánh.")
            return

        st.subheader("🏠 Phân kỳ Nhà ở Xã hội — Nợ đến hạn")

        # ── Expander 1: Upload ─────────────────────────────────────────────────
        with st.expander("📤 Upload danh sách", expanded=True):
            meta = db.doc_kv("phan_ky_nxh_meta")
            if meta:
                from datetime import datetime
                try:
                    ngay_up = datetime.fromisoformat(meta.get("ngay_upload", "")).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    ngay_up = meta.get("ngay_upload", "")
                st.info(
                    f"📋 Lần upload gần nhất: **{ngay_up}** | "
                    f"**{fmt_so(meta.get('so_dong', 0))}** khoản | "
                    f"Người upload: **{meta.get('nguoi_upload', '')}**"
                )
            else:
                st.caption("Chưa có dữ liệu — hãy upload file Excel.")

            st.caption(
                "📂 Lấy file từ TTBC: "
                "**Báo cáo theo truy vấn** → **Nhóm BC tín dụng** "
                "→ **Sao kê nợ đến hạn kỳ con theo chương trình vay**"
            )

            uploaded = st.file_uploader(
                "Chọn file Excel danh sách phân kỳ NXH",
                type=["xlsx"],
                key="phan_ky_nxh_uploader",
                help="File xuất từ TTBC: Báo cáo theo truy vấn / Nhóm BC tín dụng / Sao kê nợ đến hạn kỳ con theo chương trình vay",
            )
            if uploaded is not None:
                if st.button("💾 Xử lý & Lưu", key="phan_ky_nxh_btn_luu", type="primary"):
                    with st.spinner("Đang xử lý file lớn, vui lòng chờ..."):
                        ok, msg = luu_phan_ky_nxh(uploaded.read(), username)
                    if ok:
                        st.success(msg)
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(msg)

        # ── Expander 2: Phân công Cán bộ theo Xã/Phường ──────────────────────
        with st.expander("👤 Phân công Cán bộ theo Xã/Phường", expanded=False):
            can_bo_map: dict = db.doc_kv("nxh_can_bo_xa") or {}

            # Tóm tắt hiện trạng phân công
            so_xa_da_phan = sum(1 for v in can_bo_map.values() if v.strip())
            if so_xa_da_phan:
                st.caption(f"Đã phân công: **{so_xa_da_phan}** xã/phường có cán bộ phụ trách.")
            else:
                st.caption("Chưa có xã/phường nào được phân công cán bộ.")

            # Danh sách PGD từ config — đầy đủ, không phụ thuộc file upload
            ds_pgd = list(PGD_XA_MAP.keys())
            pgd_sel = st.selectbox(
                "Chọn PGD để phân công cán bộ",
                options=["— Chọn PGD —"] + ds_pgd,
                key="nxh_cb_pgd_sel",
            )

            if pgd_sel and pgd_sel != "— Chọn PGD —":
                # Xã/phường theo PGD từ config — đúng và đầy đủ
                ds_xa = PGD_XA_MAP.get(pgd_sel, [])

                if not ds_xa:
                    st.caption("PGD này chưa có danh sách xã/phường trong cấu hình.")
                else:
                    st.caption(f"{pgd_sel} — {len(ds_xa)} xã/phường")
                    new_map = dict(can_bo_map)
                    changed = False
                    cols_cb = st.columns(2)
                    for i, xa in enumerate(ds_xa):
                        with cols_cb[i % 2]:
                            val = st.text_input(
                                xa,
                                value=can_bo_map.get(xa, ""),
                                placeholder="Họ tên cán bộ...",
                                key=f"nxh_cb_{i}_{pgd_sel}",
                            )
                            new_map[xa] = val.strip()
                            if val.strip() != can_bo_map.get(xa, ""):
                                changed = True

                    if st.button("💾 Lưu phân công", key="nxh_cb_save", type="primary", disabled=not changed):
                        db.ghi_kv("nxh_can_bo_xa", new_map, username)
                        db.ghi_audit(username, "luu_nxh_can_bo_xa",
                                     f"Phân công cán bộ NXH: {pgd_sel} — {len(ds_xa)} xã")
                        st.success("✅ Đã lưu phân công.")
                        st.rerun()

                    if not changed:
                        st.caption("Thay đổi nội dung để kích hoạt nút Lưu.")

        # ── Expander 3: Xem danh sách tháng hiện tại ──────────────────────────
        with st.expander("📋 Danh sách tháng hiện tại", expanded=True):
            df = doc_phan_ky_nxh()
            if df.empty:
                st.warning("⚠️ Chưa có dữ liệu — hãy upload file Excel ở trên.")
                return

            today = pd.Timestamp.today()
            first_day = today.replace(day=1)
            last_day  = first_day + pd.offsets.MonthEnd(0)

            COL_NGAY = "Ngày đến hạn kỳ con"
            COL_TIEN = "Dư nợ kỳ con đến hạn"
            COL_PGD  = "Tên PGD"
            COL_GHICHU = "Ghi chú"

            # Bộ lọc tháng — mặc định tháng hiện tại
            thang_hien = today.strftime("%m/%Y")
            col_f1, col_f2 = st.columns([2, 2])
            with col_f1:
                thang_chon = st.selectbox(
                    "Lọc theo tháng đến hạn",
                    options=["Tháng hiện tại", "3 tháng tới", "6 tháng tới", "Tất cả"],
                    key="nxh_filter_thang",
                )

            if thang_chon == "Tháng hiện tại":
                mask = df[COL_NGAY].notna() & (df[COL_NGAY] >= first_day) & (df[COL_NGAY] <= last_day)
            elif thang_chon == "3 tháng tới":
                end_3m = first_day + pd.DateOffset(months=3) - pd.Timedelta(days=1)
                mask = df[COL_NGAY].notna() & (df[COL_NGAY] >= first_day) & (df[COL_NGAY] <= end_3m)
            elif thang_chon == "6 tháng tới":
                end_6m = first_day + pd.DateOffset(months=6) - pd.Timedelta(days=1)
                mask = df[COL_NGAY].notna() & (df[COL_NGAY] >= first_day) & (df[COL_NGAY] <= end_6m)
            else:
                mask = df[COL_NGAY].notna()

            df_thang = df[mask].sort_values(COL_NGAY).reset_index(drop=True)

            if df_thang.empty:
                st.info(f"ℹ️ Không có khoản nào đến hạn ({thang_chon.lower()}).")
                return

            # Metrics
            tong_khoan = len(df_thang)
            tong_tien  = df_thang[COL_TIEN].sum() if COL_TIEN in df_thang.columns else 0
            so_pgd     = df_thang[COL_PGD].nunique() if COL_PGD in df_thang.columns else 0
            so_canh_bao = (
                df_thang[COL_GHICHU].astype(str).str.strip().ne("").sum()
                if COL_GHICHU in df_thang.columns else 0
            )

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tổng khoản đến hạn", fmt_so(tong_khoan))
            c2.metric("Tổng dư nợ (triệu)", fmt_ty(tong_tien))
            c3.metric("Số PGD có khoản", str(so_pgd))
            c4.metric("⚠️ Có cảnh báo", fmt_so(so_canh_bao))

            # Filter theo PGD
            with col_f2:
                if COL_PGD in df_thang.columns:
                    ds_pgd_opt = ["Tất cả"] + sorted(df_thang[COL_PGD].dropna().unique().tolist())
                    pgd_chon = st.selectbox("Lọc theo PGD", ds_pgd_opt, key="nxh_filter_pgd")
                    if pgd_chon != "Tất cả":
                        df_thang = df_thang[df_thang[COL_PGD] == pgd_chon]

            # Chuẩn bị hiển thị
            cols_hien = [c for c in [
                COL_PGD,
                "Tên xã",
                "Tên tổ trưởng",
                "Tên khách hàng",
                "Số khế ước",
                COL_NGAY,
                COL_TIEN,
                "Tổng TG, TK",
                "Số thứ tự kỳ trả",
                "Số điện thoại",
                COL_GHICHU,
            ] if c in df_thang.columns]

            df_show = df_thang[cols_hien].copy()

            if COL_NGAY in df_show.columns:
                df_show[COL_NGAY] = df_show[COL_NGAY].dt.strftime("%d/%m/%Y")
            for col_tien in [COL_TIEN, "Tổng TG, TK"]:
                if col_tien in df_show.columns:
                    df_show[col_tien] = df_show[col_tien].apply(fmt_ty)

            st.caption(f"{thang_chon} — {fmt_so(len(df_show))} khoản")
            st.dataframe(df_show, use_container_width=True, hide_index=True)
