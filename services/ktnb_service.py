"""
KTNB Service — Kiểm toán Nội bộ (Internal Audit)
4 phân hệ:
  A. Kế hoạch & Lịch trình
  B. Chọn mẫu đối chiếu
  C. Nhập kết quả đối chiếu thực tế
  D. Giám sát & Khắc phục lỗi
"""
from __future__ import annotations

import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

import db
from auth import normalize_role
from config import (
    COT_TEN_PGD,
    COT_MA_KH,
    COT_TEN_KH,
    COT_SO_KU,
    COT_NGAY_VAY,
    COT_NGAY_DH,
    COT_THOI_HAN,
    COT_LAI_SUAT,
    COT_MUC_VAY,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_TONG_DU_NO,
    COT_DU_NO_KHOANH,
    COT_TEN_CT,
    COT_TINH_TRANG,
    COT_DIA_CHI,
    DS_PGD,
    PGD_DATA_DIR,
)
from logger import get_logger
from utils import fmt_ty, fmt_ngay, hien_thi_dataframe_phan_trang, xuat_excel, ten_file_xuat

logger = get_logger(__name__)

KTNB_DIR = PGD_DATA_DIR / "ktnb"
KTNB_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PHÂN HỆ A — KẾ HOẠCH & LỊCH TRÌNH
# ═══════════════════════════════════════════════════════════════════════════════


def them_dot_kiem_tra(
    nam: int,
    so_cv: str,
    loai_hinh: str,
    ten_pgd_ks: str,
    ngay_bat_dau: str,
    ngay_ket_thuc: str,
    truong_doan: str,
    ghi_chu: str,
    username: str,
) -> int:
    """Thêm đợt kiểm tra mới. Trả về dot_id."""
    with db.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO ktnb_dot_kiem_tra
                (nam, so_cv, loai_hinh, ten_pgd_ks, ngay_bat_dau, ngay_ket_thuc,
                 truong_doan, ghi_chu, nguoi_tao)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (nam, so_cv, loai_hinh, ten_pgd_ks, ngay_bat_dau, ngay_ket_thuc,
             truong_doan, ghi_chu, username),
        )
        conn.commit()
        dot_id = cur.lastrowid
    db.ghi_audit(username, "ktnb_them_dot", f"dot_id={dot_id}, pgd={ten_pgd_ks}")
    return dot_id


def cap_nhat_dot_kiem_tra(dot_id: int, data: dict, username: str) -> bool:
    """Cập nhật thông tin đợt kiểm tra."""
    allowed = {"so_cv", "loai_hinh", "ngay_bat_dau", "ngay_ket_thuc",
               "truong_doan", "trang_thai", "ghi_chu"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return False
    set_clause = ", ".join(f"{k}=?" for k in fields.keys())
    values = list(fields.values()) + [dot_id]
    with db.get_conn() as conn:
        conn.execute(
            f"UPDATE ktnb_dot_kiem_tra SET {set_clause}, updated_at=datetime('now','localtime') WHERE id=?",
            values,
        )
        conn.commit()
    db.ghi_audit(username, "ktnb_cap_nhat_dot", f"dot_id={dot_id}")
    return True


def lay_danh_sach_dot(nam: Optional[int] = None) -> pd.DataFrame:
    """Lấy danh sách đợt kiểm tra theo năm."""
    sql = """
        SELECT id, nam, so_cv, loai_hinh, ten_pgd_ks,
               ngay_bat_dau, ngay_ket_thuc, truong_doan, trang_thai, ghi_chu
        FROM ktnb_dot_kiem_tra
    """
    params = []
    if nam:
        sql += " WHERE nam = ?"
        params.append(nam)
    sql += " ORDER BY nam DESC, ngay_bat_dau DESC"
    with db.get_conn() as conn:
        df = pd.read_sql_query(sql, conn, params=params)
    return df


def lay_dot_by_id(dot_id: int) -> Optional[dict]:
    """Lấy chi tiết một đợt kiểm tra."""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM ktnb_dot_kiem_tra WHERE id = ?", (dot_id,)
        ).fetchone()
    if row:
        return dict(row)
    return None


