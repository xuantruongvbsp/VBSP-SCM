"""Tiến độ nộp báo cáo định kỳ của các PGD — đọc từ Google Sheets."""


from __future__ import annotations

from logger import get_logger
logger = get_logger(__name__)

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn, normalize_role
from config import DS_PGD, DON_VI_CHI_NHANH
from tabs.base_tab import TabContext
from utils import xuat_excel

# ── Import từ service lõi (single source of truth) ──
from services.report_submission_service import (
    SHEET_ID,
    SHEET_TAB,
    COT,
    DS_PGD_ALL,
    EMOJI,
    LABEL,
    _tim_credentials,
    _ket_noi_gsheet,
    chuan_hoa_ten_pgd,
    doc_du_lieu_gsheet,
    doc_deadline_config,
    luu_deadline_config,
    phan_loai_trang_thai,
    gan_trang_thai,
    doc_manual_log,
    doc_manual_log_raw,
    luu_manual_log,
    lay_pgd_chua_nop,
    kiem_tra_suc_khoe_nguon,
    kiem_tra_ket_noi_gsheet,
    lay_loi_doc_gsheet_gan_nhat,
    phat_hien_ten_lech_ten,
    doi_ten_loai_theo_doi,
    dong_bo_tat_ca_ten_theo_form,
    tao_ma_tran_tien_do,
    xay_dung_danh_muc_theo_doi,
)

# ── UI constants ──
_EMOJI_STRIP = ("🟢", "🟡", "🔴", "⚪", "⚠️", "📝")

def _clean_trang_thai(val: str) -> str:
    """Bỏ emoji + badge cho PDF — thiếu file / trễ hạn."""
    if "⚠️" in str(val):
        return "Thiếu file"
    text = str(val)
    for ch in _EMOJI_STRIP:
        text = text.replace(ch, "")
    return text.replace("*", "").strip()

def _clear_export_cache():
    """Xóa bytes export cũ khi user đổi filter — tránh tải nhầm file."""
    for k in ["_don_doc_bytes", "_don_doc_ten",
              "_dd_pdf_bytes", "_dd_pdf_bytes__ten",
              "_dd_pdf_dv_bytes", "_dd_pdf_dv_bytes__ten"]:
        st.session_state.pop(k, None)


# ── GSheet data (cached wrapper) ────────────────────────────────────────────

@st.cache_data(ttl=300)
def _doc_du_lieu() -> pd.DataFrame:
    """Đọc dữ liệu GSheet có cache 5 phút — dùng trong UI."""
    return doc_du_lieu_gsheet()


# ── Tab 1: Tổng quan ──────────────────────────────────────────────────────────

