"""
Script kiểm tra so sánh số liệu Thực hiện (TH) KHTD giữa:
  - Cấp Chi nhánh (CN) — từ _tinh_thuc_hien_khtd_cn()
  - Tổng 95 xã/phường — từ _tinh_thuc_hien_theo_ct() cho từng xã rồi cộng dồn

Kết quả in ra bảng so sánh từng ma_key, cảnh báo nếu có chênh lệch > 0.01.
"""
import sys
import os
from pathlib import Path
from collections import defaultdict

# Thêm project root vào sys.path
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

import pandas as pd

from config import CACHE_HSTD, CACHE_GQVL, PGD_XA_MAP, CHUONG_TRINH_KHTD
from config import COT_TEN_PGD, COT_TEN_XA, COT_MA_CHUONG_TRINH, COT_NGUON_VON
from config import COT_TONG_DU_NO, COT_DU_NO_TH

from tabs.tab_khtd import _tinh_thuc_hien_khtd_cn, _tinh_thuc_hien_theo_ct
from tabs.tab_khtd_nhap import _norm_xa_text


def main():
    # ── 1. Đọc dữ liệu ──────────────────────────────────────────────────────
    print("=" * 90)
    print("  KIỂM TRA SỐ LIỆU THỰC HIỆN (TH) KHTD: CHI NHÁNH vs TỔNG 95 XÃ")
    print("=" * 90)

    hstd_path = CACHE_HSTD
    if not os.path.exists(hstd_path):
        print(f"\n❌ LỖI: Không tìm thấy HSTD cache tại: {hstd_path}")
        return

    print(f"\n📂 Đang đọc HSTD từ cache...")
    df_full = pd.read_parquet(hstd_path)
    print(f"   HSTD: {len(df_full):,} dòng, {len(df_full.columns)} cột")
    print(f"   Các cột: {list(df_full.columns)}")

    gqvl_path = CACHE_GQVL
    df_gqvl = None
    if os.path.exists(gqvl_path):
        print(f"\n📂 Đang đọc GQVL từ cache...")
        df_gqvl = pd.read_parquet(gqvl_path)
        print(f"   GQVL: {len(df_gqvl):,} dòng")
    else:
        print(f"\n⚠️ Không tìm thấy GQVL cache tại: {gqvl_path}")

    # ── 2. TH cấp Chi nhánh ──────────────────────────────────────────────────
    print(f"\n{'─' * 90}")
    print("  BƯỚC 1: Tính TH cấp Chi nhánh...")
    th_cn, th_gqvl_detail = _tinh_thuc_hien_khtd_cn(df_full, df_gqvl)
    print(f"   Số ma_key: {len(th_cn)}")
    for mk, v in sorted(th_cn.items()):
        print(f"     {mk:30s} = {v:>15.2f}")

    # ── 3. TH từng xã → tổng ─────────────────────────────────────────────────
    print(f"\n{'─' * 90}")
    print("  BƯỚC 2: Duyệt 95 xã/phường và cộng dồn TH...")

    tong_th_xa = defaultdict(float)
    xa_co_du_lieu = 0
    xa_khong_du_lieu = 0
    ds_xa_khong_dl: list[str] = []

    # Đếm tổng số xã trong PGD_XA_MAP
    tong_so_xa = sum(len(v) for v in PGD_XA_MAP.values())
    print(f"   Tổng số xã trong PGD_XA_MAP: {tong_so_xa}")

    for pgd, ds_xa in PGD_XA_MAP.items():
        pgd_strip = pgd.strip()

        # Pre-filter by PGD for speed
        s_pgd = df_full[COT_TEN_PGD].astype(str).str.strip()
        df_pgd = df_full[s_pgd == pgd_strip]

        if df_pgd.empty:
            print(f"   ⚠️ PGD '{pgd}' không có dữ liệu trong HSTD")
            for xa_ten in ds_xa:
                xa_khong_du_lieu += 1
                ds_xa_khong_dl.append(f"{pgd} / {xa_ten}")
            continue

        for xa_ten in ds_xa:
            xa_norm = _norm_xa_text(xa_ten)
            s_xa = df_pgd[COT_TEN_XA].map(_norm_xa_text)
            df_xa = df_pgd[s_xa == xa_norm]

            if df_xa.empty:
                xa_khong_du_lieu += 1
                ds_xa_khong_dl.append(f"{pgd} / {xa_ten}")
                continue

            th_xa = _tinh_thuc_hien_theo_ct(df_xa)
            for mk, val in th_xa.items():
                tong_th_xa[mk] += float(val)
            xa_co_du_lieu += 1

    print(f"   ✅ Xã có dữ liệu: {xa_co_du_lieu}")
    print(f"   ⚠️ Xã không có dữ liệu: {xa_khong_du_lieu}")
    if ds_xa_khong_dl:
        print(f"   Danh sách xã không có dữ liệu:")
        for item in ds_xa_khong_dl:
            print(f"     - {item}")

    # ── 4. Bảng so sánh ──────────────────────────────────────────────────────
    print(f"\n{'=' * 100}")
    print(f"{'ma_key':30s} {'TH_CN (VND)':>18s} {'Tổng_Xã (VND)':>18s} {'Chênh_lệch':>18s} {'% lệch':>10s}")
    print(f"{'─' * 100}")

    all_keys = sorted(set(th_cn.keys()) | set(tong_th_xa.keys()))
    co_lech_keys: list[tuple[str, float, float, float]] = []
    tong_lech = 0.0

    for mk in all_keys:
        cn = th_cn.get(mk, 0.0)
        xa = tong_th_xa.get(mk, 0.0)
        lech = abs(cn - xa)
        pct = (lech / cn * 100) if cn != 0 else (100.0 if xa != 0 else 0.0)
        flag = " ⚠️ CHÊNH LỆCH" if lech > 0.01 else ""
        if lech > 0.01:
            co_lech_keys.append((mk, cn, xa, lech))
            tong_lech += lech
        print(f"{mk:30s} {cn:>18.2f} {xa:>18.2f} {lech:>18.2f} {pct:>9.2f}%{flag}")

    # ── 5. Kiểm tra tổng GQVL theo cặp ──────────────────────────────────────
    print(f"\n{'─' * 100}")
    print("  KIỂM TRA TỔNG GQVL THEO CẶP (sub-keys):")

    for pair_name, keys in [
        ("3_TW (NHCSXH+NSNN)",   ["3_TW_NHCSXH", "3_TW_NSNN"]),
        ("3_DP (TINH+XA)",        ["3_DP_TINH", "3_DP_XA"]),
        ("6_NSVSMT_DP (TINH+XA)", ["6_DP_TINH", "6_DP_XA"]),
    ]:
        cn_sum = sum(th_cn.get(k, 0.0) for k in keys)
        xa_sum = sum(tong_th_xa.get(k, 0.0) for k in keys)
        lech = abs(cn_sum - xa_sum)
        flag = " ⚠️" if lech > 0.01 else ""
        print(f"   {pair_name:30s}: CN={cn_sum:>18.2f}  Xã={xa_sum:>18.2f}  Lệch={lech:>10.2f}{flag}")

    # ── 6. Kiểm tra tổng thể ────────────────────────────────────────────────
    print(f"\n{'═' * 100}")

    if not co_lech_keys:
        print("\n✅ KẾT LUẬN: KHÔNG có chênh lệch giữa CN và tổng 95 xã.")
        print("   Số liệu Thực hiện đồng nhất hoàn toàn giữa 2 cấp.")
    else:
        print(f"\n⚠️ KẾT LUẬN: CÓ {len(co_lech_keys)} ma_key chênh lệch (>{'%.2f' % 0.01} VND).")
        print(f"   Tổng chênh lệch: {tong_lech:,.2f} VND")
        print(f"\n   Danh sách ma_key chênh lệch:")
        print(f"   {'ma_key':30s} {'TH_CN':>18s} {'Tổng_Xã':>18s} {'Lệch':>18s}")
        print(f"   {'─' * 84}")
        for mk, cn, xa, lech in sorted(co_lech_keys, key=lambda x: -x[3]):
            print(f"   {mk:30s} {cn:>18.2f} {xa:>18.2f} {lech:>18.2f}")

        # Phân loại nguyên nhân
        keys_gqvl = {"3_TW_NHCSXH", "3_TW_NSNN", "3_DP_TINH", "3_DP_XA"}
        keys_nsvsmt = {"6_DP_TINH", "6_DP_XA"}
        lech_gqvl = [k for k in co_lech_keys if k[0] in keys_gqvl]
        lech_nsvsmt = [k for k in co_lech_keys if k[0] in keys_nsvsmt]
        lech_khac = [k for k in co_lech_keys if k[0] not in keys_gqvl and k[0] not in keys_nsvsmt]

        print(f"\n   🔍 PHÂN TÍCH NGUYÊN NHÂN:")
        if lech_gqvl:
            print(f"   - Có {len(lech_gqvl)} sub-key GQVL chênh lệch:")
            for mk, cn, xa, lech in lech_gqvl:
                print(f"       {mk:20s}: CN={cn:>15.2f} / Xã={xa:>15.2f} / Lệch={lech:>10.2f}")
            print(f"     → Nguyên nhân: Cấp CN dùng `tinh_th_gqvl_phan_tang()` (merge HSTD+GQVL theo số khế ước,")
            print(f"       phân tầng bằng PL_NV và Mã NĐT), cấp xã dùng chia đều 50/50.")
            print(f"       Đây là chênh lệch MONG ĐỢI do logic phân tầng khác nhau.")
        if lech_nsvsmt:
            print(f"   - Có {len(lech_nsvsmt)} sub-key NSVSMT ĐP chênh lệch:")
            for mk, cn, xa, lech in lech_nsvsmt:
                print(f"       {mk:20s}: CN={cn:>15.2f} / Xã={xa:>15.2f} / Lệch={lech:>10.2f}")
            print(f"     → Nguyên nhân: Cần kiểm tra thêm.")
        if lech_khac:
            print(f"   - Có {len(lech_khac)} ma_key khác chênh lệch (cần điều tra thêm):")
            for mk, cn, xa, lech in lech_khac:
                print(f"       {mk:20s}: CN={cn:>15.2f} / Xã={xa:>15.2f} / Lệch={lech:>10.2f}")


if __name__ == "__main__":
    main()
