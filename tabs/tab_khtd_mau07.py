"""Tab Mẫu 07 — Giao/Điều chỉnh Kế hoạch Tín dụng theo Ấp/Thôn.

Biểu số 07/NHCS-KH · Theo CV 7064
KV store:
  khtd_ap_{pgd_slug}_{xa_slug}          → dict  {"{ten_ap}|{ma_key}": float}
  khtd_ap_lich_su_{pgd_slug}_{xa_slug}  → list  [{lan, loai, ngay, username, data}]

Ghi chú:
  - Số QĐ và ngày tháng KHÔNG lưu — để TRỐNG cho UBND xã điền tay khi ký.
  - Số gốc lũy kế: lần 1 = baseline HSTD 31/12; lần 2+ = KH lần trước.
  - Data DB chỉ lưu "Chỉ tiêu KH" (float triệu đồng), không lưu giao +/−.
"""
from datetime import datetime

import pandas as pd
import streamlit as st

import db
from auth import la_phan_he_pgd, normalize_role
from config import (
    COT_MA_CHUONG_TRINH,
    COT_NGUON_VON,
    COT_TEN_XA,
    COT_TEN_THON,
    COT_TONG_DU_NO,
    DON_VI_CHI_NHANH,
    DS_PGD,
    NAM_HT,
    PGD_XA_MAP,
    tim_ten_xa_trong_hstd,
)
from tabs.tab_khtd import MAKEY_BY_MACT_NV
from services.khtd_mau07_service import (
    _slug,
    _chuan_hoa_ten,
    _kv_key,
    _kv_key_ls,
    _doc_kv_dict,
    _doc_kv_list,
    _luu_kv,
    tinh_du_no_ap_baseline as _svc_tinh_du_no_ap_baseline,
    lay_so_goc_cho_ap,
    _sync_khtd_xa,
    _lay_ds_ma_key_co_du_lieu,
    _build_table_data,
    _extract_data_from_edited_df,
    _update_total_row,
    xuat_mau07_word,
    TEN_BY_MAKEY,
)
from utils import vn, hien_thi_dataframe_phan_trang, get_tab_context

# ── Hằng số ───────────────────────────────────────────────────────────────────
_NAM_KH_DEFAULT = int(NAM_HT)

_BG_TW = "#e3f2fd"
_BG_DP = "#fff8e1"


# ══════════════════════════════════════════════════════════════════════════════
# BUSINESS LOGIC
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def tinh_du_no_ap_baseline(_df_baseline: pd.DataFrame, ten_xa: str) -> dict:
    return _svc_tinh_du_no_ap_baseline(_df_baseline, ten_xa)