def cap_nhat_thanh_phan_doan(dot_id: int, thanh_vien: list[dict], username: str) -> bool:
    """Cập nhật danh sách thành viên đoàn kiểm tra."""
    with db.get_conn() as conn:
        conn.execute("DELETE FROM ktnb_doan_kiem_tra WHERE dot_id = ?", (dot_id,))
        for tv in thanh_vien:
            conn.execute(
                """
                INSERT INTO ktnb_doan_kiem_tra
                    (dot_id, ho_ten, chuc_vu, don_vi, vai_tro, ghi_chu)
                VALUES (?,?,?,?,?,?)
                """,
                (dot_id, tv.get("ho_ten"), tv.get("chuc_vu"), tv.get("don_vi"),
                 tv.get("vai_tro", "thanh_vien"), tv.get("ghi_chu")),
            )
        conn.commit()
    db.ghi_audit(username, "ktnb_cap_nhat_doan", f"dot_id={dot_id}, {len(thanh_vien)} TV")
    return True


def lay_thanh_phan_doan(dot_id: int) -> pd.DataFrame:
    """Lấy danh sách thành viên đoàn kiểm tra."""
    with db.get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM ktnb_doan_kiem_tra WHERE dot_id = ? ORDER BY vai_tro DESC, ho_ten",
            conn, params=(dot_id,)
        )
    return df


def _tinh_trang_lich(ngay_bat_dau: str, ngay_ket_thuc: str) -> str:
    """Trả về trạng thái lịch trình: dung_han, sap_toi, qua_han."""
    if not ngay_bat_dau or not ngay_ket_thuc:
        return "chua_xac_dinh"
    try:
        today = date.today()
        d_start = datetime.strptime(ngay_bat_dau, "%Y-%m-%d").date()
        d_end = datetime.strptime(ngay_ket_thuc, "%Y-%m-%d").date()
        if today < d_start:
            return "sap_toi"
        if d_start <= today <= d_end:
            return "dung_han"
        return "qua_han"
    except Exception:
        return "chua_xac_dinh"


def render_ke_hoach_lich_trinh(username: str, readonly: bool = False) -> None:
    """UI Phân hệ A: Kế hoạch & Lịch trình."""
    st.subheader("📅 Kế hoạch & Lịch trình kiểm toán")

    current_year = date.today().year
    nam = st.selectbox("Năm kiểm toán", list(range(current_year - 2, current_year + 3)),
                       index=2, key="ktnb_nam_ke_hoach")

    df_dots = lay_danh_sach_dot(nam)
    if not df_dots.empty:
        df_dots["Trạng thái lịch"] = df_dots.apply(
            lambda r: _tinh_trang_lich(r.get("ngay_bat_dau", ""), r.get("ngay_ket_thuc", "")), axis=1
        )
        col_map = {
            "id": "ID", "so_cv": "Số CV", "loai_hinh": "Loại hình",
            "ten_pgd_ks": "PGD kiểm tra", "truong_doan": "Trưởng đoàn",
            "ngay_bat_dau": "Ngày BĐ", "ngay_ket_thuc": "Ngày KT", "trang_thai": "Trạng thái"
        }
        df_display = df_dots.rename(columns=col_map)[["ID", "Số CV", "Loại hình", "PGD kiểm tra",
                                                       "Trưởng đoàn", "Ngày BĐ", "Ngày KT", "Trạng thái"]]
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có đợt kiểm toán nào trong năm này.")

    if readonly:
        st.caption("🔒 Chế độ chỉ xem — BGD không chỉnh sửa")
        return

    with st.expander("➕ Thêm đợt kiểm tra mới"):
        with st.form("form_them_dot"):
            col1, col2 = st.columns(2)
            with col1:
                so_cv = st.text_input("Số công văn", placeholder="VD: 1234/NHCS-KTNB")
                loai_hinh = st.selectbox("Loại hình", ["dinh_ky", "dot_xuat", "chuyen_sau"])
                ten_pgd = st.selectbox("PGD kiểm tra", DS_PGD)
            with col2:
                ngay_bd = st.date_input("Ngày bắt đầu", date.today())
                ngay_kt = st.date_input("Ngày kết thúc", date.today())
                truong_doan = st.text_input("Trưởng đoàn")
            ghi_chu = st.text_area("Ghi chú")
            submitted = st.form_submit_button("Lưu đợt kiểm tra", use_container_width=True)
            if submitted:
                if not so_cv or not truong_doan:
                    st.error("Vui lòng nhập Số CV và Trưởng đoàn")
                else:
                    dot_id = them_dot_kiem_tra(
                        nam=nam, so_cv=so_cv, loai_hinh=loai_hinh, ten_pgd_ks=ten_pgd,
                        ngay_bat_dau=ngay_bd.strftime("%Y-%m-%d"),
                        ngay_ket_thuc=ngay_kt.strftime("%Y-%m-%d"),
                        truong_doan=truong_doan, ghi_chu=ghi_chu, username=username,
                    )
                    st.success(f"Đã tạo đợt kiểm tra ID: {dot_id}")
                    st.rerun()

    if not df_dots.empty:
        with st.expander("👥 Cập nhật thành phần đoàn"):
            dot_options = {f"{r['id']}: {r['ten_pgd_ks']} ({r['so_cv']})": r['id']
                          for _, r in df_dots.iterrows()}
            dot_sel = st.selectbox("Chọn đợt", list(dot_options.keys()), key="ktnb_dot_tp")
            dot_id = dot_options[dot_sel]

            df_tv = lay_thanh_phan_doan(dot_id)
            st.caption(f"Hiện có {len(df_tv)} thành viên")
            if not df_tv.empty:
                st.dataframe(df_tv[["ho_ten", "chuc_vu", "don_vi", "vai_tro"]], hide_index=True)

            st.markdown("**Thêm thành viên**")
            with st.form("form_them_tv"):
                cols = st.columns([2, 2, 2, 1, 1])
                with cols[0]:
                    ho_ten = st.text_input("Họ tên", key="tv_hoten")
                with cols[1]:
                    chuc_vu = st.text_input("Chức vụ", key="tv_chucvu")
                with cols[2]:
                    don_vi = st.text_input("Đơn vị", key="tv_donvi")
                with cols[3]:
                    vai_tro = st.selectbox("Vai trò", ["thanh_vien", "truong_doan", "pho_doan"], key="tv_vaitro")
                with cols[4]:
                    st.markdown("<br>", unsafe_allow_html=True)
                    them_tv = st.form_submit_button("➕ Thêm", use_container_width=True)

                if them_tv and ho_ten:
                    current = df_tv.to_dict("records") if not df_tv.empty else []
                    current.append({"ho_ten": ho_ten, "chuc_vu": chuc_vu,
                                  "don_vi": don_vi, "vai_tro": vai_tro})
                    cap_nhat_thanh_phan_doan(dot_id, current, username)
                    st.success("Đã thêm thành viên")
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PHÂN HỆ B — CHỌN MẪU ĐỐI CHIẾU
# ═══════════════════════════════════════════════════════════════════════════════


