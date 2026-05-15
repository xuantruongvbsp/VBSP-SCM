"""Theo dõi nợ rủi ro QĐ62/QĐ-HĐQT NHCSXH — 2 luồng PGD (nhập) và Chi nhánh (kiểm soát)."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from auth import normalize_role
from config import DS_PGD, PGD_XA_MAP, PGD_DATA_DIR
from data.pgd import pgd_slug, thu_muc_pgd
from utils import fmt_ty

logger = logging.getLogger(__name__)

# ── Lý do rủi ro theo QĐ62 ──────────────────────────────────────────────────
LY_DO_RUI_RO = [
    "Thiên tai",
    "Dịch bệnh",
    "Chết/mất tích",
    "Bỏ đi khỏi nơi cư trú",
    "Lý do khác",
]

# ── Mapping trạng thái → badge hiển thị ─────────────────────────────────────
TRANG_THAI_BADGE = {
    "cho_duyet": "🟡 Chờ duyệt",
    "da_duyet": "🟢 Đã duyệt",
    "tu_choi": "🔴 Không duyệt",
}

# ── Cố định key prefix ──────────────────────────────────────────────────────
_KV_PREFIX = "qd62_pgd_"


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _kv_key(slug: str) -> str:
    return f"{_KV_PREFIX}{slug}"


def _doc_ds(slug: str) -> list[dict]:
    """Đọc danh sách hồ sơ QĐ62 của một PGD. Trả về list rỗng nếu chưa có."""
    data = db.doc_kv(_kv_key(slug))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "danh_sach" in data:
        return data["danh_sach"]
    return []


def _ghi_ds(slug: str, danh_sach: list[dict], username: str) -> None:
    db.ghi_kv(_kv_key(slug), danh_sach, username)


def _lay_pgd_slug(pgd_filter: str | None, role: str) -> str | None:
    """Xác định slug PGD từ filter hoặc role."""
    if pgd_filter:
        return pgd_slug(pgd_filter)
    return None


def _lay_ten_pgd_tu_slug(slug: str) -> str:
    """Tra ngược slug → tên PGD từ DS_PGD."""
    for ten in DS_PGD:
        if pgd_slug(ten) == slug:
            return ten
    return slug


def _lay_ds_xa(slug: str) -> list[str]:
    """Lấy danh sách xã của PGD từ config."""
    ten_pgd = _lay_ten_pgd_tu_slug(slug)
    return PGD_XA_MAP.get(ten_pgd, [])


def _lay_ct_registry(slug: str) -> list[str]:
    """Đọc danh sách chương trình tín dụng từ registry của PGD."""
    data = db.doc_kv(f"ct_registry_{slug}")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.keys())
    return []


def _badge(trang_thai: str) -> str:
    return TRANG_THAI_BADGE.get(trang_thai, trang_thai)


# ══════════════════════════════════════════════════════════════════════════════
# LUỒNG 1 — PGD
# ══════════════════════════════════════════════════════════════════════════════

def _render_pgd(pgd_filter: str, username: str) -> None:
    slug = pgd_slug(pgd_filter)
    ten_pgd = pgd_filter

    # ── A. Metrics ────────────────────────────────────────────────────────
    ds = _doc_ds(slug)
    tong_so = len(ds)
    tong_goc = sum(r.get("du_no_goc", 0) for r in ds)
    tong_lai = sum(r.get("du_no_lai", 0) for r in ds)
    so_cho = sum(1 for r in ds if r.get("trang_thai") == "cho_duyet")
    so_duyet = sum(1 for r in ds if r.get("trang_thai") == "da_duyet")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Tổng hồ sơ", f"{tong_so}")
    c2.metric("💰 Dư nợ gốc", fmt_ty(tong_goc) if tong_goc else "0")
    c3.metric("⏳ Chờ duyệt", f"{so_cho}")
    c4.metric("✅ Đã duyệt", f"{so_duyet}")

    # ── B. Form nhập hồ sơ mới ────────────────────────────────────────────
    with st.expander("➕ Thêm hồ sơ mới", expanded=True):
        with st.form("form_qd62_pgd", clear_on_submit=False):
            col_a, col_b = st.columns(2)
            with col_a:
                ho_ten = st.text_input("Họ tên khách hàng *", placeholder="Nguyễn Văn A", key="qd62_ho_ten")
                so_cccd = st.text_input("Số CCCD/CMND *", placeholder="0790xxxxxx", key="qd62_so_cccd")
                ds_xa = _lay_ds_xa(slug)
                xa = st.selectbox("Xã/Phường *", ds_xa if ds_xa else [""])
            with col_b:
                ds_ct = _lay_ct_registry(slug)
                chuong_trinh = st.selectbox(
                    "Chương trình tín dụng",
                    ds_ct if ds_ct else ["-- Chưa có dữ liệu --"],
                )
                du_no_goc = st.number_input(
                    "Dư nợ gốc (triệu đồng) *",
                    min_value=0.0, step=0.1, format="%.1f",
                )
                du_no_lai = st.number_input(
                    "Dư nợ lãi (triệu đồng)",
                    min_value=0.0, step=0.1, format="%.1f",
                )

            ly_do = st.selectbox("Lý do rủi ro *", LY_DO_RUI_RO)
            ghi_chu = st.text_area("Ghi chú", placeholder="Thông tin bổ sung (nếu có)", height=80)

            file_ho_so = st.file_uploader(
                "File hồ sơ đính kèm (PDF/XLSX/DOCX)",
                type=["pdf", "xlsx", "docx"],
                accept_multiple_files=False,
            )

            submitted = st.form_submit_button("💾 Lưu hồ sơ", type="primary")

        if submitted:
            # Validate
            errs = []
            if not ho_ten.strip():
                errs.append("Họ tên khách hàng")
            if not so_cccd.strip():
                errs.append("Số CCCD/CMND")
            if du_no_goc <= 0:
                errs.append("Dư nợ gốc phải > 0")
            if not xa or xa == "":
                errs.append("Xã/Phường")
            if errs:
                st.error(f"⚠️ Vui lòng nhập: {', '.join(errs)}")
                st.stop()

            # Chuyển triệu → VND
            du_no_goc_vnd = int(du_no_goc * 1_000_000)
            du_no_lai_vnd = int(du_no_lai * 1_000_000)

            # Xử lý file đính kèm
            ten_file_dinh_kem = ""
            if file_ho_so is not None:
                try:
                    thu_muc = thu_muc_pgd(ten_pgd) / "qd62"
                    thu_muc.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ten_file_dinh_kem = f"qd62_{timestamp}_{file_ho_so.name}"
                    duong_dan = thu_muc / ten_file_dinh_kem
                    with open(duong_dan, "wb") as f:
                        f.write(file_ho_so.getbuffer())
                except Exception as e:
                    logger.error(f"Lỗi lưu file đính kèm QĐ62: {e}")
                    st.error(f"⚠️ Không thể lưu file đính kèm: {e}")
                    st.stop()

            record = {
                "id": f"{slug}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "ho_ten": ho_ten.strip(),
                "so_cccd": so_cccd.strip(),
                "xa": xa,
                "chuong_trinh": chuong_trinh,
                "du_no_goc": du_no_goc_vnd,
                "du_no_lai": du_no_lai_vnd,
                "ly_do": ly_do,
                "ghi_chu": ghi_chu.strip(),
                "file_dinh_kem": ten_file_dinh_kem,
                "pgd_slug": slug,
                "ngay_lap": datetime.now().isoformat(),
                "trang_thai": "cho_duyet",
                "nguoi_lap": username,
                "nguoi_duyet": "",
                "ngay_duyet": "",
            }

            ds_moi = list(ds)
            ds_moi.append(record)
            _ghi_ds(slug, ds_moi, username)
            db.ghi_audit(username, "qd62_them_ho_so",
                         f"PGD {ten_pgd} | KH: {ho_ten.strip()} | Gốc: {fmt_ty(du_no_goc_vnd)}")
            st.cache_data.clear()
            st.success(f"✅ Đã thêm hồ sơ: {ho_ten.strip()}")
            st.rerun()

    # ── C. Bảng danh sách hồ sơ ──────────────────────────────────────────
    st.markdown("#### 📋 Danh sách hồ sơ")
    if not ds:
        st.info("ℹ️ Chưa có hồ sơ nào được lập.")
    else:
        df_hs = pd.DataFrame(ds)
        # Filter theo Xã
        ds_xa_loc = sorted(df_hs["xa"].dropna().unique().tolist()) if "xa" in df_hs.columns else []
        chon_xa_loc = st.selectbox("🔎 Lọc theo Xã", ["Tất cả"] + ds_xa_loc, key="qd62_pgd_loc_xa")
        if chon_xa_loc != "Tất cả":
            df_hs = df_hs[df_hs["xa"] == chon_xa_loc]

        # Format hiển thị
        df_show = df_hs.copy()
        if "du_no_goc" in df_show.columns:
            df_show["du_no_goc"] = df_show["du_no_goc"].apply(lambda x: fmt_ty(x) if x else "—")
        if "du_no_lai" in df_show.columns:
            df_show["du_no_lai"] = df_show["du_no_lai"].apply(lambda x: fmt_ty(x) if x else "—")
        if "trang_thai" in df_show.columns:
            df_show["trang_thai"] = df_show["trang_thai"].apply(_badge)
        if "file_dinh_kem" in df_show.columns:
            df_show["file_dinh_kem"] = df_show["file_dinh_kem"].apply(
                lambda x: "📎 Có" if x else "—"
            )

        cot_hien_thi = [c for c in ["ho_ten", "xa", "chuong_trinh", "du_no_goc",
                                      "du_no_lai", "ly_do", "trang_thai",
                                      "file_dinh_kem", "ngay_lap"] if c in df_show.columns]
        df_show = df_show[cot_hien_thi]
        df_show.index = range(1, len(df_show) + 1)
        df_show.index.name = "STT"

        st.dataframe(df_show, use_container_width=True, height=400)

        # Nút xoá cho hồ sơ "chờ duyệt"
        st.markdown("**Xoá hồ sơ (chỉ hồ sơ Chờ duyệt)**")
        ds_cho = [r for r in ds if r.get("trang_thai") == "cho_duyet"]
        if ds_cho:
            ten_cho = {r["id"]: f"{r.get('ho_ten','?')} — {fmt_ty(r.get('du_no_goc',0))}"
                       for r in ds_cho}
            id_xoa = st.selectbox(
                "Chọn hồ sơ cần xoá",
                options=list(ten_cho.keys()),
                format_func=lambda k: ten_cho.get(k, k),
                key="qd62_pgd_chon_xoa",
            )
            if st.button("🗑️ Xoá hồ sơ", type="secondary", key="qd62_pgd_btn_xoa"):
                ds_sau = [r for r in ds if r.get("id") != id_xoa]
                _ghi_ds(slug, ds_sau, username)
                db.ghi_audit(username, "qd62_xoa_ho_so",
                             f"PGD {ten_pgd} | ID: {id_xoa}")
                st.cache_data.clear()
                st.success("✅ Đã xoá hồ sơ.")
                st.rerun()
        else:
            st.caption("Không có hồ sơ nào ở trạng thái 'Chờ duyệt' để xoá.")


# ══════════════════════════════════════════════════════════════════════════════
# LUỒNG 2 — CHI NHÁNH
# ══════════════════════════════════════════════════════════════════════════════

def _doc_toan_cn() -> pd.DataFrame:
    """Gộp tất cả hồ sơ QĐ62 từ các PGD trong DS_PGD thành 1 DataFrame."""
    all_rows = []
    for ten_pgd in DS_PGD:
        slug = pgd_slug(ten_pgd)
        ds = _doc_ds(slug)
        for r in ds:
            r_copy = dict(r)
            r_copy["pgd"] = ten_pgd
            all_rows.append(r_copy)
    if not all_rows:
        return pd.DataFrame()
    return pd.DataFrame(all_rows)


def _render_cn(username: str, role: str) -> None:
    # ── A. Metrics tổng ──────────────────────────────────────────────────
    df_all = _doc_toan_cn()
    tong_ho_so = len(df_all)
    tong_goc = int(df_all["du_no_goc"].sum()) if "du_no_goc" in df_all.columns else 0
    tong_lai = int(df_all["du_no_lai"].sum()) if "du_no_lai" in df_all.columns else 0
    tong_duyet = int((df_all["trang_thai"] == "da_duyet").sum()) if "trang_thai" in df_all.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Tổng hồ sơ toàn CN", f"{tong_ho_so}")
    c2.metric("💰 Tổng dư nợ gốc", fmt_ty(tong_goc) if tong_goc else "0")
    c3.metric("📊 Tổng dư nợ lãi", fmt_ty(tong_lai) if tong_lai else "0")
    c4.metric("✅ Đã duyệt / Tổng", f"{tong_duyet}/{tong_ho_so}")

    if df_all.empty:
        st.info("ℹ️ Chưa có hồ sơ QĐ62 nào từ các PGD.")
        return

    # ── B. Bảng tổng hợp toàn CN ─────────────────────────────────────────
    st.markdown("#### 📋 Bảng tổng hợp toàn Chi nhánh")

    # Filter controls
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        ds_pgd_opt = ["Tất cả"] + sorted(df_all["pgd"].dropna().unique().tolist())
        chon_pgd = st.multiselect("PGD", ds_pgd_opt, default=["Tất cả"], key="qd62_cn_pgd")
    with col_f2:
        ds_tt_opt = ["Tất cả"] + list(TRANG_THAI_BADGE.keys())
        chon_tt = st.multiselect("Trạng thái", ds_tt_opt, default=["Tất cả"], key="qd62_cn_tt")
    with col_f3:
        ds_lydo = ["Tất cả"] + sorted(df_all["ly_do"].dropna().unique().tolist())
        chon_lydo = st.selectbox("Lý do rủi ro", ds_lydo, key="qd62_cn_lydo")

    # Apply filters
    df_loc = df_all.copy()
    if "Tất cả" not in chon_pgd and chon_pgd:
        df_loc = df_loc[df_loc["pgd"].isin(chon_pgd)]
    if "Tất cả" not in chon_tt and chon_tt:
        df_loc = df_loc[df_loc["trang_thai"].isin(chon_tt)]
    if chon_lydo != "Tất cả":
        df_loc = df_loc[df_loc["ly_do"] == chon_lydo]

    # Format display
    df_show = df_loc.copy()
    if "du_no_goc" in df_show.columns:
        df_show["du_no_goc"] = df_show["du_no_goc"].apply(lambda x: fmt_ty(x) if x else "—")
    if "du_no_lai" in df_show.columns:
        df_show["du_no_lai"] = df_show["du_no_lai"].apply(lambda x: fmt_ty(x) if x else "—")
    if "trang_thai" in df_show.columns:
        df_show["trang_thai"] = df_show["trang_thai"].apply(_badge)
    if "file_dinh_kem" in df_show.columns:
        df_show["file_dinh_kem"] = df_show["file_dinh_kem"].apply(lambda x: "📎 Có" if x else "—")

    cot_hien = [c for c in ["pgd", "ho_ten", "xa", "chuong_trinh", "du_no_goc",
                              "du_no_lai", "ly_do", "trang_thai", "file_dinh_kem",
                              "ngay_lap"] if c in df_show.columns]
    df_show = df_show[cot_hien]
    df_show.index = range(1, len(df_show) + 1)
    df_show.index.name = "STT"

    st.dataframe(df_show, use_container_width=True, height=400)

    # Dòng tổng cộng
    tong_goc_loc = int(df_loc["du_no_goc"].sum()) if "du_no_goc" in df_loc.columns else 0
    tong_lai_loc = int(df_loc["du_no_lai"].sum()) if "du_no_lai" in df_loc.columns else 0
    st.caption(f"**Tổng cộng:** Gốc {fmt_ty(tong_goc_loc)} | Lãi {fmt_ty(tong_lai_loc)} | {len(df_loc)} hồ sơ")

    # ── C. Panel kiểm soát ───────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### ✅ Duyệt hồ sơ")

    # Xác định danh sách PGD được phép duyệt
    if normalize_role(str(role or "user")) in ("admin_cn", "executive"):
        ds_pgd_duyet = DS_PGD
    else:
        ds_pgd_duyet = DS_PGD  # manager_cn được xem tất cả

    ten_pgd_chon = st.selectbox("Chọn PGD để xét duyệt", ds_pgd_duyet, key="qd62_cn_pgd_duyet")
    slug_chon = pgd_slug(ten_pgd_chon)
    ds_chon = [r for r in _doc_ds(slug_chon) if r.get("trang_thai") == "cho_duyet"]

    if not ds_chon:
        st.info(f"✅ PGD **{ten_pgd_chon}** không có hồ sơ nào chờ duyệt.")
    else:
        st.warning(f"⚠️ Có **{len(ds_chon)}** hồ sơ chờ duyệt từ {ten_pgd_chon}")

        for i, r in enumerate(ds_chon):
            with st.container(border=True):
                st.markdown(f"**{i+1}. {r.get('ho_ten','?')}** — {r.get('xa','')}")
                col_d1, col_d2, col_d3, col_d4 = st.columns(4)
                with col_d1:
                    st.markdown(f"**Gốc:** {fmt_ty(r.get('du_no_goc',0))}")
                with col_d2:
                    st.markdown(f"**Lãi:** {fmt_ty(r.get('du_no_lai',0))}")
                with col_d3:
                    st.markdown(f"**Lý do:** {r.get('ly_do','')}")
                with col_d4:
                    st.markdown(f"**CCCD:** {r.get('so_cccd','')}")
                if r.get("ghi_chu"):
                    st.caption(f"📝 {r['ghi_chu']}")

                c_duyet, c_tu_choi = st.columns(2)
                with c_duyet:
                    if st.button(f"✅ Duyệt", key=f"qd62_duyet_{r['id']}", use_container_width=True):
                        ds_cap_nhat = _doc_ds(slug_chon)
                        for rr in ds_cap_nhat:
                            if rr.get("id") == r["id"]:
                                rr["trang_thai"] = "da_duyet"
                                rr["nguoi_duyet"] = username
                                rr["ngay_duyet"] = datetime.now().isoformat()
                                break
                        _ghi_ds(slug_chon, ds_cap_nhat, username)
                        db.ghi_audit(username, "qd62_duyet",
                                     f"PGD {ten_pgd_chon} | KH: {r.get('ho_ten','')} | → da_duyet")
                        st.cache_data.clear()
                        st.success(f"✅ Đã duyệt: {r.get('ho_ten','')}")
                        st.rerun()
                with c_tu_choi:
                    if st.button(f"❌ Không duyệt", key=f"qd62_tu_choi_{r['id']}", use_container_width=True):
                        ds_cap_nhat = _doc_ds(slug_chon)
                        for rr in ds_cap_nhat:
                            if rr.get("id") == r["id"]:
                                rr["trang_thai"] = "tu_choi"
                                rr["nguoi_duyet"] = username
                                rr["ngay_duyet"] = datetime.now().isoformat()
                                break
                        _ghi_ds(slug_chon, ds_cap_nhat, username)
                        db.ghi_audit(username, "qd62_duyet",
                                     f"PGD {ten_pgd_chon} | KH: {r.get('ho_ten','')} | → tu_choi")
                        st.cache_data.clear()
                        st.success(f"✅ Đã cập nhật: {r.get('ho_ten','')}")
                        st.rerun()

    # ── D. Export Excel ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📤 Xuất báo cáo")
    if st.button("⬇️ Xuất Excel toàn CN", type="primary", key="qd62_cn_export"):
        df_xuat = _doc_toan_cn()
        if df_xuat.empty:
            st.warning("Không có dữ liệu để xuất.")
        else:
            df_xuat_tt = df_xuat.copy()
            # Lọc "chờ duyệt"
            df_xuat_cd = df_xuat_tt[df_xuat_tt["trang_thai"] == "cho_duyet"].copy()

            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_xuat_tt.to_excel(writer, sheet_name="Tổng hợp", index=False)
                df_xuat_cd.to_excel(writer, sheet_name="Chờ duyệt", index=False)
            output.seek(0)

            ten_file = f"QD62_tong_hop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            st.session_state["_bytes_qd62"] = output.getvalue()
            st.session_state["_file_qd62"] = ten_file

    if st.session_state.get("_bytes_qd62"):
        st.download_button(
            "⬇️ Tải file Excel",
            data=st.session_state["_bytes_qd62"],
            file_name=st.session_state["_file_qd62"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="qd62_cn_dl_excel",
        )


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def render(mode: str, pgd_filter: str | None = None) -> None:
    """
    Điểm vào chính cho tab QĐ62.

    Args:
        mode: "pgd" — luồng PGD (CBTD nhập hồ sơ)
              "cn"  — luồng Chi nhánh (manager/admin kiểm soát)
        pgd_filter: Tên PGD (bắt buộc nếu mode="pgd", bỏ qua nếu mode="cn")
    """
    if mode not in ("pgd", "cn"):
        st.error(f"⚠️ mode không hợp lệ: {mode}. Chỉ chấp nhận 'pgd' hoặc 'cn'.")
        return

    username = st.session_state.get("username", "unknown")
    role = st.session_state.get("user_info", {}).get("role", "user")

    st.subheader("⚠️ Theo dõi nợ rủi ro — QĐ62/QĐ-HĐQT NHCSXH")
    st.caption(
        "Quản lý hồ sơ đề nghị xử lý nợ rủi ro. "
        "PGD nhập đề nghị → Chi nhánh kiểm soát và phê duyệt."
    )

    if mode == "pgd":
        if not pgd_filter:
            # Fallback: lấy từ session
            pgd_filter = st.session_state.get("user_info", {}).get("pgd")
        if not pgd_filter:
            st.error("⚠️ Không xác định được PGD. Vui lòng chọn từ sidebar.")
            return
        _render_pgd(pgd_filter, username)
    else:
        _render_cn(username, role)
