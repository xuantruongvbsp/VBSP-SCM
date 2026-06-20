"""Quản trị Telegram Bot — cấu hình, bật/tắt, lịch gửi, thao tác thủ công."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import date
from streamlit.delta_generator import DeltaGenerator

import db
from auth import la_phan_he_cn, la_executive, la_chuyen_vien_cn, normalize_role
from logger import get_logger

logger = get_logger(__name__)

# ── Metadata 10 loại thông báo ────────────────────────────────────────────────
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
        "key": "health_check",
        "icon": "🔍", "ten": "Kết quả Health Check",
        "mo_ta": "Trạng thái hệ thống mỗi buổi sáng",
        "gio_mac_dinh": "07:00",
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
    "health_check":      "06:30",
    "deadline_bc":       "08:00 / 14:00",
    "den_han_phan_tang": "08:00 / 14:00",
    "nop_moi_gsheet":    "08:00 / 14:00",
    "lich_cong_tac":     "14:00",
}
# Loại kích hoạt theo sự kiện nghiệp vụ (không có khái niệm giờ).
_EVENT_KEYS = {"merge_thanh_cong", "upload_pgd"}
# Các loại còn lại (he_thong, khtd_tien_do) chỉ gửi thủ công qua nút "▶ Gửi ngay".


def _gui_ngay(key: str) -> tuple[bool, str]:
    """Load dữ liệu thực và gửi thông báo ngay lập tức. Trả (ok, thông tin)."""
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
            return ok, f"{so_pgd}/{len(DS_PGD)} PGD"

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
            return ok, f"{len(ds)} khoản"

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
            count = 0
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
                tg.gui_nhac_phan_ky_nxh(str(ten_pgd), ds, today_ts.strftime("%d/%m/%Y"))
                count += 1
            return True, f"Đã gửi {count} PGD"

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
            return ok, f"{len(ds_pgd)} PGD"

        elif key == "qh_moi":
            ok = tg.gui_canh_bao_qh_moi([])
            return True, "Không có PGD nào tăng NQH (test)"

        elif key == "deadline_bc":
            from tabs.tab_tien_do_nop import doc_du_lieu_gsheet, lay_pgd_chua_nop
            deadline_cfg = db.doc_kv("bao_cao_deadline_config") or {}
            if not deadline_cfg:
                return False, "Chưa cài đặt deadline (vào tab Tiến độ → ⚙️ Cài đặt thời hạn)."
            df_gs = doc_du_lieu_gsheet()
            total_sent = 0
            for loai_bao_cao in deadline_cfg:
                ds_chua_nop, deadline_str = lay_pgd_chua_nop(loai_bao_cao, df_gs)
                if not ds_chua_nop:
                    continue
                dl_hien = deadline_str or "—"
                try:
                    dl_hien = pd.to_datetime(deadline_str).strftime("%d/%m/%Y")
                except Exception:
                    pass
                ok = tg.gui_canh_bao_deadline(loai_bao_cao, dl_hien, ds_chua_nop)
                if ok:
                    total_sent += 1
            if total_sent == 0:
                return True, "Tất cả PGD đã nộp hoặc chưa đến deadline"
            return True, f"Đã gửi {total_sent} loại báo cáo"

        elif key == "health_check":
            ok = tg.gui_ket_qua_health_check(
                0, 0, 0, date.today().strftime("%d/%m/%Y"), "Test thủ công từ Admin"
            )
            return ok, ""

        elif key == "merge_thanh_cong":
            ok = tg.gui_thong_bao_merge("HSTD", 22, "admin")
            return ok, "(Test thủ công)"

        elif key == "upload_pgd":
            ok = tg.gui_thong_bao_upload_pgd("(Test PGD)", "HSTD", "admin")
            return ok, "(Test thủ công)"

        elif key == "he_thong":
            ok = tg.gui_canh_bao_he_thong("canh_bao", "Test thủ công từ Admin")
            return ok, "(Test thủ công)"

        elif key == "nop_moi_gsheet":
            from tabs.tab_tien_do_nop import doc_du_lieu_gsheet
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
            return ok, f"{len(ds)} submission trong 24h qua"

        elif key == "den_han_phan_tang":
            from data.core import CACHE_HSTD
            from config import COT_NGAY_DH, COT_TONG_DU_NO, COT_TEN_KH, COT_SO_KU, COT_TEN_PGD
            if not CACHE_HSTD.exists():
                return False, "Chưa có dữ liệu HSTD."
            df = pd.read_parquet(CACHE_HSTD)
            if COT_NGAY_DH not in df.columns:
                return False, f"Thiếu cột {COT_NGAY_DH}."
            today_ts = pd.Timestamp.today().normalize()
            buckets: dict[str, list[dict]] = {"T-1": [], "T-3": [], "T-7": []}
            tier_map = {1: "T-1", 3: "T-3", 7: "T-7"}
            for days in (1, 3, 7):
                target = today_ts + pd.Timedelta(days=days)
                mask = df[COT_NGAY_DH].notna() & (df[COT_NGAY_DH].dt.normalize() == target)
                for _, r in df[mask].iterrows():
                    buckets[tier_map[days]].append({
                        "ten_kh":  str(r.get(COT_TEN_KH, "") or ""),
                        "so_ku":   str(r.get(COT_SO_KU, "") or ""),
                        "ngay_dh": target.strftime("%d/%m/%Y"),
                        "du_no":   float(r.get(COT_TONG_DU_NO, 0) or 0),
                        "ten_pgd": str(r.get(COT_TEN_PGD, "") or ""),
                    })
            total = sum(len(v) for v in buckets.values())
            ok = tg.gui_nhac_den_han_phan_tang(buckets)
            return ok, f"{total} khoản (T-1:{len(buckets['T-1'])}, T-3:{len(buckets['T-3'])}, T-7:{len(buckets['T-7'])})"

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
            return ok, f"{len(ds_sv)} sự kiện ngày {ngay_mai_str}"

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
            return ok, f"{len(df_gn)} khoản vay mới"

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
                return ok, f"{len(ds_tang)} đơn vị tăng nợ khoanh"
            except Exception as e:
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
            return ok, f"{len(ds_pgd)} đơn vị"

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
            return ok, f"{len(ds_ct)} chương trình"

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
            return ok, f"Tháng {thang:02d}/{nam}"

        else:
            return False, f"Chưa hỗ trợ loại: {key}"

    except Exception as e:
        logger.error("_gui_ngay %s: %s", key, e, exc_info=True)
        return False, str(e)


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

        tab_cfg, tab_tb, tab_log = st.tabs(["⚙️ Cấu hình Bot", "🔔 Thông báo", "📋 Lịch sử"])

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
                    from services.telegram_service import gui_tin
                    ok = gui_tin("✅ <b>VBSP-SCM</b> kết nối Telegram thành công!")
                    if ok:
                        st.success("✅ Gửi thành công — kiểm tra group Telegram.")
                    else:
                        st.error("❌ Gửi thất bại — kiểm tra Token và Chat ID.")

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

            new_notify: dict[str, bool] = {}
            new_sched:  dict[str, str]  = dict(sched_cfg)  # giữ giá trị cũ, chỉ cập nhật loại schedule
            notify_changed = False
            sched_changed  = False

            # Header
            hdr = st.columns([2.5, 2.5, 1.5, 1, 1.5])
            hdr[0].markdown("**Loại thông báo**")
            hdr[1].markdown("**Mô tả**")
            hdr[2].markdown("**Lịch / Giờ gửi**")
            hdr[3].markdown("**Chat phụ**")
            hdr[4].markdown("**Thao tác**")
            st.divider()

            for m in _NOTIFY_META:
                key       = m["key"]
                cur_on    = bool(notify_cfg.get(key, True))
                cur_gio   = sched_cfg.get(key, m["gio_mac_dinh"])
                has_extra = bool(extra_chats.get(key, ""))

                c1, c2, c3, c4, c5 = st.columns([2.5, 2.5, 1.5, 1, 1.5])

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
                    if key in _SCHEDULE_KEYS:
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

        # ── Sub-tab 3: Lịch sử gửi ────────────────────────────────────────────
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
                    ket_qua = "✅" if ok else f"❌ {err[:60]}"
                    rows.append({
                        "Thời gian": ts,
                        "Loại": func,
                        "Nội dung": preview,
                        "Kết quả": ket_qua,
                    })
                df_log = pd.DataFrame(rows)
                st.dataframe(df_log, use_container_width=True, hide_index=True)
                st.caption(f"Hiển thị {min(50, len(log))}/{len(log)} bản ghi gần nhất.")