def chon_mau_doi_chieu(
    df_full: pd.DataFrame,
    dot_id: int,
    ty_le_pct: float = 10.0,
    uu_tien_rui_ro: bool = True,
) -> pd.DataFrame:
    """
    Chọn mẫu đối chiếu KH từ df_full.
    - Ưu tiên 100%: nợ QH > 0, nợ khoanh > 0
    - Phần còn lại: random sample theo tỷ lệ %
    """
    if df_full is None or df_full.empty:
        return pd.DataFrame()

    df = df_full.copy()
    col_ku = COT_SO_KU if COT_SO_KU in df.columns else None
    if col_ku is None:
        df["__ma_mon"] = df.index.astype(str)
        col_ku = "__ma_mon"

    col_qh = COT_DU_NO_QH if COT_DU_NO_QH in df.columns else None
    col_khoanh = COT_DU_NO_KHOANH if COT_DU_NO_KHOANH in df.columns else None

    mask_risk = pd.Series(False, index=df.index)
    if uu_tien_rui_ro and col_qh:
        mask_risk |= pd.to_numeric(df[col_qh], errors="coerce").fillna(0) > 0
    if uu_tien_rui_ro and col_khoanh:
        mask_risk |= pd.to_numeric(df[col_khoanh], errors="coerce").fillna(0) > 0

    df_risk = df[mask_risk].copy() if mask_risk.any() else pd.DataFrame()

    df_non_risk = df[~mask_risk].copy()
    n_sample = max(1, int(len(df_non_risk) * ty_le_pct / 100))
    df_sample = df_non_risk.sample(n=min(n_sample, len(df_non_risk)), random_state=42) if len(df_non_risk) > 0 else pd.DataFrame()

    df_mau = pd.concat([df_risk, df_sample], ignore_index=True)
    df_mau["__dot_id"] = dot_id
    return df_mau


