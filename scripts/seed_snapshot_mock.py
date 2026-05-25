"""Sinh dữ liệu ảo cho 4 loại snapshot: HSTD, NQ11, GQVL, CDTOTKVV.

Dùng để test tab So sánh kỳ (So sánh 2 kỳ / So sánh mốc 31/12).
Chạy: python scripts/seed_snapshot_mock.py
"""
from __future__ import annotations

import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

random.seed(42)

THANG = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]

DS_PGD = [
    "PGD Long Thành", "PGD Trảng Bom", "PGD Long Khánh",
    "PGD Xuân Lộc", "PGD Định Quán", "PGD Vĩnh Cửu",
    "PGD Tân Phú", "PGD Thống Nhất", "PGD Cẩm Mỹ",
    "PGD Nhơn Trạch", "PGD Bình Long", "PGD Lộc Ninh",
    "PGD Bình Phước", "PGD Phước Long", "PGD Bù Đăng",
    "PGD Đồng Phú", "PGD Chơn Thành", "PGD Bù Đốp",
    "PGD Bù Gia Mập", "PGD Phú Riềng", "PGD Hớn Quản",
]

# ── HSTD base data per PGD (triệu đồng) ──
# (du_no_base, nqh_pct, khoanh_pct, so_ho, so_ku)
# nqh_pct and khoanh_pct will be scaled differently for each PGD
TDN_BASE: dict[str, float] = {
    "PGD Long Thành": 450_000, "PGD Trảng Bom": 520_000,
    "PGD Long Khánh": 380_000, "PGD Xuân Lộc": 410_000,
    "PGD Định Quán": 350_000, "PGD Vĩnh Cửu": 290_000,
    "PGD Tân Phú": 270_000, "PGD Thống Nhất": 310_000,
    "PGD Cẩm Mỹ": 240_000, "PGD Nhơn Trạch": 330_000,
    "PGD Bình Long": 200_000, "PGD Lộc Ninh": 180_000,
    "PGD Bình Phước": 250_000, "PGD Phước Long": 160_000,
    "PGD Bù Đăng": 220_000, "PGD Đồng Phú": 150_000,
    "PGD Chơn Thành": 190_000, "PGD Bù Đốp": 120_000,
    "PGD Bù Gia Mập": 140_000, "PGD Phú Riềng": 130_000,
    "PGD Hớn Quản": 110_000,
}

NQH_PCT: dict[str, float] = {
    "PGD Long Thành": 0.8, "PGD Trảng Bom": 1.5,
    "PGD Long Khánh": 2.8, "PGD Xuân Lộc": 1.1,
    "PGD Định Quán": 0.9, "PGD Vĩnh Cửu": 1.3,
    "PGD Tân Phú": 0.6, "PGD Thống Nhất": 3.2,
    "PGD Cẩm Mỹ": 1.8, "PGD Nhơn Trạch": 0.7,
    "PGD Bình Long": 0.5, "PGD Lộc Ninh": 1.0,
    "PGD Bình Phước": 2.1, "PGD Phước Long": 0.9,
    "PGD Bù Đăng": 1.6, "PGD Đồng Phú": 0.4,
    "PGD Chơn Thành": 1.2, "PGD Bù Đốp": 0.3,
    "PGD Bù Gia Mập": 0.8, "PGD Phú Riềng": 0.7,
    "PGD Hớn Quản": 0.5,
}

KHOANH_PCT: dict[str, float] = {
    "PGD Long Thành": 0.3, "PGD Trảng Bom": 0.5,
    "PGD Long Khánh": 1.2, "PGD Xuân Lộc": 0.4,
    "PGD Định Quán": 0.2, "PGD Vĩnh Cửu": 0.6,
    "PGD Tân Phú": 0.1, "PGD Thống Nhất": 1.5,
    "PGD Cẩm Mỹ": 0.7, "PGD Nhơn Trạch": 0.2,
    "PGD Bình Long": 0.1, "PGD Lộc Ninh": 0.3,
    "PGD Bình Phước": 0.9, "PGD Phước Long": 0.2,
    "PGD Bù Đăng": 0.5, "PGD Đồng Phú": 0.1,
    "PGD Chơn Thành": 0.4, "PGD Bù Đốp": 0.0,
    "PGD Bù Gia Mập": 0.2, "PGD Phú Riềng": 0.1,
    "PGD Hớn Quản": 0.1,
}

# Monthly growth multipliers for each PGD (to create variation between months)
GROWTH_PGD: dict[str, float] = {
    pgd: round(random.uniform(0.98, 1.05), 4) for pgd in DS_PGD
}

# NQH trend: some PGDs improve, some worsen
NQH_TREND: dict[str, float] = {
    pgd: round(random.uniform(-0.15, 0.25), 2) for pgd in DS_PGD
}


