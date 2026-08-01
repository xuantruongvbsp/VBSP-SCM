"""
Dịch vụ xử lý upload file tập trung (Upload Service).
──────────────────────────────────────────────────────
Tất cả các tab gọi qua đây để đảm bảo:
  - Logic kiểm tra file đồng nhất (định dạng, kích thước)
  - Đường dẫn lưu trữ chính xác từ config (không hardcode ở tab)
  - Cache Streamlit được xóa nhất quán sau mỗi lần lưu thành công

Các hàm công khai:
  kiem_tra_file()          — kiểm tra cơ bản (ext + kích thước)
  kiem_tra_file_he_thong() — kiểm tra thêm: tên file phải trong FILES_HE_THONG (HSTD/NQ11)
  luu_file_he_thong()      — lưu file hệ thống qua tab Quản trị
  luu_dienbao()            — lưu Điện báo (ht / prev): toàn CN hoặc theo PGD
  luu_pgd_file()           — lưu file HSTD/NQ11/GQVL/CDTOTKVV theo PGD
                             Tự động gọi merge_du_lieu_toan_cn() sau khi lưu
                             thành công (trừ CDTOTKVV)
  merge_du_lieu_toan_cn()  — gộp file 22 đơn vị thành dữ liệu toàn CN
  luu_cdtotkvv()           — lưu file chấm điểm Tổ TK&VV theo tháng (legacy)
"""
import hashlib
import os
import re
import shutil
import socket
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
import db
from logger import get_logger

logger = get_logger(__name__)
from utils import fmt_so, vn
from data.core import ts_file, excel_to_parquet, _should_force_str, _normalize_code_series


def duong_dan_pgd(ten_pgd: str, loai: str) -> str:
    """Lazy-load data.pgd để tránh circular import khi services.__init__ được load."""
    from data.pgd import duong_dan_pgd as _fn
    return _fn(ten_pgd, loai)

from services.data_quality import kiem_tra_chat_luong
from config import (
    CACHE_DIR,
    TEN_FILE, TEN_FILE_NQ11,
    FILE_PATH, FILE_PATH_NQ11,
    DB_HT_CACHE, DB_PREV_CACHE, DB_PREV_MONTH_CACHE,
    CDTOTKVV_DIR,
    TEN_FILE_GQVL, FILE_PATH_GQVL, CACHE_GQVL, CACHE_HSTD, CACHE_NQ11,
    DS_PGD, DON_VI_CHI_NHANH, GQVL_COT_MAP, COT_TEN_PGD,
    COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_THOI_HAN, COT_GIAI_NGAN_TRONG_NAM,
    COT_MUC_VAY, COT_TONG_DU_NO, COT_LAI_TON, COT_LAI_TON_QH,
    COT_LAI_THANG, COT_GOC_TRA, COT_NGAY_SL,
    UPLOAD_CANH_BAO_NGAY,
)

_MERGE_LOCK: dict[str, threading.RLock] = {
    "hstd": threading.RLock(),
    "nq11": threading.RLock(),
    "gqvl": threading.RLock(),
}
_FILE_WRITE_LOCK = threading.RLock()

_BAD_VALS = {"nan", "None", "<NA>", "NaT"}

# ── Hằng số kiểm tra ─────────────────────────────────────────────────────────

EXTS_CHOPHEP: set[str] = {".xlsx", ".xls", ".XLSX", ".XLS"}
KICH_THUOC_TOI_THIEU: int = 1_000  # bytes — phát hiện file rỗng/lỗi

# Danh sách file hệ thống được phép upload qua tab Quản trị.
# Mỗi entry: mo_ta (hiển thị), path (nơi lưu gốc), cache (file cache cần xóa)
FILES_HE_THONG: dict[str, dict] = {
    TEN_FILE: {
        "mo_ta":  "📊 HSTD Chi tiết",
        "path":   FILE_PATH,
        # Không xóa hstd.parquet (cache merged 22 PGD) khi upload file hệ thống cũ —
        # việc cập nhật parquet phải qua merge_du_lieu_toan_cn() trong tab Upload HSTD.
    },
    TEN_FILE_NQ11: {
        "mo_ta":  "📑 Sao kê NQ11",
        "path":   FILE_PATH_NQ11,
        "cache":  str(CACHE_DIR / "nq11.parquet"),
    },
}


# ── Kết quả upload chuẩn hóa ─────────────────────────────────────────────────

@dataclass
class KetQuaUpload:
    """Kết quả trả về từ mọi hàm xử lý upload."""
    thanh_cong: bool
    thong_bao: str
    duong_dan: str = ""
    chi_tiet: dict | None = None

    def hien_thi(self) -> None:
        """Hiển thị kết quả bằng st.success hoặc st.error."""
        if self.thanh_cong:
            st.success(self.thong_bao)
        else:
            st.error(self.thong_bao)


def _fmt_ty_inline(gia_tri_vnd: float | int) -> str:
    """Format nhanh VND -> tỷ đồng theo kiểu VN để dùng trong cảnh báo ngắn."""
    return vn((float(gia_tri_vnd) if gia_tri_vnd else 0) / 1e9, 3) + " tỷ"


def _tom_tat_trung_cheo_hstd(report: dict, pham_vi: str, giu_nguyen_cache: bool) -> str:
    """Tạo thông báo ngắn gọn khi phát hiện khoản vay HSTD bị trùng chéo giữa PGD."""
    top_pairs = report.get("top_pairs") or []
    top_text = "; ".join(
        f"{row.get('cap_pgd', 'N/A')} ({_fmt_ty_inline(row.get('tong_du_no_trung', 0))})"
        for row in top_pairs[:3]
    )
    thong_bao = (
        f"Phát hiện **{fmt_so(report.get('duplicate_group_count', 0))}** món vay {pham_vi} "
        f"bị trùng chéo giữa **{report.get('duplicate_pair_count', 0)}** cặp/nhóm PGD "
        f"(khóa: **Mã KH + Số khế ước**), ước cộng thừa "
        f"**{_fmt_ty_inline(report.get('estimated_excess_amount', 0))}**."
    )
    if top_text:
        thong_bao += f" Top chênh lớn: {top_text}."
    if giu_nguyen_cache:
        thong_bao += " Cache đang dùng được giữ nguyên, chưa ghi đè số sai."
    return thong_bao


