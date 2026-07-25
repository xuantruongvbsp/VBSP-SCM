r"""
Kiểm tra so sánh số liệu KHTD — CN vs 95 xã/phường.
Phát hiện chênh lệch và tìm nguyên nhân.

Cách chạy:
  cd D:\VBSP-SCM
  venv\Scripts\python.exe test_khtd_so_lieu.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
import pandas as pd
from logger import get_logger

logger = get_logger(__name__)
from config import (
    CHUONG_TRINH_KHTD, DS_PGD, DON_VI_CHI_NHANH, PGD_XA_MAP,
    COT_TEN_PGD, COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON,
    COT_TONG_DU_NO, COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH,
    COT_TEN_CT,
    tim_ten_xa_trong_hstd,
)
from data.pgd import pgd_slug as _pgd_slug

_MAKEY_TO_MACT: dict[str, int] = {mk: mc for mk, mc, _, _, _ in CHUONG_TRINH_KHTD}
_SHORT_CT: dict[str, str] = {
    "1_TW": "Hộ nghèo",       "2_TW": "HSSV",           "3_TW_NHCSXH": "GQVL HĐ",
    "3_TW_NSNN": "GQVL NS",  "4_TW": "XKLĐ",            "6_TW": "Nước sạch",
    "7_TW": "Nhà ở HN",       "9_TW": "Mới TN",          "10_TW": "SXKD KK",
    "12_TW": "Nhà ở XH",      "15_TW": "TN KK",          "17_TW": "DTTS 755",
    "19_TW": "Cận nghèo",     "21_TW": "DTTS 2085",      "25_TW": "Vùng DTTS",
    "26_TW": "Chấp hành án",  "99_TW": "Khác TW",
    "1_DP": "HN (ĐP)",        "2_DP": "SV (ĐP)",         "3_DP_TINH": "GQVL tỉnh",
    "3_DP_XA": "GQVL xã",    "6_DP": "NS ĐP",            "9_DP": "Mới TN ĐP",
    "10_DP": "SXKD KK ĐP",   "12_DP": "NOXH ĐP",        "15_DP": "TN KK ĐP",
    "17_DP": "DTTS 755 ĐP",  "19_DP": "Cận nghèo ĐP",   "21_DP": "DTTS 2085 ĐP",
    "25_DP": "Vùng DTTS ĐP", "26_DP": "Chấp hành ĐP",   "99_DP": "Khác ĐP",
}

# ── Phát hiện đợt KHTD hiện tại ──────────────────────────────────────────────
def _tim_dot_hien_tai():
    """Tìm năm/tháng/đợt từ kv_store keys."""
    all_keys = db.doc_kv_prefix("khtd_")
    dot_keys = [k for k in all_keys if k.count("_") >= 4]
    print(f"📋 Tổng số keys kv_store với prefix 'khtd_': {len(dot_keys)}")
    
    # Tìm đợt mới nhất
    best = None
    best_key = None
    for k in dot_keys:
        parts = k.split("_", 1)  # ["khtd", "pgd_slug_Y_mm_dot"]
        if len(parts) < 2:
            continue
        rest = parts[1]
        # rest = "pgd_slug_2026_01_dot1"
        sub = rest.split("_", 1)
        if len(sub) < 2:
            continue
        pgd_part = sub[0]
        date_part = sub[1]  # "2026_01_dot1"
        try:
            nam_s = date_part.split("_")[0]
            thang_s = date_part.split("_")[1]
            dot_s = "_".join(date_part.split("_")[2:])
            key_tuple = (int(nam_s), int(thang_s), dot_s)
            if best is None or key_tuple > best:
                best = key_tuple
                best_key = k
        except (ValueError, IndexError):
            continue
    
    if best:
        print(f"  → Đợt mới nhất: năm={best[0]}, tháng={best[1]:02d}, đợt={best[2]}")
        return best[0], f"{best[1]:02d}", best[2]
    print("  ⚠️ Không tìm thấy đợt KHTD nào trong kv_store")
    return 2026, "06", "dot1"


def _slug_to_ten(slug: str) -> str:
    if slug == "hoi_so":
        return DON_VI_CHI_NHANH
    for ten in DS_PGD:
        if _pgd_slug(ten) == slug:
            return ten
    return slug


def _ds_slug() -> list[str]:
    return ["hoi_so"] + [_pgd_slug(ten) for ten in DS_PGD]


def _ten_ngan(ma_key: str) -> str:
    return _SHORT_CT.get(ma_key, ma_key)


# ── Đọc KHTD từ kv_store ─────────────────────────────────────────────────────
def _doc_khtd(nam, thang, dot) -> pd.DataFrame:
    """Đọc giống tong_hop() nhưng giữ định dạng VND."""
    cols = [
        "pgd_slug", "xa", "ma_key", "ten_ct", "nguon", "loai",
        "kh_tw", "dc_tw", "kh_moi_tw", "kh_dp", "dc_dp", "kh_moi_dp", "ly_do",
    ]
    rows: list[dict] = []
    for pgd_s in _ds_slug():
        key = f"khtd_{pgd_s}_{nam}_{thang}_{dot}"
        raw = db.doc_kv(key)
        if not raw or not isinstance(raw, dict):
            continue
        loai = raw.get("loai") or ""
        for item in raw.get("du_lieu") or []:
            if not isinstance(item, dict):
                continue
            row = {"pgd_slug": pgd_s, "loai": loai}
            for c in cols[2:]:
                row[c] = item.get(c)
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


# ── Đọc HSTD từ parquet ─────────────────────────────────────────────────────
def _doc_hstd():
    """Đọc HSTD parquet cache."""
    import pyarrow.parquet as pq
    import duckdb
    cache_path = "D:/VBSP-SCM/cache/hstd.parquet"
    if not os.path.exists(cache_path):
        print("  ⚠️ Không tìm thấy cache/hstd.parquet")
        return pd.DataFrame()
    try:
        schema = pq.read_schema(cache_path)
        cols = [f.name for f in schema]
        print(f"  → HSTD columns ({len(cols)}): {cols[:10]}...")
        df = duckdb.query(f"SELECT * FROM '{cache_path}'").df()
        print(f"  → HSTD rows: {len(df):,}")
        return df
    except Exception as e:
        logger.error("doc_hstd: lỗi đọc HSTD — %s", e, exc_info=True)
        print(f"  ⚠️ Lỗi đọc HSTD: {e}")
        return pd.DataFrame()


# ── Kiểm tra chính ────────────────────────────────────────────────────────────
def kiem_tra_khtd(nam, thang, dot):
    print(f"\n{'='*80}")
    print(f"🔍 KIỂM TRA SỐ LIỆU KHTD — Năm {nam}, Tháng {thang}, Đợt {dot}")
    print(f"{'='*80}")
    
    # ── Bước 1: Đọc KHTD ──
    print(f"\n{'─'*40}")
    print("📥 Bước 1: Đọc KHTD từ kv_store")
    print(f"{'─'*40}")
    
    df_kh = _doc_khtd(nam, thang, dot)
    if df_kh.empty:
        print("❌ KHÔNG có dữ liệu KHTD cho đợt này!")
        return
    print(f"  → Tổng số dòng KHTD: {len(df_kh):,}")
    print(f"  → Các cột: {list(df_kh.columns)}")
    
    # Thống kê PGD
    n_pgd_kv = df_kh["pgd_slug"].nunique()
    slugs = df_kh["pgd_slug"].unique()
    print(f"  → Số PGD có dữ liệu: {n_pgd_kv}")
    print(f"    Danh sách slug: {sorted(slugs)}")
    
    # Kiểm tra xã
    n_xa_kh = df_kh["xa"].nunique()
    xa_kh_set = set(df_kh["xa"].dropna().unique())
    print(f"  → Số xã có trong KHTD: {n_xa_kh}")
    xa_vnone = df_kh["xa"].isna().sum() + (df_kh["xa"] == "").sum()
    print(f"  → Số dòng xã trống/None: {xa_vnone}")
    if xa_vnone > 0:
        print(f"    ⚠️ CÓ DỮ LIỆU XÃ TRỐNG!")
        rows_empty_xa = df_kh[df_kh["xa"].isna() | (df_kh["xa"] == "")]
        print(f"    → {len(rows_empty_xa)} dòng xã trống:")
        for _, r in rows_empty_xa.iterrows():
            print(f"      PGD={r['pgd_slug']}, ma_key={r['ma_key']}, "
                  f"kh_moi_tw={r['kh_moi_tw']/1e6:.1f}M, kh_moi_dp={r['kh_moi_dp']/1e6:.1f}M")
    
    # ── Xây dựng PGD_XA_MAP ──
    print(f"\n{'─'*40}")
    print("🗺️ Bước 2: Kiểm tra PGD_XA_MAP")
    print(f"{'─'*40}")
    all_xa_map: dict[str, list[str]] = {}
    for ten_pgd in DS_PGD:
        slug = _pgd_slug(ten_pgd)
        xas = PGD_XA_MAP.get(ten_pgd, [])
        all_xa_map[slug] = xas
    all_xa_set = set()
    for slug, xas in all_xa_map.items():
        all_xa_set.update(xas)
    print(f"  → Tổng số xã trong PGD_XA_MAP: {len(all_xa_set)}")
    
    # So sánh xã trong KHTD vs PGD_XA_MAP
    xa_kh_norm = set(str(x).strip().casefold() for x in xa_kh_set if pd.notna(x) and str(x).strip())
    xa_map_norm = set(str(x).strip().casefold() for x in all_xa_set if pd.notna(x) and str(x).strip())
    xa_thieu = xa_map_norm - xa_kh_norm
    xa_extra = xa_kh_norm - xa_map_norm
    print(f"  → Xã trong MAP nhưng không trong KHTD: {len(xa_thieu)}")
    if xa_thieu:
        for x in sorted(xa_thieu)[:20]:
            print(f"    - {x}")
    print(f"  → Xã trong KHTD nhưng không trong MAP: {len(xa_extra)}")
    if xa_extra:
        for x in sorted(xa_extra)[:20]:
            print(f"    - {x}")
    
    # ── Bước 3: So sánh CN vs Xã cho KH ──
    print(f"\n{'─'*40}")
    print("📊 Bước 3: So sánh KH — CN level vs Xã level")
    print(f"{'─'*40}")
    
    df_kh_raw = df_kh.copy()
    df_kh_raw["ten_pgd"] = df_kh_raw["pgd_slug"].apply(_slug_to_ten)
    df_kh_raw["ma_ct"] = df_kh_raw["ma_key"].map(_MAKEY_TO_MACT).fillna(-1).astype(int)
    for c in ("kh_moi_tw", "kh_moi_dp"):
        df_kh_raw[c] = pd.to_numeric(df_kh_raw[c], errors="coerce").fillna(0)
    
    # CN-level: group by (ten_pgd, ma_key, nguon)
    kh_cn = (
        df_kh_raw.groupby(["pgd_slug", "ma_key", "nguon"], as_index=False)
        .agg(
            ten_pgd=("ten_pgd", "first"),
            ten_ct=("ten_ct", "first"),
            kh_tw=("kh_moi_tw", "sum"),
            kh_dp=("kh_moi_dp", "sum"),
        )
    )
    kh_cn["kh_vnd"] = kh_cn.apply(
        lambda r: r["kh_tw"] if r["nguon"] == "TW" else r["kh_dp"], axis=1
    )
    kh_cn["kh_trieu"] = kh_cn["kh_vnd"] / 1e6
    
    # Xã-level: group by (pgd_slug, xa, ma_key, nguon)
    kh_xa = (
        df_kh_raw.groupby(["pgd_slug", "xa", "ma_key", "nguon"], as_index=False)
        .agg(
            ten_pgd=("ten_pgd", "first"),
            ten_ct=("ten_ct", "first"),
            kh_tw=("kh_moi_tw", "sum"),
            kh_dp=("kh_moi_dp", "sum"),
        )
    )
    kh_xa["kh_vnd"] = kh_xa.apply(
        lambda r: r["kh_tw"] if r["nguon"] == "TW" else r["kh_dp"], axis=1
    )
    kh_xa["kh_trieu"] = kh_xa["kh_vnd"] / 1e6
    
    # Tổng bằng CN-level
    tong_cn = kh_cn["kh_vnd"].sum()
    tong_xa = kh_xa["kh_vnd"].sum()
    print(f"  TỔNG KH (CN-level): {tong_cn/1e6:,.1f} triệu ({(tong_cn/1e9):,.2f} tỷ)")
    print(f"  TỔNG KH (Xã-level): {tong_xa/1e6:,.1f} triệu ({(tong_xa/1e9):,.2f} tỷ)")
    chenh = tong_cn - tong_xa
    print(f"  CHÊNH LỆCH: {chenh/1e6:,.1f} triệu ({chenh/1e9:,.2f} tỷ)")
    if abs(chenh) < 1000:  # < 1.000đ = coi như bằng
        print("  ✅ KHÔNG chênh lệch (sai số < 1.000đ)")
    else:
        print(f"  ❌ CÓ CHÊNH LỆCH! Nguyên nhân có thể:")
        print(f"     1. Dòng xã trống/None → không được tính vào xã-level")
        print(f"     2. Giá trị xa lạ (không trong PGD_XA_MAP)")

    # So sánh từng (pgd_slug, ma_key, nguon)
    print(f"\n  So sánh chi tiết theo (PGD, Mã CT, Nguồn):")
    print(f"  {'PGD':25s} {'Mã CT':15s} {'Nguồn':6s} {'CN (trđ)':12s} {'Xã (trđ)':12s} {'Chênh':12s}")
    print(f"  {'─'*80}")
    
    merge_cn_xa = kh_cn.merge(
        kh_xa.groupby(["pgd_slug", "ma_key", "nguon"])["kh_vnd"].sum().reset_index(),
        on=["pgd_slug", "ma_key", "nguon"],
        how="outer",
        suffixes=("_cn", "_xa"),
    )
    merge_cn_xa["kh_cn"] = pd.to_numeric(merge_cn_xa.get("kh_vnd_cn", 0), errors="coerce").fillna(0)
    merge_cn_xa["kh_xa"] = pd.to_numeric(merge_cn_xa.get("kh_vnd_xa", 0), errors="coerce").fillna(0)
    merge_cn_xa["chenh"] = merge_cn_xa["kh_cn"] - merge_cn_xa["kh_xa"]
    merge_cn_xa["chenh_trieu"] = merge_cn_xa["chenh"] / 1e6
    
    chenh_items = merge_cn_xa[abs(merge_cn_xa["chenh"]) > 1].copy()  # > 1đ
    if len(chenh_items) > 0:
        for _, r in chenh_items.iterrows():
            ten_pgd_disp = _slug_to_ten(r["pgd_slug"])
            mk = r["ma_key"]
            print(f"  ❌ {ten_pgd_disp:25s} {mk:15s} {r['nguon']:6s} "
                  f"{r['kh_cn']/1e6:10.1f}  {r['kh_xa']/1e6:10.1f}  {r['chenh_trieu']:10.1f}")
            # Tìm các dòng xã trống cho PGD+ma_key này
            empty = df_kh_raw[
                (df_kh_raw["pgd_slug"] == r["pgd_slug"]) &
                (df_kh_raw["ma_key"] == r["ma_key"]) &
                (df_kh_raw["nguon"] == r["nguon"]) &
                ((df_kh_raw["xa"].isna()) | (df_kh_raw["xa"] == ""))
            ]
            if len(empty) > 0:
                for _, e in empty.iterrows():
                    val = e["kh_moi_tw"] if e["nguon"] == "TW" else e["kh_moi_dp"]
                    print(f"    → Dòng xã trống: {val/1e6:.1f} triệu")
    else:
        print(f"  ✅ Tất cả các cặp (PGD, Mã CT, Nguồn) đều khớp!")
    
    # ── Bước 4: Đọc HSTD và so sánh TH ──
    print(f"\n{'─'*40}")
    print("📥 Bước 4: Đọc HSTD và so sánh TH (Thực hiện)")
    print(f"{'─'*40}")
    
    df_hstd = _doc_hstd()
    if df_hstd.empty:
        print("⚠️ Không có HSTD, bỏ qua so sánh TH")
        return
    
    # Tính TH theo CN-level (PGD + mã CT + nguồn)
    dh = df_hstd.copy()
    dh["_mc"] = pd.to_numeric(dh[COT_MA_CHUONG_TRINH], errors="coerce").fillna(-1).astype(int)
    dh["_nv"] = pd.to_numeric(dh[COT_NGUON_VON], errors="coerce").fillna(0).astype(int)
    if COT_TONG_DU_NO in dh.columns:
        dh["_dn"] = pd.to_numeric(dh[COT_TONG_DU_NO], errors="coerce").fillna(0)
    else:
        cols_dn = [c for c in (COT_DU_NO_TH, COT_DU_NO_QH, COT_DU_NO_KHOANH) if c in dh.columns]
        for c in cols_dn:
            dh[c] = pd.to_numeric(dh[c], errors="coerce").fillna(0)
        dh["_dn"] = dh[cols_dn].sum(axis=1)
    
    # TH CN-level (PGD + mã CT + nguồn)
    th_cn = dh.groupby([COT_TEN_PGD, "_mc", "_nv"])["_dn"].sum().reset_index()
    th_cn["th_trieu"] = th_cn["_dn"] / 1e6
    tong_th_cn = th_cn["_dn"].sum()
    print(f"  TỔNG TH (CN-level): {tong_th_cn/1e6:,.1f} triệu ({tong_th_cn/1e9:,.2f} tỷ)")
    
    # TH Xã-level (PGD + xã + mã CT + nguồn)
    dh["_xa_key"] = dh[COT_TEN_XA].map(
        lambda value: tim_ten_xa_trong_hstd(str(value).strip()).casefold()
        if pd.notna(value) else ""
    )
    th_xa = dh.groupby([COT_TEN_PGD, "_xa_key", "_mc", "_nv"])["_dn"].sum().reset_index()
    th_xa["th_trieu"] = th_xa["_dn"] / 1e6
    tong_th_xa = th_xa["_dn"].sum()
    print(f"  TỔNG TH (Xã-level): {tong_th_xa/1e6:,.1f} triệu ({tong_th_xa/1e9:,.2f} tỷ)")
    
    th_chenh = tong_th_cn - tong_th_xa
    print(f"  CHÊNH LỆCH TH: {th_chenh/1e6:,.1f} triệu ({th_chenh/1e9:,.2f} tỷ)")
    if abs(th_chenh) < 1000:
        print(f"  ✅ TH CN-level == TH Xã-level")
    else:
        print(f"  ❌ TH CÓ CHÊNH LỆCH! Kiểm tra xã trống/NaN trong HSTD")
        xa_na = dh[COT_TEN_XA].isna().sum()
        xa_empty = (dh[COT_TEN_XA] == "").sum() if COT_TEN_XA in dh.columns else 0
        print(f"    → Số dòng HSTD có xã NaN: {xa_na}")
        print(f"    → Số dòng HSTD có xã rỗng: {xa_empty}")
    
    # ── Bước 5: So sánh KH vs TH ──
    print(f"\n{'─'*40}")
    print("📊 Bước 5: So sánh KH vs TH theo CN-level")
    print(f"{'─'*40}")
    
    # Xây map TH: (PGD, mã CT, nguồn) → TH (triệu)
    th_map = {
        (r[COT_TEN_PGD], int(r["_mc"]), int(r["_nv"])): r["th_trieu"]
        for _, r in th_cn.iterrows()
    }
    
    chenh_list = []
    for _, r in kh_cn.iterrows():
        nguon_int = 1 if r["nguon"] == "TW" else 2
        kh_trieu = r["kh_trieu"]
        th_trieu = th_map.get((r["ten_pgd"], int(r["ma_ct"]), nguon_int), 0.0)
        if kh_trieu > 0 or th_trieu > 0:
            chenh_list.append({
                "PGD": r["ten_pgd"],
                "Mã CT": r["ma_key"],
                "Chương trình": r["ten_ct"],
                "Nguồn": r["nguon"],
                "KH (triệu)": round(kh_trieu, 1),
                "TH (triệu)": round(th_trieu, 1),
                "Chênh lệch TH-KH": round(th_trieu - kh_trieu, 1),
                "% TH/KH": round(th_trieu / kh_trieu * 100, 1) if kh_trieu > 0 else 0,
            })
    
    df_ss = pd.DataFrame(chenh_list)
    if not df_ss.empty:
        print(f"\n  Tổng hợp KH vs TH (theo CN-level):\n")
        print(f"  {'PGD':25s} {'Mã CT':12s} {'Nguồn':6s} {'KH':10s} {'TH':10s} {'Chênh':10s} {'%':8s}")
        print(f"  {'─'*80}")
        # In 20 dòng có chênh lệch lớn nhất
        df_ss_abs = df_ss.copy()
        df_ss_abs["|chenh|"] = df_ss_abs["Chênh lệch TH-KH"].abs()
        df_ss_abs = df_ss_abs.sort_values("|chenh|", ascending=False).head(30)
        for _, r in df_ss_abs.iterrows():
            print(f"  {r['PGD']:25s} {str(r['Mã CT']):12s} {r['Nguồn']:6s} "
                  f"{r['KH (triệu)']:>8.1f}  {r['TH (triệu)']:>8.1f}  "
                  f"{r['Chênh lệch TH-KH']:>8.1f}  {r['% TH/KH']:>6.1f}%")
        
        # Dòng tổng
        print(f"  {'─'*80}")
        tong_kh = df_ss["KH (triệu)"].sum()
        tong_th = df_ss["TH (triệu)"].sum()
        print(f"  {'TỔNG CỘNG':25s} {'':12s} {'':6s} "
              f"{tong_kh:>8.1f}  {tong_th:>8.1f}  {tong_th - tong_kh:>8.1f}")
    
    # ── Bước 6: Phát hiện xã bị thiếu ──
    print(f"\n{'─'*40}")
    print("🔎 Bước 6: Phát hiện xã bị thiếu trong KHTD")
    print(f"{'─'*40}")
    
    # Xã nào có trong PGD_XA_MAP nhưng không có trong KHTD
    for slug, xas in all_xa_map.items():
        ten_pgd = _slug_to_ten(slug)
        kh_xas = set(df_kh_raw[df_kh_raw["pgd_slug"] == slug]["xa"].dropna().unique())
        for xa in xas:
            xa_cf = str(xa).strip().casefold()
            found = False
            for kx in kh_xas:
                if str(kx).strip().casefold() == xa_cf:
                    found = True
                    break
            if not found:
                print(f"  ⚠️ {ten_pgd} — thiếu xã '{xa}' trong KHTD")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 80)
    print("🔬 KIỂM TRA SỐ LIỆU KẾ HOẠCH TÍN DỤNG (KHTD)")
    print("   So sánh dữ liệu giữa cấp Chi nhánh và cấp Xã")
    print("=" * 80)
    
    nam, thang, dot = _tim_dot_hien_tai()
    kiem_tra_khtd(nam, thang, dot)
    
    print(f"\n{'='*80}")
    print("✅ KIỂM TRA HOÀN TẤT")
    print(f"{'='*80}")