def _render_tong_quan(df: pd.DataFrame, deadline_cfg: dict, is_cn: bool, pgd_user: str | None, username: str, can_config: bool) -> None:
    if df.empty:
        st.info("Chưa có dữ liệu từ Google Sheets.")
        return

    if not deadline_cfg:
        st.info("ℹ️ Chưa có thời hạn hoàn thành nào được cài đặt. Vào tab **⚙️ Cài đặt thời hạn** để thêm.")
        return

    ds_loai_gsheet_hint = sorted(df["loai_bao_cao"].dropna().unique().tolist()) if not df.empty else []
    dm = xay_dung_danh_muc_theo_doi(deadline_cfg, ds_loai_gsheet_hint)
    ds_lech = phat_hien_ten_lech_ten(deadline_cfg, ds_loai_gsheet_hint)
    if ds_lech and can_config:
        n_co_goi_y = sum(1 for x in ds_lech if x.get("ten_form"))
        st.warning(
            f"⚠️ **{len(ds_lech)}** loại đang theo dõi chưa khớp tên Google Form"
            + (f" ({n_co_goi_y} có gợi ý liên kết)" if n_co_goi_y else "")
            + " — hệ thống đang tự ghép tạm theo tên Form khi đủ rõ, nhưng vẫn nên vào **⚙️ Cài đặt thời hạn** để **🔗 Liên kết**."
        )

    # Chỉ hiển thị loại báo cáo có thời hạn — xóa thời hạn là không còn theo dõi
    ds_loai = dm["display_keys"]
    deadline_cfg_hien = dm["display_cfg"]
    ds_pgd_scope = [pgd_user] if (not is_cn and pgd_user) else DS_PGD_ALL

    rows, metrics = tao_ma_tran_tien_do(df, deadline_cfg, ds_pgd_scope)
    dung_han = metrics["dung_han"]
    tre = metrics["tre"]
    chua_nop = metrics["chua_nop"]
    thieu_file = metrics.get("thieu_file", 0)
    da_nop = metrics["da_nop"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Đã nộp (đơn vị × loại)", da_nop)
    c2.metric("🟢 Đúng hạn", dung_han)
    c3.metric("🟡 Trễ hạn", tre)
    c4.metric("⚠️ Thiếu file", thieu_file)
    c5.metric("🔴 Chưa nộp", chua_nop)

    st.divider()
    st.markdown("**Ma trận trạng thái — PGD × Loại báo cáo**")

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("* Ghi đè thủ công  ·  📝 Có ghi chú")

    ds_tat_ca = []
    ds_chua = []
    ds_da = []
    for r in rows:
        for loai in ds_loai:
            cell = str(r.get(loai, ""))
            dl = deadline_cfg_hien.get(loai, "")
            dl_hien = dl
            if dl:
                try:
                    dl_hien = pd.to_datetime(dl).strftime("%d/%m/%Y")
                except Exception:
                    dl_hien = dl
            entry = {
                "Đơn vị": r["Đơn vị"],
                "Loại báo cáo": loai,
                "Trạng thái": cell,
                "Thời hạn": dl_hien or "Chưa cài",
            }
            ds_tat_ca.append(entry)
            if "🔴" in cell or "⚠️" in cell:
                ds_chua.append(entry)
            elif "🟢" in cell or "🟡" in cell:
                ds_da.append(entry)

    st.divider()
    st.markdown("### 📥 Xuất báo cáo")

    loai_xuat = st.radio(
        "Chọn loại danh sách để xuất",
        ["Tất cả", "Đã hoàn thành", "Chưa hoàn thành"],
        horizontal=True,
        key="tq_loai_xuat",
        on_change=_clear_export_cache,
    )

    if loai_xuat == "Tất cả":
        ds_xuat = ds_tat_ca
    elif loai_xuat == "Đã hoàn thành":
        ds_xuat = ds_da
    else:
        ds_xuat = ds_chua

    if not ds_xuat:
        st.info(f"Không có báo cáo **{loai_xuat.lower()}**.")
    else:
        if loai_xuat == "Chưa hoàn thành":
            st.warning(f"⚠️ **{len(ds_xuat)} báo cáo chưa hoàn thành**")
        else:
            st.caption(f"📋 {len(ds_xuat)} báo cáo — **{loai_xuat}**")

        df_xuat_full = pd.DataFrame(ds_xuat)
        ds_pgd_thieu = ["Tất cả"] + sorted(df_xuat_full["Đơn vị"].unique().tolist())
        pgd_xuat = st.selectbox("Lọc đơn vị trước khi xuất", ds_pgd_thieu, key="dd_pgd_xuat", on_change=_clear_export_cache)
        df_xuat = df_xuat_full if pgd_xuat == "Tất cả" else df_xuat_full[df_xuat_full["Đơn vị"] == pgd_xuat]

        st.dataframe(df_xuat, hide_index=True, use_container_width=True)

        _slug_map = {"Tất cả": "tat_ca", "Đã hoàn thành": "da_hoan_thanh", "Chưa hoàn thành": "chua_hoan_thanh"}
        ten_file_goc = f"tien_do_{_slug_map.get(loai_xuat, 'xuat')}"
        username_xuat = st.session_state.get("username", "unknown")

        # Import 1 lần — tránh lặp trong từng handler
        from pdf_service import xuat_pdf, xuat_pdf_group_header

        # df đã clean emoji — dùng chung cho cả 2 loại PDF
        df_pdf_base = df_xuat.copy()
        if "Trạng thái" in df_pdf_base.columns:
            df_pdf_base["Trạng thái"] = df_pdf_base["Trạng thái"].apply(_clean_trang_thai)

        # df Excel — clean emoji cho nhất quán với file công vụ
        df_excel = df_xuat.copy()
        if "Trạng thái" in df_excel.columns:
            df_excel["Trạng thái"] = df_excel["Trạng thái"].apply(_clean_trang_thai)

        def _pdf_button(col, btn_label, btn_key, dl_key, file_name, generator_fn):
            """Helper dùng chung: nút generate → lưu session_state → nút download."""
            _ten_key = f"{dl_key}__ten"
            with col:
                if st.button(btn_label, key=btn_key, use_container_width=True, type="primary"):
                    try:
                        with st.spinner("Đang tạo PDF..."):
                            pdf_bytes = generator_fn()
                        st.session_state[dl_key] = pdf_bytes
                        st.session_state[_ten_key] = file_name
                    except Exception as e:
                        logger.error("%s: %s", btn_key, e, exc_info=True)
                        st.error(f"❌ Lỗi PDF: {e}")
                if st.session_state.get(dl_key):
                    st.download_button(
                        "⬇ Tải PDF",
                        data=st.session_state[dl_key],
                        file_name=st.session_state.get(_ten_key, file_name),
                        mime="application/pdf",
                        key=f"dl_{dl_key}",
                    )

        col_excel, col_pdf, col_pdf_dv, _ = st.columns([1, 1, 1.2, 3])

        with col_excel:
            if st.button("📥 Excel", key="btn_dd_excel", use_container_width=True, type="primary"):
                with st.spinner("Đang tạo Excel..."):
                    st.session_state["_don_doc_bytes"] = xuat_excel({f"Tiến độ — {loai_xuat}": df_excel})
                    st.session_state["_don_doc_ten"] = f"{ten_file_goc}.xlsx"
            if st.session_state.get("_don_doc_bytes"):
                st.download_button(
                    "⬇ Tải Excel",
                    data=st.session_state["_don_doc_bytes"],
                    file_name=st.session_state["_don_doc_ten"],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_don_doc",
                )

        _pdf_button(
            col=col_pdf,
            btn_label="📄 PDF",
            btn_key="btn_dd_pdf",
            dl_key="_dd_pdf_bytes",
            file_name=f"{ten_file_goc}.pdf",
            generator_fn=lambda: xuat_pdf(
                df_pdf_base,
                f"Tiến độ nộp báo cáo — {loai_xuat}",
                username_xuat,
                cols_tien=[],
                them_dong_tong=False,
            ),
        )

        _pdf_button(
            col=col_pdf_dv,
            btn_label="📊 PDF theo đơn vị",
            btn_key="btn_dd_pdf_dv",
            dl_key="_dd_pdf_dv_bytes",
            file_name=f"{ten_file_goc}_theo_don_vi.pdf",
            generator_fn=lambda: xuat_pdf_group_header(
                df_pdf_base,
                tieu_de=f"DANH SÁCH TIẾN ĐỘ NỘP BÁO CÁO — {loai_xuat.upper()}",
                nhom_theo="Đơn vị",
                nguoi_xuat=username_xuat,
                loai_van_ban="DANH SÁCH",
            ),
        )

    # ── Đánh dấu thủ công (chỉ admin CN) ────────────────────────────────────
    if can_config:
        st.divider()
        st.markdown("### ✏️ Đánh dấu thủ công")
        st.caption("Dùng khi PGD gửi báo cáo ngoài Google Form (email, Zip...)")

        manual_ds = doc_manual_log_raw()

        # Bao gồm cả loại BC từ GSheet (dù chưa có deadline) để hỗ trợ đánh dấu
        ds_loai_gsheet_manual = sorted(df["loai_bao_cao"].dropna().unique().tolist()) if not df.empty else []
        ds_loai_manual = sorted(set(ds_loai) | set(ds_loai_gsheet_manual))

        col_pgd, col_loai, col_ngay = st.columns([2, 2, 1.5])
        with col_pgd:
            pgd_manual = st.selectbox("PGD", ds_pgd_scope, key="man_pgd")
        with col_loai:
            loai_manual = st.selectbox("Loại BC", ds_loai_manual, key="man_loai")
        with col_ngay:
            ngay_manual = st.date_input("Ngày nộp", value=date.today(), format="DD/MM/YYYY", key="man_ngay")

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
                ds_moi = [e for e in manual_ds if not (e.get("pgd") == pgd_manual and e.get("loai") == loai_manual)]
                ds_moi.append({
                    "pgd": pgd_manual,
                    "loai": loai_manual,
                    "ngay_nop": ngay_manual.strftime("%Y-%m-%d"),
                    "ghi_chu": ghi_chu_manual.strip(),
                    "ghi_de": ghi_de_manual,
                    "username_tao": username,
                    "tao_luc": pd.Timestamp.now().isoformat(),
                })
                luu_manual_log(ds_moi, username)
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
                e_pgd  = entry.get("pgd", "?")
                e_loai = entry.get("loai", "?")
                e_ngay = entry.get("ngay_nop", "?")
                e_note = entry.get("ghi_chu", "")
                e_gde  = entry.get("ghi_de", True)
                try:
                    e_ngay_str = pd.to_datetime(e_ngay).strftime("%d/%m/%Y")
                except Exception:
                    e_ngay_str = str(e_ngay)
                loai_str = "* ghi đè" if e_gde else "📝 ghi chú"
                c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
                with c1:
                    st.write(f"**{e_pgd}**")
                with c2:
                    st.write(f"{e_loai} — {e_ngay_str} ({loai_str})")
                with c3:
                    st.write(e_note if e_note else "—")
                with c4:
                    if st.button("↩️ Bỏ", key=f"man_del_{i}", use_container_width=True):
                        ds_moi = [e for j, e in enumerate(manual_ds) if j != i]
                        luu_manual_log(ds_moi, username)
                        st.success(f"✅ Đã bỏ: **{e_pgd}** — **{e_loai}**")
                        st.rerun()


# ── Tab 2: Danh sách nộp ─────────────────────────────────────────────────────

def _render_danh_sach(df: pd.DataFrame, deadline_cfg: dict, is_cn: bool, pgd_user: str | None) -> None:
    if df.empty:
        st.info("Chưa có dữ liệu.")
        return

    col1, col2 = st.columns(2)
    with col1:
        ds_loai = ["Tất cả"] + sorted(df["loai_bao_cao"].dropna().unique().tolist())
        loai_chon = st.selectbox("Loại báo cáo", ds_loai, key="ds_loai")
    with col2:
        if is_cn:
            ds_don_vi = ["Tất cả"] + sorted(df["ten_pgd"].dropna().unique().tolist())
            pgd_chon = st.selectbox("Đơn vị", ds_don_vi, key="ds_pgd")
        else:
            pgd_chon = pgd_user or "Tất cả"
            st.caption(f"Đơn vị: **{pgd_chon}**")

    df_loc = df.copy()
    if loai_chon != "Tất cả":
        df_loc = df_loc[df_loc["loai_bao_cao"] == loai_chon]
    if pgd_chon and pgd_chon != "Tất cả":
        df_loc = df_loc[df_loc["ten_pgd"] == pgd_chon]

    df_loc, _ = gan_trang_thai(df_loc, deadline_cfg)
    df_loc["tt_hien"] = df_loc["tt"].map(lambda x: f"{EMOJI.get(x, '')} {LABEL.get(x, x)}")

    st.caption(f"Hiển thị {len(df_loc)} / {len(df)} lượt nộp")

    df_hien = df_loc[["thoi_gian", "ho_ten", "ten_pgd", "loai_bao_cao",
                       "tt_hien", "noi_dung", "file_dinh_kem"]].copy()
    df_hien["thoi_gian"] = df_hien["thoi_gian"].dt.strftime("%d/%m/%Y %H:%M")
    df_hien = df_hien.rename(columns={
        "thoi_gian": "Thời gian", "ho_ten": "Họ tên", "ten_pgd": "Đơn vị",
        "loai_bao_cao": "Loại", "tt_hien": "Trạng thái",
        "noi_dung": "Nội dung", "file_dinh_kem": "File",
    })
    st.dataframe(
        df_hien, use_container_width=True, hide_index=True,
        column_config={
            "File": st.column_config.LinkColumn("File", display_text="📎 Xem"),
            "Nội dung": st.column_config.TextColumn(width="large"),
        },
    )
    st.caption("💡 Nếu link Drive không mở được: PGD cần set quyền chia sẻ file là **\"Anyone with the link can view\"** trước khi paste vào Form.")

    st.divider()
    st.markdown("### 📥 Xuất báo cáo")
    loai_xuat_ds = st.radio(
        "Chọn trạng thái để xuất",
        ["Tất cả", "Đã hoàn thành", "Chưa hoàn thành"],
        horizontal=True,
        key="ds_loai_xuat",
    )
    if loai_xuat_ds == "Đã hoàn thành":
        df_xuat_ds = df_loc[df_loc["tt"].isin(["dung_han", "tre", "da_nop"])]
    elif loai_xuat_ds == "Chưa hoàn thành":
        df_xuat_ds = df_loc[df_loc["tt"] == "chua_nop"]
    else:
        df_xuat_ds = df_loc

    if df_xuat_ds.empty:
        st.info(f"Không có báo cáo **{loai_xuat_ds.lower()}**.")
    else:
        st.caption(f"📋 {len(df_xuat_ds)} lượt nộp — **{loai_xuat_ds}**")
        ten_file_ds = f"tien_do_nop_{loai_xuat_ds.replace(' ', '_').lower()}"
        col_excel, col_pdf, _ = st.columns([1, 1, 5])
        with col_excel:
            if st.button("📥 Xuất Excel", key="btn_xuat_tdn", use_container_width=True, type="primary"):
                df_export = df_xuat_ds.drop(columns=["tt", "tt_hien"], errors="ignore")
                st.session_state["_excel_tdn_bytes"] = xuat_excel({f"Tiến độ nộp — {loai_xuat_ds}": df_export})
                st.session_state["_excel_tdn_ten"] = f"{ten_file_ds}.xlsx"
        if st.session_state.get("_excel_tdn_bytes"):
            st.download_button(
                "⬇ Tải Excel",
                data=st.session_state["_excel_tdn_bytes"],
                file_name=st.session_state["_excel_tdn_ten"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_excel_tdn",
            )
        with col_pdf:
            from pdf_service import nut_xuat_pdf

            # Chuẩn bị DataFrame sạch cho PDF: bỏ cột nội bộ/URL dài, format datetime
            df_for_pdf = df_xuat_ds.drop(columns=["tt", "tt_hien", "file_dinh_kem", "email"], errors="ignore").copy()
            if "thoi_gian" in df_for_pdf.columns:
                df_for_pdf["thoi_gian"] = df_for_pdf["thoi_gian"].dt.strftime("%d/%m/%Y")
            if "noi_dung" in df_for_pdf.columns:
                df_for_pdf["noi_dung"] = df_for_pdf["noi_dung"].astype(str).str[:80]
            df_for_pdf = df_for_pdf.rename(columns={
                "thoi_gian":    "Thời gian",
                "ho_ten":       "Họ tên",
                "ten_pgd":      "Đơn vị",
                "loai_bao_cao": "Loại BC",
                "ky_bao_cao":   "Kỳ",
                "noi_dung":     "Nội dung",
            })

            nut_xuat_pdf(
                df_for_pdf,
                f"Tiến độ nộp báo cáo — {loai_xuat_ds}",
                st.session_state.get("username", "unknown"),
                cols_tien=[],
                prefix_file=ten_file_ds,
                key="pdf_tdn",
            )


# ── Tab 3: Cài đặt thời hạn hoàn thành ────────────────────────────────────────

def _render_canh_bao_lech_ten(
    deadline_cfg: dict,
    ds_loai_gsheet: list[str],
    username: str,
) -> None:
    """Cảnh báo tên theo dõi ≠ Google Form + nút liên kết một lần bấm."""
    ds_lech = phat_hien_ten_lech_ten(deadline_cfg, ds_loai_gsheet)
    if not ds_lech:
        return

    with st.container(border=True):
        st.markdown("#### ⚠️ Tên theo dõi chưa khớp Google Form")
        st.caption(
            "Ma trận Tổng quan và Telegram nhắc hạn so khớp **đúng từng chữ**. "
            "Nếu Form đổi tên (VD giai đoạn năm), hãy **liên kết** với tên trên Form."
        )
        ds_goi_y = [x for x in ds_lech if x.get("ten_form")]
        if ds_goi_y:
            if st.button(
                f"🔗 Chuẩn hóa tất cả ({len(ds_goi_y)} mục)",
                key="cd_link_all_form",
                type="primary",
                use_container_width=False,
            ):
                kq = dong_bo_tat_ca_ten_theo_form(deadline_cfg, ds_loai_gsheet, username)
                if kq.get("so_doi"):
                    st.success(f"✅ {kq.get('msg')}")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.warning(kq.get("msg", "Không có tên nào được cập nhật."))

        for idx, item in enumerate(ds_lech):
            ten_cu = item["ten_theo_doi"]
            ten_form = item.get("ten_form") or ""
            col_a, col_b = st.columns([3, 1])
            with col_a:
                if ten_form:
                    st.markdown(
                        f"**{ten_cu}**  \n"
                        f"→ Gợi ý trên Form: **{ten_form}**"
                    )
                else:
                    st.markdown(f"**{ten_cu}** — không thấy trên Form")
            with col_b:
                if ten_form:
                    if st.button(
                        "🔗 Liên kết",
                        key=f"cd_link_form_{idx}",
                        use_container_width=True,
                        type="primary",
                    ):
                        kq = doi_ten_loai_theo_doi(ten_cu, ten_form, username)
                        if kq.get("ok"):
                            extra = []
                            if kq.get("so_manual_cap_nhat"):
                                extra.append(f"{kq['so_manual_cap_nhat']} đánh dấu thủ công")
                            if kq.get("allowlist_cap_nhat"):
                                extra.append("Telegram allowlist")
                            msg = kq.get("msg", "Đã liên kết")
                            if extra:
                                msg += f" (+ cập nhật {', '.join(extra)})"
                            st.success(f"✅ {msg}")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"❌ {kq.get('msg', 'Lỗi')}")
                else:
                    st.caption("Chờ Form có tên mới")


def _render_cai_dat(df: pd.DataFrame, deadline_cfg: dict, username: str) -> None:
    """Tab ⚙️ Cài đặt thời hạn — thiết kế kiểu 2 khối rõ: cần cài / đang theo dõi."""

    # ── CSS inline (dùng CSS variable để tương thích dark mode) ─────
    st.html("""
    <style>
    .cd-header-bar {
        background: linear-gradient(135deg, var(--primary-color) 0%, color-mix(in srgb, var(--primary-color) 70%, #2563eb) 100%);
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 4px;
    }
    .cd-header-bar h3 { color: white; margin: 0 0 2px; font-size: 1.05rem; }
    .cd-header-bar p  { color: rgba(255,255,255,0.85); margin: 0; font-size: 0.82rem; }
    .cd-stat-card {
        border-radius: 10px;
        padding: 14px 16px;
        text-align: center;
        margin-bottom: 4px;
    }
    .cd-stat-card .num { font-size: 1.6rem; font-weight: 800; margin:0; line-height:1.2; }
    .cd-stat-card .lbl { font-size: 0.8rem; opacity:0.85; margin:0; }
    .cd-stat-green  { background: #e6f7ec; border: 1px solid #a3e4b8; }
    .cd-stat-amber  { background: #fff7e0; border: 1px solid #fcd34d; }
    .cd-stat-green .num { color: #15803d; }
    .cd-stat-amber .num { color: #b45309; }
    .cd-section-title {
        display: flex; align-items: center; gap: 8px;
        padding: 8px 12px; border-radius: 8px; margin-bottom: 8px;
        font-weight: 700; font-size: 0.92rem;
    }
    .cd-title-amber { background: #fff7e0; color: #92400e; }
    .cd-title-green { background: #e6f7ec; color: #15803d; }
    .cd-dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
    .cd-dot-amber { background:#f59e0b; }
    .cd-dot-green { background:#22c55e; }
    .cd-table-badge {
        display: inline-block; padding: 2px 10px; border-radius: 12px;
        font-size: 0.78rem; font-weight: 600;
    }
    .cd-badge-green { background: #dcfce7; color: #166534; }
    .cd-badge-gray  { background: #f3f4f6; color: #6b7280; }
    </style>
    """)

    # ── Gom dữ liệu ───────────────────────────────────────────────
    ds_loai_gsheet  = sorted(df["loai_bao_cao"].dropna().unique().tolist()) if not df.empty else []
    dm = xay_dung_danh_muc_theo_doi(deadline_cfg, ds_loai_gsheet)
    ds_loai_cfg = dm["display_keys"]
    ds_loai = sorted(set(ds_loai_gsheet) | set(ds_loai_cfg))
    ds_loai_chua_cai = dm["ds_loai_chua_cai"]

    if not ds_loai:
        st.info("📭 Chưa có loại báo cáo nào từ Google Form. Sau khi PGD gửi form, các loại báo cáo sẽ xuất hiện ở đây.")
        with st.expander("✏️ Tạo thủ công loại báo cáo chưa có trong Form", expanded=False):
            _render_them_loai_thu_cong(deadline_cfg, username)
        return

    # ── Banner header màu ──────────────────────────────────────────
    st.html(f"""
    <div class="cd-header-bar">
        <h3>⚙️ Cài đặt thời hạn hoàn thành</h3>
        <p>Các loại báo cáo có deadline sẽ tự hiện 🟢 Đúng hạn · 🟡 Trễ · 🔴 Chưa nộp trong tab Tổng quan</p>
    </div>
    """)

    # ── 2 thẻ số liệu màu ──────────────────────────────────────────
    c1, c2, c3 = st.columns([1, 1, 4])
    with c1:
        st.html(f"""
        <div class="cd-stat-card cd-stat-green">
            <div class="num">{len(ds_loai_cfg)}</div>
            <div class="lbl">✅ Đang theo dõi</div>
        </div>
        """)
    with c2:
        st.html(f"""
        <div class="cd-stat-card cd-stat-amber">
            <div class="num">{len(ds_loai_chua_cai)}</div>
            <div class="lbl">📋 Cần cài</div>
        </div>
        """)
    with c3:
        st.write("")

    if ds_loai_cfg:
        _render_canh_bao_lech_ten(deadline_cfg, ds_loai_gsheet, username)

    st.divider()

    # ════════════════════════════════════════════════════════════════
    # KHỐI 1: CẦN CÀI DEADLINE
    # ════════════════════════════════════════════════════════════════
    if ds_loai_chua_cai:
        with st.container(border=True):
            st.html(
                '<div class="cd-section-title cd-title-amber">'
                '<span class="cd-dot cd-dot-amber"></span> CẦN CÀI DEADLINE'
                '</div>'
            )
            st.caption(f"Đã ghi nhận từ Google Form — chọn loại và deadline để bắt đầu theo dõi.")

            col_left, col_right = st.columns([2, 1])
            with col_left:
                loai_can_them = st.multiselect(
                    "Chọn loại báo cáo",
                    options=ds_loai_chua_cai,
                    default=[],
                    key="cd_loai_chua_cai",
                    placeholder=f"Chọn trong {len(ds_loai_chua_cai)} loại...",
                    label_visibility="collapsed",
                )
            with col_right:
                dl_moi_auto = st.date_input(
                    "Deadline",
                    value=date.today(),
                    format="DD/MM/YYYY",
                    key="cd_dl_auto",
                    label_visibility="collapsed",
                )
                if st.button(
                    "➕ Thêm vào theo dõi",
                    key="cd_btn_add_auto",
                    type="primary",
                    use_container_width=True,
                    disabled=not loai_can_them,
                ):
                    cfg_moi = dict(deadline_cfg)
                    for loai in loai_can_them:
                        cfg_moi[loai] = dl_moi_auto.strftime("%Y-%m-%d")
                    luu_deadline_config(cfg_moi, username)
                    st.success(f"✅ Đã thêm {len(loai_can_them)} loại — deadline {dl_moi_auto.strftime('%d/%m/%Y')}")
                    st.rerun()

            st.dataframe(
                pd.DataFrame({"Loại báo cáo chưa theo dõi": ds_loai_chua_cai}),
                hide_index=True,
                use_container_width=True,
                height=max(120, min(400, len(ds_loai_chua_cai) * 35 + 38)),
            )

    # ════════════════════════════════════════════════════════════════
    # KHỐI 2: ĐANG THEO DÕI
    # ════════════════════════════════════════════════════════════════
    if ds_loai_cfg:
        with st.container(border=True):
            st.html(
                '<div class="cd-section-title cd-title-green">'
                '<span class="cd-dot cd-dot-green"></span> ĐANG THEO DÕI'
                '</div>'
            )
            st.caption("Chọn một loại bên dưới để sửa deadline hoặc ngừng theo dõi.")

            loai_chon = st.selectbox(
                "Chọn loại đang theo dõi",
                ds_loai_cfg,
                key="cd_loai_cfg",
                label_visibility="collapsed",
            )
            loai_chon_track = dm["display_to_tracked"].get(loai_chon, loai_chon)

            goi_y_form = next(
                (x.get("ten_form") for x in phat_hien_ten_lech_ten(deadline_cfg, ds_loai_gsheet)
                 if x.get("ten_theo_doi") == loai_chon_track and x.get("ten_form")),
                None,
            )
            if goi_y_form:
                st.info(
                    f"ℹ️ Tên trên Form: **{goi_y_form}**. "
                    f"Dùng **🔗 Liên kết** ở khối cảnh báo phía trên để đồng bộ Telegram + ma trận."
                )

            dl_hien = deadline_cfg.get(loai_chon_track)
            dl_default = pd.to_datetime(dl_hien).date() if dl_hien else date.today()

            col_a, col_b, col_c = st.columns([2, 1, 1])
            with col_a:
                dl_moi = st.date_input(
                    "Deadline mới",
                    value=dl_default,
                    format="DD/MM/YYYY",
                    key="cd_dl_input",
                    label_visibility="collapsed",
                )
            with col_b:
                if st.button("💾 Cập nhật", key="cd_btn_luu", use_container_width=True):
                    cfg_moi = dict(deadline_cfg)
                    cfg_moi[loai_chon_track] = dl_moi.strftime("%Y-%m-%d")
                    luu_deadline_config(cfg_moi, username)
                    st.success(f"✅ {loai_chon} → {dl_moi.strftime('%d/%m/%Y')}")
                    st.rerun()
            with col_c:
                if st.button("🗑 Ngưng", key="cd_btn_ngung_nhanh", use_container_width=True,
                             help=f"Ngưng theo dõi {loai_chon}"):
                    cfg_moi = dict(deadline_cfg)
                    cfg_moi.pop(loai_chon_track, None)
                    luu_deadline_config(cfg_moi, username)
                    st.success(f"✅ Đã ngưng theo dõi: {loai_chon}")
                    st.rerun()

            # Bảng tóm tắt nhanh — đánh dấu màu deadline sắp đến / đã qua
            rows = []
            today = date.today()
            for loai_hien, dl in sorted(dm["display_cfg"].items()):
                dl_dt = pd.to_datetime(dl).date() if dl else None
                dl_str = dl_dt.strftime("%d/%m/%Y") if dl_dt else "—"
                if dl_dt is None:
                    badge = '<span class="cd-table-badge cd-badge-gray">Chưa đặt</span>'
                elif dl_dt < today:
                    badge = f'<span class="cd-table-badge cd-badge-gray">🔴 {dl_str}</span>'
                elif (dl_dt - today).days <= 3:
                    badge = f'<span class="cd-table-badge cd-badge-gray">🟡 {dl_str}</span>'
                else:
                    badge = f'<span class="cd-table-badge cd-badge-gray">🟢 {dl_str}</span>'
                rows.append({"Loại báo cáo": loai_hien, "Thời hạn": badge})

            df_rows = pd.DataFrame(rows)
            st.dataframe(
                df_rows,
                hide_index=True,
                use_container_width=True,
                height=max(120, min(400, len(rows) * 35 + 38)),
                column_config={
                    "Thời hạn": st.column_config.Column("Thời hạn", width="small"),
                },
            )

    # ── Góc dưới: thêm thủ công + xóa tất cả ──────────────────────
    st.divider()
    with st.expander("✏️ Thêm thủ công loại báo cáo chưa có trong Form", expanded=False):
        _render_them_loai_thu_cong(deadline_cfg, username)

    if ds_loai_cfg:
        # Tìm deadline "cũ" — đang theo dõi nhưng không còn xuất hiện trong GSheet
        ds_deadline_cu = [loai for loai in deadline_cfg if loai not in ds_loai_gsheet]

        col_don, col_xoa = st.columns([1, 1])
        with col_don:
            if ds_deadline_cu:
                with st.popover(f"🧹 Dọn thời hạn cũ ({len(ds_deadline_cu)})", use_container_width=True):
                    st.warning(
                        f"**{len(ds_deadline_cu)} loại** đang theo dõi nhưng **không còn xuất hiện** "
                        f"trong Google Sheet (PGD chưa từng nộp hoặc Sheet đã xóa dữ liệu):"
                    )
                    for loai in ds_deadline_cu:
                        dl = deadline_cfg.get(loai, "")
                        try:
                            dl_str = pd.to_datetime(dl).strftime("%d/%m/%Y") if dl else "—"
                        except Exception:
                            dl_str = str(dl)
                        st.caption(f"• **{loai}** (thời hạn: {dl_str})")
                    st.caption("Xóa các loại này sẽ không ảnh hưởng loại BC đang có dữ liệu trong Sheet.")
                    if st.button(
                        f"🧹 Xóa {len(ds_deadline_cu)} thời hạn cũ",
                        key="cd_btn_don_cu",
                        type="primary",
                        use_container_width=True,
                    ):
                        cfg_moi = {k: v for k, v in deadline_cfg.items() if k not in ds_deadline_cu}
                        luu_deadline_config(cfg_moi, username)
                        db.ghi_audit(username, "don_deadline_cu", f"Xóa {len(ds_deadline_cu)} thời hạn cũ: {', '.join(ds_deadline_cu)}")
                        st.success(f"✅ Đã dọn {len(ds_deadline_cu)} thời hạn cũ.")
                        st.rerun()
            else:
                st.button("🧹 Dọn thời hạn cũ", disabled=True, use_container_width=True,
                          help="Tất cả thời hạn đang theo dõi đều có dữ liệu trong Google Sheet — không có gì cần dọn.")

        with col_xoa:
            with st.popover("🗑 Xóa tất cả thời hạn", use_container_width=True):
                st.warning(f"Xóa toàn bộ **{len(ds_loai_cfg)} deadline** đã cài?")
                st.caption("Các loại báo cáo sẽ không còn được theo dõi ở tab Tổng quan.")
                if st.button("⚠️ Xác nhận xóa tất cả", key="cd_btn_xoa_het", type="primary", use_container_width=True):
                    luu_deadline_config({}, username)
                    st.success("✅ Đã xóa toàn bộ deadline.")
                    st.rerun()


def _render_them_loai_thu_cong(deadline_cfg: dict, username: str) -> None:
    """Thêm loại báo cáo bằng tay (chưa có trong Google Form)."""
    col_ten, col_dl, col_add = st.columns([3, 2, 1])
    with col_ten:
        ten_moi = st.text_input(
            "Tên loại báo cáo",
            placeholder="VD: Báo cáo tháng 7/2026",
            key="cd_ten_moi",
            label_visibility="collapsed",
        )
    with col_dl:
        dl_moi_add = st.date_input(
            "Deadline",
            value=date.today(),
            format="DD/MM/YYYY",
            key="cd_dl_moi",
            label_visibility="collapsed",
        )
    with col_add:
        st.write("")
        if st.button("💾 Thêm", key="cd_btn_add", type="primary", use_container_width=True):
            ten_moi = ten_moi.strip()
            if not ten_moi:
                st.warning("⚠️ Nhập tên loại báo cáo.")
            elif ten_moi in deadline_cfg:
                st.warning(f"⚠️ **{ten_moi}** đã tồn tại.")
            else:
                cfg_moi = dict(deadline_cfg)
                cfg_moi[ten_moi] = dl_moi_add.strftime("%Y-%m-%d")
                luu_deadline_config(cfg_moi, username)
                st.success(f"✅ Đã thêm **{ten_moi}** → {dl_moi_add.strftime('%d/%m/%Y')}")
                st.rerun()


# ── Tab Hướng dẫn với Mockup ───────────────────────────────────────────────────

def _render_huong_dan_mockup() -> None:
    """Hiển thị hướng dẫn sử dụng và mockup luồng xử lý."""
    st.markdown("## 📖 Hướng dẫn sử dụng")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        **👤 Dành cho PGD**
        
        1. Nhận **link Google Form** từ Phòng KH-NV
        2. Truy cập Form → điền đầy đủ thông tin
        3. Upload file báo cáo lên **Google Drive**
        4. **Set quyền "Anyone with the link can view"** cho file trên Drive
        5. Copy link Drive dán vào Form
        6. Bấm **"Gửi báo cáo"**
        7. Đợi ~5 phút, kiểm tra tab *Danh sách nộp*
        """)
    with col2:
        st.success("""
        **👔 Dành cho Phòng KH-NV**
        
        1. **Cài đặt thời hạn hoàn thành** trước mỗi kỳ báo cáo
        2. Theo dõi tiến độ qua tab *Tổng quan*
        3. Xem ma trận PGD × Loại báo cáo
        4. Danh sách 🔴 Chưa nộp tự động hiện
        5. Xuất Excel/PDF để **đôn đốc** các PGD
        6. Gọi điện/Zalo nhắc nhở đơn vị trễ hạn
        """)
    
    st.divider()
    st.markdown("### 🔄 Quy trình xử lý")
    
    # Flow diagram bằng HTML
    flow_html = """
    <div style="display: flex; align-items: center; justify-content: center; gap: 15px;
                flex-wrap: wrap; padding: 20px; background: var(--background-color, transparent);
                border: 1px solid var(--border-color, #ddd); border-radius: 12px;">
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📝</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">PGD nộp Form</div>
        </div>
        <div style="font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📊</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">Lưu Sheets</div>
        </div>
        <div style="font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">⚙️</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">VBSP đọc (5 phút)</div>
        </div>
        <div style="font-size: 24px;">→</div>
        <div style="text-align: center; padding: 15px; border: 1px solid var(--border-color, #ccc);
                    border-radius: 10px; min-width: 120px;">
            <div style="font-size: 32px;">📈</div>
            <div style="font-weight: 600; font-size: 13px; margin-top: 5px;">KH-NV theo dõi</div>
        </div>
    </div>
    """
    st.html(flow_html)
    
    st.caption("💡 Dữ liệu từ Form → Sheets là **tức thời** | Sheets → VBSP-SCM có độ trễ **5 phút** (do cache)")
    
    st.divider()
    st.markdown("### 📋 Các trạng thái báo cáo")
    
    status_cols = st.columns(4)
    with status_cols[0]:
        st.metric("🟢 Đúng hạn", "Nộp ≤ thời hạn")
    with status_cols[1]:
        st.metric("🟡 Trễ hạn", "Nộp > thời hạn")
    with status_cols[2]:
        st.metric("🔴 Chưa nộp", "Quá hạn, chưa có data")
    with status_cols[3]:
        st.metric("⚪ Chưa nộp", "Chưa có thời hạn")
    
    st.divider()
    with st.expander("📊 Xem mockup chi tiết (Google Form mẫu)", expanded=False):
        try:
            mockup_path = Path(__file__).parent.parent / "docs" / "mockup_bc_tu_pgd.html"
            if mockup_path.exists():
                with open(mockup_path, "r", encoding="utf-8") as f:
                    mockup_content = f.read()
                # Chỉ lấy phần body và giới hạn chiều cao
                st.components.v1.html(
                    f'<div style="height: 600px; overflow-y: auto; border: 1px solid #ddd; border-radius: 8px;">{mockup_content}</div>',
                    height=620,
                    scrolling=True
                )
            else:
                st.info("File mockup chưa được tạo. Vui lòng kiểm tra docs/mockup_bc_tu_pgd.html")
        except Exception as e:
            logger.error("render mockup html: %s", e, exc_info=True)
            st.error(f"Không thể tải mockup: {e}")


# ── Entry point ───────────────────────────────────────────────────────────────

_CACHE_VER = "v2"

def render(tab: DeltaGenerator = None, **kwargs) -> None:
    # Clear cache cũ mỗi khi vào tab — đảm bảo data GSheet luôn mới
    _doc_du_lieu.clear()

    role_raw = str(kwargs.get("role", "user") or "user")
    role_n = normalize_role(role_raw)
    is_cn = la_phan_he_cn(role_n)
    pgd_user = kwargs.get("pgd_user")
    username = kwargs.get("username", st.session_state.get("username", "unknown"))

    ctx = TabContext(tab, **kwargs)
    with ctx:
        ok, msg = kiem_tra_ket_noi_gsheet()
        if not ok:
            st.error(f"🔴 **GSheet lỗi:** {msg}")
        else:
            st.success(f"🟢 **GSheet OK** — {msg}")

        st.subheader("📋 Tiến độ Báo cáo của PGD")
        st.caption("Dữ liệu từ Google Form · Tự động cập nhật mỗi 5 phút")

        col_r, _ = st.columns([1, 7])
        with col_r:
            if st.button("🔄 Làm mới", key="tdn_refresh"):
                st.cache_data.clear()
                st.rerun()

        df = _doc_du_lieu()
        if df.empty:
            loi_gs = lay_loi_doc_gsheet_gan_nhat()
            if loi_gs:
                st.warning(f"⚠️ Không đọc được Google Sheets: {loi_gs}")
            else:
                st.warning("⚠️ Chưa có dữ liệu từ Google Sheets. Thử nhấn 🔄 Làm mới.")
        deadline_cfg = doc_deadline_config()

        # PGD role: chỉ thấy dữ liệu của PGD mình
        if not is_cn and pgd_user:
            df = df[df["ten_pgd"] == pgd_user]

        can_config = role_n in ("admin_cn", "manager_cn", "admin", "manager")

        # Tab hướng dẫn hiển thị cho tất cả users
        if can_config:
            # Thứ tự tab theo quy trình vận hành trong hướng dẫn:
            # Bước 1: Cài đặt thời hạn → Bước 2: Tổng quan → Bước 4: Danh sách nộp
            t0, t1, t2, t3 = st.tabs(["📖 Hướng dẫn PGD gửi BC về CN", "⚙️ Cài đặt thời hạn", "📊 Tổng quan", "📋 Danh sách nộp"])
        else:
            t0, t2, t3 = st.tabs(["📖 Hướng dẫn PGD gửi BC về CN", "📊 Tổng quan", "📋 Danh sách nộp"])
            t1 = None

        with t0:
            _render_huong_dan_mockup()

        if t1 is not None:
            with t1:
                _render_cai_dat(df, deadline_cfg, username)

        with t2:
            _render_tong_quan(df, deadline_cfg, is_cn, pgd_user, username, can_config)

        with t3:
            _render_danh_sach(df, deadline_cfg, is_cn, pgd_user)