def luu_mau_doi_chieu(dot_id: int, df_mau: pd.DataFrame, username: str) -> int:
    """Lưu mẫu đối chiếu vào DB. Trả về số bản ghi đã lưu."""
    if df_mau is None or df_mau.empty:
        return 0

    col_ku = COT_SO_KU if COT_SO_KU in df_mau.columns else "__ma_mon"
    col_pgd = COT_TEN_PGD if COT_TEN_PGD in df_mau.columns else None
    col_tenkh = COT_TEN_KH if COT_TEN_KH in df_mau.columns else None
    col_mucvay = COT_MUC_VAY if COT_MUC_VAY in df_mau.columns else None
    col_tongdn = COT_TONG_DU_NO if COT_TONG_DU_NO in df_mau.columns else None
    col_tinhtrang = COT_TINH_TRANG if COT_TINH_TRANG in df_mau.columns else None
    col_qh = COT_DU_NO_QH if COT_DU_NO_QH in df_mau.columns else None
    col_khoanh = COT_DU_NO_KHOANH if COT_DU_NO_KHOANH in df_mau.columns else None

    count = 0
    with db.get_conn() as conn:
        for _, row in df_mau.iterrows():
            ma_mon = str(row.get(col_ku, ""))
            if not ma_mon:
                continue
            uu_tien = 0
            if col_qh and pd.to_numeric(row.get(col_qh, 0), errors="coerce") > 0:
                uu_tien = 1
            if col_khoanh and pd.to_numeric(row.get(col_khoanh, 0), errors="coerce") > 0:
                uu_tien = 1

            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO ktnb_mau_doi_chieu_kh
                        (dot_id, ma_mon_vay, ten_pgd, ten_kh, so_tien_vay, du_no_hstd,
                         tinh_trang, uu_tien_rui_ro, trang_thai_doi_chieu, nguoi_nhap)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (dot_id, ma_mon,
                     row.get(col_pgd) if col_pgd else None,
                     row.get(col_tenkh) if col_tenkh else None,
                     float(row.get(col_mucvay, 0)) if col_mucvay else None,
                     float(row.get(col_tongdn, 0)) if col_tongdn else None,
                     row.get(col_tinhtrang) if col_tinhtrang else None,
                     uu_tien, "chua_doi_chieu", username),
                )
                count += 1
            except Exception as e:
                logger.error("Lỗi lưu mẫu đối chiếu: %s", e)
        conn.commit()
    db.ghi_audit(username, "ktnb_luu_mau", f"dot_id={dot_id}, count={count}")
    return count


def render_chon_mau(dot_id: int, df_full: pd.DataFrame, username: str, readonly: bool = False) -> None:
    """UI Phân hệ B: Chọn mẫu đối chiếu."""
    st.subheader("🎯 Chọn mẫu đối chiếu khách hàng")

    dot = lay_dot_by_id(dot_id)
    if dot:
        st.caption(f"Đợt: {dot['ten_pgd_ks']} — CV: {dot['so_cv']} — Trưởng đoàn: {dot['truong_doan']}")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        ty_le = st.slider("Tỷ lệ mẫu (non-risk)", 1, 50, 10, key="ktnb_ty_le")
    with col2:
        uu_tien = st.checkbox("Ưu tiên rủi ro 100%", value=True, key="ktnb_uu_tien")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if not readonly:
            if st.button("🎲 Tạo mẫu đối chiếu", use_container_width=True):
                df_mau = chon_mau_doi_chieu(df_full, dot_id, ty_le, uu_tien)
                count = luu_mau_doi_chieu(dot_id, df_mau, username)
                st.success(f"Đã lưu {count} KH vào mẫu đối chiếu")
                st.session_state["ktnb_df_mau"] = df_mau
                st.rerun()

    # Hiển thị mẫu hiện có
    with db.get_conn() as conn:
        df_existing = pd.read_sql_query(
            "SELECT * FROM ktnb_mau_doi_chieu_kh WHERE dot_id = ? ORDER BY uu_tien_rui_ro DESC, ma_mon_vay",
            conn, params=(dot_id,)
        )
    if not df_existing.empty:
        st.write(f"**Mẫu đã chọn: {len(df_existing)} KH** (Ưu tiên rủi ro: {df_existing['uu_tien_rui_ro'].sum()})")
        df_display = df_existing.rename(columns={
            "ma_mon_vay": "Số KU", "ten_pgd": "PGD", "ten_kh": "Tên KH",
            "so_tien_vay": "Mức vay", "du_no_hstd": "Dư nợ HSTD",
            "trang_thai_doi_chieu": "Trạng thái", "uu_tien_rui_ro": "Ưu tiên"
        })
        hien_thi_dataframe_phan_trang(df_display, so_dong_moi_trang=100, key="ktnb_mau")
    else:
        st.info("Chưa có mẫu đối chiếu — Nhấn 'Tạo mẫu' để chọn")


# ═══════════════════════════════════════════════════════════════════════════════
# PHÂN HỆ C — NHẬP KẾT QUẢ ĐỐI CHIẾU THỰC TẾ
# ═══════════════════════════════════════════════════════════════════════════════


