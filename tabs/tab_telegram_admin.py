"""Quản trị Telegram Bot — cấu hình, bật/tắt, lịch gửi, thao tác thủ công."""
from __future__ import annotations

import json

import streamlit as st
import pandas as pd
from datetime import date, time
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn, la_executive, la_chuyen_vien_cn, normalize_role
from logger import get_logger

logger = get_logger(__name__)

# ── Metadata các loại thông báo ────────────────────────────────────────────
_NOTIFY_META = [
    {
        "key": "bao_cao_sang",
        "icon": "📊", "ten": "Báo cáo tổng hợp sáng",
        "mo_ta": "Số liệu dư nợ, NQH — gửi mỗi sáng",
        "gio_mac_dinh": "07:30",
    },
    {
        "key": "khoang_den_han",
        "icon": "⏰", "ten": "Nhắc khoản đến hạn",
        "mo_ta": "Danh sách khoản vay đáo hạn trong tháng",
        "gio_mac_dinh": "07:45",
    },
    {
        "key": "phan_ky_nxh",
        "icon": "🏠", "ten": "Nhắc phân kỳ NXH",
        "mo_ta": "Khoản đến hạn phân kỳ nhà ở XH (1 tin/PGD)",
        "gio_mac_dinh": "08:00",
    },
    {
        "key": "khtd_tien_do",
        "icon": "📈", "ten": "Tiến độ KHTD",
        "mo_ta": "% hoàn thành kế hoạch tín dụng theo PGD",
        "gio_mac_dinh": "",
    },
    {
        "key": "qh_moi",
        "icon": "🔴", "ten": "Cảnh báo NQH tăng",
        "mo_ta": "Tỷ lệ nợ quá hạn tăng bất thường so ngày trước",
        "gio_mac_dinh": "08:15",
    },
    {
        "key": "deadline_bc",
        "icon": "⚠️", "ten": "Nhắc nộp báo cáo",
        "mo_ta": "PGD chưa nộp khi gần đến deadline",
        "gio_mac_dinh": "",
    },
    {
        "key": "nhap_lieu",
        "icon": "📝", "ten": "Nhắc nhập liệu",
        "mo_ta": "Nhắc PGD chưa hoàn thành nhập liệu theo cấu hình Google Sheets",
        "gio_mac_dinh": "",
    },
    {
        "key": "health_check",
        "icon": "🔍", "ten": "Kết quả Health Check",
        "mo_ta": "Trạng thái hệ thống mỗi buổi sáng",
        "gio_mac_dinh": "06:30",
    },
    {
        "key": "merge_thanh_cong",
        "icon": "✅", "ten": "Thông báo merge dữ liệu",
        "mo_ta": "Khi Phòng KH-NV gộp xong 22 PGD (sự kiện tự động)",
        "gio_mac_dinh": "",
    },
    {
        "key": "upload_pgd",
        "icon": "📤", "ten": "PGD upload file",
        "mo_ta": "Thông báo khi PGD upload dữ liệu thành công (sự kiện tự động)",
        "gio_mac_dinh": "",
    },
    {
        "key": "he_thong",
        "icon": "🔐", "ten": "Cảnh báo hệ thống",
        "mo_ta": "Đăng nhập bất thường, lỗi hệ thống (sự kiện tự động)",
        "gio_mac_dinh": "",
    },
    {
        "key": "nop_moi_gsheet",
        "icon": "📋", "ten": "PGD nộp BC mới (GSheet)",
        "mo_ta": "Thông báo khi phát hiện báo cáo mới từ Google Form (daily_report tự kiểm)",
        "gio_mac_dinh": "",
    },
    {
        "key": "den_han_phan_tang",
        "icon": "⏰", "ten": "Nhắc đến hạn T-7/T-3/T-1",
        "mo_ta": "Khoản đến hạn 1/3/7 ngày tới — phân tầng cảnh báo",
        "gio_mac_dinh": "08:00",
    },
    {
        "key": "lich_cong_tac",
        "icon": "📅", "ten": "Lịch công tác ngày mai",
        "mo_ta": "Chiều hôm trước: nhắc lịch Phòng KH-NV ngày mai",
        "gio_mac_dinh": "14:00",
    },
    {
        "key": "giai_ngan_tuan",
        "icon": "💸", "ten": "Giải ngân tuần",
        "mo_ta": "Thứ Sáu: tổng hợp khoản vay mới 7 ngày qua theo PGD",
        "gio_mac_dinh": "07:30",
    },
    {
        "key": "khoanh_tang",
        "icon": "⚠️", "ten": "Cảnh báo nợ khoanh tăng",
        "mo_ta": "Tỷ lệ nợ khoanh tăng ≥ 5% so với kỳ snapshot trước",
        "gio_mac_dinh": "08:15",
    },
    {
        "key": "nqh_tuan",
        "icon": "📊", "ten": "Báo cáo NQH tuần",
        "mo_ta": "Thứ Hai: NQH từng đơn vị + top 3 cần chú ý",
        "gio_mac_dinh": "08:00",
    },
    {
        "key": "khtd_ct",
        "icon": "🎯", "ten": "KHTD theo chương trình",
        "mo_ta": "Tiến độ KHTD phân tích theo từng CT tín dụng (TW/ĐP)",
        "gio_mac_dinh": "",
    },
    {
        "key": "tong_ket_thang",
        "icon": "📅", "ten": "Tổng kết tháng",
        "mo_ta": "Ngày 25–31: dư nợ vs KH%, NQH%, top/bottom 5 PGD",
        "gio_mac_dinh": "07:30",
    },
]

# Chỉ phân nhóm trình bày UI; key cấu hình và cơ chế gửi giữ nguyên.
_NOTIFY_GROUPS = [
    {
        "icon": "📊",
        "ten": "Báo cáo định kỳ",
        "mo_ta": "Tổng hợp số liệu theo ngày, tuần, tháng và tiến độ KHTD.",
        "keys": (
            "bao_cao_sang", "khtd_tien_do", "giai_ngan_tuan",
            "nqh_tuan", "khtd_ct", "tong_ket_thang",
        ),
    },
    {
        "icon": "🔔",
        "ten": "Nhắc nghiệp vụ",
        "mo_ta": "Nhắc đến hạn, nộp báo cáo, nhập liệu và lịch công tác.",
        "keys": (
            "khoang_den_han", "phan_ky_nxh", "deadline_bc", "nhap_lieu",
            "nop_moi_gsheet", "den_han_phan_tang", "lich_cong_tac",
        ),
    },
    {
        "icon": "⚠️",
        "ten": "Cảnh báo rủi ro",
        "mo_ta": "Cảnh báo biến động nợ quá hạn và nợ khoanh.",
        "keys": ("qh_moi", "khoanh_tang"),
    },
    {
        "icon": "⚙️",
        "ten": "Sự kiện hệ thống",
        "mo_ta": "Theo dõi upload, merge, Health Check và cảnh báo hệ thống.",
        "keys": ("upload_pgd", "merge_thanh_cong", "health_check", "he_thong"),
    },
]

# ── Phân nhóm cơ chế gửi (quyết định ô "Giờ gửi" có hiển thị không) ────────────
# Chỉ các loại đi qua _trong_gio_gui() trong daily_report.py mới đọc giờ admin nhập.
_SCHEDULE_KEYS = {
    "qh_moi", "giai_ngan_tuan", "khoanh_tang",
    "nqh_tuan", "khtd_ct", "tong_ket_thang",
}
# Loại chạy theo Task Scheduler giờ cố định — giờ KHÔNG sửa được ở UI này.
_TASK_GIO = {
    "bao_cao_sang":      "07:30",
    "khoang_den_han":    "07:45",
    "phan_ky_nxh":       "08:00",
    "deadline_bc":       "08:00 / 14:00",
    "nhap_lieu":         "08:00 / 14:00",
    "health_check":      "06:30",
    "den_han_phan_tang": "08:00 / 14:00",
    "nop_moi_gsheet":    "08:00 / 14:00",
    "lich_cong_tac":     "14:00",
}
# Loại kích hoạt theo sự kiện nghiệp vụ (không có khái niệm giờ).
_EVENT_KEYS = {"merge_thanh_cong", "upload_pgd"}
# Các loại còn lại (he_thong, khtd_tien_do) chỉ gửi thủ công qua nút "▶ Gửi ngay".


def _loc_allowlist_deadline(
    allowlist: list[str] | None,
    ds_loai: list[str],
) -> tuple[list[str] | None, list[str]]:
    """Lọc allowlist theo danh mục deadline hiện có để tránh state stale làm vỡ UI."""
    if allowlist is None:
        return None, []

    ds_loai_hop_le = {str(loai).strip() for loai in ds_loai if str(loai).strip()}
    ds_chon: list[str] = []
    ds_stale: list[str] = []
    for loai in allowlist:
        loai_str = str(loai).strip()
        if not loai_str:
            continue
        if loai_str in ds_loai_hop_le:
            if loai_str not in ds_chon:
                ds_chon.append(loai_str)
        else:
            ds_stale.append(loai_str)
    return ds_chon, ds_stale