# ══════════════════════════════════════════════════════════════════════════════
# UI — BẢNG NHẬP TỔNG HỢP (1 BẢNG DUY NHẤT THAY VÌ EXPANDER)
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# UI — LỊCH SỬ
# ══════════════════════════════════════════════════════════════════════════════
def _render_lich_su(lich_su: list) -> None:
    if not lich_su:
        st.info("Chưa có lịch sử giao/điều chỉnh nào.")
        return

    rows = [{
        "Lần":    item.get("lan", "?"),
        "Loại":   "Giao" if item.get("loai") == "giao" else "Điều chỉnh",
        "Ngày":   item.get("ngay", "")[:10],
        "Người":  item.get("username", ""),
        "Tổng KH (triệu)": vn(sum(float(v) for v in item.get("data", {}).values()), 1),
    } for item in lich_su]
    hien_thi_dataframe_phan_trang(
        pd.DataFrame(rows),
        key="mau07_lich_su",
    )

    lan_xem = st.selectbox(
        "Xem chi tiết lần",
        [f"Lần {i+1} — {item.get('ngay','')[:10]}" for i, item in enumerate(lich_su)],
        key="m07_ls_xem",
    )
    idx_xem  = int(lan_xem.split()[1]) - 1
    item_xem = lich_su[idx_xem]
    st.markdown(
        f"**Loại:** {'Giao' if item_xem.get('loai')=='giao' else 'Điều chỉnh'}"
        f" &nbsp;|&nbsp; **Người lưu:** {item_xem.get('username','')}"
    )
    df_ct = pd.DataFrame([
        {
            "Ấp/Thôn":              composite.split("|")[0] if "|" in composite else composite,
            "Chương trình":         TEN_BY_MAKEY.get(composite.split("|")[1] if "|" in composite else "", composite),
            "Chỉ tiêu KH (triệu)": v,
        }
        for composite, v in item_xem.get("data", {}).items()
    ])
    if not df_ct.empty:
        hien_thi_dataframe_phan_trang(df_ct, key="mau07_chi_tiet_lan")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def render(tab, **kwargs) -> None:
    """Entry point — render tab Mẫu 07."""
    role = normalize_role(str(kwargs.get("role", "user") or "user"))
    username = kwargs.get("username", "system")
    pgd_user = kwargs.get("pgd_user")

    ctx = get_tab_context(tab)
    with ctx:
        st.subheader("📋 Mẫu 07 — Giao/Điều chỉnh Chỉ tiêu KHTD theo Ấp/Thôn")
        st.caption("Biểu số 07/NHCS-KH · Theo CV 7064 · Số QĐ & ngày tháng để trống cho UBND xã điền khi ký")

        # ── ① PGD / Xã / Năm ──────────────────────────────────────────────────────
        col_pgd, col_xa, col_nam = st.columns([2, 2, 1])

        with col_pgd:
            if la_phan_he_pgd(role) and pgd_user:
                st.info(f"PGD: **{pgd_user}**")
                pgd_chon = pgd_user
            else:
                # Danh sách đơn vị = Hội sở + 21 PGD
                ds_don_vi = [DON_VI_CHI_NHANH] + DS_PGD
                pgd_chon = st.selectbox(
                    "Chọn Đơn vị",
                    ds_don_vi,
                    format_func=lambda x: f"🏦 {x}" if x == DON_VI_CHI_NHANH else f"🏢 {x}",
                    key="m07_pgd",
                )

        ds_xa_pgd = PGD_XA_MAP.get(pgd_chon, [])

        # ═══ MAPPING VÀ FUZZY MATCHING TÊNN XÃ ═══
        df_full = kwargs.get("df_full")
        ten_xa_mapping: dict = {}

        # Mapping từ XA_NAME_MAP + tự động bỏ prefix (config -> HSTD)
        for xa_pgd in ds_xa_pgd:
            mapped = tim_ten_xa_trong_hstd(xa_pgd)
            if mapped != xa_pgd:
                ten_xa_mapping[xa_pgd] = mapped

        # Fuzzy matching (chuẩn hóa) cho các xã chưa có mapping
        cot_xa_full = COT_TEN_XA if df_full is not None and COT_TEN_XA in df_full.columns else None
        if df_full is not None and isinstance(df_full, pd.DataFrame) and not df_full.empty:
            if cot_xa_full:
                ds_xa_co_data = df_full[cot_xa_full].dropna().unique()
                for xa_pgd in ds_xa_pgd:
                    if xa_pgd in ten_xa_mapping:
                        continue
                    key_pgd = _chuan_hoa_ten(xa_pgd)
                    for xa_data in ds_xa_co_data:
                        if _chuan_hoa_ten(xa_data) == key_pgd:
                            ten_xa_mapping[xa_pgd] = xa_data
                            break

        with col_xa:
            if not ds_xa_pgd:
                st.warning(f"⚠️ Đơn vị **{pgd_chon}** chưa có danh sách xã trong cấu hình PGD_XA_MAP.")
                return

            if st.query_params.get("debug") == "1":
                with st.expander("🔍 Debug: Mapping xã", expanded=False):
                    st.write("**Từ PGD_XA_MAP:**", ds_xa_pgd)
                    if cot_xa_full:
                        st.write("**Trong HSTD:**", sorted(df_full[cot_xa_full].dropna().unique().tolist())[:20])
                    st.write("**Mapping:**", ten_xa_mapping if ten_xa_mapping else "(Tất cả tên khớp trực tiếp)")

            xa_chon_raw = st.selectbox("Chọn Xã/Phường", ds_xa_pgd, key="m07_xa")

            # xa_chon_raw: tên gốc từ config (dùng cho slug/key lưu)
            # xa_chon:     tên trong HSTD (dùng cho filter dữ liệu)
            xa_chon = ten_xa_mapping.get(xa_chon_raw, xa_chon_raw)
            if st.query_params.get("debug") == "1" and xa_chon != xa_chon_raw:
                st.caption(f"📌 Mapping: '{xa_chon_raw}' → '{xa_chon}' (trong HSTD)")
            elif cot_xa_full:
                ds_xa_co_data = df_full[cot_xa_full].dropna().unique()
                if xa_chon not in ds_xa_co_data:
                    st.warning(f"⚠️ Xã '{xa_chon}' không tìm thấy trong HSTD. Kiểm tra XA_NAME_MAP hoặc tên xã.")

        with col_nam:
            nam_kh = st.number_input(
                "Năm KH", min_value=2024, max_value=2030,
                value=_NAM_KH_DEFAULT, step=1, key="m07_nam",
            )

        pgd_slug_key = _slug(pgd_chon)
        xa_slug_key  = _slug(xa_chon_raw)  # Dùng xa_chon_raw (tên gốc) cho slug để ổn định key lưu
        nam_baseline = nam_kh - 1

        # ── ② Loại văn bản ────────────────────────────────────────────────────
        loai_chon = st.radio(
            "Loại văn bản",
            ["🆕 Giao lần đầu", "✏️ Điều chỉnh"],
            horizontal=True,
            key="m07_loai",
            label_visibility="collapsed",
        )
        loai_van_ban = "giao" if "Giao" in loai_chon else "dieu_chinh"

        # ── ③ Đọc dữ liệu ─────────────────────────────────────────────────────
        kv_key_ht = _kv_key(pgd_chon, xa_chon_raw)
        kv_key_ls = _kv_key_ls(pgd_chon, xa_chon_raw)
        data_hien_tai: dict = _doc_kv_dict(kv_key_ht)
        lich_su: list       = _doc_kv_list(kv_key_ls)

        # Đọc baseline HSTD 31/12
        df_baseline = None
        co_baseline = False
        try:
            from config import (
                baseline_pgd_path, baseline_path,
                danh_sach_nam_baseline_pgd,
            )
            from data.hstd import doc_baseline_merged, doc_baseline

            ds_nam_bl = danh_sach_nam_baseline_pgd()
            if nam_baseline in ds_nam_bl:
                fp = baseline_pgd_path(pgd_chon, nam_baseline)
                _ts = os.path.getmtime(fp) if os.path.exists(fp) else 0
                df_baseline = doc_baseline_merged(nam_baseline, _ts=_ts)
                co_baseline = df_baseline is not None and not df_baseline.empty

            if not co_baseline:
                fp2  = baseline_path(nam_baseline)
                _ts2 = os.path.getmtime(fp2) if os.path.exists(fp2) else 0
                df_baseline = doc_baseline(nam_baseline, _ts=_ts2)
                co_baseline = df_baseline is not None and not df_baseline.empty
        except Exception:
            co_baseline = False

        if co_baseline:
            _raw = tinh_du_no_ap_baseline(df_baseline, xa_chon)
            # Kiểm tra lỗi trả về từ hàm
            if "_err" in _raw:
                _err_msg = _raw["_err"]
                st.warning(f"⚠️ Baseline 31/12/{nam_baseline} có nhưng không đọc được dư nợ: {_err_msg}")
                # Vẫn hiển thị debug để chẩn đoán
                with st.expander("🔍 Debug baseline", expanded=True):
                    st.write(f"**Cột trong file:** {list(df_baseline.columns[:15])}")
                    if COT_TEN_XA in df_baseline.columns:
                        col_xa_debug = COT_TEN_XA
                        ds_xa_debug = sorted(df_baseline[col_xa_debug].dropna().unique().tolist())
                        st.write(f"**Danh sách xã trong baseline ({len(ds_xa_debug)} xã):** {ds_xa_debug[:10]}")
                        st.caption(f"Đang tìm xã: **'{xa_chon}'** — kiểm tra tên có khớp không")
                du_no_baseline = {}
            else:
                so_ap = len({k.split("|")[0] for k in _raw})
                so_ct = len(_raw)
                st.success(
                    f"✅ Baseline 31/12/{nam_baseline}: {so_ap} ấp/thôn, {so_ct} chỉ tiêu "
                    f"— dùng làm số gốc lần đầu"
                )
                du_no_baseline = _raw
        else:
            st.warning(
                f"⚠️ Chưa có dữ liệu HSTD 31/12/{nam_baseline} — "
                "số gốc lần đầu = 0. Vui lòng upload baseline trước."
            )
            du_no_baseline = {}

        if lich_su:
            st.info(
                f"📜 Đã có **{len(lich_su)}** lần giao/điều chỉnh. "
                f"Số gốc hiện tại = Chỉ tiêu KH lần {len(lich_su)}."
            )

        st.divider()

        # ── ④⑤ BẢNG NHẬP DUY NHẤT (THAY CHO EXPANDER TỪNG ẤP) ────────────────

        # ═══ LẤY DANH SÁCH ẤP TỰ ĐỘNG ═══
        # Nguồn 1: Từ baseline (ưu tiên)
        ds_ap_from_baseline = set()
        if du_no_baseline:
            ds_ap_from_baseline = set(key.split("|")[0] for key in du_no_baseline.keys() if "|" in key)

        # Nguồn 2: Từ df_baseline (HSTD 31/12)
        ds_ap_from_baseline_df = set()
        if co_baseline and df_baseline is not None and not df_baseline.empty:
            col_xa_bl = COT_TEN_XA if COT_TEN_XA in df_baseline.columns else None
            col_thon_bl = COT_TEN_THON if COT_TEN_THON in df_baseline.columns else None
            if col_xa_bl and col_thon_bl:
                df_xa_bl = df_baseline[df_baseline[col_xa_bl] == xa_chon]
                ap_list = df_xa_bl[col_thon_bl].dropna().astype(str).str.strip()
                ds_ap_from_baseline_df = set(ap_list[ap_list != ""].unique())

        # Nguồn 3: Từ HSTD hiện tại (df_full) - đã lấy từ kwargs ở trên
        ds_ap_from_hstd_current = set()
        if df_full is not None and isinstance(df_full, pd.DataFrame) and not df_full.empty:
            col_xa_hstd = COT_TEN_XA if COT_TEN_XA in df_full.columns else None
            col_thon_hstd = COT_TEN_THON if COT_TEN_THON in df_full.columns else None
            if col_xa_hstd and col_thon_hstd:
                df_xa_full = df_full[df_full[col_xa_hstd] == xa_chon]
                ap_list = df_xa_full[col_thon_hstd].dropna().astype(str).str.strip()
                ds_ap_from_hstd_current = set(ap_list[ap_list != ""].unique())

        # Nguồn 4: Từ lịch sử
        ds_ap_from_history = set()
        for item in lich_su:
            for key in item.get("data", {}).keys():
                if "|" in key:
                    ds_ap_from_history.add(key.split("|")[0])
        for key in data_hien_tai.keys():
            if "|" in key:
                ds_ap_from_history.add(key.split("|")[0])

        # Gộp tất cả nguồn
        ds_ap = sorted(ds_ap_from_baseline | ds_ap_from_baseline_df | ds_ap_from_hstd_current | ds_ap_from_history)

        # Debug info
        if ds_ap:
            with st.expander("🔍 Debug: Nguồn dữ liệu ấp", expanded=False):
                st.caption(f"✅ Tìm thấy **{len(ds_ap)}** ấp/thôn cho xã **{xa_chon}**")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.markdown("**Từ baseline:**")
                    st.write(sorted(ds_ap_from_baseline) if ds_ap_from_baseline else "(Chưa có)")
                with col2:
                    st.markdown("**Từ baseline df:**")
                    st.write(sorted(ds_ap_from_baseline_df) if ds_ap_from_baseline_df else "(Chưa có)")
                with col3:
                    st.markdown("**Từ HSTD hiện tại:**")
                    st.write(sorted(ds_ap_from_hstd_current) if ds_ap_from_hstd_current else "(Chưa có)")
                with col4:
                    st.markdown("**Từ lịch sử:**")
                    st.write(sorted(ds_ap_from_history) if ds_ap_from_history else "(Chưa có)")
        else:
            st.error(
                f"❌ Không tìm thấy dữ liệu ấp/thôn cho xã **{xa_chon}**\n\n"
                "**Nguyên nhân có thể:**\n"
                "- Tên xã không khớp (kiểm tra dấu cách, dấu thanh)\n"
                "- Chưa có dữ liệu HSTD cho xã này\n"
                "- File HSTD chưa được upload\n\n"
                "**Giải pháp:** Upload file HSTD có chứa dữ liệu xã này"
            )
            st.stop()

        # ═══ LẤY DANH SÁCH CHƯƠNG TRÌNH CÓ DỮ LIỆU ═══
        ds_ma_key = _lay_ds_ma_key_co_du_lieu(xa_chon, df_full, du_no_baseline, lich_su)

        # ═══ BUILD VÀ HIỂN THỊ BẢNG ═══
        st.markdown("### 📊 Nhập chỉ tiêu theo ấp/thôn")

        lan = len(lich_su) + 1 if lich_su else 1
        st.caption(
            f"Xã: **{xa_chon}** · Năm: **{nam_kh}** · "
            f"Số gốc từ: **{'Dư nợ 31/12/' + str(nam_kh-1) if lan == 1 else 'KH lũy kế lần ' + str(lan-1)}**"
        )

        # Build DataFrame
        df_edit = _build_table_data(ds_ap, ds_ma_key, du_no_baseline, lich_su, data_hien_tai, nam_kh)

        # st.data_editor
        col_so_goc = f"Số gốc (triệu)"
        col_giao = "Giao tăng/giảm (triệu)"
        col_kh = f"Chỉ tiêu KH {nam_kh} (triệu)"

        edited_df = st.data_editor(
            df_edit,
            disabled=["Ấp/Thôn", "Chương trình", "Nguồn vốn", col_so_goc, col_kh],
            column_config={
                "_type": None,  # Ẩn cột internal
                "_key": None,
                "Ấp/Thôn": st.column_config.TextColumn("Ấp/Thôn", width="medium"),
                "Chương trình": st.column_config.TextColumn("Chương trình", width="large"),
                "Nguồn vốn": st.column_config.TextColumn("NV", width="small"),
                col_so_goc: st.column_config.NumberColumn("Số gốc\n(triệu)", format=",.0f", width="small"),
                col_giao: st.column_config.NumberColumn("Giao tăng/giảm\n(triệu)", format=",.0f", width="medium", step=1.0),
                col_kh: st.column_config.NumberColumn(f"Chỉ tiêu KH {nam_kh}\n(triệu)", format=",.0f", width="medium"),
            },
            hide_index=True,
            use_container_width=True,
            height=600,
            key=f"m07_table_edit_{pgd_slug_key}_{xa_slug_key}_{nam_kh}",
        )

        # Auto-calculate cột "Chỉ tiêu KH" khi user nhập "Giao tăng/giảm"
        if edited_df is not None and not edited_df.empty:
            for idx, row in edited_df.iterrows():
                if row.get("_type") == "data":
                    so_goc = row.get(col_so_goc) or 0
                    giao = row.get(col_giao) or 0
                    edited_df.at[idx, col_kh] = round(so_goc + giao)

            # Update tổng
            edited_df = _update_total_row(edited_df, nam_kh)

            # Hiển thị dòng tổng nổi bật
            total_row = edited_df[edited_df["_type"] == "total"]
            if not total_row.empty:
                tong_so_goc = total_row.iloc[0][col_so_goc]
                tong_giao = total_row.iloc[0][col_giao]
                tong_kh = total_row.iloc[0][col_kh]
                _giao_str = (f"+{vn(tong_giao, 0)}" if tong_giao > 0 else vn(tong_giao, 0))
                st.markdown(
                    f"<div style='background:#e3f2fd;padding:10px 14px;border-radius:6px;"
                    f"font-weight:700;font-size:14px;margin-top:8px'>"
                    f"📊 TỔNG CỘNG TOÀN XÃ: Số gốc {vn(tong_so_goc, 0)} · "
                    f"Giao tăng/giảm {_giao_str} · "
                    f"Chỉ tiêu KH {vn(tong_kh, 0)} triệu đồng</div>",
                    unsafe_allow_html=True,
                )

        # Extract data để lưu
        data_nhap = _extract_data_from_edited_df(edited_df, nam_kh) if edited_df is not None else {}

        st.divider()

        # ── ⑥ Hành động: Lưu + Xuất Word ─────────────────────────────────────
        col_luu, col_word_label, col_word_sel, col_word_btn = st.columns([1, 1, 2, 1])

        with col_luu:
            btn_luu = st.button("💾 Lưu", type="primary", key="m07_btn_luu")

        with col_word_label:
            st.markdown("<div style='padding-top:8px'>📄 Xuất Word lần:</div>",
                        unsafe_allow_html=True)

        with col_word_sel:
            opts_xuat = ["Đang nhập"] + [f"Lần {i+1}" for i in range(len(lich_su))]
            lan_xuat = st.selectbox(
                "Xuất lần", opts_xuat,
                key="m07_lan_xuat",
                label_visibility="collapsed",
            )

        with col_word_btn:
            btn_word = st.button("Xuất ▶", key="m07_btn_word")

        # ── Xử lý Lưu ─────────────────────────────────────────────────────────
        if btn_luu:
            co_du_lieu = any(float(v) != 0 for v in data_nhap.values()) if data_nhap else False
            if not co_du_lieu:
                st.error("❌ Chưa có chỉ tiêu nào khác 0. Vui lòng nhập dữ liệu trước khi lưu.")
            else:
                # Cảnh báo nếu tổng thay đổi > 20% so với lần trước
                if lich_su:
                    tong_cu = sum(float(v) for v in lich_su[-1].get("data", {}).values())
                    tong_moi = sum(float(v) for v in data_nhap.values())
                    if tong_cu > 0:
                        pct_thay_doi = abs(tong_moi - tong_cu) / tong_cu * 100
                        if pct_thay_doi > 20:
                            st.warning(
                                f"⚠️ Tổng xã thay đổi **{pct_thay_doi:.1f}%** so với lần trước "
                                f"({vn(tong_cu,1)} → {vn(tong_moi,1)} triệu). Nhấn **Lưu** lần nữa để xác nhận."
                            )
                            if "m07_confirmed" not in st.session_state:
                                st.session_state["m07_confirmed"] = False
                                st.stop()

                lan_moi = len(lich_su) + 1
                entry = {
                    "lan":      lan_moi,
                    "loai":     loai_van_ban,
                    "ngay":     datetime.now().isoformat(),
                    "username": username,
                    "data":     data_nhap,
                }
                ok1 = _luu_kv(kv_key_ht, data_nhap, username)
                ok2 = _luu_kv(kv_key_ls, lich_su + [entry], username)
                _sync_khtd_xa(xa_chon_raw, data_nhap, username)
                db.ghi_audit(
                    username,
                    "luu_khtd_mau07",
                    f"{loai_van_ban} lần {lan_moi} — {xa_chon_raw} ({pgd_chon})",
                )
                if ok1 and ok2:
                    st.success(f"✅ Đã lưu lần {lan_moi} thành công!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("❌ Lỗi khi lưu dữ liệu. Vui lòng thử lại.")

        # ── Xử lý Xuất Word ───────────────────────────────────────────────────
        if btn_word:
            xuat_data_src = data_nhap if lan_xuat == "Đang nhập" else (
                lich_su[int(lan_xuat.split()[1]) - 1]["data"] if lich_su else data_nhap
            )
            if not xuat_data_src:
                st.error("❌ Không có dữ liệu để xuất.")
            else:
                lan_chon_val = "dang_nhap" if lan_xuat == "Đang nhập" else int(lan_xuat.split()[1])
                try:
                    doc_bytes = xuat_mau07_word(
                        xa=xa_chon_raw,
                        nam=nam_kh,
                        loai_van_ban=loai_van_ban,
                        data_dict=xuat_data_src,
                        du_no_baseline=du_no_baseline,
                        lich_su=lich_su,
                        lan_chon=lan_chon_val,
                    )
                    ten_file = (
                        f"Mau07_{_slug(xa_chon_raw)}_{loai_van_ban}_"
                        f"{datetime.now().strftime('%d%m%Y')}.docx"
                    )
                    st.download_button(
                        label="⬇️ Tải về Word (.docx)",
                        data=doc_bytes,
                        file_name=ten_file,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="m07_dl_word",
                    )
                    st.success("✅ Đã tạo file Word — nhấn nút trên để tải về!")
                except Exception as e:
                    st.error(f"❌ Lỗi xuất Word: {e}")
                    st.exception(e)

        # ── ⑦ Lịch sử ────────────────────────────────────────────────────────
        st.divider()
        with st.expander("📜 Lịch sử giao/điều chỉnh", expanded=False):
            _render_lich_su(lich_su)