def lay_ho_so_doi_chieu(dot_id: int) -> pd.DataFrame:
    """Lấy danh sách hồ sơ đối chiếu của đợt kiểm tra."""
    with db.get_conn() as conn:
        df = pd.read_sql_query(
            """SELECT * FROM ktnb_mau_doi_chieu_kh WHERE dot_id = ?
               ORDER BY uu_tien_rui_ro DESC, ma_mon_vay""",
            conn, params=(dot_id,)
        )
    return df


def luu_ket_qua_doi_chieu(
    dot_id: int,
    ma_mon_vay: str,
    data_thuc_te: dict,
    username: str,
) -> bool:
    """Lưu kết quả đối chiếu thực tế cho một món vay."""
    allowed = {"du_no_thuc_te", "ghi_nhan_loi", "phat_hien_sai_sot", "ghi_chu"}
    fields = {k: v for k, v in data_thuc_te.items() if k in allowed}
    if not fields:
        return False

    set_clause = ", ".join(f"{k}=?" for k in fields.keys())
    values = list(fields.values()) + [datetime.now().isoformat(), dot_id, ma_mon_vay]

    with db.get_conn() as conn:
        conn.execute(
            f"""UPDATE ktnb_mau_doi_chieu_kh
                SET {set_clause}, updated_at=?, trang_thai_doi_chieu='da_doi_chieu'
                WHERE dot_id=? AND ma_mon_vay=?""",
            values,
        )
        conn.commit()
    db.ghi_audit(username, "ktnb_luu_doi_chieu", f"dot_id={dot_id}, ku={ma_mon_vay}")
    return True