def _loi_gui_telegram(log_key: str, fallback: str = "") -> str:
    """Lấy lỗi Telegram gần nhất cho log key tương ứng."""
    from services import telegram_service as tg

    err = tg.lay_loi_gui_gan_nhat(log_key)
    return err or fallback or "Telegram không trả về chi tiết lỗi."


def _ket_qua_gui_telegram(
    ok: bool,
    thong_tin_thanh_cong: str,
    log_key: str,
    fallback_err: str = "",
) -> tuple[bool, str]:
    """Chuẩn hóa tuple trả về cho UI: thành công thì giữ info, thất bại thì trả lỗi thật."""
    if ok:
        return True, thong_tin_thanh_cong
    return False, _loi_gui_telegram(log_key, fallback_err)


def _gui_ngay(key: str) -> tuple[bool, str]:
    """Load dữ liệu thực và gửi thông báo ngay lập tức. Trả (ok, thông tin/lỗi)."""
    from services import telegram_service as tg
    try:
        if key == "bao_cao_sang":
            from data.core import CACHE_HSTD
            from config import DS_PGD, COT_TONG_DU_NO, COT_DU_NO_QH
            if not CACHE_HSTD.exists():
                return False, "Chưa có dữ liệu HSTD."
            df = pd.read_parquet(CACHE_HSTD, columns=[COT_TONG_DU_NO, COT_DU_NO_QH])
            tong_dn = df[COT_TONG_DU_NO].sum()
            tong_qh = df[COT_DU_NO_QH].sum()
            ty_le   = f"{tong_qh / tong_dn * 100:.2f}%".replace(".", ",") if tong_dn else "0%"
            meta    = db.doc_kv("merge_meta_hstd") or {}
            so_pgd  = meta.get("so_pgd", 0)
            ok = tg.gui_bao_cao_sang(
                date.today().strftime("%d/%m/%Y"),
                f"{tong_dn / 1e9:.1f}".replace(".", ",") + " tỷ",
                f"{tong_qh / 1e6:.0f} triệu",
                ty_le, so_pgd, len(DS_PGD),
            )
            return _ket_qua_gui_telegram(ok, f"{so_pgd}/{len(DS_PGD)} PGD", "bao_cao_sang")

        elif key == "khoang_den_han":
            from data.core import CACHE_HSTD
            from config import COT_NGAY_DH, COT_TONG_DU_NO, COT_TEN_PGD, COT_TEN_KH, COT_SO_KU
            if not CACHE_HSTD.exists():
                return False, "Chưa có dữ liệu HSTD."
            df = pd.read_parquet(CACHE_HSTD)
            today_ts = pd.Timestamp.today().normalize()
            last_day = today_ts.replace(day=1) + pd.offsets.MonthEnd(0)
            if COT_NGAY_DH not in df.columns:
                return False, f"Thiếu cột {COT_NGAY_DH}."
            mask = (
                df[COT_NGAY_DH].notna()
                & (df[COT_NGAY_DH] >= today_ts)
                & (df[COT_NGAY_DH] <= last_day)
            )
            df_dh = df[mask].sort_values(COT_NGAY_DH)
            ds = [
                {
                    "ten_kh":  str(r.get(COT_TEN_KH, "")),
                    "so_ku":   str(r.get(COT_SO_KU, "")),
                    "ngay_dh": r[COT_NGAY_DH].strftime("%d/%m/%Y") if pd.notna(r[COT_NGAY_DH]) else "",
                    "du_no":   f"{float(r.get(COT_TONG_DU_NO, 0) or 0) / 1e6:.0f} tr",
                    "ten_pgd": str(r.get(COT_TEN_PGD, "")),
                }
                for _, r in df_dh.iterrows()
            ]
            ok = tg.gui_nhac_khoang_den_han(ds)
            return _ket_qua_gui_telegram(ok, f"{len(ds)} khoản", "khoang_den_han")

        elif key == "phan_ky_nxh":
            from data.phan_ky_nxh import doc_phan_ky_nxh
            df = doc_phan_ky_nxh()
            if df.empty:
                return False, "Chưa có dữ liệu phân kỳ NXH."
            today_ts = pd.Timestamp.today().normalize()
            last_day = today_ts.replace(day=1) + pd.offsets.MonthEnd(0)
            COL_NGAY = "Ngày đến hạn kỳ con"
            mask = (
                df[COL_NGAY].notna()
                & (df[COL_NGAY] >= today_ts)
                & (df[COL_NGAY] <= last_day)
            )
            df_t = df[mask].sort_values(["Tên xã", COL_NGAY])
            if df_t.empty:
                return True, "Không có khoản đến hạn tháng này"
            sent_count = 0
            failed_count = 0
            first_err = ""
            for ten_pgd, grp in df_t.groupby("Tên PGD"):
                ds = [
                    {
                        "ten_kh":        str(r.get("Tên khách hàng", "")),
                        "so_ku":         str(r.get("Số khế ước", "")),
                        "ngay_dh":       r[COL_NGAY].strftime("%d/%m/%Y") if pd.notna(r[COL_NGAY]) else "",
                        "du_no":         float(r.get("Dư nợ kỳ con đến hạn", 0) or 0),
                        "lai_ton":       float(r.get("Lãi tồn", 0) or 0),
                        "tong_tgk":      float(r.get("Tổng TG, TK", 0) or 0),
                        "sdt":           str(r.get("Số điện thoại", "") or ""),
                        "ten_xa":        str(r.get("Tên xã", "") or ""),
                        "ten_to_truong": str(r.get("Tên tổ trưởng", "") or ""),
                        "ghi_chu":       str(r.get("Ghi chú", "") or ""),
                    }
                    for _, r in grp.iterrows()
                ]
                ok_pgd = tg.gui_nhac_phan_ky_nxh(str(ten_pgd), ds, today_ts.strftime("%d/%m/%Y"))
                if ok_pgd:
                    sent_count += 1
                else:
                    failed_count += 1
                    if not first_err:
                        first_err = _loi_gui_telegram("phan_ky_nxh")
            if failed_count:
                if sent_count:
                    return False, f"Đã gửi {sent_count} PGD, lỗi {failed_count} PGD — {first_err}"
                return False, first_err
            return True, f"Đã gửi {sent_count} PGD"

        elif key == "khtd_tien_do":
            from data.core import CACHE_HSTD
            from config import COT_TEN_PGD, COT_TONG_DU_NO
            khtd_cn = db.doc_kv("khtd_cn")
            if not khtd_cn:
                return False, "Chưa có dữ liệu KHTD (cần giao KHTD trước)."
            if not CACHE_HSTD.exists():
                return False, "Chưa có dữ liệu HSTD (cần merge trước)."
            df_dn = pd.read_parquet(CACHE_HSTD, columns=[COT_TEN_PGD, COT_TONG_DU_NO])
            du_no_pgd = df_dn.groupby(COT_TEN_PGD)[COT_TONG_DU_NO].sum().to_dict()
            # Cộng KHTD tất cả chương trình theo PGD
            kh_pgd: dict[str, float] = {}
            for _ct, targets in khtd_cn.items():
                if not isinstance(targets, dict):
                    continue
                for ten_pgd, val in targets.items():
                    if isinstance(val, (int, float)):
                        kh_pgd[ten_pgd] = kh_pgd.get(ten_pgd, 0) + float(val)
            if not kh_pgd:
                return False, "Dữ liệu KHTD không có thông tin PGD."
            ds_pgd = []
            for ten_pgd, ke_hoach in sorted(kh_pgd.items()):
                thuc_hien = float(du_no_pgd.get(ten_pgd, 0))
                pct = (thuc_hien / ke_hoach * 100) if ke_hoach > 0 else 0.0
                ds_pgd.append({
                    "ten_pgd":   ten_pgd,
                    "ke_hoach":  ke_hoach,
                    "thuc_hien": thuc_hien,
                    "pct":       round(pct, 1),
                })
            ok = tg.gui_khtd_tien_do(ds_pgd)
            return _ket_qua_gui_telegram(ok, f"{len(ds_pgd)} PGD", "khtd_tien_do")

        elif key == "qh_moi":
            ok = tg.gui_canh_bao_qh_moi([])
            return True, "Không có PGD nào tăng NQH (test)"

        elif key == "deadline_bc":
            from services.telegram_jobs import run_telegram_job

            result = run_telegram_job("deadline_bc")
            return result.ok, result.info if result.ok else result.error

        elif key == "nhap_lieu":
            from services.telegram_jobs import run_telegram_job

            result = run_telegram_job("nhap_lieu")
            return result.ok, result.info if result.ok else result.error

        elif key == "health_check":
            ok = tg.gui_ket_qua_health_check(
                0, 0, 0, date.today().strftime("%d/%m/%Y"), "Test thủ công từ Admin"
            )
            return _ket_qua_gui_telegram(ok, "", "health_check")

        elif key == "merge_thanh_cong":
            ok = tg.gui_thong_bao_merge("HSTD", 22, "admin")
            return _ket_qua_gui_telegram(ok, "(Test thủ công)", "merge_thanh_cong")

        elif key == "upload_pgd":
            ok = tg.gui_thong_bao_upload_pgd("(Test PGD)", "HSTD", "admin")
            return _ket_qua_gui_telegram(ok, "(Test thủ công)", "upload_pgd")

        elif key == "he_thong":
            ok = tg.gui_canh_bao_he_thong("canh_bao", "Test thủ công từ Admin")
            return _ket_qua_gui_telegram(ok, "(Test thủ công)", "he_thong")

        elif key == "nop_moi_gsheet":
            from services.report_submission_service import doc_du_lieu_gsheet
            df_gs = doc_du_lieu_gsheet()
            if df_gs.empty:
                return False, "Không có dữ liệu GSheet (kiểm tra credentials.json)."
            cutoff = pd.Timestamp.now() - pd.Timedelta(hours=24)
            df_moi = df_gs[df_gs["thoi_gian"] > cutoff]
            if df_moi.empty:
                return True, "Không có submission mới trong 24h qua"
            ds = []
            for _, r in df_moi.iterrows():
                ts_str = ""
                try:
                    if pd.notna(r.get("thoi_gian")):
                        ts_str = pd.Timestamp(r["thoi_gian"]).strftime("%d/%m %H:%M")
                except Exception:
                    pass
                ds.append({
                    "ten_pgd":      str(r.get("ten_pgd", "") or ""),
                    "loai_bao_cao": str(r.get("loai_bao_cao", "") or ""),
                    "thoi_gian":    ts_str,
                    "ho_ten":       str(r.get("ho_ten", "") or ""),
                })
            ok = tg.gui_thong_bao_nop_moi_gsheet(ds)
            return _ket_qua_gui_telegram(ok, f"{len(ds)} submission trong 24h qua", "nop_moi_gsheet")

        elif key == "den_han_phan_tang":
            from services.telegram_jobs import run_telegram_job

            result = run_telegram_job("den_han_phan_tang")
            return result.ok, result.info if result.ok else result.error

        elif key == "lich_cong_tac":
            ds_lich = db.doc_kv("khnv_lich_list")
            if not ds_lich or not isinstance(ds_lich, list):
                return False, "Chưa có lịch công tác (vào tab Phòng KH-NV → Lịch để thêm)."
            import datetime as _dt
            tomorrow = date.today() + _dt.timedelta(days=1)
            ngay_mai_str = tomorrow.strftime("%d/%m/%Y")
            tomorrow_ts  = pd.Timestamp(tomorrow)
            ds_sv = []
            for entry in ds_lich:
                if not isinstance(entry, dict):
                    continue
                ngay_raw = entry.get("ngay") or entry.get("date") or ""
                try:
                    ngay_entry = pd.to_datetime(ngay_raw, dayfirst=True).normalize()
                except Exception:
                    continue
                if ngay_entry != tomorrow_ts:
                    continue
                ds_sv.append({
                    "gio":             str(entry.get("gio", "") or ""),
                    "noi_dung":        str(entry.get("noi_dung", "") or ""),
                    "nguoi_phu_trach": str(entry.get("nguoi_phu_trach", "") or ""),
                    "dia_diem":        str(entry.get("dia_diem", "") or ""),
                })
            if not ds_sv:
                return True, f"Không có lịch ngày mai ({ngay_mai_str})"
            ds_sv.sort(key=lambda x: x["gio"] or "99:99")
            ok = tg.gui_nhac_lich_cong_tac(ds_sv, ngay_mai_str)
            return _ket_qua_gui_telegram(ok, f"{len(ds_sv)} sự kiện ngày {ngay_mai_str}", "lich_cong_tac")

        elif key == "giai_ngan_tuan":
            from data.core import CACHE_HSTD
            from config import COT_NGAY_VAY, COT_TEN_PGD, COT_TONG_DU_NO, DON_VI_CHI_NHANH
            if not CACHE_HSTD.exists():
                return False, "Chưa có dữ liệu HSTD."
            df = pd.read_parquet(CACHE_HSTD)
            if COT_NGAY_VAY not in df.columns:
                return False, f"Thiếu cột {COT_NGAY_VAY}."
            today_ts = pd.Timestamp.today().normalize()
            t7 = today_ts - pd.Timedelta(days=7)
            mask = df[COT_NGAY_VAY].notna() & (df[COT_NGAY_VAY] >= t7) & (df[COT_NGAY_VAY] <= today_ts)
            df_gn = df[mask & (df[COT_TEN_PGD] != DON_VI_CHI_NHANH)]
            if df_gn.empty:
                return True, "Không có khoản vay mới trong 7 ngày qua"
            tuan_str = f"{t7.strftime('%d/%m')}–{today_ts.strftime('%d/%m/%Y')}"
            grp = df_gn.groupby(COT_TEN_PGD)[COT_TONG_DU_NO].agg(["sum", "count"]).reset_index()
            ds_pgd = [
                {"ten_pgd": str(r[COT_TEN_PGD]), "so_khoan": int(r["count"]), "giai_ngan": float(r["sum"])}
                for _, r in grp.iterrows()
            ]
            ok = tg.gui_giai_ngan_tuan(ds_pgd, tuan_str)
            return _ket_qua_gui_telegram(ok, f"{len(df_gn)} khoản vay mới", "giai_ngan_tuan")

        elif key == "khoanh_tang":
            try:
                from snapshot_service import doc_snapshot, danh_sach_ky
                ky_list = danh_sach_ky()
                if len(ky_list) < 2:
                    return True, "Không đủ snapshot để so sánh (cần ≥ 2 kỳ)"
                df_moi = doc_snapshot(ky_list[0])
                df_cu  = doc_snapshot(ky_list[1])
                if df_moi.empty or "du_no_khoanh" not in df_moi.columns:
                    return False, "Thiếu dữ liệu snapshot hoặc cột du_no_khoanh."
                ds_tang = []
                for _, row_m in df_moi.iterrows():
                    pgd   = row_m["ten_pgd"]
                    match = df_cu[df_cu["ten_pgd"] == pgd]
                    if match.empty:
                        continue
                    row_c  = match.iloc[0]
                    kh_moi = float(row_m.get("du_no_khoanh") or 0)
                    kh_cu  = float(row_c.get("du_no_khoanh") or 0)
                    if kh_cu == 0 or kh_moi == 0:
                        continue
                    tang_pct = (kh_moi - kh_cu) / kh_cu * 100
                    if tang_pct >= 5.0:
                        ds_tang.append({"ten_pgd": str(pgd), "khoanh_cu": kh_cu, "khoanh_moi": kh_moi, "tang_pct": tang_pct})
                if not ds_tang:
                    return True, "Không có đơn vị nào tăng nợ khoanh ≥ 5%"
                ok = tg.gui_canh_bao_khoanh_tang(ds_tang)
                return _ket_qua_gui_telegram(ok, f"{len(ds_tang)} đơn vị tăng nợ khoanh", "khoanh_tang")
            except Exception as e:
                logger.error("_gui_ngay khoanh_tang: %s", e, exc_info=True)
                return False, str(e)

        elif key == "nqh_tuan":
            from data.core import CACHE_HSTD
            from config import COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, DON_VI_CHI_NHANH
            if not CACHE_HSTD.exists():
                return False, "Chưa có dữ liệu HSTD."
            df = pd.read_parquet(CACHE_HSTD, columns=[COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH])
            df = df[df[COT_TEN_PGD] != DON_VI_CHI_NHANH]
            grp = df.groupby(COT_TEN_PGD)[[COT_TONG_DU_NO, COT_DU_NO_QH]].sum().reset_index()
            meta = db.doc_kv("merge_meta_hstd") or {}
            ngay_sl = meta.get("ngay_sl", date.today().strftime("%d/%m/%Y"))
            ds_pgd = []
            for _, r in grp.iterrows():
                dn  = float(r[COT_TONG_DU_NO] or 0)
                qh  = float(r[COT_DU_NO_QH]   or 0)
                tl  = qh / dn * 100 if dn > 0 else 0.0
                ds_pgd.append({
                    "ten_pgd":   str(r[COT_TEN_PGD]),
                    "du_no":     dn,
                    "nqh":       qh,
                    "ty_le_nqh": round(tl, 2),
                })
            ok = tg.gui_bao_cao_nqh_tuan(ds_pgd, str(ngay_sl))
            return _ket_qua_gui_telegram(ok, f"{len(ds_pgd)} đơn vị", "nqh_tuan")

        elif key == "khtd_ct":
            from data.core import CACHE_HSTD
            from config import COT_TONG_DU_NO, CHUONG_TRINH_KHTD
            khtd_cn = db.doc_kv("khtd_cn")
            if not khtd_cn:
                return False, "Chưa có dữ liệu KHTD (cần giao KHTD trước)."
            if not CACHE_HSTD.exists():
                return False, "Chưa có dữ liệu HSTD (cần merge trước)."
            # Tính thực hiện theo chương trình từ HSTD
            # _tinh_thuc_hien_theo_ct trả về dict[ma_key -> float], không phải DataFrame
            from tabs.tab_khtd_xuat import _tinh_thuc_hien_theo_ct
            th_dict = _tinh_thuc_hien_theo_ct(pd.read_parquet(CACHE_HSTD))
            meta = db.doc_kv("merge_meta_hstd") or {}
            ngay_sl = str(meta.get("ngay_sl", date.today().strftime("%d/%m/%Y")))
            ds_ct = []
            for ma_key, ma_ct, ten_hien_thi, nguon_von, _tm in CHUONG_TRINH_KHTD:
                kh_ct  = float(khtd_cn.get(ma_key, {}).get("_cn", 0) or 0)
                th_val = float(th_dict.get(ma_key, 0.0))
                pct    = th_val / kh_ct * 100 if kh_ct > 0 else 0.0
                ds_ct.append({
                    "ten_ct":    ten_hien_thi,
                    "nguon_von": nguon_von,
                    "ke_hoach":  kh_ct,
                    "thuc_hien": th_val,
                    "pct":       round(pct, 1),
                })
            ok = tg.gui_khtd_theo_chuong_trinh(ds_ct, ngay_sl)
            return _ket_qua_gui_telegram(ok, f"{len(ds_ct)} chương trình", "khtd_ct")

        elif key == "tong_ket_thang":
            from data.core import CACHE_HSTD
            from config import COT_TEN_PGD, COT_TONG_DU_NO, COT_DU_NO_QH, COT_NGAY_DH, DON_VI_CHI_NHANH
            if not CACHE_HSTD.exists():
                return False, "Chưa có dữ liệu HSTD."
            df = pd.read_parquet(CACHE_HSTD)
            khtd_cn = db.doc_kv("khtd_cn") or {}
            # Tổng CN
            du_no  = float(df[COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df.columns else 0.0
            nqh    = float(df[COT_DU_NO_QH].sum())   if COT_DU_NO_QH   in df.columns else 0.0
            # KH tổng từ khtd_cn — tổng tất cả ct × CN
            ke_hoach = 0.0
            for _ct, targets in khtd_cn.items():
                if isinstance(targets, dict):
                    ke_hoach += float(targets.get("_cn", 0) or 0)
            # Khoản đến hạn tháng sau
            so_dh, dn_dh = 0, 0.0
            if COT_NGAY_DH in df.columns:
                today_ts = pd.Timestamp.today().normalize()
                nm1 = (today_ts.replace(day=1) + pd.offsets.MonthBegin(1))
                nm_end = nm1 + pd.offsets.MonthEnd(0)
                mask_dh = df[COT_NGAY_DH].notna() & (df[COT_NGAY_DH] >= nm1) & (df[COT_NGAY_DH] <= nm_end)
                so_dh  = int(mask_dh.sum())
                dn_dh  = float(df.loc[mask_dh, COT_TONG_DU_NO].sum()) if COT_TONG_DU_NO in df.columns else 0.0
            # Top/bottom PGD theo % KH
            kh_pgd: dict[str, float] = {}
            for _ct, targets in khtd_cn.items():
                if isinstance(targets, dict):
                    for pgd, val in targets.items():
                        if pgd != "_cn" and isinstance(val, (int, float)):
                            kh_pgd[pgd] = kh_pgd.get(pgd, 0) + float(val)
            df_pgd = (
                df[df[COT_TEN_PGD] != DON_VI_CHI_NHANH]
                .groupby(COT_TEN_PGD)[COT_TONG_DU_NO].sum()
                .reset_index()
            ) if COT_TEN_PGD in df.columns else pd.DataFrame()
            ds_ranked = []
            for _, r in df_pgd.iterrows():
                pgd = str(r[COT_TEN_PGD])
                kh  = kh_pgd.get(pgd, 0)
                th  = float(r[COT_TONG_DU_NO] or 0)
                pct = th / kh * 100 if kh > 0 else 0.0
                ds_ranked.append({"ten_pgd": pgd, "pct_kh": round(pct, 1)})
            ds_ranked.sort(key=lambda x: x["pct_kh"], reverse=True)
            top5 = ds_ranked[:5]
            bot5 = list(reversed(ds_ranked[-5:])) if len(ds_ranked) >= 5 else ds_ranked
            thang = date.today().month
            nam   = date.today().year
            ok = tg.gui_tong_ket_thang(
                thang, nam, du_no, ke_hoach, nqh,
                so_dh, dn_dh, top5, bot5,
            )
            return _ket_qua_gui_telegram(ok, f"Tháng {thang:02d}/{nam}", "tong_ket_thang")

        else:
            return False, f"Chưa hỗ trợ loại: {key}"

    except Exception as e:
        logger.error("_gui_ngay %s: %s", key, e, exc_info=True)
        return False, str(e)


_SCHEDULER_FORM_KEYS = (
    "tg_rule_name", "tg_rule_notify", "tg_rule_mode", "tg_rule_times",
    "tg_rule_weekdays", "tg_rule_max_runs", "tg_rule_grace",
    "tg_rule_attempts", "tg_rule_cooldown", "tg_rule_enabled",
)


def _reset_scheduler_rule_form() -> None:
    for key in _SCHEDULER_FORM_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop("_tg_scheduler_preset_defaults", None)


def _apply_scheduler_preset(preset: str) -> None:
    presets = {
        "morning": {"mode": "daily", "times": ["08:00"], "weekdays": [], "max_runs": 1},
        "twice": {"mode": "daily", "times": ["08:00", "14:00"], "weekdays": [], "max_runs": 2},
        "monday": {"mode": "weekly", "times": ["08:00"], "weekdays": [0], "max_runs": 1},
        "weekdays": {
            "mode": "weekly", "times": ["08:00"], "weekdays": [0, 1, 2, 3, 4], "max_runs": 1,
        },
    }
    for key in _SCHEDULER_FORM_KEYS:
        st.session_state.pop(key, None)
    st.session_state["_tg_scheduler_preset_defaults"] = presets[preset]


def _fmt_scheduler_dt(value) -> str:
    return value.strftime("%H:%M %d/%m/%Y") if value is not None else "—"


def _render_scheduler_rules(username: str) -> None:
    """UI cấu hình MVP scheduler daily/weekly nhiều mốc giờ."""
    from services.telegram_jobs import telegram_job_keys
    from services.telegram_schedule_service import (
        RUNLOG_PREFIX,
        doc_schedule_config,
        luu_schedule_config,
        run_rule_now,
        scheduler_health,
    )

    cfg = doc_schedule_config()
    st.markdown("##### Lịch gửi Telegram tự động")
    st.caption(
        "Chọn nội dung, ngày và giờ gửi. Hệ thống sẽ tự chạy theo lịch đã lưu."
    )
    with st.expander("📘 Hướng dẫn cài đặt và chuyển sang máy mới", expanded=False):
        st.markdown(
            """
**Nguyên tắc quan trọng:** chỉ để **một máy** chạy `VBSP-TelegramScheduler`.

Nếu máy cũ và máy mới cùng chạy, Telegram có thể gửi thông báo hai lần.

**Bước 1 — Trên máy cũ (nếu còn sử dụng)**

Mở PowerShell bằng **Run as administrator**, rồi tắt scheduler:
"""
        )
        st.code(
            'Disable-ScheduledTask -TaskName "VBSP-TelegramScheduler"',
            language="powershell",
        )
        st.markdown(
            """
**Bước 2 — Chuyển chương trình sang máy mới**

- Copy toàn bộ thư mục dự án vào `D:\\VBSP-SCM`.
- Copy an toàn file `vbsp_scm.db` nếu muốn giữ Token, Chat ID và các rule hiện có.
- Hoặc dùng mục **Xuất/Nhập cấu hình rule** phía dưới; file xuất không chứa Token và Chat ID.
- File database có thông tin cấu hình Telegram: **không gửi qua nhóm chat, email công khai hoặc đưa lên GitHub**.
- Nếu không copy database, nhập lại Token/Chat ID và tạo lại rule trong màn hình này.

**Bước 3 — Cài Windows Task Scheduler trên máy mới**

Mở PowerShell bằng **Run as administrator**, dán lần lượt:
"""
        )
        st.code(
            """cd D:\\VBSP-SCM
Set-ExecutionPolicy -Scope Process Bypass
.\\scripts\\setup_task_scheduler.ps1""",
            language="powershell",
        )
        st.markdown("Nếu dự án nằm ở thư mục khác, dùng lệnh:")
        st.code(
            '.\\scripts\\setup_task_scheduler.ps1 -ProjectDir "D:\\ThuMucKhac"',
            language="powershell",
        )
        st.markdown(
            """
**Bước 4 — Kiểm tra task đã được cài**
"""
        )
        st.code(
            'Get-ScheduledTask -TaskName "VBSP-TelegramScheduler"',
            language="powershell",
        )
        st.markdown(
            """
Kết quả cần có trạng thái `Ready` hoặc `Running`.

**Bước 5 — Tạo lịch và bật gửi**

1. Tạo hoặc kiểm tra các rule ở phía dưới.
2. Bật **Bật rule-based scheduler**.
3. Bấm **💾 Lưu trạng thái Scheduler**.
4. Xem mục **Runlog hôm nay** để kiểm tra lần chạy.

**Gợi ý lịch đơn giản:** nhập `08:00, 14:00`, đặt `Lượt chạy tối đa/ngày = 2`,
`Cửa sổ chạy = 10 phút`, `Thử lại tối đa = 1`.
"""
        )
        st.info(
            "Nếu máy mới chưa gửi: kiểm tra task Windows, Token/Chat ID, toggle loại thông báo "
            "và trạng thái Scheduler trong màn hình này."
        )

    health = scheduler_health()
    labels = {
        "deadline_bc": "⚠️ PGD chưa nộp báo cáo",
        "nhap_lieu": "📝 PGD chưa hoàn thành nhập liệu",
        "den_han_phan_tang": "⏰ Khoản vay đến hạn T-7/T-3/T-1",
    }
    rules = list(cfg["rules"])
    has_active_rule = bool(cfg["enabled"] and any(rule["enabled"] for rule in rules))
    if not has_active_rule:
        st.info("ℹ️ Chưa có lịch gửi tự động đang bật.")
    elif health["status"] == "stale":
        st.error("❌ Hệ thống gửi tự động đang ngừng hoạt động. Hãy kiểm tra Windows Task Scheduler.")
    elif health["status"] == "never" and cfg["enabled"]:
        st.warning("⚠️ Đã bật lịch nhưng hệ thống gửi tự động chưa chạy lần nào.")
    elif health["status"] == "ok":
        next_text = _fmt_scheduler_dt(health["next_run"])
        st.success(f"✅ Hệ thống gửi tự động đang hoạt động. Lần gửi kế tiếp: {next_text}")
    else:
        st.info("ℹ️ Chưa bật lịch gửi tự động.")

    if rules:
        st.markdown("##### Lịch đã tạo")
        for rule in rules:
            trang_thai = "Đang bật" if rule["enabled"] and cfg["enabled"] else "Đang tắt"
            if rule["mode"] == "daily":
                ngay_gui = "Mỗi ngày"
            elif rule["weekdays"] == [0, 1, 2, 3, 4]:
                ngay_gui = "Thứ Hai–Thứ Sáu"
            else:
                ngay_gui = "Theo các thứ đã chọn"
            st.write(
                f"• **{labels.get(rule['notify_key'], rule['name'])}** — "
                f"{ngay_gui}, lúc {', '.join(rule['times'])} — {trang_thai}"
                + (" — lần sau chỉ gửi thay đổi" if rule.get("delivery_mode") == "full_then_delta" else "")
            )

    st.markdown("##### Tạo hoặc thay đổi lịch")
    simple_notify = st.selectbox(
        "Chọn nội dung nhắc tự động",
        options=list(telegram_job_keys()),
        format_func=lambda x: labels.get(x, x),
        key="tg_simple_notify",
    )
    existing = next((rule for rule in rules if rule["notify_key"] == simple_notify), None)
    existing_times = existing["times"] if existing else ["08:00"]
    default_period = "daily" if not existing or existing["mode"] == "daily" else "weekdays"
    period = st.radio(
        "Gửi vào ngày nào?",
        options=["daily", "weekdays"],
        index=0 if default_period == "daily" else 1,
        format_func=lambda x: "Mỗi ngày" if x == "daily" else "Thứ Hai đến Thứ Sáu",
        horizontal=True,
        key=f"tg_simple_period_{simple_notify}",
    )
    so_lan_mac_dinh = min(max(len(existing_times), 1), 4)
    so_lan = st.radio(
        "Mỗi ngày gửi mấy lần?",
        options=[1, 2, 3, 4],
        index=so_lan_mac_dinh - 1,
        format_func=lambda x: f"{x} lần",
        horizontal=True,
        key=f"tg_simple_count_v2_{simple_notify}",
    )

    def _to_time(value: str, fallback: time) -> time:
        try:
            hour, minute = map(int, value.split(":"))
            return time(hour, minute)
        except (TypeError, ValueError):
            return fallback

    gio_mac_dinh = [time(8, 0), time(10, 0), time(14, 0), time(16, 0)]
    gio_gui: list[time] = []
    time_cols = st.columns(so_lan)
    for index in range(so_lan):
        current_time = existing_times[index] if index < len(existing_times) else ""
        with time_cols[index]:
            gio_gui.append(st.time_input(
                f"Giờ gửi lần {index + 1}",
                value=_to_time(current_time, gio_mac_dinh[index]),
                step=300,
                key=f"tg_simple_time{index + 1}_{simple_notify}",
            ))

    delivery_mode = "full_each_time"
    if so_lan > 1:
        current_delivery = existing.get("delivery_mode", "full_then_delta") if existing else "full_then_delta"
        delivery_mode = st.radio(
            "Nội dung các lần gửi sau",
            options=["full_then_delta", "full_each_time"],
            index=0 if current_delivery == "full_then_delta" else 1,
            format_func=lambda x: (
                "Chỉ gửi thay đổi so với lần đầu" if x == "full_then_delta"
                else "Gửi lại toàn bộ nội dung"
            ),
            key=f"tg_simple_delivery_{simple_notify}",
        )

    save_col, test_col, stop_col = st.columns(3)
    with save_col:
        save_simple = st.button(
            "💾 Lưu và bật lịch",
            type="primary",
            key="tg_simple_save",
            use_container_width=True,
        )
    with test_col:
        test_simple = st.button(
            "▶ Gửi thử ngay",
            key="tg_simple_test",
            disabled=existing is None,
            use_container_width=True,
        )
    with stop_col:
        stop_simple = st.button(
            "⏸ Tắt lịch này",
            key="tg_simple_stop",
            disabled=existing is None or not existing["enabled"],
            use_container_width=True,
        )

    if save_simple:
        times = [value.strftime("%H:%M") for value in gio_gui]
        payload = {
            "id": existing.get("id") if existing else None,
            "name": labels.get(simple_notify, simple_notify),
            "notify_key": simple_notify,
            "enabled": True,
            "mode": "daily" if period == "daily" else "weekly",
            "delivery_mode": delivery_mode,
            "times": times,
            "weekdays": [] if period == "daily" else [0, 1, 2, 3, 4],
            "timezone": "Asia/Bangkok",
            "grace_minutes": 10,
            "max_runs_per_day": len(times),
            "max_attempts_per_slot": 1,
            "cooldown_minutes": 15,
        }
        new_rules = [rule for rule in rules if rule.get("notify_key") != simple_notify]
        new_rules.append(payload)
        try:
            if len(set(times)) != len(times):
                raise ValueError("Các lần gửi phải có giờ khác nhau.")
            luu_schedule_config({**cfg, "enabled": True, "rules": new_rules}, username)
            st.success("✅ Đã lưu và bật lịch gửi.")
            st.rerun()
        except Exception as e:
            logger.error("Lưu lịch Telegram đơn giản: %s", e, exc_info=True)
            st.error(f"❌ Không lưu được lịch: {e}")

    if test_simple and existing is not None:
        try:
            with st.spinner("Đang gửi thử..."):
                result = run_rule_now(existing["id"], username)
            if result.ok:
                st.success("✅ Đã gửi thử thành công.")
            else:
                st.error(f"❌ Gửi thử thất bại: {result.error or result.info}")
        except Exception as e:
            logger.error("Gửi thử lịch Telegram đơn giản: %s", e, exc_info=True)
            st.error(f"❌ Không gửi thử được: {e}")

    if stop_simple and existing is not None:
        try:
            new_rules = [
                {**rule, "enabled": False} if rule["id"] == existing["id"] else rule
                for rule in rules
            ]
            luu_schedule_config({**cfg, "rules": new_rules}, username)
            st.success("✅ Đã tắt lịch này.")
            st.rerun()
        except Exception as e:
            logger.error("Tắt lịch Telegram đơn giản: %s", e, exc_info=True)
            st.error(f"❌ Không tắt được lịch: {e}")

    st.divider()
    if not st.toggle("⚙️ Hiện cài đặt nâng cao", value=False, key="tg_show_advanced"):
        return

    st.caption("Phần dưới chỉ dành cho người cần chỉnh retry, cooldown, runlog hoặc chuyển máy.")
    status_labels = {
        "ok": "🟢 Đang hoạt động",
        "stale": "🔴 Mất heartbeat",
        "never": "🟠 Chưa chạy lần nào",
        "disabled": "⚪ Scheduler đang tắt",
    }
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Trạng thái", status_labels[health["status"]])
    h2.metric("Kiểm tra gần nhất", _fmt_scheduler_dt(health["heartbeat"]))
    h3.metric("Gửi thành công gần nhất", _fmt_scheduler_dt(health["last_success"]))
    h4.metric("Lần chạy kế tiếp", _fmt_scheduler_dt(health["next_run"]))

    global_enabled = st.toggle(
        "Bật rule-based scheduler",
        value=bool(cfg["enabled"]),
        key="tg_scheduler_enabled",
        help="Khi bật, các job có rule hoạt động sẽ được bỏ qua ở task nhac_deadline.py cũ để tránh gửi trùng.",
    )
    if st.button("💾 Lưu trạng thái Scheduler", key="tg_scheduler_enabled_save"):
        try:
            luu_schedule_config({**cfg, "enabled": global_enabled}, username)
            st.success("✅ Đã lưu trạng thái Scheduler.")
            st.rerun()
        except Exception as e:
            logger.error("Lưu trạng thái Telegram scheduler: %s", e, exc_info=True)
            st.error(f"❌ Không lưu được Scheduler: {e}")

    rule_map = {rule["id"]: rule for rule in rules}
    options = ["__new__", *rule_map]
    selected_id = st.selectbox(
        "Chọn rule để sửa",
        options=options,
        format_func=lambda x: "➕ Tạo rule mới" if x == "__new__" else rule_map[x]["name"],
        key="tg_scheduler_rule_select",
        on_change=_reset_scheduler_rule_form,
    )
    current = rule_map.get(selected_id, {})
    weekday_labels = {
        0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm",
        4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ nhật",
    }
    if selected_id != "__new__":
        if st.button("▶ Chạy thử rule đang chọn", key="tg_scheduler_rule_test", type="secondary"):
            try:
                with st.spinner("Đang chạy thử..."):
                    result = run_rule_now(selected_id, username)
                if result.ok:
                    st.success(f"✅ Chạy thử thành công — {result.info or f'đã gửi {result.sent} tin'}")
                else:
                    st.error(f"❌ Chạy thử thất bại: {result.error or result.info}")
            except Exception as e:
                logger.error("Chạy thử Telegram schedule rule: %s", e, exc_info=True)
                st.error(f"❌ Không chạy thử được: {e}")

    st.markdown("**Mẫu lịch tạo nhanh:**")
    p1, p2, p3, p4 = st.columns(4)
    p1.button("🌅 08:00 hằng ngày", key="tg_preset_morning", on_click=_apply_scheduler_preset, args=("morning",))
    p2.button("🔁 08:00 · 14:00", key="tg_preset_twice", on_click=_apply_scheduler_preset, args=("twice",))
    p3.button("📅 Thứ Hai", key="tg_preset_monday", on_click=_apply_scheduler_preset, args=("monday",))
    p4.button("💼 Thứ Hai–Sáu", key="tg_preset_weekdays", on_click=_apply_scheduler_preset, args=("weekdays",))
    preset_defaults = st.session_state.pop("_tg_scheduler_preset_defaults", {})
    default_mode = preset_defaults.get("mode", current.get("mode", "daily"))
    default_times = preset_defaults.get("times", current.get("times", ["08:00"]))
    default_weekdays = preset_defaults.get("weekdays", current.get("weekdays", [0, 1, 2, 3, 4]))
    default_max_runs = preset_defaults.get("max_runs", current.get("max_runs_per_day", 2))

    with st.form("tg_scheduler_rule_form"):
        name = st.text_input(
            "Tên rule",
            value=str(current.get("name", "")),
            placeholder="Ví dụ: Nhắc deadline sáng và chiều",
            key="tg_rule_name",
        )
        notify_key = st.selectbox(
            "Loại thông báo",
            options=list(telegram_job_keys()),
            index=max(0, list(telegram_job_keys()).index(current.get("notify_key")))
            if current.get("notify_key") in telegram_job_keys() else 0,
            format_func=lambda x: labels.get(x, x),
            key="tg_rule_notify",
        )
        mode = st.radio(
            "Chu kỳ",
            options=["daily", "weekly"],
            index=1 if default_mode == "weekly" else 0,
            format_func=lambda x: "Hằng ngày" if x == "daily" else "Hằng tuần",
            horizontal=True,
            key="tg_rule_mode",
        )
        times_text = st.text_input(
            "Các mốc giờ (phân cách bằng dấu phẩy)",
            value=", ".join(default_times),
            placeholder="08:00, 14:00",
            key="tg_rule_times",
        )
        weekdays = st.multiselect(
            "Các thứ áp dụng (chỉ dùng cho lịch tuần)",
            options=list(weekday_labels),
            default=default_weekdays,
            format_func=lambda x: weekday_labels[x],
            key="tg_rule_weekdays",
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            max_runs = st.number_input(
                "Lượt chạy tối đa/ngày", min_value=1, max_value=20,
                value=int(default_max_runs), step=1, key="tg_rule_max_runs",
            )
        with c2:
            grace = st.number_input(
                "Cửa sổ chạy (phút)", min_value=1, max_value=60,
                value=int(current.get("grace_minutes", 10)), step=1, key="tg_rule_grace",
            )
        with c3:
            attempts = st.number_input(
                "Thử lại tối đa/slot", min_value=1, max_value=3,
                value=int(current.get("max_attempts_per_slot", 1)), step=1, key="tg_rule_attempts",
            )
        with c4:
            cooldown = st.number_input(
                "Cooldown (phút)", min_value=0, max_value=1440,
                value=int(current.get("cooldown_minutes", 15)), step=5, key="tg_rule_cooldown",
            )
        rule_enabled = st.toggle(
            "Bật rule này", value=bool(current.get("enabled", True)), key="tg_rule_enabled"
        )
        submitted = st.form_submit_button("💾 Lưu rule", type="primary")

    if submitted:
        times = [x.strip() for x in times_text.split(",") if x.strip()]
        payload = {
            "id": current.get("id"),
            "name": name or labels.get(notify_key, notify_key),
            "notify_key": notify_key,
            "enabled": rule_enabled,
            "mode": mode,
            "delivery_mode": current.get("delivery_mode", "full_each_time"),
            "times": times,
            "weekdays": weekdays if mode == "weekly" else [],
            "timezone": "Asia/Bangkok",
            "grace_minutes": int(grace),
            "max_runs_per_day": int(max_runs),
            "max_attempts_per_slot": int(attempts),
            "cooldown_minutes": int(cooldown),
        }
        new_rules = [rule for rule in rules if rule["id"] != selected_id]
        new_rules.append(payload)
        try:
            luu_schedule_config({**cfg, "rules": new_rules}, username)
            st.success("✅ Đã lưu rule Telegram.")
            st.rerun()
        except Exception as e:
            logger.error("Lưu Telegram schedule rule: %s", e, exc_info=True)
            st.error(f"❌ Rule không hợp lệ: {e}")

    if selected_id != "__new__" and st.button("🗑️ Xóa rule đang chọn", key="tg_scheduler_rule_delete"):
        try:
            luu_schedule_config(
                {**cfg, "rules": [rule for rule in rules if rule["id"] != selected_id]},
                username,
            )
            st.success("✅ Đã xóa rule.")
            st.rerun()
        except Exception as e:
            logger.error("Xóa Telegram schedule rule: %s", e, exc_info=True)
            st.error(f"❌ Không xóa được rule: {e}")

    st.divider()
    st.markdown("##### Xuất / nhập cấu hình rule")
    st.caption("File JSON chỉ chứa lịch gửi, không chứa Bot Token hoặc Chat ID. Khi nhập, Scheduler luôn để Tắt.")
    export_payload = {"schema_version": cfg["schema_version"], "enabled": False, "rules": rules}
    export_bytes = json.dumps(export_payload, ensure_ascii=False, indent=2).encode("utf-8")
    ex1, ex2 = st.columns(2)
    with ex1:
        st.download_button(
            "⬇️ Xuất cấu hình rule",
            data=export_bytes,
            file_name=f"telegram_schedule_rules_{date.today():%Y%m%d}.json",
            mime="application/json",
            key="tg_scheduler_export",
            use_container_width=True,
        )
    with ex2:
        import_file = st.file_uploader(
            "Chọn file rule JSON",
            type=["json"],
            key="tg_scheduler_import_file",
            label_visibility="collapsed",
        )
    if st.button(
        "⬆️ Nhập cấu hình rule",
        key="tg_scheduler_import",
        disabled=import_file is None,
    ):
        try:
            imported = json.loads(import_file.getvalue().decode("utf-8-sig"))
            if not isinstance(imported, dict):
                raise ValueError("File JSON phải chứa một object cấu hình.")
            imported["enabled"] = False
            saved = luu_schedule_config(imported, username)
            st.success(f"✅ Đã nhập {len(saved['rules'])} rule. Scheduler đang Tắt để kiểm tra an toàn.")
            _reset_scheduler_rule_form()
            st.rerun()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RuntimeError) as e:
            logger.error("Nhập Telegram schedule rules: %s", e, exc_info=True)
            st.error(f"❌ Không nhập được cấu hình: {e}")

    st.divider()
    today_key = date.today().strftime("%Y%m%d")
    runlog = db.doc_kv(f"{RUNLOG_PREFIX}{today_key}") or {}
    st.markdown("##### Runlog hôm nay")
    if not runlog:
        st.caption("Chưa có slot Scheduler nào chạy hôm nay.")
    else:
        rows = [
            {
                "Slot": entry.get("slot_id", slot_id),
                "Loại": labels.get(entry.get("notify_key"), entry.get("notify_key", "")),
                "Trạng thái": entry.get("status", ""),
                "Lần thử": entry.get("attempts", 0),
                "Đã gửi": entry.get("sent", 0),
                "Lỗi": entry.get("error", ""),
                "Cập nhật": str(entry.get("updated_at", ""))[:19].replace("T", " "),
            }
            for slot_id, entry in sorted(runlog.items(), reverse=True)
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render(tab: DeltaGenerator = None, **kwargs) -> None:
    role_raw = str(kwargs.get("role", "user") or "user")
    role     = normalize_role(role_raw)
    username = kwargs.get("username", "unknown")

    ctx = tab if tab is not None else st.container()
    with ctx:
        # Chỉ admin_cn và manager_cn — không cho executive và chuyenvien_cn
        if not la_phan_he_cn(role) or la_executive(role) or la_chuyen_vien_cn(role):
            st.warning("⚠️ Chức năng dành riêng cho Admin và Quản lý Chi nhánh.")
            return

        st.subheader("🤖 Quản trị Telegram Bot")

        tab_cfg, tab_tb, tab_sched, tab_log = st.tabs(
            ["⚙️ Cấu hình Bot", "🔔 Thông báo", "🗓️ Lịch nâng cao", "📋 Lịch sử"]
        )

        # ── Sub-tab 1: Cấu hình Bot ───────────────────────────────────────────
        with tab_cfg:
            cfg         = db.doc_kv("telegram_config") or {}
            cur_token   = cfg.get("token", "")
            cur_chat_id = cfg.get("chat_id", "-5339155216")
            extra_chats = cfg.get("extra_chats", {})

            st.markdown("##### Token & Chat ID chính")
            col1, col2 = st.columns(2)
            with col1:
                new_token = st.text_input(
                    "Bot Token",
                    value=cur_token,
                    type="password",
                    placeholder="110xxxxxxx:AAF...",
                    key="tg_token",
                )
            with col2:
                new_chat_id = st.text_input(
                    "Chat ID chính",
                    value=cur_chat_id,
                    placeholder="-100xxxxxxxxxx",
                    key="tg_chat_id",
                )

            c_luu, c_test, _ = st.columns([1, 1, 4])
            with c_luu:
                if st.button("💾 Lưu", key="tg_btn_luu", use_container_width=True):
                    if not new_token.strip():
                        st.error("❌ Token không được để trống.")
                    elif not new_chat_id.strip():
                        st.error("❌ Chat ID không được để trống.")
                    else:
                        from services.telegram_service import luu_config
                        luu_config(new_token.strip(), new_chat_id.strip(), username)
                        st.success("✅ Đã lưu cấu hình bot.")
            with c_test:
                if st.button("🧪 Test kết nối", key="tg_btn_test", use_container_width=True):
                    from services.telegram_service import gui_tin_chi_tiet_voi_config

                    msg_html = "✅ <b>VBSP-SCM</b> kết nối Telegram thành công!"
                    err_html = ""
                    da_fallback_plain_text = False
                    ok, err = gui_tin_chi_tiet_voi_config(
                        new_token.strip(),
                        new_chat_id.strip(),
                        msg_html,
                        parse_mode="HTML",
                    )
                    # Nếu lỗi do parse HTML, thử lại plain text để tách lỗi nội dung khỏi lỗi cấu hình.
                    if (not ok) and err and "parse" in err.lower():
                        err_html = err
                        da_fallback_plain_text = True
                        ok, err = gui_tin_chi_tiet_voi_config(
                            new_token.strip(),
                            new_chat_id.strip(),
                            "VBSP-SCM ket noi Telegram thanh cong!",
                            parse_mode="",
                        )
                    if ok:
                        st.success("✅ Gửi thành công — kiểm tra group Telegram.")
                        if da_fallback_plain_text and err_html:
                            st.warning(
                                "⚠️ Token/Chat ID hợp lệ nhưng Telegram từ chối parse HTML. "
                                f"Chi tiết: {err_html}"
                            )
                    else:
                        st.error(f"❌ Gửi thất bại — {err or 'kiểm tra Token và Chat ID.'}")

            if cur_token:
                st.caption(f"Token: `...{cur_token[-8:]}`   |   Chat ID chính: `{cur_chat_id}`")
            else:
                st.caption("⚠️ Chưa cấu hình token — đang dùng giá trị mặc định từ biến môi trường.")

            st.divider()

            # ── Chat ID phụ theo loại thông báo ──────────────────────────────
            st.markdown("##### Chat ID phụ (tuỳ chọn)")
            st.caption(
                "Mỗi loại thông báo có thể gửi vào 1 group riêng. "
                "Để trống = dùng Chat ID chính ở trên."
            )

            notify_labels = {m["key"]: f"{m['icon']} {m['ten']}" for m in _NOTIFY_META}
            sel_key = st.selectbox(
                "Chọn loại thông báo để cấu hình chat ID phụ",
                options=[m["key"] for m in _NOTIFY_META],
                format_func=lambda k: notify_labels[k],
                key="tg_extra_sel",
            )
            cur_extra = extra_chats.get(sel_key, "")
            new_extra = st.text_input(
                f"Chat ID phụ cho {notify_labels[sel_key]}",
                value=cur_extra,
                placeholder="-100xxxxxxxxxx (để trống = dùng chat chính)",
                key="tg_extra_val",
            )
            if st.button("💾 Lưu Chat ID phụ", key="tg_extra_save"):
                from services.telegram_service import luu_extra_chat
                luu_extra_chat(sel_key, new_extra, username)
                if new_extra.strip():
                    st.success(f"✅ Đã lưu Chat ID phụ cho {notify_labels[sel_key]}.")
                else:
                    st.success(f"✅ Đã xóa Chat ID phụ — sẽ dùng chat chính.")
                st.rerun()

            # Hiển thị tóm tắt extra_chats đã cấu hình
            if extra_chats:
                st.markdown("**Đã cấu hình chat ID phụ:**")
                for k, v in extra_chats.items():
                    label = notify_labels.get(k, k)
                    st.caption(f"📡 {label}: `{v}`")

            st.divider()

            # ── Chat ID riêng từng PGD ────────────────────────────────────────
            st.markdown("##### Chat ID riêng từng PGD (tuỳ chọn)")
            st.caption(
                "Mỗi PGD có thể nhận tin nhắn vào group chat riêng của PGD đó. "
                "Ưu tiên: Chat PGD > Chat phụ loại TB > Chat chính."
            )
            from config import DS_PGD
            pgd_chats = (db.doc_kv("telegram_config") or {}).get("pgd_chats", {})
            sel_pgd = st.selectbox(
                "Chọn PGD để cấu hình chat riêng",
                options=DS_PGD,
                key="tg_pgd_sel",
            )
            from data.pgd import pgd_slug as _slug_fn
            cur_pgd_chat = pgd_chats.get(_slug_fn(sel_pgd), "")
            new_pgd_chat = st.text_input(
                f"Chat ID riêng cho {sel_pgd}",
                value=cur_pgd_chat,
                placeholder="-100xxxxxxxxxx (để trống = dùng chat chính)",
                key="tg_pgd_chat_val",
            )
            if st.button("💾 Lưu Chat PGD", key="tg_pgd_chat_save"):
                from services.telegram_service import luu_pgd_chat
                luu_pgd_chat(sel_pgd, new_pgd_chat, username)
                if new_pgd_chat.strip():
                    st.success(f"✅ Đã lưu Chat ID riêng cho {sel_pgd}.")
                else:
                    st.success(f"✅ Đã xóa Chat ID riêng — PGD {sel_pgd} sẽ dùng chat chính.")
                st.rerun()
            if pgd_chats:
                st.markdown("**PGD đã cấu hình chat riêng:**")
                for slug, cid in pgd_chats.items():
                    st.caption(f"📱 `{slug}`: `{cid}`")

        # ── Sub-tab 2: Thông báo ──────────────────────────────────────────────
        with tab_tb:
            notify_cfg  = db.doc_kv("telegram_notify_config") or {}
            sched_cfg   = db.doc_kv("telegram_schedule_config") or {}
            extra_chats = (db.doc_kv("telegram_config") or {}).get("extra_chats", {})
            from services.telegram_schedule_service import doc_schedule_config

            advanced_cfg = doc_schedule_config()
            advanced_keys = {
                rule["notify_key"] for rule in advanced_cfg["rules"]
                if advanced_cfg["enabled"] and rule["enabled"]
            }

            new_notify: dict[str, bool] = {}
            new_sched:  dict[str, str]  = dict(sched_cfg)  # giữ giá trị cũ, chỉ cập nhật loại schedule
            notify_changed = False
            sched_changed  = False

            meta_by_key = {m["key"]: m for m in _NOTIFY_META}
            group_by_key = {
                key: group
                for group in _NOTIFY_GROUPS
                for key in group["keys"]
            }
            ordered_meta = [
                meta_by_key[key]
                for group in _NOTIFY_GROUPS
                for key in group["keys"]
            ]
            st.caption(
                f"{len(_NOTIFY_META)} loại thông báo được sắp xếp theo 4 nhóm nghiệp vụ."
            )

            current_group = None
            group_container = None
            for m in ordered_meta:
                key       = m["key"]
                cur_on    = bool(notify_cfg.get(key, True))
                cur_gio   = sched_cfg.get(key, m["gio_mac_dinh"])
                has_extra = bool(extra_chats.get(key, ""))

                group = group_by_key[key]
                if group["ten"] != current_group:
                    group_container = st.expander(
                        f"{group['icon']} {group['ten']} ({len(group['keys'])})",
                        expanded=current_group is None,
                    )
                    group_container.caption(group["mo_ta"])
                    hdr = group_container.columns([2.5, 2.5, 1.5, 1, 1.5])
                    hdr[0].markdown("**Loại thông báo**")
                    hdr[1].markdown("**Mô tả**")
                    hdr[2].markdown("**Lịch / Giờ gửi**")
                    hdr[3].markdown("**Chat phụ**")
                    hdr[4].markdown("**Thao tác**")
                    current_group = group["ten"]

                c1, c2, c3, c4, c5 = group_container.columns([2.5, 2.5, 1.5, 1, 1.5])

                with c1:
                    new_on = st.toggle(
                        f"{m['icon']} {m['ten']}",
                        value=cur_on,
                        key=f"tg_t_{key}",
                    )
                    new_notify[key] = new_on
                    if new_on != cur_on:
                        notify_changed = True

                with c2:
                    st.caption(m["mo_ta"])

                with c3:
                    if key in advanced_keys:
                        st.caption("🗓️ Theo rule", help="Cấu hình tại tab Lịch nâng cao")
                    elif key in _SCHEDULE_KEYS:
                        new_gio = st.text_input(
                            "Giờ",
                            value=cur_gio,
                            placeholder="HH:MM",
                            key=f"tg_gio_{key}",
                            label_visibility="collapsed",
                        )
                        new_sched[key] = new_gio.strip()
                        if new_gio.strip() != cur_gio:
                            sched_changed = True
                    elif key in _TASK_GIO:
                        st.caption(
                            f"🕐 {_TASK_GIO[key]}",
                            help="Theo lịch hệ thống (Task Scheduler) — không chỉnh tại đây",
                        )
                    elif key in _EVENT_KEYS:
                        st.caption("⚡ Sự kiện tự động")
                    else:
                        st.caption("✋ Chỉ gửi thủ công")

                with c4:
                    if has_extra:
                        st.markdown("📡", help="Đã cấu hình chat ID phụ")
                    else:
                        st.caption("—")

                with c5:
                    if st.button("▶ Gửi ngay", key=f"tg_send_{key}", use_container_width=True):
                        with st.spinner("Đang gửi..."):
                            ok, info = _gui_ngay(key)
                        if ok:
                            msg = f"✅ Đã gửi {m['icon']} {m['ten']}"
                            if info:
                                msg += f" — {info}"
                            st.toast(msg)
                        else:
                            st.toast(f"❌ Lỗi: {info}", icon="❌")

            st.divider()
            c_sv1, c_sv2, _ = st.columns([1.5, 1.5, 4])
            with c_sv1:
                if st.button(
                    "💾 Lưu bật/tắt",
                    key="tg_notify_save",
                    type="primary",
                    disabled=not notify_changed,
                ):
                    db.ghi_kv("telegram_notify_config", new_notify, username)
                    db.ghi_audit(username, "telegram_notify_config", "Cập nhật bật/tắt thông báo Telegram")
                    st.success("✅ Đã lưu trạng thái bật/tắt.")
                    st.rerun()
            with c_sv2:
                if st.button(
                    "🕐 Lưu lịch gửi",
                    key="tg_sched_save",
                    type="secondary",
                    disabled=not sched_changed,
                ):
                    db.ghi_kv("telegram_schedule_config", new_sched, username)
                    db.ghi_audit(username, "telegram_schedule_config", "Cập nhật lịch gửi Telegram")
                    st.success("✅ Đã lưu lịch gửi.")
                    st.rerun()

            if not notify_changed and not sched_changed:
                st.caption("Thay đổi toggle hoặc giờ gửi để kích hoạt nút Lưu.")

            st.divider()
            with st.expander("🧾 Nhắc nộp báo cáo — chọn loại báo cáo muốn gửi", expanded=False):
                deadline_cfg = db.doc_kv("bao_cao_deadline_config") or {}
                ds_loai = sorted([str(k) for k in deadline_cfg.keys()]) if isinstance(deadline_cfg, dict) else []
                from services.telegram_service import doc_deadline_bc_allowlist, luu_deadline_bc_allowlist
                allowlist_raw = doc_deadline_bc_allowlist()
                allowlist, stale_allowlist = _loc_allowlist_deadline(allowlist_raw, ds_loai)

                if not ds_loai:
                    st.info("Chưa có danh mục deadline báo cáo. Vào tab Tiến độ nộp BC để cài đặt trước.")
                else:
                    mode = st.radio(
                        "Phạm vi gửi nhắc deadline",
                        options=["Tất cả loại báo cáo", "Chỉ một số loại (lọc)"],
                        index=0 if allowlist_raw is None else 1,
                        horizontal=True,
                        key="tg_deadline_mode",
                    )
                    sel = None
                    if mode.startswith("Chỉ"):
                        sel = st.multiselect(
                            "Chọn loại báo cáo sẽ gửi Telegram",
                            options=ds_loai,
                            default=allowlist if allowlist is not None else ds_loai,
                            key="tg_deadline_allowlist",
                        )
                        st.caption(f"Đang chọn {len(sel)}/{len(ds_loai)} loại.")
                        if stale_allowlist:
                            preview = ", ".join(stale_allowlist[:3])
                            if len(stale_allowlist) > 3:
                                preview += ", ..."
                            st.warning(
                                f"⚠️ Allowlist cũ có {len(stale_allowlist)} loại không còn trong deadline hiện tại: {preview}"
                            )
                    else:
                        st.caption(f"Đang bật: gửi tất cả {len(ds_loai)} loại báo cáo.")

                    if st.button("💾 Lưu lọc loại báo cáo", key="tg_deadline_save", type="primary"):
                        if mode.startswith("Chỉ") and not sel:
                            st.error("❌ Chưa chọn loại báo cáo nào.")
                        else:
                            luu_deadline_bc_allowlist(sel if mode.startswith("Chỉ") else None, username)
                            st.success("✅ Đã lưu cấu hình lọc loại báo cáo.")
                            st.rerun()

        with tab_sched:
            _render_scheduler_rules(username)

        # ── Sub-tab 4: Lịch sử gửi ────────────────────────────────────────────
        with tab_log:
            log = db.doc_kv("telegram_send_log") or []
            if not log:
                st.caption("Chưa có lịch sử gửi.")
            else:
                rows = []
                for entry in log[:50]:
                    ts      = (entry.get("ts") or "")[:19].replace("T", " ")
                    func    = entry.get("func", "")
                    preview = entry.get("preview", "")
                    ok      = entry.get("ok", False)
                    err     = entry.get("error", "")
                    ket_qua = "✅" if ok else f"❌ {err[:180]}"
                    rows.append({
                        "Thời gian": ts,
                        "Loại": func,
                        "Nội dung": preview,
                        "Kết quả": ket_qua,
                    })
                df_log = pd.DataFrame(rows)
                st.dataframe(df_log, use_container_width=True, hide_index=True)
                st.caption(f"Hiển thị {min(50, len(log))}/{len(log)} bản ghi gần nhất.")