def make_hstd():
    import db
    print("[HSTD] Generating snapshots...")
    so_dong = 0
    with db.get_conn() as conn:
        for mi, ky in enumerate(THANG):
            ngay_sl = f"{ky}-15"
            for pgd in DS_PGD:
                base = TDN_BASE[pgd] * (GROWTH_PGD[pgd] ** mi)
                nqh_pct = NQH_PCT[pgd] + NQH_TREND[pgd] * mi
                nqh_pct = max(0.1, nqh_pct)
                khoanh_pct = max(0.05, KHOANH_PCT[pgd])

                tong_du_no = base * (1 + random.uniform(-0.03, 0.03))
                du_no_qh = tong_du_no * nqh_pct / 100
                du_no_khoanh = tong_du_no * khoanh_pct / 100
                du_no_th = tong_du_no - du_no_qh - du_no_khoanh
                so_ho = int(tong_du_no / random.uniform(30, 55))
                so_ku = int(so_ho * random.uniform(1.05, 1.4))
                gn_nam = tong_du_no * (mi + 1) * 0.06

                conn.execute(
                    """INSERT OR REPLACE INTO hstd_snapshot
                    (ky, ten_pgd, ma_ct, nguon_von, tong_du_no, du_no_th,
                     du_no_qh, du_no_khoanh, so_ho, so_ku, gn_nam, ngay_so_lieu, created_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (ky, pgd, "ALL", "ALL",
                     round(tong_du_no, 2), round(du_no_th, 2),
                     round(du_no_qh, 2), round(du_no_khoanh, 2),
                     so_ho, so_ku,
                     round(gn_nam, 2), ngay_sl, "seed_mock"),
                )
                so_dong += 1

            # CN total row
            conn.execute(
                """SELECT SUM(tong_du_no), SUM(du_no_th), SUM(du_no_qh),
                   SUM(du_no_khoanh), SUM(so_ho), SUM(so_ku), SUM(gn_nam)
                   FROM hstd_snapshot WHERE ky=? AND ma_ct='ALL' AND nguon_von='ALL'""",
                (ky,),
            )
            row = conn.execute(
                "SELECT * FROM hstd_snapshot WHERE ky=? AND ma_ct='ALL' AND nguon_von='ALL' LIMIT 1",
                (ky,),
            ).fetchone()
            if row is None:
                t, th, qh, kh, h, k, g = 0, 0, 0, 0, 0, 0, 0
                for pgd in DS_PGD:
                    r = conn.execute(
                        "SELECT tong_du_no,du_no_th,du_no_qh,du_no_khoanh,so_ho,so_ku,gn_nam "
                        "FROM hstd_snapshot WHERE ky=? AND ten_pgd=?", (ky, pgd),
                    ).fetchone()
                    if r:
                        t += r["tong_du_no"]; th += r["du_no_th"]
                        qh += r["du_no_qh"]; kh += r["du_no_khoanh"]
                        h += r["so_ho"]; k += r["so_ku"]; g += r["gn_nam"]
                conn.execute(
                    """INSERT OR REPLACE INTO hstd_snapshot
                    (ky, ten_pgd, ma_ct, nguon_von, tong_du_no, du_no_th,
                     du_no_qh, du_no_khoanh, so_ho, so_ku, gn_nam, ngay_so_lieu, created_by)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (ky, "__CN__", "ALL", "ALL", round(t, 2), round(th, 2),
                     round(qh, 2), round(kh, 2), int(h), int(k),
                     round(g, 2), ngay_sl, "seed_mock"),
                )
                so_dong += 1
        conn.commit()
    print(f"  [OK] HSTD: {so_dong} rows ({len(THANG)} months x {len(DS_PGD)} PGD + CN)")


def make_nq11():
    import db
    print("[NQ11] Generating snapshots...")
    so_dong = 0
    with db.get_conn() as conn:
        for ky in THANG:
            ngay_bc = f"{ky}-10"
            for pgd in DS_PGD:
                base = TDN_BASE[pgd] * 0.08
                tong_du_no = base * (1 + random.uniform(-0.1, 0.1))
                no_qh = tong_du_no * max(0.01, NQH_PCT[pgd] / 100 * 0.5)
                no_th = tong_du_no - no_qh
                so_kh = int(tong_du_no / random.uniform(40, 80))
                gn_nam = tong_du_no * 0.15
                conn.execute(
                    """INSERT OR REPLACE INTO nq11_snapshot
                    (ky, ten_pgd, tong_du_no, no_th, no_qh, so_kh, gn_nam, ngay_bc, created_by)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (ky, pgd, round(tong_du_no, 2), round(no_th, 2), round(no_qh, 2),
                     so_kh, round(gn_nam, 2), ngay_bc, "seed_mock"),
                )
                so_dong += 1
            # CN total
            t, th, qh, kh, g = 0, 0, 0, 0, 0
            for pgd in DS_PGD:
                r = conn.execute(
                    "SELECT tong_du_no,no_th,no_qh,so_kh,gn_nam "
                    "FROM nq11_snapshot WHERE ky=? AND ten_pgd=?", (ky, pgd),
                ).fetchone()
                if r:
                    t += r["tong_du_no"]; th += r["no_th"]
                    qh += r["no_qh"]; kh += r["so_kh"]; g += r["gn_nam"]
            conn.execute(
                """INSERT OR REPLACE INTO nq11_snapshot
                (ky, ten_pgd, tong_du_no, no_th, no_qh, so_kh, gn_nam, ngay_bc, created_by)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (ky, "__CN__", round(t, 2), round(th, 2), round(qh, 2),
                 int(kh), round(g, 2), ngay_bc, "seed_mock"),
            )
            so_dong += 1
        conn.commit()
    print(f"  [OK] NQ11: {so_dong} rows")


