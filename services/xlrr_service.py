"""Service layer cho Xử lý Rủi ro (XLRR) — unified data model & operations."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional, Literal
from pathlib import Path
import uuid

import pandas as pd

import db
from config import DS_PGD, DON_VI_CHI_NHANH, COT_TEN_PGD
from data.pgd import pgd_slug
from logger import get_logger

logger = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
NGUON_TW = 1
NGUON_DP = 2

LOAI_HO_SO_HSTD = "hstd"
LOAI_HO_SO_QD62 = "qd62"

TRANG_THAI_CHO_DUYET = "cho_duyet"
TRANG_THAI_DA_DUYET = "da_duyet"
TRANG_THAI_TU_CHOI = "tu_choi"

# Kết quả xử lý từ NHCSXH TW
KET_QUA_DA_KHOANH   = "da_khoanh"
KET_QUA_DA_XOA      = "da_xoa"
KET_QUA_KHONG_DUYET = "khong_duyet"
KET_QUA_CHO_XU_LY  = "cho_xu_ly"

KET_QUA_LABEL: dict[str, str] = {
    KET_QUA_DA_KHOANH:   "✅ Đã khoanh",
    KET_QUA_DA_XOA:      "✅ Đã xóa",
    KET_QUA_KHONG_DUYET: "❌ Không duyệt",
    KET_QUA_CHO_XU_LY:  "⏳ Chờ xử lý",
}

# ── Data Model ───────────────────────────────────────────────────────────────

@dataclass
class HoSoRuiRo:
    """Unified data model cho hồ sơ xử lý rủi ro (cả HSTD và QĐ62)."""
    
    # Core identification
    id: str
    ma_kh: str
    ten_kh: str
    so_ku: str
    
    # Location
    xa: str
    ten_pgd: str
    pgd_slug: str
    
    # Loan details
    ten_ct: str
    du_no_goc: float = 0.0
    du_no_lai: float = 0.0
    lai_ton: float = 0.0
    ngay_vay: Optional[date] = None
    ngay_dh: Optional[date] = None
    
    # Risk handling
    bien_phap: Literal["khoanh", "xoa", "khac"] = "khoanh"
    nguyen_nhan: str = ""
    muc_do: Literal["40-80", "80-100", "khac", ""] = ""
    so_thang: int = 0
    ngay_rr: Optional[date] = None
    ghi_chu: str = ""
    
    # Source & status
    nguon_von: Literal[1, 2] = NGUON_TW  # 1=TW, 2=ĐP
    loai_ho_so: Literal["hstd", "qd62"] = LOAI_HO_SO_HSTD
    trang_thai: Literal["cho_duyet", "da_duyet", "tu_choi"] = TRANG_THAI_CHO_DUYET
    
    # QĐ62 specific
    so_cccd: str = ""
    ly_do: str = ""  # For QĐ62
    file_dinh_kem: str = ""
    
    # Audit
    ngay_tao: datetime = field(default_factory=datetime.now)
    nguoi_tao: str = ""
    ngay_duyet: Optional[datetime] = None
    nguoi_duyet: str = ""
    
    # Đợt XLRR (theo quy định TW)
    dot_id: str = ""          # ID đợt, VD: "cn_2026_1" hoặc "pgd_tanphong_2026_1"
    da_gui_cn: bool = False   # PGD đã bấm gửi đợt lên CN chưa
    
    # Flags
    lap_thay_pgd: bool = False  # CN lập thay PGD
    
    # Thông tin mẫu 01/XLN — Đơn đề nghị
    ngay_ky_01: Optional[date] = None
    ma_to: str = ""
    ten_to_truong: str = ""
    so_tien_thiet_hai_01: str = ""
    muc_do_thiet_hai_01: str = ""
    kha_nang_tra_no_01: str = ""
    ke_hoach_tra_no_01: str = ""
    
    # Thông tin mẫu 02/XLN — Biên bản
    ngay_lap_02: Optional[date] = None
    dia_diem_02: str = ""
    ten_pgd_02: str = ""        # GĐ hoặc Phó GĐ NHCSXH
    chuc_vu_pgd_02: str = "Phó Giám đốc"
    ten_ubnd_02: str = ""
    chuc_vu_ubnd_02: str = "Phó Chủ tịch"
    ten_hoi_nd_02: str = ""
    chuc_vu_hoi_nd_02: str = "Chủ tịch Hội Nông dân xã"
    ten_cbtd_02: str = ""
    ten_to_truong_02: str = ""
    chi_tiet_thiet_hai_02: str = ""
    danh_gia_thiet_hai_02: str = ""
    danh_gia_du_an_02: str = ""
    tai_san_hien_tai_02: str = ""
    kha_nang_tra_no_02: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        d = asdict(self)
        # Convert datetime/date to string; NaT/NaN/None → None (an toàn cho json.dumps)
        for key in ["ngay_vay", "ngay_dh", "ngay_rr", "ngay_tao", "ngay_duyet", "ngay_ky_01", "ngay_lap_02"]:
            val = d.get(key)
            if val is None:
                continue
            # Kiểm tra pd.NaT và các giá trị null-like của pandas
            try:
                if pd.isnull(val):
                    d[key] = None
                    continue
            except (TypeError, ValueError):
                pass
            if isinstance(val, (datetime, date)):
                d[key] = val.isoformat()
            else:
                # Fallback: ép về string nếu không serialize được
                try:
                    d[key] = str(val) if val is not None else None
                except Exception:
                    d[key] = None
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "HoSoRuiRo":
        """Create from dict (e.g., from kv_store)."""
        # Convert string dates back to date objects
        for key in ["ngay_vay", "ngay_dh", "ngay_rr", "ngay_ky_01", "ngay_lap_02"]:
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = date.fromisoformat(data[key])
                except ValueError:
                    data[key] = None
        for key in ["ngay_tao", "ngay_duyet"]:
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = datetime.fromisoformat(data[key])
                except ValueError:
                    data[key] = None
        return cls(**data)
    
    @property
    def tong_du_no(self) -> float:
        """Tính tổng dư nợ (gốc + lãi)."""
        return self.du_no_goc + self.du_no_lai
    
    @property
    def is_khoanh(self) -> bool:
        return self.bien_phap == "khoanh"
    
    @property
    def is_xoa(self) -> bool:
        return self.bien_phap == "xoa"


@dataclass
class DotXLRR:
    """Đợt xử lý rủi ro — theo quy định TW, 1-3 đợt/năm."""
    id: str
    ten_dot: str
    nam: int
    ngay_bat_dau: date
    ngay_ket_thuc: date
    nguoi_tao: str
    loai: Literal["cn", "pgd"]
    pgd_slug: str = ""
    ngay_tao: datetime = field(default_factory=datetime.now)
    da_gui_tw: bool = False
    
    def to_dict(self) -> dict:
        d = asdict(self)
        for key in ["ngay_bat_dau", "ngay_ket_thuc", "ngay_tao"]:
            val = d.get(key)
            if isinstance(val, (datetime, date)):
                d[key] = val.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "DotXLRR":
        for key in ["ngay_bat_dau", "ngay_ket_thuc"]:
            if key in data and isinstance(data[key], str):
                try:
                    data[key] = date.fromisoformat(data[key])
                except ValueError:
                    data[key] = date.today()
        if "ngay_tao" in data and isinstance(data["ngay_tao"], str):
            try:
                data["ngay_tao"] = datetime.fromisoformat(data["ngay_tao"])
            except ValueError:
                data["ngay_tao"] = datetime.now()
        return cls(**data)
    
    @property
    def con_lai(self) -> int:
        delta = (self.ngay_ket_thuc - date.today()).days
        return max(delta, 0)
    
    @property
    def qua_han(self) -> bool:
        return date.today() > self.ngay_ket_thuc
    
    @property
    def trang_thai_label(self) -> str:
        if self.qua_han:
            return "🔴 Quá hạn"
        if self.con_lai <= 7:
            return f"🟡 Sắp hết hạn ({self.con_lai} ngày)"
        return f"🟢 Đang mở ({self.con_lai} ngày)"


class LuuTruDotXLRR:
    """Quản lý lưu trữ đợt XLRR trong kv_store."""
    
    @staticmethod
    def _key_cn(nam: int) -> str:
        return f"xlrr_dot_cn_{nam}"
    
    @staticmethod
    def _key_pgd(slug: str, nam: int) -> str:
        return f"xlrr_dot_pgd_{slug}_{nam}"
    
    @classmethod
    def tao_dot(cls, ten_dot: str, nam: int, ngay_bat_dau: date, ngay_ket_thuc: date,
                nguoi_tao: str, loai: Literal["cn", "pgd"], pgd_slug_val: str = "") -> DotXLRR:
        ds = cls.doc_ds(nam, loai, pgd_slug_val)
        dot_id = f"{loai}_{'' if loai == 'cn' else pgd_slug_val + '_'}{nam}_{len(ds) + 1}"
        dot = DotXLRR(id=dot_id, ten_dot=ten_dot, nam=nam,
                      ngay_bat_dau=ngay_bat_dau, ngay_ket_thuc=ngay_ket_thuc,
                      nguoi_tao=nguoi_tao, loai=loai, pgd_slug=pgd_slug_val)
        ds.append(dot)
        key = cls._key_cn(nam) if loai == "cn" else cls._key_pgd(pgd_slug_val, nam)
        db.ghi_kv(key, [d.to_dict() for d in ds], nguoi_tao)
        db.ghi_audit(nguoi_tao, "xlrr_tao_dot", f"{ten_dot} ({loai})")
        return dot
    
    @classmethod
    def doc_ds(cls, nam: int, loai: Literal["cn", "pgd"], pgd_slug_val: str = "") -> list[DotXLRR]:
        key = cls._key_cn(nam) if loai == "cn" else cls._key_pgd(pgd_slug_val, nam)
        data = db.doc_kv(key)
        if not data:
            return []
        return [DotXLRR.from_dict(d) for d in data] if isinstance(data, list) else []
    
    @classmethod
    def xoa_dot(cls, dot_id: str, nam: int, loai: Literal["cn", "pgd"], pgd_slug_val: str, username: str) -> bool:
        ds = cls.doc_ds(nam, loai, pgd_slug_val)
        ds_moi = [d for d in ds if d.id != dot_id]
        if len(ds_moi) == len(ds):
            return False
        key = cls._key_cn(nam) if loai == "cn" else cls._key_pgd(pgd_slug_val, nam)
        db.ghi_kv(key, [d.to_dict() for d in ds_moi], username)
        db.ghi_audit(username, "xlrr_xoa_dot", f"{dot_id}")
        return True
    
    @classmethod
    def cap_nhat_dot(cls, dot_id: str, nam: int, loai: Literal["cn", "pgd"],
                     pgd_slug_val: str, username: str, **updates) -> DotXLRR | None:
        ds = cls.doc_ds(nam, loai, pgd_slug_val)
        for dot in ds:
            if dot.id == dot_id:
                for k, v in updates.items():
                    if hasattr(dot, k):
                        setattr(dot, k, v)
                key = cls._key_cn(nam) if loai == "cn" else cls._key_pgd(pgd_slug_val, nam)
                db.ghi_kv(key, [d.to_dict() for d in ds], username)
                db.ghi_audit(username, "xlrr_sua_dot", f"{dot_id}")
                return dot
        return None


# ── Storage Layer ──────────────────────────────────────────────────────────

class LuuTruXLRR:
    """Quản lý lưu trữ hồ sơ XLRR trong kv_store."""
    
    @staticmethod
    def _key_pgd(pgd_slug: str, nam: int, thang: int) -> str:
        return f"xlrr_pgd_{pgd_slug}_{nam}_{thang:02d}"
    
    @staticmethod
    def _key_cn(nam: int, thang: int) -> str:
        return f"xlrr_cn_{nam}_{thang:02d}"
    
    @staticmethod
    def _key_qd62(nam: int, thang: int) -> str:
        return f"qd62_cn_{nam}_{thang:02d}"
    
    @classmethod
    def luu_pgd(
        cls,
        ds_ho_so: list[HoSoRuiRo],
        pgd_slug: str,
        nam: int,
        thang: int,
        username: str,
    ) -> None:
        """Lưu danh sách hồ sơ PGD."""
        key = cls._key_pgd(pgd_slug, nam, thang)
        data = {
            "danh_sach": [hs.to_dict() for hs in ds_ho_so],
            "ngay_cap_nhat": datetime.now().isoformat(),
            "nguoi_cap_nhat": username,
        }
        db.ghi_kv(key, data, username)
        db.ghi_audit(username, "xlrr_luu_pgd", f"{len(ds_ho_so)} hồ sơ — {pgd_slug} T{thang}/{nam}")
    
    @classmethod
    def doc_pgd(cls, pgd_slug: str, nam: int, thang: int) -> list[HoSoRuiRo]:
        """Đọc danh sách hồ sơ PGD."""
        key = cls._key_pgd(pgd_slug, nam, thang)
        data = db.doc_kv(key)
        if not data or "danh_sach" not in data:
            return []
        return [HoSoRuiRo.from_dict(d) for d in data["danh_sach"]]
    
    @classmethod
    def luu_cn(
        cls,
        ds_ho_so: list[HoSoRuiRo],
        nam: int,
        thang: int,
        username: str,
    ) -> None:
        """Lưu danh sách hồ sơ CN (QĐ62 hoặc lập thay PGD)."""
        key = cls._key_cn(nam, thang)
        data = db.doc_kv(key) or {"danh_sach": []}
        ds_cu = [HoSoRuiRo.from_dict(d) for d in data.get("danh_sach", [])]
        
        # Merge: cập nhật nếu có id trùng, thêm mới nếu không
        ds_dict = {hs.id: hs for hs in ds_cu}
        for hs in ds_ho_so:
            ds_dict[hs.id] = hs
        
        data = {
            "danh_sach": [hs.to_dict() for hs in ds_dict.values()],
            "ngay_cap_nhat": datetime.now().isoformat(),
            "nguoi_cap_nhat": username,
        }
        db.ghi_kv(key, data, username)
        db.ghi_audit(username, "xlrr_luu_cn", f"{len(ds_ho_so)} hồ sơ — T{thang}/{nam}")
    
    @classmethod
    def doc_cn(cls, nam: int, thang: int) -> list[HoSoRuiRo]:
        """Đọc danh sách hồ sơ CN."""
        key = cls._key_cn(nam, thang)
        data = db.doc_kv(key)
        if not data or "danh_sach" not in data:
            return []
        return [HoSoRuiRo.from_dict(d) for d in data["danh_sach"]]
    
    @classmethod
    def luu_qd62(
        cls,
        ds_ho_so: list[HoSoRuiRo],
        nam: int,
        thang: int,
        username: str,
    ) -> None:
        """Lưu danh sách QĐ62 (dành cho CN)."""
        key = cls._key_qd62(nam, thang)
        data = db.doc_kv(key) or {"danh_sach": []}
        ds_cu = [HoSoRuiRo.from_dict(d) for d in data.get("danh_sach", [])]
        
        ds_dict = {hs.id: hs for hs in ds_cu}
        for hs in ds_ho_so:
            ds_dict[hs.id] = hs
        
        data = {
            "danh_sach": [hs.to_dict() for hs in ds_dict.values()],
            "ngay_cap_nhat": datetime.now().isoformat(),
            "nguoi_cap_nhat": username,
        }
        db.ghi_kv(key, data, username)
        db.ghi_audit(username, "xlrr_luu_qd62", f"{len(ds_ho_so)} hồ sơ — T{thang}/{nam}")
    
    @classmethod
    def doc_qd62(cls, nam: int, thang: int) -> list[HoSoRuiRo]:
        """Đọc danh sách QĐ62."""
        key = cls._key_qd62(nam, thang)
        data = db.doc_kv(key)
        if not data or "danh_sach" not in data:
            return []
        return [HoSoRuiRo.from_dict(d) for d in data["danh_sach"]]
    
    @classmethod
    def xoa_ho_so(cls, ho_so_id: str, nam: int, thang: int, username: str, loai: str = "cn") -> bool:
        """Xóa một hồ sơ theo ID."""
        if loai == "pgd":
            # Cần biết pgd_slug, nên tìm trong tất cả PGD
            for pgd in DS_PGD:
                ds = cls.doc_pgd(pgd_slug(pgd), nam, thang)
                ds_moi = [hs for hs in ds if hs.id != ho_so_id]
                if len(ds_moi) < len(ds):
                    cls.luu_pgd(ds_moi, pgd_slug(pgd), nam, thang, username)
                    return True
            return False
        elif loai == "cn":
            ds = cls.doc_cn(nam, thang)
            ds_moi = [hs for hs in ds if hs.id != ho_so_id]
            if len(ds_moi) < len(ds):
                cls.luu_cn(ds_moi, nam, thang, username)
                return True
            return False
        elif loai == "qd62":
            ds = cls.doc_qd62(nam, thang)
            ds_moi = [hs for hs in ds if hs.id != ho_so_id]
            if len(ds_moi) < len(ds):
                cls.luu_qd62(ds_moi, nam, thang, username)
                return True
            return False
        return False

    @staticmethod
    def _key_ket_qua(nam: int, thang: int) -> str:
        return f"xlrr_ket_qua_{nam}_{thang:02d}"

    @classmethod
    def luu_ket_qua(cls, data: dict, nam: int, thang: int, username: str) -> None:
        """Lưu kết quả xử lý từ NHCSXH TW theo kỳ."""
        key = cls._key_ket_qua(nam, thang)
        db.ghi_kv(key, data, username)
        so_hs = len(data.get("ds_ket_qua", []))
        so_qd = data.get("so_quyet_dinh", "")
        db.ghi_audit(username, "xlrr_luu_ket_qua", f"QĐ {so_qd} — {so_hs} hồ sơ T{thang}/{nam}")

    @classmethod
    def doc_ket_qua(cls, nam: int, thang: int) -> dict | None:
        """Đọc kết quả xử lý từ NHCSXH TW theo kỳ."""
        key = cls._key_ket_qua(nam, thang)
        return db.doc_kv(key)

    @classmethod
    def doc_ket_qua_pgd(cls, pgd_slug_val: str, nam: int, thang: int) -> list[dict]:
        """Lọc kết quả của 1 PGD cụ thể."""
        data = cls.doc_ket_qua(nam, thang)
        if not data:
            return []
        return [
            r for r in data.get("ds_ket_qua", [])
            if pgd_slug(r.get("ten_pgd", "")) == pgd_slug_val
        ]


# ── Aggregation Layer ───────────────────────────────────────────────────────

class TongHopXLRR:
    """Tổng hợp dữ liệu XLRR từ nhiều nguồn."""
    
    @classmethod
    def tong_hop_theo_pgd(
        cls,
        nam: int,
        thang: int,
    ) -> pd.DataFrame:
        """Tổng hợp hồ sơ theo PGD (cả PGD lập và CN lập thay)."""
        rows = []
        
        for ten_pgd in DS_PGD:
            slug = pgd_slug(ten_pgd)
            
            # Hồ sơ PGD tự lập
            ds_pgd = LuuTruXLRR.doc_pgd(slug, nam, thang)
            
            # Hồ sơ CN lập thay cho PGD này
            ds_cn = [hs for hs in LuuTruXLRR.doc_cn(nam, thang) 
                     if hs.pgd_slug == slug and hs.lap_thay_pgd]
            
            # Hồ sơ QĐ62 của PGD
            ds_qd62 = [hs for hs in LuuTruXLRR.doc_qd62(nam, thang)
                       if hs.pgd_slug == slug]
            
            if ds_pgd or ds_cn or ds_qd62:
                rows.append({
                    "PGD": ten_pgd,
                    "Hồ sơ PGD lập": len(ds_pgd),
                    "Dư nợ PGD (tỷ)": sum(hs.tong_du_no for hs in ds_pgd) / 1e9,
                    "Hồ sơ CN lập thay": len(ds_cn),
                    "Dư nợ CN thay (tỷ)": sum(hs.tong_du_no for hs in ds_cn) / 1e9,
                    "Hồ sơ QĐ62": len(ds_qd62),
                    "Dư nợ QĐ62 (tỷ)": sum(hs.tong_du_no for hs in ds_qd62) / 1e9,
                    "Tổng hồ sơ": len(ds_pgd) + len(ds_cn) + len(ds_qd62),
                    "Tổng dư nợ (tỷ)": sum(hs.tong_du_no for hs in (ds_pgd + ds_cn + ds_qd62)) / 1e9,
                })
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    @classmethod
    def tong_hop_theo_chuong_trinh(
        cls,
        nam: int,
        thang: int,
    ) -> pd.DataFrame:
        """Tổng hợp theo chương trình tín dụng."""
        ds_all = []
        
        for ten_pgd in DS_PGD:
            slug = pgd_slug(ten_pgd)
            ds_all.extend(LuuTruXLRR.doc_pgd(slug, nam, thang))
        
        ds_all.extend(LuuTruXLRR.doc_cn(nam, thang))
        ds_all.extend(LuuTruXLRR.doc_qd62(nam, thang))
        
        if not ds_all:
            return pd.DataFrame()
        
        # Group by chương trình
        ct_groups = {}
        for hs in ds_all:
            ct = hs.ten_ct or "Không xác định"
            if ct not in ct_groups:
                ct_groups[ct] = []
            ct_groups[ct].append(hs)
        
        rows = []
        for ct, ds in ct_groups.items():
            rows.append({
                "Chương trình": ct,
                "Số hồ sơ": len(ds),
                "Khoanh nợ": sum(1 for hs in ds if hs.is_khoanh),
                "Xóa nợ": sum(1 for hs in ds if hs.is_xoa),
                "TW (tỷ)": sum(hs.tong_du_no for hs in ds if hs.nguon_von == NGUON_TW) / 1e9,
                "ĐP (tỷ)": sum(hs.tong_du_no for hs in ds if hs.nguon_von == NGUON_DP) / 1e9,
                "Tổng dư nợ (tỷ)": sum(hs.tong_du_no for hs in ds) / 1e9,
            })
        
        return pd.DataFrame(rows)
    
    @classmethod
    def tong_hop_toan_cn(
        cls,
        nam: int,
        thang: int,
    ) -> dict:
        """Tổng hợp toàn bộ cho dashboard."""
        ds_pgd_all = []
        for ten_pgd in DS_PGD:
            ds_pgd_all.extend(LuuTruXLRR.doc_pgd(pgd_slug(ten_pgd), nam, thang))
        
        ds_cn = LuuTruXLRR.doc_cn(nam, thang)
        ds_qd62 = LuuTruXLRR.doc_qd62(nam, thang)
        
        ds_all = ds_pgd_all + ds_cn + ds_qd62
        
        if not ds_all:
            return {
                "tong_ho_so": 0,
                "tong_du_no": 0,
                "so_pgd_co_hs": 0,
                "so_khoanh": 0,
                "so_xoa": 0,
                "tw_tien": 0,
                "dp_tien": 0,
            }
        
        return {
            "tong_ho_so": len(ds_all),
            "tong_du_no": sum(hs.tong_du_no for hs in ds_all),
            "so_pgd_co_hs": len(set(hs.ten_pgd for hs in ds_all if hs.ten_pgd)),
            "so_khoanh": sum(1 for hs in ds_all if hs.is_khoanh),
            "so_xoa": sum(1 for hs in ds_all if hs.is_xoa),
            "tw_tien": sum(hs.tong_du_no for hs in ds_all if hs.nguon_von == NGUON_TW),
            "dp_tien": sum(hs.tong_du_no for hs in ds_all if hs.nguon_von == NGUON_DP),
        }


# ── Export ──────────────────────────────────────────────────────────────────

__all__ = [
    "HoSoRuiRo",
    "DotXLRR",
    "LuuTruXLRR",
    "LuuTruDotXLRR",
    "TongHopXLRR",
    "NGUON_TW",
    "NGUON_DP",
    "LOAI_HO_SO_HSTD",
    "LOAI_HO_SO_QD62",
    "TRANG_THAI_CHO_DUYET",
    "TRANG_THAI_DA_DUYET",
    "TRANG_THAI_TU_CHOI",
]