def render_nhap_ket_qua(dot_id: int, df_full: pd.DataFrame, username: str, readonly: bool = False) -> None:
    """UI Phân hệ C: Nhập kết quả đối chiếu thực tế."""
    st.subheader("📝 Nhập kết quả đối chiếu thực tế")

    df_mau = lay_ho_so_doi_chieu(dot_id)
    if df_mau.empty:
        st.warning("Chưa có mẫu đối chiếu — Vui lòng chọn mẫu ở Phân hệ B trước")
        return

    # Merge với df_full để lấy thông tin đầy đủ
    col_ku = COT_SO_KU if COT_SO_KU in df_full.columns else None
    if col_ku:
        df_display = df_mau.merge(
            df_full[[col_ku, COT_TEN_KH, COT_TEN_PGD, COT_TEN_CT, COT_MUC_VAY,
                    COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH]],
            left_on="ma_mon_vay", right_on=col_ku, how="left"
        )
    else:
        df_display = df_mau.copy()

    # Bộ lọc trạng thái
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        loc_trang_thai = st.selectbox("Lọc trạng thái",
                                       ["Tất cả", "Chưa đối chiếu", "Đã đối chiếu"],
                                       key="ktnb_loc_tt")
    with col_f2:
        st.write(f"**Tổng: {len(df_display)} KH** | Đã đối chiếu: {(df_display['trang_thai_doi_chieu']=='da_doi_chieu').sum()}")

    if loc_trang_thai == "Chưa đối chiếu":
        df_display = df_display[df_display["trang_thai_doi_chieu"] == "chua_doi_chieu"]
    elif loc_trang_thai == "Đã đối chiếu":
        df_display = df_display[df_display["trang_thai_doi_chieu"] == "da_doi_chieu"]

    # Hiển thị dạng expandable cho từng KH
    for _, row in df_display.iterrows():
        with st.expander(f"{row.get('ma_mon_vay', '')} — {row.get(COT_TEN_KH, row.get('ten_kh', 'KH'))} ({row.get(COT_TEN_PGD, row.get('ten_pgd', ''))})"):
            cols = st.columns([1, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**Chương trình:** {row.get(COT_TEN_CT, '—')}")
                st.markdown(f"**Mức vay:** {fmt_ty(row.get(COT_MUC_VAY, row.get('so_tien_vay', 0)))}")
            with cols[1]:
                st.markdown(f"**Dư nợ HSTD:** {fmt_ty(row.get(COT_TONG_DU_NO, row.get('du_no_hstd', 0)))}")
                qh = row.get(COT_DU_NO_QH, 0)
                khoanh = row.get(COT_DU_NO_KHOANH, 0)
                if pd.to_numeric(qh, errors="coerce") > 0:
                    st.markdown(f"⚠️ **Nợ QH:** {fmt_ty(qh)}")
                if pd.to_numeric(khoanh, errors="coerce") > 0:
                    st.markdown(f"🔒 **Nợ khoanh:** {fmt_ty(khoanh)}")
            with cols[2]:
                du_no_tt = st.number_input("Dư nợ thực tế", key=f"tt_{row['ma_mon_vay']}",
                                            value=float(row.get("du_no_thuc_te") or 0),
                                            disabled=readonly)
            with cols[3]:
                phat_hien = st.checkbox("Phát hiện sai sót", key=f"ss_{row['ma_mon_vay']}",
                                        value=bool(row.get("phat_hien_sai_sot")),
                                        disabled=readonly)
            with cols[4]:
                ghi_chu = st.text_input("Ghi chú", key=f"gc_{row['ma_mon_vay']}",
                                        value=str(row.get("ghi_chu", "")),
                                        disabled=readonly)

            if not readonly:
                if st.button("💾 Lưu", key=f"save_{row['ma_mon_vay']}", use_container_width=True):
                    data = {
                        "du_no_thuc_te": du_no_tt,
                        "phat_hien_sai_sot": 1 if phat_hien else 0,
                        "ghi_chu": ghi_chu,
                    }
                    luu_ket_qua_doi_chieu(dot_id, row["ma_mon_vay"], data, username)
                    st.success("Đã lưu")
                    st.rerun()

    # Export
    if not df_display.empty:
        st.divider()
        if st.button("📥 Xuất Excel kết quả đối chiếu", use_container_width=True):
            df_export = df_display.rename(columns={
                "ma_mon_vay": "Số KU", "ten_pgd": "PGD", "ten_kh": "Tên KH",
                "du_no_hstd": "Dư nợ HSTD", "du_no_thuc_te": "Dư nợ thực tế",
                "phat_hien_sai_sot": "Phát hiện sai sót", "ghi_chu": "Ghi chú"
            })
            excel_bytes = xuat_excel({"Ket_qua_doi_chieu": df_export})
            st.download_button("Tải xuống", excel_bytes,
                              file_name=ten_file_xuat(f"KTNB_Dot{dot_id}_DoiChieu"),
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ═══════════════════════════════════════════════════════════════════════════════
# PHÂN HỆ D — GIÁM SÁT & KHẮC PHỤC LỖI
# ═══════════════════════════════════════════════════════════════════════════════


def lay_danh_muc_loi() -> pd.DataFrame:
    """Lấy danh mục lỗi chuẩn theo CV 9919."""
    with db.get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM ktnb_danh_muc_loi_chuan WHERE con_hieu_luc=1 ORDER BY ma_loi",
            conn
        )
    return df


def them_loi(
    dot_id: int,
    ma_loi: str,
    mo_ta_ct: str,
    bien_phap: str,
    thoi_han: str,
    don_vi: str,
    nguoi_ghi: str,
    username: str,
    ma_mon_vay: str = None,
) -> int:
    """Thêm lỗi phát hiện mới. Trả về id lỗi."""
    with db.get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO ktnb_ket_qua_loi
                (dot_id, ma_loi, ma_mon_vay, mo_ta_cu_the, bien_phap_xu_ly,
                 thoi_han_kp, don_vi_chiu_trach, trang_thai, nguoi_ghi_nhan)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (dot_id, ma_loi, ma_mon_vay, mo_ta_ct, bien_phap, thoi_han, don_vi,
             "chua_khac_phuc", nguoi_ghi),
        )
        conn.commit()
        loi_id = cur.lastrowid
    db.ghi_audit(username, "ktnb_them_loi", f"dot_id={dot_id}, ma_loi={ma_loi}")
    return loi_id


def cap_nhat_trang_thai_loi(
    loi_id: int,
    trang_thai: str,
    minh_chung_path: str = None,
    nguoi_dong: str = None,
    username: str = None,
) -> bool:
    """Cập nhật trạng thái khắc phục lỗi. Chỉ trưởng đoàn mới đóng lỗi (trang_thai='da_khac_phuc')."""
    with db.get_conn() as conn:
        # Lấy dot_id và kiểm tra trưởng đoàn
        row = conn.execute(
            """SELECT k.dot_id, d.truong_doan
               FROM ktnb_ket_qua_loi k
               JOIN ktnb_dot_kiem_tra d ON k.dot_id = d.id
               WHERE k.id = ?""", (loi_id,)
        ).fetchone()

        if not row:
            return False

        dot_id, truong_doan = row["dot_id"], row["truong_doan"]

        # Nếu đóng lỗi, chỉ trưởng đoàn được phép
        if trang_thai == "da_khac_phuc" and nguoi_dong != truong_doan:
            logger.warning("Người %s không phải trưởng đoàn %s, không được đóng lỗi",
                         nguoi_dong, truong_doan)
            return False

        ngay_dong = datetime.now().isoformat() if trang_thai == "da_khac_phuc" else None
        conn.execute(
            """UPDATE ktnb_ket_qua_loi
               SET trang_thai=?, minh_chung_path=?,
                   nguoi_dong_loi=?, ngay_dong_loi=?, updated_at=datetime('now','localtime')
               WHERE id=?""",
            (trang_thai, minh_chung_path, nguoi_dong, ngay_dong, loi_id),
        )
        conn.commit()

    if username:
        db.ghi_audit(username, "ktnb_cap_nhat_loi", f"loi_id={loi_id}, tt={trang_thai}")
    return True


def thong_ke_loi_theo_khoi(dot_id: int) -> pd.DataFrame:
    """Thống kê lỗi theo khối nghiệp vụ."""
    with db.get_conn() as conn:
        df = pd.read_sql_query(
            """
            SELECT c.khoi_nghiep_vu, c.muc_do, COUNT(*) as so_loi,
                   SUM(CASE WHEN l.trang_thai='da_khac_phuc' THEN 1 ELSE 0 END) as da_kp
            FROM ktnb_ket_qua_loi l
            JOIN ktnb_danh_muc_loi_chuan c ON l.ma_loi = c.ma_loi
            WHERE l.dot_id = ?
            GROUP BY c.khoi_nghiep_vu, c.muc_do
            """, conn, params=(dot_id,)
        )
    return df


def lay_danh_sach_loi(dot_id: int) -> pd.DataFrame:
    """Lấy danh sách lỗi phát hiện của đợt kiểm tra."""
    with db.get_conn() as conn:
        df = pd.read_sql_query(
            """
            SELECT l.*, c.ten_loi, c.khoi_nghiep_vu, c.muc_do, c.so_cv
            FROM ktnb_ket_qua_loi l
            JOIN ktnb_danh_muc_loi_chuan c ON l.ma_loi = c.ma_loi
            WHERE l.dot_id = ?
            ORDER BY l.created_at DESC
            """, conn, params=(dot_id,)
        )
    return df


def _luu_minh_chung(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile, dot_id: int) -> str:
    """Lưu file minh chứng và trả về đường dẫn tương đối."""
    if uploaded_file is None:
        return None
    dot_dir = KTNB_DIR / f"dot_{dot_id}"
    dot_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{timestamp}_{uploaded_file.name}"
    file_path = dot_dir / file_name

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getvalue())

    return str(file_path.relative_to(PGD_DATA_DIR))