def _normalize_merge_dataframe_for_parquet(df_toan_cn: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa dtype trước khi ghi parquet để dùng chung cho merge hiện tại và baseline."""
    df_out = df_toan_cn
    _cols_so_cn = [
        COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH,
        "Tổng giải ngân", COT_GIAI_NGAN_TRONG_NAM, "Dư tài khoản",
        COT_THOI_HAN,
        COT_MUC_VAY, COT_TONG_DU_NO, COT_LAI_TON, COT_LAI_TON_QH,
        COT_LAI_THANG, COT_GOC_TRA,
    ]
    for col in _cols_so_cn:
        if col in df_out.columns:
            df_out[col] = pd.to_numeric(df_out[col], errors="coerce")

    _bad_vals_lower = {v.lower() for v in _BAD_VALS}
    for col in df_out.columns:
        if col in _cols_so_cn:
            continue
        ser = df_out[col]
        if _should_force_str(col):
            if pd.api.types.is_numeric_dtype(ser.dtype):
                df_out[col] = _normalize_code_series(ser)
            continue
        if isinstance(ser.dtype, pd.CategoricalDtype):
            ser = ser.astype(object)
        elif not ser.dtype == object:
            continue
        _ser_str = ser.fillna("").astype(str).str.strip()
        df_out[col] = _ser_str.where(~_ser_str.str.lower().isin(_bad_vals_lower), "")
    return df_out


def _tao_ket_qua_block_trung_cheo_hstd(
    df_hstd: pd.DataFrame,
    *,
    pham_vi: str,
    action_audit: str,
    giu_nguyen_cache: bool = True,
) -> KetQuaUpload | None:
    """Trả về KetQuaUpload lỗi nếu phát hiện khoản vay HSTD bị trùng chéo giữa PGD."""
    from services.validation_service import validate_hstd_cross_pgd_duplicates

    report = validate_hstd_cross_pgd_duplicates(df_hstd)
    if report.is_valid:
        return None

    report_dict = asdict(report)
    thong_bao = _tom_tat_trung_cheo_hstd(report_dict, pham_vi, giu_nguyen_cache)
    username = st.session_state.get("username", "unknown")
    db.ghi_audit(
        username,
        action_audit,
        f"{pham_vi} — trung_cheo={report.duplicate_group_count} mon "
        f"| cap_nhom={report.duplicate_pair_count} "
        f"| uoc_thua={_fmt_ty_inline(report.estimated_excess_amount)}",
    )
    logger.warning(
        "block merge HSTD do trùng chéo liên PGD: %s | groups=%d | pairs=%d | excess=%s",
        pham_vi,
        report.duplicate_group_count,
        report.duplicate_pair_count,
        _fmt_ty_inline(report.estimated_excess_amount),
    )
    return KetQuaUpload(
        False,
        thong_bao,
        chi_tiet={
            "kind": "hstd_cross_pgd_duplicates",
            "scope": pham_vi,
            "report": report_dict,
        },
    )


def _kiem_tra_tai_chinh_hstd(df: "pd.DataFrame", report: dict) -> dict:
    """Kiểm tra logic tài chính cho HSTD — thêm cảnh báo vào report."""
    from config import COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH, COT_MA_KH

    warnings: list[str] = []
    critical: list[str] = []
    tong_dong = len(df)
    if tong_dong == 0:
        return report

    # Kiểm tra dư nợ âm (CRITICAL nếu > 5% rows)
    if COT_TONG_DU_NO in df.columns:
        du_no = pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce")
        so_am = int((du_no < 0).sum())
        if so_am > 0:
            pct_am = so_am / tong_dong * 100
            msg = f"Dư nợ âm: {so_am} dòng ({pct_am:.1f}%)"
            if pct_am >= 5:
                critical.append(msg)
            else:
                warnings.append(msg)

    # Kiểm tra cân bằng: Tổng dư nợ ≈ TH + QH + Khoanh (cảnh báo nếu lệch > 1K)
    cols_can_bang = [COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH]
    if all(c in df.columns for c in cols_can_bang):
        tong = pd.to_numeric(df[COT_TONG_DU_NO], errors="coerce").fillna(0)
        phan_chia = (
            pd.to_numeric(df[COT_DU_NO_TH], errors="coerce").fillna(0)
            + pd.to_numeric(df[COT_DU_NO_QH], errors="coerce").fillna(0)
            + pd.to_numeric(df[COT_DU_NO_KHOANH], errors="coerce").fillna(0)
        )
        lech = int((abs(tong - phan_chia) > 1000).sum())
        if lech > 0:
            warnings.append(f"Tổng dư nợ lệch TH+QH+Khoanh: {lech} dòng")

    # Kiểm tra mã KH format (INFO)
    if COT_MA_KH in df.columns:
        import re
        ma_kh = df[COT_MA_KH].dropna().astype(str)
        so_sai_format = int((~ma_kh.str.match(r"^\d{8,12}$")).sum())
        if so_sai_format > 0:
            warnings.append(f"Mã KH không đúng định dạng (8-12 chữ số): {so_sai_format} dòng")

    updated = dict(report)
    if critical:
        updated["canh_bao_critical"] = critical
        updated["co_loi_critical"] = True
    if warnings:
        updated["canh_bao_tai_chinh"] = warnings
    return updated


def danh_gia_chat_luong_file_upload(loai: str, file_bytes: bytes) -> tuple[bool, str, dict]:
    """
    Đánh giá nhanh chất lượng dữ liệu ngay tại bước upload.
    Trả về (hop_le, thong_bao, bao_cao).
    Với HSTD: bổ sung kiểm tra tài chính (dư nợ âm, cân bằng, mã KH).
    """
    try:
        buf = BytesIO(file_bytes)
        if loai in ("hstd", "nq11"):
            df = pd.read_excel(buf, sheet_name="BCQUERY", header=4)
            df = df.iloc[:, 1:].dropna(how="all")
        elif loai == "gqvl":
            df = pd.read_excel(buf, sheet_name="Sheet1", header=7)
            df = df.iloc[:, 1:].dropna(how="all").iloc[1:]
            df = df.rename(columns=GQVL_COT_MAP).reset_index(drop=True)
        else:
            return True, "Không áp dụng Data Quality cho loại này.", {}

        kq = kiem_tra_chat_luong(df, loai)
        report = kq.report

        # Bổ sung kiểm tra tài chính cho HSTD
        if loai == "hstd":
            report = _kiem_tra_tai_chinh_hstd(df, report)

        if report.get("co_loi_critical"):
            loi_str = "; ".join(report.get("canh_bao_critical", []))
            return False, f"❌ Lỗi nghiêm trọng — {loi_str}", report

        if report["so_loi"] == 0 and not report.get("canh_bao_tai_chinh"):
            return True, "Dữ liệu đạt chuẩn kiểm tra nhanh.", report

        msgs = []
        if report["so_loi"] > 0:
            msgs.append(f"{report['so_loi']} nhóm lỗi cấu trúc")
        if report.get("canh_bao_tai_chinh"):
            msgs.append("; ".join(report["canh_bao_tai_chinh"]))
        return False, "⚠️ " + " · ".join(msgs), report
    except Exception as e:
        logger.error("danh_gia_chat_luong_file_upload: không đọc được file %s — %s", loai, e, exc_info=True)
        return False, f"Không thể đọc file để đánh giá chất lượng: {e}", {}


# ── Kiểm tra file ─────────────────────────────────────────────────────────────

def kiem_tra_file(
    ten_file: str,
    file_bytes: bytes,
    exts_chophep: set[str] | None = None,
    kich_thuoc_toi_thieu: int = KICH_THUOC_TOI_THIEU,
) -> tuple[bool, str]:
    """
    Kiểm tra cơ bản cho mọi loại upload: định dạng + kích thước tối thiểu.
    Trả về (ok: bool, thong_bao: str).
    """
    if exts_chophep is None:
        exts_chophep = EXTS_CHOPHEP

    ext = Path(ten_file).suffix
    if ext not in exts_chophep:
        return False, f"Định dạng '{ext}' không được hỗ trợ. Chỉ chấp nhận .xlsx / .xls"

    if len(file_bytes) < kich_thuoc_toi_thieu:
        return False, "File quá nhỏ — có thể bị lỗi hoặc rỗng (< 1 KB)."

    return True, "OK"


def kiem_tra_file_he_thong(ten_file: str, file_bytes: bytes) -> tuple[bool, str]:
    """
    Kiểm tra file hệ thống: định dạng + tên file phải khớp FILES_HE_THONG + kích thước.
    Dùng cho tab Quản trị — upload file HSTD, NQ11.
    """
    ok, msg = kiem_tra_file(ten_file, file_bytes)
    if not ok:
        return False, msg

    if ten_file not in FILES_HE_THONG:
        ds_ten = "\n".join(f"• {k}" for k in FILES_HE_THONG)
        return False, (
            f"Tên file '**{ten_file}**' không hợp lệ.\n"
            f"Tên file phải là một trong:\n{ds_ten}"
        )

    return True, "OK"


# ── Ghi file nội bộ ───────────────────────────────────────────────────────────

def _noi_dung_file_khop(duong_dan: Path, file_bytes: bytes) -> bool:
    """So sánh theo SHA-256 mà không nạp thêm toàn bộ file đĩa vào RAM."""
    try:
        if not duong_dan.is_file() or duong_dan.stat().st_size != len(file_bytes):
            return False
        digest = hashlib.sha256()
        with duong_dan.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.digest() == hashlib.sha256(file_bytes).digest()
    except OSError:
        return False


def _ghi_va_xoa_cache(
    duong_dan: str,
    file_bytes: bytes,
    duong_dan_cache: str | None = None,
) -> None:
    """
    Ghi bytes nguyên tử ra đĩa, xóa file cache liên quan nếu tồn tại.
    Hàm nội bộ — không gọi trực tiếp từ ngoài module.
    Retry bước replace trên Windows khi file bị khóa tạm thời.
    """
    target = Path(duong_dan).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    with _FILE_WRITE_LOCK:
        # Uploader có thể rerun với cùng payload; không mở lại file đích.
        if not _noi_dung_file_khop(target, file_bytes):
            temp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=target.parent,
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temp_file:
                    temp_file.write(file_bytes)
                    temp_path = Path(temp_file.name)

                for attempt in range(5):
                    try:
                        os.replace(temp_path, target)
                        temp_path = None
                        break
                    except OSError:
                        # Process/session khác có thể vừa ghi cùng payload.
                        if _noi_dung_file_khop(target, file_bytes):
                            break
                        if attempt == 4:
                            raise
                        time.sleep(0.3 * (attempt + 1))
            finally:
                if temp_path is not None:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        logger.warning(
                            "Không xóa được file upload tạm: %s",
                            temp_path,
                            exc_info=True,
                        )

    if duong_dan_cache and Path(duong_dan_cache).exists():
        os.remove(duong_dan_cache)


# ── Lưu file hệ thống (tab Quản trị) ─────────────────────────────────────────

def luu_file_he_thong(ten_file: str, file_bytes: bytes) -> KetQuaUpload:
    """
    Lưu file hệ thống (HSTD / NQ11) vào data/ và xóa cache.
    Dùng cho tab Quản trị khi upload nhiều file cùng lúc.
    """
    ok, msg = kiem_tra_file_he_thong(ten_file, file_bytes)
    if not ok:
        return KetQuaUpload(False, msg)

    info = FILES_HE_THONG[ten_file]
    _ghi_va_xoa_cache(info["path"], file_bytes, info.get("cache"))

    mb = len(file_bytes) / 1024 / 1024
    username = st.session_state.get("username", "unknown")
    db.ghi_audit(username, "upload_he_thong",
                 f"{ten_file} ({mb:.1f} MB)")
    return KetQuaUpload(
        True,
        f"✅ Đã lưu **{ten_file}** ({mb:.1f} MB) — cache đã xóa, dữ liệu mới nhất!",
        info["path"],
    )


# ── Lưu file Điện báo (tab Cân đối) ──────────────────────────────────────────


def trich_xuat_ky_dienbao(ten_file: str) -> str | None:
    """Trích ngày từ tên file Điện báo → 'DD/MM/YYYY' hoặc None.

    Hỗ trợ: '31.07.2026', '31-07-2026', '31_07_2026', '31072026'.
    """
    if not ten_file:
        return None
    # Dạng có dấu phân cách: 31.07.2026 / 31-07-2026 / 31_07_2026
    m = re.search(r"(\d{1,2})[.\-_](\d{1,2})[.\-_](\d{4})", ten_file)
    if m:
        ng, th, nam = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= ng <= 31 and 1 <= th <= 12:
            return f"{ng:02d}/{th:02d}/{nam}"
    # Dạng liền: 31072026
    m = re.search(r"(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)", ten_file)
    if m:
        ng, th, nam = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= ng <= 31 and 1 <= th <= 12:
            return f"{ng:02d}/{th:02d}/{nam}"
    return None


def luu_dienbao(
    loai: str,
    file_bytes: bytes,
    ten_file_goc: str | None = None,
    ten_pgd: str | None = None,
) -> KetQuaUpload:
    """
    Lưu file Điện báo: toàn CN (cache/) hoặc theo PGD (pgd_data/{slug}/).
    loai: "ht"   → Điện báo hiện tại
          "prev" → Điện báo 31/12 năm trước
    ten_pgd: None → DB_HT_CACHE / DB_PREV_CACHE (toàn CN)
             có giá trị → duong_dan_pgd(..., "dienbao_ht" | "dienbao_prev")
    ten_file_goc: tên file người dùng chọn (để audit), tùy chọn.
    """
    if loai == "ht":
        ten_hien = "Điện báo hiện tại"
        duong_dan = (
            duong_dan_pgd(ten_pgd, "dienbao_ht")
            if ten_pgd
            else DB_HT_CACHE
        )
    elif loai == "prev":
        ten_hien = "Điện báo 31/12 năm trước"
        duong_dan = (
            duong_dan_pgd(ten_pgd, "dienbao_prev")
            if ten_pgd
            else DB_PREV_CACHE
        )
    elif loai == "prev_month":
        ten_hien = "Điện báo tháng trước"
        duong_dan = (
            duong_dan_pgd(ten_pgd, "dienbao_prev_month")
            if ten_pgd
            else DB_PREV_MONTH_CACHE
        )
    else:
        return KetQuaUpload(False, f"Loại Điện báo không hợp lệ: '{loai}'")

    ok, msg = kiem_tra_file(ten_hien + ".xlsx", file_bytes)
    if not ok:
        return KetQuaUpload(False, msg)

    # Kiểm tra cấu trúc nội dung file điện báo
    try:
        df_check = pd.read_excel(BytesIO(file_bytes), header=None)

        # File phải có ít nhất 3 cột (STT, Tên chỉ tiêu, Giá trị)
        if len(df_check.columns) < 3:
            return KetQuaUpload(
                False,
                f"❌ File {ten_hien} sai cấu trúc: cần ít nhất 3 cột "
                f"(hiện có {len(df_check.columns)} cột). "
                f"Vui lòng tải file mẫu từ: Báo cáo nhanh → Báo cáo theo công thức → Điện báo ngày → Chọn tick tất cả",
            )

        # Cột giá trị (iloc[2]) phải có ít nhất 1 số hợp lệ
        col_gia_tri = pd.to_numeric(df_check.iloc[:, 2], errors="coerce")
        if col_gia_tri.dropna().empty:
            return KetQuaUpload(
                False,
                f"❌ File {ten_hien} không có số liệu hợp lệ ở cột 3. "
                f"Kiểm tra lại định dạng file mẫu.",
            )

        # ── Phát hiện format ma trận (nhiều cột PGD) ──
        is_matrix = False
        if len(df_check.columns) >= 5 and len(df_check) >= 5:
            v_header = str(df_check.iloc[4, 2]).strip().lower() if pd.notna(df_check.iloc[4, 2]) else ""
            if "cộng" in v_header or "tong" in v_header:
                is_matrix = True

        # Kiểm tra số sheet nếu là file có sheet
        try:
            xls = pd.ExcelFile(BytesIO(file_bytes))
            n_sheets = len(xls.sheet_names)
        except Exception:
            n_sheets = 1

        # Đếm số chỉ tiêu và đơn vị
        n_chi_tieu = 0
        n_don_vi = 0
        skip_kw = ("", "nan", "chỉ tiêu", "điện báo ngày", "stt", "b.", "a.")
        for i in range(5, len(df_check)):
            ten = str(df_check.iloc[i, 1]).strip() if pd.notna(df_check.iloc[i, 1]) else ""
            if ten and ten.lower() not in skip_kw and ten.lower() not in ("i", "ii", "iii"):
                n_chi_tieu += 1

        if is_matrix:
            for j in range(3, len(df_check.columns)):
                if pd.notna(df_check.iloc[4, j]) and str(df_check.iloc[4, j]).strip().lower() != "nan":
                    n_don_vi += 1

    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        return KetQuaUpload(False, f"❌ Không đọc được file {ten_hien}: {e}")

    _ghi_va_xoa_cache(duong_dan, file_bytes)
    username = st.session_state.get("username", "unknown")
    hostname = socket.gethostname()
    ten = ten_file_goc or "(không tên)"
    chi_tiet = (
        f"[{hostname}] loai={loai} file={ten} "
        f"sheets={n_sheets} chi_tieu={n_chi_tieu}"
    )
    if is_matrix:
        chi_tiet += f" dv={n_don_vi} format=matrix"
    if ten_pgd:
        chi_tiet += f" pgd={ten_pgd}"
    db.ghi_audit(username, "upload_dienbao", chi_tiet)

    # ── Ghi metadata upload vào kv_store (mục B) ──
    try:
        from data.pgd import pgd_slug as _slug_fn
        _key_sfx = f"_{_slug_fn(ten_pgd)}" if ten_pgd else ""
    except Exception:
        _key_sfx = ""
    ky_tu_file = trich_xuat_ky_dienbao(ten_file_goc or "")
    _meta_key = f"dienbao_meta_{loai}{_key_sfx}"
    _meta_value = {
        "ky": ky_tu_file or "",
        "ten_file": ten_file_goc or "",
        "ngay_upload": datetime.now().isoformat(),
        "n_sheets": n_sheets,
        "n_chi_tieu": n_chi_tieu,
        "is_matrix": is_matrix,
        "n_don_vi": n_don_vi if is_matrix else 0,
    }
    db.ghi_kv(_meta_key, _meta_value, username)
    db.ghi_audit(username, "dienbao_meta", f"{_meta_key} file={ten}")

    # Thông báo kết quả kèm kỳ số liệu phát hiện
    ky_note = (
        f" · 📅 Kỳ số liệu: **{ky_tu_file}** (từ tên file)"
        if ky_tu_file
        else " · ⚠️ Không phát hiện kỳ số liệu từ tên file — vui lòng chọn ngày bên dưới"
    )
    return KetQuaUpload(
        True,
        f"✅ Đã lưu file {ten_hien} ({n_sheets} sheet, {n_chi_tieu} chỉ tiêu"
        + (f", {n_don_vi} đơn vị" if is_matrix else "")
        + f"){ky_note}",
        duong_dan,
    )


# ── Upload CDTOTKVV toàn Chi nhánh (1 file tổng hợp → tách 22 PGD) ──────────

def xu_ly_cdto_toan_cn(file_bytes: bytes) -> dict[str, "KetQuaUpload"]:
    """
    Tách file CDTOTKVV toàn CN và lưu cho từng PGD.
    Trả về {ten_pgd: KetQuaUpload}.
    Caller phải ghi audit sau khi nhận kết quả.
    """
    from data.cdtotkvv import (
        tach_file_cdto_toan_cn,
        doc_thang_tu_cdto_toan_cn,
        doc_thang_nam_tu_file,
    )
    from data.pgd import luu_file_pgd_voi_lich_su, luu_file_pgd

    try:
        pgd_map = tach_file_cdto_toan_cn(file_bytes)
    except Exception as e:
        logger.error("xu_ly_cdto_toan_cn: lỗi đọc/tách file — %s", e, exc_info=True)
        return {"_loi_doc": KetQuaUpload(False, f"Lỗi đọc/tách file: {e}")}

    if not pgd_map:
        return {"_loi_doc": KetQuaUpload(False, "Không tìm thấy dữ liệu đơn vị nào trong file")}

    # Thống nhất tháng theo NGÀY CHỐT SỐ LIỆU (NGAYBC, cột S) — khớp với luồng
    # upload từng PGD. Tiêu đề file có thể ghi kỳ báo cáo / ngày xuất khác tháng.
    thang = doc_thang_tu_cdto_toan_cn(file_bytes) or doc_thang_nam_tu_file(file_bytes)
    ket_qua: dict[str, KetQuaUpload] = {}

    for ten_pgd, pgd_bytes in pgd_map.items():
        mb = len(pgd_bytes) / 1024 / 1024
        try:
            if thang:
                luu_file_pgd_voi_lich_su(
                    ten_pgd,
                    "cdtotkvv",
                    pgd_bytes,
                    thang,
                    ghi_de_lich_su=True,
                )
                msg = f"✅ Lưu OK · tháng {thang} · {mb:.1f} MB"
            else:
                luu_file_pgd(ten_pgd, "cdtotkvv", pgd_bytes)
                msg = f"✅ Lưu OK · {mb:.1f} MB"
            ket_qua[ten_pgd] = KetQuaUpload(True, msg)
        except Exception as e:
            logger.error("xu_ly_cdto_toan_cn: lỗi lưu PGD %s — %s", ten_pgd, e, exc_info=True)
            ket_qua[ten_pgd] = KetQuaUpload(False, f"❌ Lỗi: {e}")

    return ket_qua


# ── Tách file NQ11 / GQVL toàn CN → lưu riêng từng PGD ──────────────────────

def tach_file_nq11_toan_cn(file_bytes: bytes) -> dict[str, bytes]:
    """
    Tách file NQ11 toàn CN thành dict {ten_pgd: excel_bytes}.

    NQ11 có cột "Tên PGD" → groupby trực tiếp.
    Mỗi file con là 1 sheet BCQUERY với header dòng 4.
    Raises ValueError nếu không tìm thấy PGD hợp lệ.
    """
    from io import BytesIO
    from config import COT_TEN_PGD as _COT_PGD

    df = pd.read_excel(BytesIO(file_bytes), sheet_name="BCQUERY", header=4, engine="openpyxl")
    # Bỏ cột đầu tiên (BoQua)
    df = df.iloc[:, 1:].dropna(how="all").reset_index(drop=True)

    # Lọc các dòng có dữ liệu
    if _COT_PGD not in df.columns:
        raise ValueError("File NQ11 toàn CN không có cột 'Tên PGD'. Kiểm tra lại file.")

    df[_COT_PGD] = df[_COT_PGD].astype(str).str.strip()
    ds_tat_ca = [DON_VI_CHI_NHANH] + DS_PGD

    pgd_map: dict[str, bytes] = {}
    for ten_pgd, group in df.groupby(_COT_PGD):
        if ten_pgd not in ds_tat_ca:
            continue
        bio = BytesIO()
        # Tạo lại cấu trúc: cột BoQua rỗng + dữ liệu, ghi từ dòng 4
        out_df = group.copy()
        out_df.insert(0, "BoQua", "x")
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            out_df.to_excel(writer, sheet_name="BCQUERY", startrow=4, index=False)
        pgd_map[ten_pgd] = bio.getvalue()

    if not pgd_map:
        raise ValueError("Không tìm thấy dữ liệu của đơn vị nào trong file NQ11 toàn CN.")
    return pgd_map


def tach_file_gqvl_toan_cn(
    file_bytes: bytes,
    df_hstd: pd.DataFrame | None = None,
) -> dict[str, bytes]:
    """
    Tách file GQVL toàn CN thành dict {ten_pgd: excel_bytes}.

    GQVL không có cột Tên PGD → join với HSTD qua Số khế ước để lấy Tên PGD.
    Nếu không có df_hstd → trả về dict 1 key DON_VI_CHI_NHANH (toàn bộ dữ liệu).
    Raises ValueError nếu không đọc được file.
    """
    from io import BytesIO
    from config import COT_SO_KU, COT_TEN_PGD as _COT_PGD

    df = pd.read_excel(BytesIO(file_bytes), sheet_name="Sheet1", header=7, engine="openpyxl")
    df = df.iloc[:, 1:].dropna(how="all").iloc[1:].reset_index(drop=True)
    df = df.rename(columns=GQVL_COT_MAP)

    if df.empty:
        raise ValueError("File GQVL toàn CN trống hoặc không đúng định dạng.")

    # Gán Tên PGD: mặc định là Hội sở, join với HSTD nếu có
    df["_TEN_PGD_TMP"] = DON_VI_CHI_NHANH
    if df_hstd is not None and not df_hstd.empty and COT_SO_KU in df.columns and COT_SO_KU in df_hstd.columns:
        pgd_lookup = (
            df_hstd[[COT_SO_KU, _COT_PGD]]
            .drop_duplicates(subset=COT_SO_KU)
            .set_index(COT_SO_KU)[_COT_PGD]
        )
        df["_TEN_PGD_TMP"] = df[COT_SO_KU].map(pgd_lookup).fillna(DON_VI_CHI_NHANH)

    ds_tat_ca = [DON_VI_CHI_NHANH] + DS_PGD
    pgd_map: dict[str, bytes] = {}
    for ten_pgd, group in df.groupby("_TEN_PGD_TMP", sort=False):
        if ten_pgd not in ds_tat_ca:
            continue
        out_df = group.drop(columns=["_TEN_PGD_TMP"])
        out_df.insert(0, "BoQua", "x")
        # Chèn 1 dòng placeholder trước dữ liệu thật.
        # Lý do: _doc_mot_pgd._clean dùng .iloc[1:] để bỏ qua dòng đầu tiên
        # sau header (đây là dòng tổng/khoảng trống trong file gốc của từng PGD).
        # Vì tach_file đã loại bỏ dòng đó khi đọc, ta phải chèn placeholder
        # để .iloc[1:] bỏ qua đúng chỗ, không mất dòng dữ liệu thật.
        placeholder = pd.DataFrame([[None] * len(out_df.columns)], columns=out_df.columns)
        placeholder.iloc[0, 1] = "_"  # cột 1 (không phải BoQua) có giá trị → qua dropna(how="all")
        out_df = pd.concat([placeholder, out_df], ignore_index=True)
        bio = BytesIO()
        with pd.ExcelWriter(bio, engine="openpyxl") as writer:
            out_df.to_excel(writer, sheet_name="Sheet1", startrow=7, index=False)
        pgd_map[ten_pgd] = bio.getvalue()

    if not pgd_map:
        raise ValueError("Không tìm thấy dữ liệu của đơn vị nào trong file GQVL toàn CN.")
    return pgd_map


def xu_ly_nq11_toan_cn(file_bytes: bytes) -> dict[str, "KetQuaUpload"]:
    """
    Tách file NQ11 toàn CN và lưu cho từng PGD.
    Trả về {ten_pgd: KetQuaUpload}.
    """
    from data.pgd import luu_file_pgd

    try:
        pgd_map = tach_file_nq11_toan_cn(file_bytes)
    except Exception as e:  # conv: skip — trả về KetQuaUpload thay vì raise
        return {"_loi_doc": KetQuaUpload(False, f"Lỗi đọc/tách file NQ11: {e}")}

    ket_qua: dict[str, KetQuaUpload] = {}
    for ten_pgd, pgd_bytes in pgd_map.items():
        mb = len(pgd_bytes) / 1024 / 1024
        try:
            luu_file_pgd(ten_pgd, "nq11", pgd_bytes)
            ket_qua[ten_pgd] = KetQuaUpload(True, f"✅ Lưu OK · {mb:.1f} MB")
        except Exception as e:  # conv: skip
            ket_qua[ten_pgd] = KetQuaUpload(False, f"❌ Lỗi: {e}")

    return ket_qua


def xu_ly_gqvl_toan_cn(
    file_bytes: bytes,
    df_hstd: pd.DataFrame | None = None,
) -> dict[str, "KetQuaUpload"]:
    """
    Tách file GQVL toàn CN và lưu cho từng PGD.
    Trả về {ten_pgd: KetQuaUpload}.
    """
    from data.pgd import luu_file_pgd

    try:
        pgd_map = tach_file_gqvl_toan_cn(file_bytes, df_hstd=df_hstd)
    except Exception as e:  # conv: skip — trả về KetQuaUpload thay vì raise
        return {"_loi_doc": KetQuaUpload(False, f"Lỗi đọc/tách file GQVL: {e}")}

    ket_qua: dict[str, KetQuaUpload] = {}
    for ten_pgd, pgd_bytes in pgd_map.items():
        mb = len(pgd_bytes) / 1024 / 1024
        try:
            luu_file_pgd(ten_pgd, "gqvl", pgd_bytes)
            ket_qua[ten_pgd] = KetQuaUpload(True, f"✅ Lưu OK · {mb:.1f} MB")
        except Exception as e:  # conv: skip
            ket_qua[ten_pgd] = KetQuaUpload(False, f"❌ Lỗi: {e}")

    return ket_qua


# ── Gộp dữ liệu toàn Chi nhánh từ 22 đơn vị ─────────────────────────────────


def _path_merge_pgd(ten_pgd: str, loai: str) -> str:
    """
    Trả về đường dẫn file nguồn cho merge.
    HSTD: ưu tiên hstd_khnv.xlsx (Phòng KH-NV) → fallback hstd_latest.xlsx.
    """
    if loai == "hstd":
        path_khnv = duong_dan_pgd(ten_pgd, "hstd_khnv")
        if Path(path_khnv).exists():
            return path_khnv
    return duong_dan_pgd(ten_pgd, loai)


def _doc_excel_pgd_thanh_df(path_excel: str, loai: str) -> pd.DataFrame:
    """Đọc Excel PGD → DataFrame, dùng cache parquet per-PGD nếu còn mới."""
    path_pq = str(Path(path_excel).with_suffix(".parquet"))
    if loai in ("hstd", "nq11"):
        def _clean(df: pd.DataFrame) -> pd.DataFrame:
            return df.iloc[:, 1:].dropna(how="all")

        return excel_to_parquet(
            path_excel,
            path_pq,
            sheet="BCQUERY",
            header=4,
            post_fn=_clean,
        )

    def _clean_gqvl(df: pd.DataFrame) -> pd.DataFrame:
        d = df.iloc[:, 1:].dropna(how="all").iloc[1:]
        d = d.rename(columns=GQVL_COT_MAP).reset_index(drop=True)
        _cols_so = [
            COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH,
            "Tổng giải ngân", COT_GIAI_NGAN_TRONG_NAM, "Dư tài khoản",
            COT_THOI_HAN,
        ]
        for col in _cols_so:
            if col in d.columns:
                d[col] = pd.to_numeric(d[col], errors="coerce")
        return d

    return excel_to_parquet(
        path_excel,
        path_pq,
        sheet="Sheet1",
        header=7,
        post_fn=_clean_gqvl,
    )


def prewarm_pgd_parquet(ten_pgd: str, loai: str) -> bool:
    """
    Tạo sẵn parquet per-PGD sau khi lưu Excel.
    Merge toàn CN sau đó đọc parquet (~200x nhanh hơn đọc Excel).
    """
    if loai not in ("hstd", "nq11", "gqvl"):
        return False
    path_excel = _path_merge_pgd(ten_pgd, loai)
    if not Path(path_excel).exists():
        return False
    try:
        _doc_excel_pgd_thanh_df(path_excel, loai)
        return True
    except Exception as e:
        logger.warning(
            "prewarm_pgd_parquet: lỗi %s/%s — %s", ten_pgd, loai, e, exc_info=True
        )
        return False


def merge_nhieu_loai_toan_cn(loai_list: list[str]) -> list[dict]:
    """
    Merge nhiều loại (hstd/nq11/gqvl).
    Chạy tuần tự — merge_du_lieu_toan_cn() dùng st.progress/session_state,
    không an toàn khi gọi từ worker thread.
    """
    if not loai_list:
        return []

    ket_qua: list[dict] = []
    for loai in loai_list:
        try:
            kq = merge_du_lieu_toan_cn(loai)
            meta = lay_meta_merge(loai) if kq.thanh_cong else None
            ket_qua.append({
                "loai": loai,
                "thanh_cong": kq.thanh_cong,
                "thong_bao": kq.thong_bao,
                "so_pgd": (meta or {}).get("so_pgd"),
                "so_dong": (meta or {}).get("so_dong"),
                "chi_tiet": kq.chi_tiet,
            })
        except Exception as e:
            logger.error("merge_nhieu_loai_toan_cn: merge %s lỗi — %s", loai, e, exc_info=True)
            ket_qua.append({
                "loai": loai,
                "thanh_cong": False,
                "thong_bao": f"Lỗi tổng hợp: {e}",
                "so_pgd": None,
                "so_dong": None,
            })
    return ket_qua


def merge_du_lieu_toan_cn(
    loai: str,
    ds_pgd: list[str] | None = None,
    pgd_moi_upload: str | None = None,
) -> KetQuaUpload:
    """
    Gộp file {loai} của tất cả 22 đơn vị thành dữ liệu toàn Chi nhánh.
    Đọc pgd_data/{slug}/{loai}_latest.xlsx → concat → ghi ra parquet cache.

    loai: "hstd" | "nq11" | "gqvl"
    Không áp dụng cho "cdtotkvv".
    """
    if loai not in ("hstd", "nq11", "gqvl"):
        return KetQuaUpload(False, f"merge_du_lieu_toan_cn không hỗ trợ loai='{loai}'")

    lock = _MERGE_LOCK[loai]
    if not lock.acquire(blocking=False):
        logger.warning("merge_du_lieu_toan_cn: loai=%s đang được merge bởi session khác — bỏ qua", loai)
        return KetQuaUpload(False, f"⏳ Hệ thống đang merge {loai.upper()} — vui lòng chờ vài giây rồi thử lại.")

    try:
        return _merge_du_lieu_toan_cn_impl(loai, ds_pgd, pgd_moi_upload)
    finally:
        lock.release()


def _merge_du_lieu_toan_cn_impl(
    loai: str,
    ds_pgd: list[str] | None = None,
    pgd_moi_upload: str | None = None,
) -> KetQuaUpload:
    """Thực thi merge — chỉ gọi qua merge_du_lieu_toan_cn() đã giữ lock."""
    tat_ca_dv = ds_pgd if ds_pgd is not None else ([DON_VI_CHI_NHANH] + DS_PGD)
    if not tat_ca_dv:
        return KetQuaUpload(False, f"Không có đơn vị nào để gộp {loai.upper()}.")
    logger.info("merge_du_lieu_toan_cn: bắt đầu loai=%s, %d đơn vị", loai, len(tat_ca_dv))
    frames: list[pd.DataFrame] = []
    pgd_da_merge: list[str] = []
    pgd_cu: list[str] = []       # đơn vị dùng số liệu cũ (quá ngưỡng)
    pgd_loi: list[str] = []
    bao_cao_chat_luong: list[dict] = []

    nguong_ngay = UPLOAD_CANH_BAO_NGAY.get(loai, 3)

    _u = st.session_state.get("username", "unknown")

    meta_map: dict[str, tuple[bool, bool]] = {}
    for ten_pgd in tat_ca_dv:
        path_excel = _path_merge_pgd(ten_pgd, loai)
        if not Path(path_excel).exists():
            meta_map[ten_pgd] = (False, False)
            continue
        path_pq = Path(path_excel).with_suffix(".parquet")
        da_dung_cache = (
            path_pq.exists()
            and ts_file(str(path_pq)) >= ts_file(path_excel)
        )
        so_ngay_cu = (
            datetime.now()
            - datetime.fromtimestamp(os.path.getmtime(path_excel))
        ).days
        qua_nguong = so_ngay_cu > nguong_ngay
        meta_map[ten_pgd] = (da_dung_cache, qua_nguong)

    def _doc_mot_pgd(
        ten_pgd: str, loai: str
    ) -> tuple[str, pd.DataFrame | None, str | None]:
        """Trả về (ten_pgd, df | None, canh_bao_str | None)."""
        path_excel = _path_merge_pgd(ten_pgd, loai)
        if not Path(path_excel).exists():
            return ten_pgd, None, None
        try:
            df = _doc_excel_pgd_thanh_df(path_excel, loai)
            df[COT_TEN_PGD] = ten_pgd
            return ten_pgd, df, None
        except Exception as e:
            logger.error("merge_du_lieu_toan_cn: lỗi đọc file PGD %s/%s — %s", ten_pgd, loai, e, exc_info=True)
            return ten_pgd, None, str(e)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    raw_results: list[tuple[str, pd.DataFrame, bool, bool]] = []
    tong = len(tat_ca_dv)

    _start_iso = datetime.now().isoformat()
    db.ghi_kv("_merge_progress", {
        "loai": loai, "total": tong, "done": 0,
        "running": True, "start": _start_iso,
    }, _u)

    prog = st.progress(0, text=f"⏳ Đang đọc 0/{tong} PGD...")
    da_xong = 0
    try:
        with ThreadPoolExecutor(max_workers=min(len(tat_ca_dv), 12)) as ex:
            futures = {ex.submit(_doc_mot_pgd, dv, loai): dv for dv in tat_ca_dv}
            for future in as_completed(futures):
                da_xong += 1
                prog.progress(min(1.0, da_xong / max(tong, 1)), text=f"⏳ Đang đọc {da_xong}/{tong} PGD...")
                ten_pgd, df, canh_bao_str = future.result()
                if canh_bao_str:
                    pgd_loi.append(f"{ten_pgd}: {canh_bao_str}")
                    logger.warning("merge_du_lieu_toan_cn: PGD lỗi đọc file — %s: %s", ten_pgd, canh_bao_str)
                    db.ghi_audit(
                        _u,
                        "merge_toan_cn_pgd_loi",
                        f"{loai.upper()} — {ten_pgd} — {canh_bao_str}",
                    )
                    continue
                if df is None:
                    continue
                da_dung_cache, qua_nguong = meta_map.get(ten_pgd, (False, False))
                raw_results.append((ten_pgd, df, da_dung_cache, qua_nguong))
    finally:
        prog.empty()
        db.ghi_kv("_merge_progress", {
            "loai": loai, "total": tong, "done": da_xong,
            "running": False, "start": _start_iso, "end": datetime.now().isoformat(),
        }, _u)

    # Kiểm tra chất lượng sau khi tất cả luồng đọc file đã hoàn thành
    for ten_pgd, df, da_dung_cache, qua_nguong in raw_results:
        if (not da_dung_cache) and (pgd_moi_upload is not None) and (ten_pgd == pgd_moi_upload):
            kq_dq = kiem_tra_chat_luong(df, loai)
            df = kq_dq.df
            bao_cao_chat_luong.append({**kq_dq.report, "don_vi": ten_pgd})
        frames.append(df)
        pgd_da_merge.append(ten_pgd)
        if qua_nguong:
            pgd_cu.append(ten_pgd)

    if pgd_cu:
        logger.warning("merge_du_lieu_toan_cn: %d PGD dùng số liệu cũ — %s", len(pgd_cu), ", ".join(pgd_cu))

    if not frames:
        logger.warning("merge_du_lieu_toan_cn: không có frames nào để gộp, loai=%s", loai)
        return KetQuaUpload(
            False,
            f"Không có đơn vị nào có file {loai.upper()} để gộp."
        )

    # ── Chuẩn hóa schema: tránh DataType(null) khi các PGD
    #    có cột toàn null hoặc thiếu cột ──────────────────────
    # reindex() nhanh hơn for-loop lồng O(22×N_cols) — pandas tối ưu hoá nội bộ
    all_cols = list(dict.fromkeys(
        col for df in frames for col in df.columns
    ))
    frames = [df.reindex(columns=all_cols) for df in frames]

    df_toan_cn = pd.concat(frames, ignore_index=True)

    # Xác định đường dẫn parquet cache đích
    cache_map = {
        "hstd": CACHE_HSTD,
        "nq11": CACHE_NQ11,
        "gqvl": CACHE_GQVL,
    }
    cache_path = cache_map[loai]

    # Ghi trực tiếp vào parquet cache (không qua Excel)
    os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)

    df_toan_cn = _normalize_merge_dataframe_for_parquet(df_toan_cn)

    if loai == "hstd":
        kq_block = _tao_ket_qua_block_trung_cheo_hstd(
            df_toan_cn,
            pham_vi="HSTD hiện tại toàn Chi nhánh",
            action_audit="merge_toan_cn_blocked",
            giu_nguyen_cache=True,
        )
        if kq_block is not None:
            return kq_block

    with _MERGE_LOCK[loai]:
        bak_path = cache_path + ".bak"
        if os.path.exists(cache_path):
            shutil.copy2(cache_path, bak_path)
        try:
            df_toan_cn.to_parquet(cache_path, index=False, engine="pyarrow", compression="zstd", compression_level=3)
        except Exception as e:
            logger.error("merge_du_lieu_toan_cn: lỗi ghi parquet, rollback — %s", e, exc_info=True)
            _u_merge = st.session_state.get("username", "unknown")
            db.ghi_audit(_u_merge, "merge_loi_dtype",
                         f"{loai.upper()} — {str(e)[:200]}")
            if os.path.exists(bak_path):
                os.replace(bak_path, cache_path)
            raise
        if os.path.exists(bak_path):
            os.remove(bak_path)

        username = st.session_state.get("username", "unknown")

        canh_bao = f" | {len(pgd_loi)} PGD lỗi" if pgd_loi else ""
        logger.info(
            "merge_du_lieu_toan_cn: hoàn thành loai=%s, %d dòng, %d PGD%s",
            loai, len(df_toan_cn), len(pgd_da_merge), canh_bao,
        )
        db.ghi_audit(
            username,
            "merge_toan_cn",
            f"{loai.upper()} — {fmt_so(len(df_toan_cn))} dòng, {len(pgd_da_merge)} PGD{canh_bao}",
        )

        # Xác định ngày số liệu từ dữ liệu merged
        ngay_sl = ""
        if COT_NGAY_SL in df_toan_cn.columns:
            _sl = pd.to_datetime(df_toan_cn[COT_NGAY_SL], dayfirst=True, errors="coerce").dropna()
            if not _sl.empty:
                ngay_sl = _sl.max().strftime("%d/%m/%Y")

        # Ghi metadata vào kv_store để các tab phân tích hiển thị caption
        db.ghi_kv(
            f"merge_meta_{loai}",
            {
                "thoi_gian": datetime.now().isoformat(),
                "so_pgd":    len(pgd_da_merge),
                "so_dong":   len(df_toan_cn),
                "pgd_cu":    pgd_cu,
                "ngay_sl":   ngay_sl,
            },
            username,
        )
        db.ghi_kv(
            f"data_quality_meta_{loai}",
            {
                "thoi_gian": datetime.now().isoformat(),
                "bao_cao": bao_cao_chat_luong,
                "tong_so_loi": int(sum(x.get("so_loi", 0) for x in bao_cao_chat_luong)),
                "tong_dong": int(sum(x.get("tong_dong", 0) for x in bao_cao_chat_luong)),
            },
            username,
        )

        # Clear Streamlit cache để UI đọc dữ liệu mới ngay lập tức
        try:
            st.cache_data.clear()
            st.cache_resource.clear()
        except Exception:
            pass

        # Thông báo Telegram sau merge thành công
        try:
            from services.telegram_service import gui_thong_bao_merge
            gui_thong_bao_merge(loai, len(pgd_da_merge), username)
        except Exception as _tg_err:
            logger.warning("telegram merge notify: %s", _tg_err)

    # Auto-snapshot NGOÀI lock — chạy background thread để không block luồng chính
    import threading as _threading
    _snap_user = st.session_state.get("username", "system")
    _snap_cache_path = cache_path

    if loai == "hstd":
        def _snap_bg() -> None:
            df_snap = None
            try:
                from snapshot_service import (
                    _ky_tu_df as _ky_hstd,
                    luu_snapshot as _luu_snap,
                    luu_uy_thac_snapshot as _luu_uy_thac_snap,
                )
                df_snap = pd.read_parquet(_snap_cache_path, engine="pyarrow")
                _luu_snap(df_snap, _snap_user)
                _luu_uy_thac_snap(df_snap, _snap_user)
            except Exception as e:
                logger.error("auto-snapshot HSTD background thread thất bại — %s", e, exc_info=True)
            # Sau HSTD snapshot, thử lưu CDTOTKVV snapshot cùng kỳ
            try:
                from data.cdtotkvv import doc_cdtotkvv_toan_cn_pgd as _doc_cdtot
                from snapshot_service import luu_cdtotkvv_snapshot as _luu_cdtot
                if df_snap is None:
                    df_snap = pd.read_parquet(_snap_cache_path, engine="pyarrow")
                _ky_str = _ky_hstd(df_snap)
                _df_cdtot = _doc_cdtot()
                if _df_cdtot is not None and not _df_cdtot.empty:
                    _luu_cdtot(_df_cdtot, _ky_str, _snap_user)
            except Exception as e:
                logger.error("auto-snapshot CDTOTKVV background thread thất bại — %s", e, exc_info=True)
            try:
                st.cache_data.clear()
            except Exception as e:
                logger.error("auto-snapshot: không clear được cache — %s", e, exc_info=True)

        _threading.Thread(target=_snap_bg, daemon=True).start()

    elif loai == "nq11":
        def _snap_nq11_bg() -> None:
            try:
                from snapshot_service import luu_nq11_snapshot as _luu_nq11
                df_snap = pd.read_parquet(_snap_cache_path, engine="pyarrow")
                _luu_nq11(df_snap, _snap_user)
            except Exception as e:
                logger.error("auto-snapshot NQ11 background thread thất bại — %s", e, exc_info=True)

        _threading.Thread(target=_snap_nq11_bg, daemon=True).start()

    elif loai == "gqvl":
        def _snap_gqvl_bg() -> None:
            try:
                from snapshot_service import luu_gqvl_snapshot as _luu_gqvl
                df_snap = pd.read_parquet(_snap_cache_path, engine="pyarrow")
                _luu_gqvl(df_snap, _snap_user)
            except Exception as e:
                logger.error("auto-snapshot GQVL background thread thất bại — %s", e, exc_info=True)

        _threading.Thread(target=_snap_gqvl_bg, daemon=True).start()

    return KetQuaUpload(
        True,
        (
            f"✅ Đã gộp **{loai.upper()}** toàn Chi nhánh: "
            f"**{len(pgd_da_merge)}** đơn vị · **{fmt_so(len(df_toan_cn))}** dòng"
            + (f" ⚠️ {len(pgd_loi)} đơn vị lỗi" if pgd_loi else "")
            + (
                f" · DQ lỗi: {sum(x.get('so_loi', 0) for x in bao_cao_chat_luong)}"
                if bao_cao_chat_luong
                else ""
            )
        ),
        cache_path,
    )


# ── Tổng hợp baseline 31/12 toàn Chi nhánh ───────────────────────────────────

def merge_baseline_toan_cn(loai: str, nam: int) -> KetQuaUpload:
    """
    Gộp file baseline 31/12 của tất cả 22 đơn vị thành 1 parquet cache.
    Đọc data/baseline_pgd/{slug}/{LOAI}_3112_{nam}.XLSX → concat → cache.

    loai: "hstd" | "nq11" | "gqvl" | "cdtotkvv"
    """
    from config import baseline_pgd_path_loai, baseline_cache_loai
    from concurrent.futures import ThreadPoolExecutor, as_completed

    tat_ca_dv = [DON_VI_CHI_NHANH] + DS_PGD

    def _doc_mot(ten_pgd: str) -> tuple[str, pd.DataFrame | None, str | None]:
        path = baseline_pgd_path_loai(ten_pgd, nam, loai)
        if not Path(path).exists():
            return ten_pgd, None, None
        try:
            path_pq = str(Path(path).with_suffix(".parquet"))
            if loai in ("hstd", "nq11"):
                def _clean(df: pd.DataFrame) -> pd.DataFrame:
                    return df.iloc[:, 1:].dropna(how="all")
                df = excel_to_parquet(path, path_pq, sheet="BCQUERY", header=4, post_fn=_clean)
            elif loai == "gqvl":
                def _clean(df: pd.DataFrame) -> pd.DataFrame:
                    d = df.iloc[:, 1:].dropna(how="all").iloc[1:]
                    d = d.rename(columns=GQVL_COT_MAP).reset_index(drop=True)
                    for col in [COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH,
                                "Tổng giải ngân", COT_GIAI_NGAN_TRONG_NAM, COT_THOI_HAN]:
                        if col in d.columns:
                            d[col] = pd.to_numeric(d[col], errors="coerce")
                    return d
                df = excel_to_parquet(path, path_pq, sheet="Sheet1", header=7, post_fn=_clean)
            else:
                df = pd.read_excel(path, header=7)
                df = df.dropna(how="all")
            df[COT_TEN_PGD] = ten_pgd
            return ten_pgd, df, None
        except Exception as e:
            logger.error("merge_baseline_toan_cn: lỗi đọc %s/%s/%d — %s", ten_pgd, loai, nam, e, exc_info=True)
            return ten_pgd, None, str(e)

    frames: list[pd.DataFrame] = []
    da_merge: list[str] = []
    loi: list[str] = []

    tong = len(tat_ca_dv)
    prog = st.progress(0, text=f"⏳ Đang đọc baseline {loai.upper()} 31/12/{nam}...")
    da_xong = 0

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_doc_mot, dv): dv for dv in tat_ca_dv}
        for future in as_completed(futures):
            da_xong += 1
            prog.progress(
                min(1.0, da_xong / max(tong, 1)),
                text=f"⏳ Đang đọc {da_xong}/{tong} đơn vị...",
            )
            ten_pgd, df, err = future.result()
            if err:
                loi.append(f"{ten_pgd}: {err}")
            elif df is not None:
                frames.append(df)
                da_merge.append(ten_pgd)

    prog.empty()

    if not frames:
        return KetQuaUpload(
            False,
            f"❌ Không có đơn vị nào có file baseline {loai.upper()} 31/12/{nam}.",
        )

    df_all = pd.concat(frames, ignore_index=True)
    df_all = _normalize_merge_dataframe_for_parquet(df_all)

    if loai == "hstd":
        kq_block = _tao_ket_qua_block_trung_cheo_hstd(
            df_all,
            pham_vi=f"baseline HSTD 31/12/{nam}",
            action_audit="merge_baseline_blocked",
            giu_nguyen_cache=True,
        )
        if kq_block is not None:
            return kq_block

    cache_path = baseline_cache_loai(nam, loai)
    os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
    df_all.to_parquet(cache_path, index=False, engine="pyarrow", compression="zstd", compression_level=3)

    username = st.session_state.get("username", "unknown")
    db.ghi_audit(
        username,
        "merge_baseline",
        f"{loai.upper()} 31/12/{nam} — {fmt_so(len(df_all))} dòng, {len(da_merge)} đơn vị"
        + (f" | {len(loi)} lỗi" if loi else ""),
    )

    ky_baseline = f"{nam}-12"
    try:
        if loai == "nq11":
            from snapshot_service import luu_nq11_snapshot as _luu_nq11
            kq_snap = _luu_nq11(df_all, username, ky=ky_baseline)
            if kq_snap.thanh_cong:
                logger.info("merge_baseline_toan_cn: NQ11 snapshot %s OK", ky_baseline)
            else:
                logger.warning("merge_baseline_toan_cn: NQ11 snapshot lỗi — %s", kq_snap.thong_bao)
        elif loai == "gqvl":
            from snapshot_service import luu_gqvl_snapshot as _luu_gqvl
            kq_snap = _luu_gqvl(df_all, username, ky=ky_baseline)
            if kq_snap.thanh_cong:
                logger.info("merge_baseline_toan_cn: GQVL snapshot %s OK", ky_baseline)
            else:
                logger.warning("merge_baseline_toan_cn: GQVL snapshot lỗi — %s", kq_snap.thong_bao)
        elif loai == "hstd":
            from snapshot_service import (
                luu_snapshot as _luu_snap,
                luu_uy_thac_snapshot as _luu_uy_thac_snap,
            )
            kq_snap = _luu_snap(df_all, username)
            if kq_snap.thanh_cong:
                logger.info("merge_baseline_toan_cn: HSTD snapshot %s OK", ky_baseline)
            else:
                logger.warning("merge_baseline_toan_cn: HSTD snapshot lỗi — %s", kq_snap.thong_bao)
            kq_uy_thac = _luu_uy_thac_snap(df_all, username, ky=ky_baseline)
            if kq_uy_thac.thanh_cong:
                logger.info("merge_baseline_toan_cn: Uy thac snapshot %s OK", ky_baseline)
            else:
                logger.warning("merge_baseline_toan_cn: Uy thac snapshot lỗi — %s", kq_uy_thac.thong_bao)
    except Exception as e:
        logger.error("merge_baseline_toan_cn: lỗi tạo snapshot %s — %s", loai, e, exc_info=True)

    return KetQuaUpload(
        True,
        f"✅ Tổng hợp baseline **{loai.upper()}** 31/12/{nam}: "
        f"**{len(da_merge)}** đơn vị · **{fmt_so(len(df_all))}** dòng"
        + (f" ⚠️ {len(loi)} lỗi" if loi else ""),
        cache_path,
    )


# ── Lưu file theo PGD ─────────────────────────────────────────────────────────

def luu_pgd_file(ten_pgd: str, loai: str, file_bytes: bytes) -> KetQuaUpload:
    """
    Lưu file dữ liệu theo PGD vào pgd_data/{slug}/{loai}_latest.xlsx.
    loai: "hstd" | "nq11" | "gqvl" | "cdtotkvv"

    Sau khi lưu thành công hstd/nq11/gqvl → tự động gọi merge_du_lieu_toan_cn().
    CDTOTKVV không merge toàn CN.
    """
    ok, msg = kiem_tra_file(f"{loai}_{ten_pgd}.xlsx", file_bytes)
    if not ok:
        return KetQuaUpload(False, msg)
    
    # Validate dữ liệu trước khi lưu (chỉ cho HSTD, GQVL, NQ11)
    if loai in ["hstd", "gqvl", "nq11"]:
        try:
            from services.validation_service import validate_dataframe
            from io import BytesIO
            import pandas as pd
            
            # Đọc file để validate — phải dùng đúng header/sheet như khi parse thật
            if loai in ("hstd", "nq11"):
                df = pd.read_excel(BytesIO(file_bytes), sheet_name="BCQUERY", header=4)
                df = df.iloc[:, 1:].dropna(how="all")
            elif loai == "gqvl":
                df = pd.read_excel(BytesIO(file_bytes), sheet_name="Sheet1", header=7)
                df = df.iloc[:, 1:].dropna(how="all").iloc[1:]
            else:
                df = pd.read_excel(BytesIO(file_bytes))
            
            # Validate theo loại bảng
            validation_result = validate_dataframe(df, loai)
            
            # Nếu có lỗi critical, block upload
            if not validation_result.is_valid:
                error_msgs = []
                for error in validation_result.errors:
                    if error.level.value == "critical":
                        error_msgs.append(f"• {error.column}: {error.message}")
                
                if error_msgs:
                    return KetQuaUpload(
                        False, 
                        f"🚫 Dữ liệu không hợp lệ, không thể lưu:\n" + "\n".join(error_msgs[:5])
                    )
            
            # Log warnings cho admin
            if validation_result.warning_count > 0:
                warning_msgs = []
                for error in validation_result.errors:
                    if error.level.value == "warning":
                        warning_msgs.append(f"• {error.column}: {error.message}")
                
                if warning_msgs:
                    logger.warning(
                        "Validation warnings for %s/%s: %s", 
                        ten_pgd, loai, "\n".join(warning_msgs[:3])
                    )
        
        except Exception as e:
            logger.error("Lỗi validation %s/%s: %s", ten_pgd, loai, e, exc_info=True)
            # Không block upload nếu có lỗi trong validation logic
            logger.debug("Tiếp tục lưu file %s/%s dù validation lỗi", ten_pgd, loai)

    from data.pgd import luu_file_pgd as _luu_pgd, thu_muc_pgd
    path = _luu_pgd(ten_pgd, loai, file_bytes)
    pq_pgd = Path(path).with_suffix(".parquet")
    if pq_pgd.exists():
        os.remove(str(pq_pgd))

    thang_nam: str | None = None
    try:
        if loai == "cdtotkvv":
            from data.cdtotkvv import doc_thang_nam_tu_file
            thang_nam = doc_thang_nam_tu_file(file_bytes)
        else:
            import re as _re
            from io import BytesIO as _BytesIO
            from datetime import datetime as _dt, date as _date
            import openpyxl as _openpyxl

            wb = _openpyxl.load_workbook(
                _BytesIO(file_bytes), read_only=True, data_only=True
            )
            ws = wb.active
            pat_ngay_vn = _re.compile(
                r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
                _re.IGNORECASE
            )
            pat_ddmmyyyy = _re.compile(
                r"\b([0-2]?\d|3[0-1])[/\-]([0]?\d|1[0-2])[/\-](\d{4})\b"
            )
            for row in ws.iter_rows(max_row=10, values_only=True):
                for cell in row:
                    if cell is None:
                        continue
                    if isinstance(cell, (_dt, _date)):
                        thang_nam = cell.strftime("%d/%m/%Y")
                        break
                    text = str(cell).strip()
                    if not text:
                        continue
                    m = pat_ngay_vn.search(text)
                    if m:
                        dd = m.group(1).zfill(2)
                        mm = m.group(2).zfill(2)
                        yyyy = m.group(3)
                        thang_nam = f"{dd}/{mm}/{yyyy}"
                        break
                    m = pat_ddmmyyyy.search(text)
                    if m:
                        dd = m.group(1).zfill(2)
                        mm = m.group(2).zfill(2)
                        yyyy = m.group(3)
                        thang_nam = f"{dd}/{mm}/{yyyy}"
                        break
                if thang_nam:
                    break
    except Exception as e:
        logger.error("Lỗi trong khối except: %s", e, exc_info=True)
        logger.debug("luu_pgd_file: không đọc được ngày tháng từ file %s/%s — %s", ten_pgd, loai, e)
        thang_nam = None

    # Chỉ lưu lịch sử cho CDTOTKVV (dữ liệu theo tháng)
    # HSTD/NQ11/GQVL là sao kê theo ngày -> chỉ giữ latest
    if thang_nam and loai == "cdtotkvv":
        from datetime import datetime as _dt
        from pathlib import Path as _Path

        suffix = thang_nam.replace("/", "_")
        try:
            dt = _dt.strptime(thang_nam, "%m/%Y")
            suffix = dt.strftime("%Y_%m")
        except ValueError:
            pass
        try:
            path_version = _Path(str(thu_muc_pgd(ten_pgd))) / f"{loai}_{suffix}.xlsx"
            if not path_version.exists():
                path_version.write_bytes(file_bytes)
        except Exception as e:
            logger.error("Lỗi trong khối except: %s", e, exc_info=True)
            logger.debug("luu_pgd_file: lỗi lưu lịch sử CDTOTKVV %s/%s — %s", ten_pgd, suffix, e)

    if thang_nam:
        if loai == "cdtotkvv":
            thang_label = f" · Tháng {thang_nam} · ✓ Lưu lịch sử"
        else:
            thang_label = f" · Số liệu {thang_nam}"
    else:
        thang_label = ""

    username = st.session_state.get("username", "unknown")
    db.ghi_audit(username, "upload_pgd", f"{loai.upper()} — {ten_pgd}")

    try:
        from services.telegram_service import gui_thong_bao_upload_pgd
        gui_thong_bao_upload_pgd(ten_pgd, loai, username)
    except Exception:
        pass  # Telegram lỗi không được làm gián đoạn upload

    ket_qua = KetQuaUpload(
        True,
        f"✅ Đã lưu {loai.upper()} — {ten_pgd}{thang_label}",
        path,
    )

    # KHÔNG tự động merge toàn CN ở đây.
    # Theo kiến trúc 2 luồng (HUONG_DAN_NGUON_DU_LIEU.md):
    #   - luu_pgd_file() chỉ ghi vào pgd_data/{slug}/ — dùng cho ws_operation
    #   - merge_du_lieu_toan_cn() do tab_upload_khnv (Phòng KH-NV) gọi — dùng cho ws_management
    # Chỉ clear cache PGD đơn lẻ để ws_operation đọc được file mới nhất.

    return ket_qua


# ── Đọc metadata lần merge gần nhất ─────────────────────────────────────────

def lay_meta_merge(loai: str) -> dict | None:
    """
    Đọc metadata lần merge gần nhất của loại dữ liệu.
    Trả về dict hoặc None nếu chưa từng merge.

    Cấu trúc trả về:
      {
        "thoi_gian": str (ISO),
        "so_pgd":    int,
        "so_dong":   int,
        "pgd_cu":    list[str]   — đơn vị dùng số liệu cũ quá ngưỡng
      }

    Dùng trong tab phân tích để hiển thị caption dưới biểu đồ:
      Cập nhật lúc 08:30 14/04 · 22 đơn vị · 45,231 dòng
      (và ⚠️ 2 đơn vị dùng số liệu cũ nếu pgd_cu không rỗng)
    """
    return db.doc_kv(f"merge_meta_{loai}")


def format_caption_merge(loai: str) -> str | None:
    """
    Tạo chuỗi caption hiển thị bên dưới biểu đồ cho tab phân tích.
    Trả về None nếu chưa có metadata (chưa merge lần nào).
    """
    meta = lay_meta_merge(loai)
    if not meta:
        return None

    try:
        thoi_gian = datetime.fromisoformat(meta["thoi_gian"])
        thoi_gian_str = thoi_gian.strftime("%H:%M %d/%m")
    except Exception as e:  # conv: skip — debug-level, fallback về str thô
        logger.debug("lay_thong_tin_merge: không parse được thời gian ISO — %s", e)
        thoi_gian_str = str(meta.get("thoi_gian", ""))

    so_pgd  = meta.get("so_pgd", 0)
    so_dong = meta.get("so_dong", 0)
    pgd_cu  = meta.get("pgd_cu", [])

    caption = f"Cập nhật lúc {thoi_gian_str} · {so_pgd} đơn vị · {fmt_so(so_dong)} dòng"
    if pgd_cu:
        caption += f" · ⚠️ {len(pgd_cu)} đơn vị dùng số liệu cũ"
    return caption


def lay_meta_chat_luong(loai: str) -> dict | None:
    """
    Đọc metadata chất lượng dữ liệu gần nhất cho một loại dữ liệu.
    """
    return db.doc_kv(f"data_quality_meta_{loai}")


# ── Lưu file chấm điểm Tổ TK&VV (tháng, dùng chung toàn CN) ─────────────────

def luu_cdtotkvv(thang_nam: str, file_bytes: bytes) -> KetQuaUpload:
    """Lưu file chấm điểm Tổ TK-VV tháng {thang_nam} vào CDTOTKVV_DIR."""
    ok, msg = kiem_tra_file(f"CDTOTKVV_{thang_nam}.xlsx", file_bytes)
    if not ok:
        return KetQuaUpload(False, msg)
    duong_dan = str(CDTOTKVV_DIR / f"CDTOTKVV_{thang_nam}.xlsx")
    _ghi_va_xoa_cache(duong_dan, file_bytes)
    mb = len(file_bytes) / 1024 / 1024
    username = st.session_state.get("username", "unknown")
    db.ghi_audit(username, "upload_cdtotkvv", f"thang={thang_nam} ({mb:.1f} MB)")
    return KetQuaUpload(
        True,
        f"Đã lưu chấm điểm tháng **{thang_nam}** ({mb:.1f} MB)",
        duong_dan,
    )


# ── Lưu file đính kèm kết quả nhiệm vụ ───────────────────────────────────────

_EXTS_ATTACHMENT = {
    ".xlsx", ".xls", ".XLSX", ".XLS",
    ".pdf", ".PDF",
    ".docx", ".DOCX", ".doc", ".DOC",
}
_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024   # 5 MB


def luu_attachment_nhiem_vu(
    ten_pgd: str,
    nv_id: int,
    ten_file: str,
    file_bytes: bytes,
    username: str,
) -> KetQuaUpload:
    """
    Lưu file đính kèm kết quả nhiệm vụ vào pgd_data/{slug}/nhiem_vu_attach/.
    Cho phép: Excel, PDF, Word (≤ 5 MB).
    Trả về KetQuaUpload; .duong_dan chứa đường dẫn file đã lưu.
    """
    ext = Path(ten_file).suffix
    if ext not in _EXTS_ATTACHMENT:
        return KetQuaUpload(
            False,
            f"⚠️ Định dạng không hỗ trợ: {ext}. Chấp nhận: Excel, PDF, Word",
        )
    if len(file_bytes) > _MAX_ATTACHMENT_BYTES:
        mb = len(file_bytes) / 1024 / 1024
        return KetQuaUpload(False, f"⚠️ File quá lớn ({mb:.1f} MB). Tối đa 5 MB.")
    if len(file_bytes) < 10:
        return KetQuaUpload(False, "⚠️ File trống hoặc không hợp lệ.")

    try:
        from data.pgd import pgd_slug
        slug = pgd_slug(ten_pgd)
        attach_dir = Path("pgd_data") / slug / "nhiem_vu_attach"
        attach_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"nv{nv_id}_{ten_file}"
        save_path = attach_dir / safe_name
        save_path.write_bytes(file_bytes)
        mb = len(file_bytes) / 1024 / 1024
        db.ghi_audit(
            username, "upload_nhiem_vu_attach",
            f"nv_id={nv_id} · file={ten_file} ({mb:.1f} MB) · pgd={ten_pgd}",
        )
        return KetQuaUpload(True, f"✅ Đã lưu file: **{ten_file}** ({mb:.1f} MB)", str(save_path))
    except Exception as e:  # conv: skip
        logger.error("luu_attachment_nhiem_vu thất bại nv_id=%s: %s", nv_id, e, exc_info=True)
        return KetQuaUpload(False, f"❌ Lỗi lưu file: {e}")