def make_gqvl():
    import db
    print("[GQVL] Generating snapshots...")
    so_dong = 0
    with db.get_conn() as conn:
        for ky in THANG:
            for pgd in DS_PGD:
                base = TDN_BASE[pgd] * 0.12
                dn_th = base * (1 + random.uniform(-0.08, 0.08))
                dn_qh = dn_th * max(0.005, NQH_PCT[pgd] / 100 * 0.6)
                dn_khoanh = dn_th * max(0.001, KHOANH_PCT[pgd] / 100 * 0.3)
                so_kh = int(base / random.uniform(35, 70))
                gn_nam = base * 0.10
                conn.execute(
                    """INSERT OR REPLACE INTO gqvl_snapshot
                    (ky, ten_pgd, dn_th, dn_qh, dn_khoanh, so_kh, gn_nam, created_by)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (ky, pgd, round(dn_th, 2), round(dn_qh, 2),
                     round(dn_khoanh, 2), so_kh, round(gn_nam, 2), "seed_mock"),
                )
                so_dong += 1
            # CN total
            t, q, kh, k, g = 0, 0, 0, 0, 0
            th_acc = 0
            for pgd in DS_PGD:
                r = conn.execute(
                    "SELECT dn_th,dn_qh,dn_khoanh,so_kh,gn_nam "
                    "FROM gqvl_snapshot WHERE ky=? AND ten_pgd=?", (ky, pgd),
                ).fetchone()
                if r:
                    th_acc += r["dn_th"]; q += r["dn_qh"]
                    kh += r["dn_khoanh"]; k += r["so_kh"]; g += r["gn_nam"]
            conn.execute(
                """INSERT OR REPLACE INTO gqvl_snapshot
                (ky, ten_pgd, dn_th, dn_qh, dn_khoanh, so_kh, gn_nam, created_by)
                VALUES (?,?,?,?,?,?,?,?)""",
                (ky, "__CN__", round(th_acc, 2), round(q, 2),
                 round(kh, 2), int(k), round(g, 2), "seed_mock"),
            )
            so_dong += 1
        conn.commit()
    print(f"  [OK] GQVL: {so_dong} rows")


def make_cdtotkvv():
    import db
    print("[CDTOTKVV] Generating snapshots...")
    so_dong = 0
    with db.get_conn() as conn:
        for ky in THANG:
            for pgd in DS_PGD:
                so_to = random.randint(15, 60)
                so_tot = random.randint(int(so_to * 0.3), int(so_to * 0.7))
                so_kha = random.randint(int(so_to * 0.1), int(so_to * 0.4))
                so_tb = random.randint(0, int(so_to * 0.2))
                so_yeu = so_to - so_tot - so_kha - so_tb
                so_yeu = max(0, so_yeu)
                diem_tb = round(random.uniform(65, 95), 1)
                conn.execute(
                    """INSERT OR REPLACE INTO cdtotkvv_snapshot
                    (ky, ten_pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb, created_by)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (ky, pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb, "seed_mock"),
                )
                so_dong += 1
            # CN total
            st_, t_, k_, tb_, y_, d_ = 0, 0, 0, 0, 0, 0
            cnt = 0
            for pgd in DS_PGD:
                r = conn.execute(
                    "SELECT so_to,so_tot,so_kha,so_tb,so_yeu,diem_tb "
                    "FROM cdtotkvv_snapshot WHERE ky=? AND ten_pgd=?", (ky, pgd),
                ).fetchone()
                if r:
                    st_ += r["so_to"]; t_ += r["so_tot"]; k_ += r["so_kha"]
                    tb_ += r["so_tb"]; y_ += r["so_yeu"]; d_ += r["diem_tb"]
                    cnt += 1
            conn.execute(
                """INSERT OR REPLACE INTO cdtotkvv_snapshot
                (ky, ten_pgd, so_to, so_tot, so_kha, so_tb, so_yeu, diem_tb, created_by)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (ky, "__CN__", st_, t_, k_, tb_, y_, round(d_ / cnt, 1) if cnt else 0, "seed_mock"),
            )
            so_dong += 1
        conn.commit()
    print(f"  [OK] CDTOTKVV: {so_dong} rows")


def main():
    print("=" * 60)
    print("Seed Snapshot Mock Data - 5 months (2026-01 -> 2026-05)")
    print(f"   {len(DS_PGD)} PGD x 4 data types")
    print("=" * 60)
    make_hstd()
    make_nq11()
    make_gqvl()
    make_cdtotkvv()
    print("\nDone! Open app -> tab 'So sanh ky' to test.")
    print("   Compare 2 periods: pick 2026-01 vs 2026-05 for max delta.")
    print("   Compare year-end: use HSTD/NQ11/GQVL/CDTOTKVV tabs.")


if __name__ == "__main__":
    main()