def render_giam_sat_khac_phuc(dot_id: int, username: str, readonly: bool = False) -> None:
    """UI Phân hệ D: Giám sát & Khắc phục lỗi."""
    st.subheader("⚠️ Giám sát & Khắc phục lỗi")

    dot = lay_dot_by_id(dot_id)
    is_truong_doan = dot and dot.get("truong_doan") == username

    # Thống kê
    df_stats = thong_ke_loi_theo_khoi(dot_id)
    if not df_stats.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tổng lỗi phát hiện", int(df_stats["so_loi"].sum()))
        with col2:
            da_kp = int(df_stats["da_kp"].sum())
            st.metric("Đã khắc phục", da_kp)
        with col3:
            chua_kp = int(df_stats["so_loi"].sum()) - da_kp
            st.metric("Chưa khắc phục", chua_kp)

        # Pie chart
        try:
            import plotly.express as px
            df_pie = df_stats.groupby("khoi_nghiep_vu")["so_loi"].sum().reset_index()
            fig = px.pie(df_pie, values="so_loi", names="khoi_nghiep_vu",
                         title="Lỗi theo khối nghiệp vụ")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass  # Plotly optional

    # Thêm lỗi mới
    if not readonly:
        with st.expander("➕ Thêm lỗi phát hiện"):
            df_dm = lay_danh_muc_loi()
            with st.form("form_them_loi"):
                col_a, col_b = st.columns(2)
                with col_a:
                    ma_loi = st.selectbox("Mã lỗi", df_dm["ma_loi"].tolist(),
                                          format_func=lambda x: f"{x} — {df_dm[df_dm['ma_loi']==x]['ten_loi'].values[0]}")
                    ma_mon = st.text_input("Món vay liên quan (optional)", placeholder="Số KU")
                with col_b:
                    don_vi = st.text_input("Đơn vị chịu trách nhiệm")
                    thoi_han = st.date_input("Thời hạn khắc phục", date.today())
                mo_ta = st.text_area("Mô tả cụ thể lỗi")
                bien_phap = st.text_area("Biện pháp xử lý")

                if st.form_submit_button("Lưu lỗi", use_container_width=True):
                    if mo_ta and don_vi:
                        loi_id = them_loi(dot_id, ma_loi, mo_ta, bien_phap,
                                         thoi_han.strftime("%Y-%m-%d"), don_vi, username, username, ma_mon)
                        st.success(f"Đã thêm lỗi ID: {loi_id}")
                        st.rerun()
                    else:
                        st.error("Vui lòng nhập mô tả và đơn vị chịu trách nhiệm")

    # Danh sách lỗi
    df_loi = lay_danh_sach_loi(dot_id)
    if df_loi.empty:
        st.info("Chưa phát hiện lỗi nào")
        return

    st.divider()
    st.write("**Danh sách lỗi phát hiện**")

    for _, row in df_loi.iterrows():
        color = "🟢" if row["trang_thai"] == "da_khac_phuc" else "🔴"
        with st.expander(f"{color} {row['ma_loi']} — {row['ten_loi']} ({row['khoi_nghiep_vu']}) — {row['trang_thai']}"):
            cols = st.columns([2, 2, 1, 1])
            with cols[0]:
                st.markdown(f"**Mô tả:** {row['mo_ta_cu_the']}")
                st.markdown(f"**Biện pháp:** {row['bien_phap_xu_ly']}")
            with cols[1]:
                st.markdown(f"**Đơn vị:** {row['don_vi_chiu_trach']}")
                st.markdown(f"**Thời hạn:** {row['thoi_han_kp']}")
                st.markdown(f"**Người ghi nhận:** {row['nguoi_ghi_nhan']}")
            with cols[2]:
                if row["trang_thai"] != "da_khac_phuc":
                    st.markdown("**Chưa khắc phục**")
                    if row["minh_chung_path"]:
                        st.markdown(f"📎 {row['minh_chung_path']}")
                else:
                    st.markdown(f"✅ Đã đóng: {row['nguoi_dong_loi']} — {row['ngay_dong_loi']}")
            with cols[3]:
                if not readonly and row["trang_thai"] != "da_khac_phuc":
                    # Upload minh chứng
                    up_file = st.file_uploader("Minh chứng", key=f"up_{row['id']}",
                                              accept_multiple_files=False)
                    if up_file:
                        path = _luu_minh_chung(up_file, dot_id)
                        cap_nhat_trang_thai_loi(row["id"], "dang_khac_phuc", path, username, username)
                        st.success("Đã lưu minh chứng")
                        st.rerun()

                    # Đóng lỗi — chỉ trưởng đoàn
                    if is_truong_doan:
                        if st.button("✅ Đóng lỗi", key=f"close_{row['id']}", use_container_width=True):
                            cap_nhat_trang_thai_loi(row["id"], "da_khac_phuc", row.get("minh_chung_path"), username, username)
                            st.success("Đã đóng lỗi")
                            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════


