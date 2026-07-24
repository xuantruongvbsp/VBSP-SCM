"""UI cài đặt thời hạn cho tab Tiến độ nộp báo cáo."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import db
from logger import get_logger
from services.report_submission_service import (
    doi_ten_loai_theo_doi,
    dong_bo_tat_ca_ten_theo_form,
    luu_deadline_config,
    luu_tru_loai_bao_cao,
    phat_hien_ten_lech_ten,
    xay_dung_danh_muc_theo_doi,
)

logger = get_logger(__name__)


def _render_canh_bao_lech_ten(
    deadline_cfg: dict,
    ds_loai_gsheet: list[str],
    username: str,
) -> None:
    """Cảnh báo tên theo dõi khác Google Form và nút liên kết một lần bấm."""
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


def render_settings(df: pd.DataFrame, deadline_cfg: dict, username: str) -> None:
    """Render tab Cài đặt thời hạn hoàn thành."""
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

    ds_loai_gsheet = sorted(df["loai_bao_cao"].dropna().unique().tolist()) if not df.empty else []
    dm = xay_dung_danh_muc_theo_doi(deadline_cfg, ds_loai_gsheet)
    ds_loai_cfg = dm["display_keys"]
    ds_loai = sorted(set(ds_loai_gsheet) | set(ds_loai_cfg))
    ds_loai_chua_cai = dm["ds_loai_chua_cai"]

    if not ds_loai:
        st.info("📭 Chưa có loại báo cáo nào từ Google Form. Sau khi PGD gửi form, các loại báo cáo sẽ xuất hiện ở đây.")
        return

    st.html(f"""
    <div class="cd-header-bar">
        <h3>⚙️ Cài đặt thời hạn hoàn thành</h3>
        <p>Các loại báo cáo có deadline sẽ tự hiện 🟢 Đúng hạn · 🟡 Trễ · 🔴 Chưa nộp trong tab Tổng quan</p>
    </div>
    """)

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

    if ds_loai_chua_cai:
        with st.container(border=True):
            st.html(
                '<div class="cd-section-title cd-title-amber">'
                '<span class="cd-dot cd-dot-amber"></span> CẦN CÀI DEADLINE'
                '</div>'
            )
            st.caption("Đã ghi nhận từ Google Form — chọn loại và deadline để bắt đầu theo dõi.")

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
                if st.button(
                    "🗑 Ngưng",
                    key="cd_btn_ngung_nhanh",
                    use_container_width=True,
                    help=f"Ngưng theo dõi {loai_chon}",
                ):
                    cfg_moi = dict(deadline_cfg)
                    cfg_moi.pop(loai_chon_track, None)
                    luu_deadline_config(cfg_moi, username)
                    st.success(f"✅ Đã ngưng theo dõi: {loai_chon}")
                    st.rerun()

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

    st.divider()
    with st.expander("📦 Hoàn thành và lưu trữ loại báo cáo", expanded=False):
        st.caption(
            "Dữ liệu Google Form vẫn được giữ nguyên. Loại đã lưu trữ sẽ không còn ở "
            "Cài deadline, Tổng quan hoặc Telegram và được chuyển sang tab Đã lưu trữ."
        )
        loai_luu_tru = st.selectbox(
            "Chọn loại báo cáo đã hoàn thành",
            options=ds_loai,
            key="cd_archive_type",
        )
        ten_track = dm["display_to_tracked"].get(loai_luu_tru, loai_luu_tru)
        so_luot = int((df["loai_bao_cao"] == loai_luu_tru).sum()) if not df.empty else 0
        st.info(
            f"Sẽ lưu trữ **{loai_luu_tru}** — hiện có **{so_luot} lượt nộp**. "
            "Deadline hiện tại (nếu có) sẽ được gỡ."
        )
        xac_nhan = st.checkbox(
            "Tôi xác nhận loại báo cáo này đã hoàn thành",
            key="cd_archive_confirm",
        )
        if st.button(
            "📦 Lưu trữ báo cáo",
            key="cd_archive_save",
            type="primary",
            disabled=not xac_nhan,
        ):
            try:
                luu_tru_loai_bao_cao(loai_luu_tru, username, ten_track)
                st.cache_data.clear()
                st.success(f"✅ Đã lưu trữ: **{loai_luu_tru}**")
                st.rerun()
            except Exception as e:
                logger.error("Lưu trữ loại báo cáo: %s", e, exc_info=True)
                st.error(f"❌ Không lưu trữ được: {e}")

    st.divider()
    if ds_loai_cfg:
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
                        db.ghi_audit(
                            username,
                            "don_deadline_cu",
                            f"Xóa {len(ds_deadline_cu)} thời hạn cũ: {', '.join(ds_deadline_cu)}",
                        )
                        st.success(f"✅ Đã dọn {len(ds_deadline_cu)} thời hạn cũ.")
                        st.rerun()
            else:
                st.button(
                    "🧹 Dọn thời hạn cũ",
                    key="cd_btn_don_cu_disabled",
                    disabled=True,
                    use_container_width=True,
                    help="Tất cả thời hạn đang theo dõi đều có dữ liệu trong Google Sheet — không có gì cần dọn.",
                )

        with col_xoa:
            with st.popover("🗑 Xóa tất cả thời hạn", use_container_width=True):
                st.warning(f"Xóa toàn bộ **{len(ds_loai_cfg)} deadline** đã cài?")
                st.caption("Các loại báo cáo sẽ không còn được theo dõi ở tab Tổng quan.")
                if st.button("⚠️ Xác nhận xóa tất cả", key="cd_btn_xoa_het", type="primary", use_container_width=True):
                    luu_deadline_config({}, username)
                    st.success("✅ Đã xóa toàn bộ deadline.")
                    st.rerun()
