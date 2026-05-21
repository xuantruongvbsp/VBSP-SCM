"""
backup_service.py -- Sao luu du lieu runtime (DB + Parquet + Excel PGD).

Ham cong khai:
  chay_backup()            -- backup 1 lan, tra ve dict ket qua
  zip_ban_backup(ten_ky)   -- zip 1 ban backup thanh bytes de download
  phuc_hoi_backup(zip_bytes) -- phuc hoi tu zip bytes (upload tu may khac)
  don_backup()             -- xoa ban cu, giu MAX_KEEP ban gan nhat

Goi tu:
  tab_trang_thai_nguon.py  -- nut "Backup ngay", "Tai zip", "Phuc hoi"
"""
from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from logger import get_logger

logger = get_logger(__name__)

# -- Cau hinh ------------------------------------------------------------------
ROOT = Path(__file__).parent
BACKUP_DIR = str(ROOT / "backups")      # UI import constant nay
_MAX_KEEP  = 7                          # giu toi da 7 ban gan nhat

_DB_FILE   = ROOT / "vbsp_scm.db"
_PGD_DIR   = ROOT / "pgd_data"
_CACHE_DIR = ROOT / "cache"


# -- chay_backup ---------------------------------------------------------------

def chay_backup() -> dict:
    """
    Thuc hien backup toan bo du lieu runtime.

    Tra ve:
      {
        "ky":       "20260521_193000",
        "db_ok":    True,
        "parquet":  3,
        "pgd_xlsx": 22,
        "out_dir":  "D:/VBSP-SCM/backups/20260521_193000",
      }
    """
    ky  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(BACKUP_DIR) / ky
    out.mkdir(parents=True, exist_ok=True)

    result: dict = {
        "ky": ky, "db_ok": False,
        "parquet": 0, "pgd_xlsx": 0,
        "out_dir": str(out),
    }

    # 1. SQLite DB
    try:
        if _DB_FILE.exists():
            shutil.copy2(_DB_FILE, out / _DB_FILE.name)
            result["db_ok"] = True
            logger.info("backup [%s]: DB ok (%d KB)", ky, _DB_FILE.stat().st_size // 1024)
        else:
            logger.warning("backup [%s]: vbsp_scm.db khong tim thay", ky)
    except Exception as exc:
        logger.error("backup [%s]: loi copy DB -- %s", ky, exc, exc_info=True)

    # 2. Parquet cache
    try:
        if _CACHE_DIR.exists():
            dst_cache = out / "cache"
            dst_cache.mkdir(exist_ok=True)
            count = 0
            for f in _CACHE_DIR.glob("*.parquet"):
                shutil.copy2(f, dst_cache / f.name)
                count += 1
            result["parquet"] = count
    except Exception as exc:
        logger.error("backup [%s]: loi copy parquet -- %s", ky, exc, exc_info=True)

    # 3. Excel PGD
    try:
        if _PGD_DIR.exists():
            dst_pgd = out / "pgd_data"
            count   = 0
            for f in list(_PGD_DIR.rglob("*.xlsx")) + list(_PGD_DIR.rglob("*.XLSX")):
                rel    = f.relative_to(_PGD_DIR)
                target = dst_pgd / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
                count += 1
            result["pgd_xlsx"] = count
    except Exception as exc:
        logger.error("backup [%s]: loi copy pgd_data -- %s", ky, exc, exc_info=True)

    # Don ban cu
    try:
        don_backup()
    except Exception as exc:
        logger.warning("backup [%s]: don_backup loi -- %s", ky, exc)

    return result


# -- zip_ban_backup ------------------------------------------------------------

def zip_ban_backup(ten_ky: str) -> bytes:
    """
    Nen 1 ban backup thanh ZIP trong bo nho va tra ve bytes.
    ten_ky: ten thu muc, vi du "20260521_193000"
    """
    src = Path(BACKUP_DIR) / ten_ky
    if not src.exists():
        raise FileNotFoundError(f"Backup '{ten_ky}' khong ton tai")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(src))
    buf.seek(0)
    data = buf.read()
    logger.info("zip_ban_backup [%s]: %d KB", ten_ky, len(data) // 1024)
    return data


# -- phuc_hoi_backup -----------------------------------------------------------

def phuc_hoi_backup(zip_bytes: bytes) -> dict:
    """
    Phuc hoi du lieu tu zip bytes (upload tu may khac).

    Quy trinh:
      1. Giai nen vao thu muc tam
      2. Close ket noi SQLite hien tai
      3. Ghi de vbsp_scm.db
      4. Ghi de cache/*.parquet
      5. Ghi de pgd_data/**/*.xlsx
      6. Reinit DB + xoa cache Streamlit

    Tra ve:
      {
        "db_ok":    True,
        "parquet":  3,
        "pgd_xlsx": 22,
        "loi":      []   # danh sach loi neu co
      }
    """
    result: dict = {"db_ok": False, "parquet": 0, "pgd_xlsx": 0, "loi": []}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Giai nen
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                zf.extractall(tmp_path)
        except Exception as exc:
            msg = f"Khong giai nen duoc zip: {exc}"
            logger.error("phuc_hoi: %s", msg, exc_info=True)
            result["loi"].append(msg)
            return result

        # 1. DB
        db_src = tmp_path / "vbsp_scm.db"
        if db_src.exists():
            try:
                import db as db_module
                db_module.reset_conn()          # dong connection truoc khi ghi
                shutil.copy2(db_src, _DB_FILE)
                db_module.init_db()             # mo lai + dam bao schema
                result["db_ok"] = True
                logger.info("phuc_hoi: DB ok (%d KB)", _DB_FILE.stat().st_size // 1024)
            except Exception as exc:
                msg = f"Loi ghi DB: {exc}"
                logger.error("phuc_hoi: %s", msg, exc_info=True)
                result["loi"].append(msg)
        else:
            result["loi"].append("Zip khong chua vbsp_scm.db")

        # 2. Parquet cache
        cache_src = tmp_path / "cache"
        if cache_src.exists():
            try:
                _CACHE_DIR.mkdir(exist_ok=True)
                count = 0
                for f in cache_src.glob("*.parquet"):
                    shutil.copy2(f, _CACHE_DIR / f.name)
                    count += 1
                result["parquet"] = count
            except Exception as exc:
                msg = f"Loi ghi parquet: {exc}"
                logger.error("phuc_hoi: %s", msg, exc_info=True)
                result["loi"].append(msg)

        # 3. Excel PGD
        pgd_src = tmp_path / "pgd_data"
        if pgd_src.exists():
            try:
                count = 0
                for f in list(pgd_src.rglob("*.xlsx")) + list(pgd_src.rglob("*.XLSX")):
                    rel    = f.relative_to(pgd_src)
                    target = _PGD_DIR / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)
                    count += 1
                result["pgd_xlsx"] = count
            except Exception as exc:
                msg = f"Loi ghi pgd_data: {exc}"
                logger.error("phuc_hoi: %s", msg, exc_info=True)
                result["loi"].append(msg)

    # Xoa cache Streamlit de load lai du lieu moi
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:
        pass

    logger.info(
        "phuc_hoi: db=%s parquet=%d pgd=%d loi=%d",
        result["db_ok"], result["parquet"], result["pgd_xlsx"], len(result["loi"]),
    )
    return result


# -- don_backup ----------------------------------------------------------------

def don_backup(max_keep: int = _MAX_KEEP) -> int:
    """Xoa ban backup cu, giu max_keep ban gan nhat. Tra ve so ban da xoa."""
    bk_dir = Path(BACKUP_DIR)
    if not bk_dir.exists():
        return 0
    ds = sorted(
        [d for d in bk_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    xoa = ds[max_keep:]
    for d in xoa:
        try:
            shutil.rmtree(d)
            logger.info("don_backup: xoa %s", d.name)
        except Exception as exc:
            logger.warning("don_backup: khong xoa duoc %s -- %s", d.name, exc)
    return len(xoa)