def render_ktnb(df_full: pd.DataFrame, role: str, username: str) -> None:
    """
    Main entry point cho Tab Kiểm toán Nội bộ.
    Được gọi từ tab_kiem_soat.py.

    Params
    ------
    df_full : DataFrame toàn CN (HSTD)
    role    : role của user
    username: username của user
    """
    readonly = normalize_role(role) == "executive"

    # Chọn đợt kiểm tra ở đầu
    df_dots = lay_danh_sach_dot()
    if df_dots.empty:
        st.warning("Chưa có đợt kiểm toán nào — Vui lòng tạo ở Phân hệ A")
        if not readonly:
            render_ke_hoach_lich_trinh(username, readonly)
        return

    dot_options = {f"{r['id']}: {r['ten_pgd_ks']} ({r['so_cv']}, {r['nam']})": r['id']
                   for _, r in df_dots.iterrows()}
    dot_sel = st.selectbox("📋 Chọn đợt kiểm toán", list(dot_options.keys()), key="ktnb_dot_main")
    dot_id = dot_options[dot_sel]

    st.divider()

    # 4 sub-tabs
    tab_a, tab_b, tab_c, tab_d = st.tabs([
        "📅 A. Kế hoạch & Lịch trình",
        "🎯 B. Chọn mẫu đối chiếu",
        "📝 C. Nhập kết quả đối chiếu",
        "⚠️ D. Giám sát & Khắc phục lỗi"
    ])

    with tab_a:
        # Hiển thị chỉ đợt đang chọn trong tab A
        dot = lay_dot_by_id(dot_id)
        st.json(dot) if dot else st.error("Không tìm thấy đợt")
        render_ke_hoach_lich_trinh(username, readonly)

    with tab_b:
        render_chon_mau(dot_id, df_full, username, readonly)

    with tab_c:
        render_nhap_ket_qua(dot_id, df_full, username, readonly)

    with tab_d:
        render_giam_sat_khac_phuc(dot_id, username, readonly)
