# -*- coding: utf-8 -*-
"""Bước 3: dựng ánh xạ Mã thôn -> Điểm GD cho Hội sở CN Đồng Nai, đối chiếu PDF.

Nguồn đối chiếu: 4601_RPT_DNO_XA_DIEMGD_31072026_3010.pdf (số liệu 31/07/2026,
đơn vị triệu đồng) — mỗi Điểm GD có: số tổ, KH vay, tổng dư nợ.

Phương pháp:
  1. Chỉ tính phần dư nợ thuộc Điểm GD: Hình thức vay != 1 (loại vay trực tiếp).
  2. Chỉ tiêu so khớp tính trên dòng có Tổng dư nợ > 0 (dòng dư nợ 0 là hồ sơ đã
     tất toán, vẫn giữ Ngày GDXA cũ nên làm lệch số tổ).
  3. Nhóm theo (Xã, Ngày GDXA):
       - khớp 1-1 duy nhất với 1 Điểm GD  -> nhận luôn
       - còn nhiều Điểm GD chưa gán mà tổng chỉ tiêu xấp xỉ cả nhóm -> duyệt tập con
         mã thôn để tách (bài toán Long Hưng ngày 18 và Tam Hiệp ngày 22).
  4. Mã thôn chỉ xuất hiện ở dòng thiếu Ngày GDXA (dư nợ 0) -> suy ra Điểm GD theo
     mã thôn cùng xã đã biết, nếu không thì đưa vào nhóm chưa xác định.

Kết quả: outputs/gom_dgd_hoi_so_20260906/06_ma_thon_dgd_hoi_so.json
Chạy:  venv\\Scripts\\python.exe outputs\\gom_dgd_hoi_so_20260906\\solve_mapping.py
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import pandas as pd

from analyze_hoi_so import nap_du_lieu
from analyze_metrics import PDF_DGD

OUT = Path(__file__).resolve().parent

DUNG_SAI_DU_NO = 200.0   # triệu đồng — PDF và HSTD lệch vài món lẻ (xem 07_kiem_chung)
DUNG_SAI_KH = 5          # số KH vay
TEN_COT_DGD_CHUA_XAC_DINH = "(chưa xác định)"


def _metrics(g: pd.DataFrame) -> tuple[int, int, float]:
    """(số tổ, số KH vay, tổng dư nợ triệu đồng) — chỉ tính dòng dư nợ > 0."""
    g = g[g["_dn"] > 0]
    return (int(g.loc[g["_to"] != "", "_to"].nunique()),
            int(g["_kh"].nunique()),
            round(float(g["_dn"].sum() / 1e6), 2))


def _khop(m: tuple[int, int, float], pdf: tuple[int, int, float]) -> bool:
    return (m[0] == pdf[0]
            and abs(m[1] - pdf[1]) <= DUNG_SAI_KH
            and abs(m[2] - pdf[2]) <= DUNG_SAI_DU_NO)


def _gop(per_mt: dict, ds_mt: list[str]) -> tuple[int, int, float]:
    return (sum(per_mt[m][0] for m in ds_mt),
            sum(per_mt[m][1] for m in ds_mt),
            round(sum(per_mt[m][2] for m in ds_mt), 2))


def _tach_tap_con(ma_thons: list[str], per_mt: dict, ds_dgd: list[tuple],
                  tim_tat_ca: bool = False) -> list[dict] | None:
    """Phân bổ tập mã thôn vào các Điểm GD sao cho khớp chỉ tiêu PDF.

    Trả về danh sách lời giải [{ten_dgd: [ma_thon,...]}, ...].
    tim_tat_ca=True -> liệt kê mọi lời giải để kiểm tra tính duy nhất.
    """
    muc_tieu = sorted(ds_dgd, key=lambda x: x[3])   # Điểm GD dư nợ nhỏ trước
    ket_qua_tat_ca: list[dict] = []
    loi_giai: dict[str, list[str]] = {}

    def _duyet(idx: int, con_lai: list[str]) -> bool:
        ten, to_pdf, kh_pdf, dn_pdf = muc_tieu[idx]
        if idx == len(muc_tieu) - 1:
            if _khop(_gop(per_mt, con_lai), (to_pdf, kh_pdf, dn_pdf)):
                loi_giai[ten] = list(con_lai)
                ket_qua_tat_ca.append(dict(loi_giai))
                loi_giai.pop(ten, None)
                return not tim_tat_ca
            return False
        for k in range(1, len(con_lai)):
            for bo in itertools.combinations(con_lai, k):
                if not _khop(_gop(per_mt, list(bo)), (to_pdf, kh_pdf, dn_pdf)):
                    continue
                loi_giai[ten] = list(bo)
                if _duyet(idx + 1, [x for x in con_lai if x not in bo]):
                    if not tim_tat_ca:
                        return True
                loi_giai.pop(ten, None)
        return False

    if not _duyet(0, list(ma_thons)) and not ket_qua_tat_ca:
        return None
    return ket_qua_tat_ca


def main() -> None:
    df = nap_du_lieu()
    d = df[df["_htv"] != 1].copy()
    d_co_du_no = d[d["_dn"] > 0]

    print(f"HSTD Hội sở: {len(df):,} dòng | dư nợ {df['_dn'].sum()/1e6:,.2f} triệu")
    print(f"Phần thuộc Điểm GD (HTV!=1, dư nợ>0): {len(d_co_du_no):,} dòng | "
          f"{d_co_du_no['_dn'].sum()/1e6:,.2f} triệu | PDF 681.418,00 triệu")

    ket_qua: dict[str, dict] = {}
    nhat_ky: list[str] = []
    canh_bao: list[str] = []
    chua_xd_ngay_trung: list[dict] = []

    for xa, ds_dgd in PDF_DGD.items():
        ket_qua[xa] = {}
        g_xa = d[d["_xa"] == xa]
        ds_ngay = sorted({int(x) for x in g_xa["_ngay"].dropna().unique()})
        print(f"\n--- {xa}: {len(ds_dgd)} Điểm GD | ngày GDXA {ds_ngay}")

        theo_ngay: dict[int, tuple] = {}
        for ngay in ds_ngay:
            g_n = g_xa[g_xa["_ngay"] == ngay]
            theo_ngay[ngay] = (_metrics(g_n), sorted(g_n["_mt"].unique()))

        con_lai_dgd = list(ds_dgd)

        # Lượt 1 — khớp 1-1 duy nhất
        for ngay in ds_ngay:
            m_n, ma_thons = theo_ngay[ngay]
            khang = [x for x in con_lai_dgd if _khop(m_n, (x[1], x[2], x[3]))]
            if len(khang) != 1:
                continue
            dgd = khang[0]
            ket_qua[xa][dgd[0]] = {"ngay_gdxa": ngay, "ma_thon": ma_thons,
                                   "m_hstd": m_n, "m_pdf": (dgd[1], dgd[2], dgd[3]),
                                   "cach": "khớp 1-1 theo ngày GDXA"}
            nhat_ky.append(f"{xa} | ngày {ngay} -> {dgd[0]}")
            con_lai_dgd.remove(dgd)
            print(f"  ngày {ngay:>2} -> {dgd[0]:<13} tổ {m_n[0]}/{dgd[1]} | KH {m_n[1]}/{dgd[2]}"
                  f" | dư nợ {m_n[2]:>10,.2f}/{dgd[3]:>10,.2f} | {len(ma_thons)} mã thôn")

        # Lượt 2 — nhóm ngày còn lại: tách tập con mã thôn
        for ngay in ds_ngay:
            if any(e["ngay_gdxa"] == ngay for e in ket_qua[xa].values()):
                continue
            if not con_lai_dgd:
                break
            m_n, ma_thons = theo_ngay[ngay]
            tong_pdf = (sum(x[1] for x in con_lai_dgd), sum(x[2] for x in con_lai_dgd),
                        round(sum(x[3] for x in con_lai_dgd), 2))
            if len(con_lai_dgd) == 1 and _khop(m_n, (con_lai_dgd[0][1], con_lai_dgd[0][2], con_lai_dgd[0][3])):
                dgd = con_lai_dgd[0]
                ket_qua[xa][dgd[0]] = {"ngay_gdxa": ngay, "ma_thon": ma_thons, "m_hstd": m_n,
                                       "m_pdf": (dgd[1], dgd[2], dgd[3]),
                                       "cach": "khớp Điểm GD cuối cùng còn lại"}
                nhat_ky.append(f"{xa} | ngày {ngay} -> {dgd[0]} (Điểm GD cuối)")
                con_lai_dgd = []
                print(f"  ngày {ngay:>2} -> {dgd[0]:<13} tổ {m_n[0]}/{dgd[1]} | KH {m_n[1]}/{dgd[2]}"
                      f" | dư nợ {m_n[2]:>10,.2f}/{dgd[3]:>10,.2f} | {len(ma_thons)} mã thôn")
                continue

            if not _khop(m_n, tong_pdf):
                canh_bao.append(f"{xa} ngày {ngay}: nhóm {m_n} không xấp xỉ tổng {len(con_lai_dgd)} "
                                f"Điểm GD còn lại {tong_pdf}")
                print(f"  ngày {ngay:>2}: ⚠️ {m_n} ≠ tổng Điểm GD còn lại {tong_pdf}")
                continue

            g_n = g_xa[g_xa["_ngay"] == ngay]
            ma_thon_co_du_no = sorted(g_n.loc[g_n["_dn"] > 0, "_mt"].unique())
            ma_thon_du_no_0 = [m for m in ma_thons if m not in ma_thon_co_du_no]
            per_mt = {mt: _metrics(g_n[g_n["_mt"] == mt]) for mt in ma_thon_co_du_no}
            ds_loi_giai = _tach_tap_con(ma_thon_co_du_no, per_mt, con_lai_dgd, tim_tat_ca=True)
            if not ds_loi_giai:
                canh_bao.append(f"{xa} ngày {ngay}: không tách được {len(ma_thon_co_du_no)} mã thôn "
                                f"có dư nợ cho {[x[0] for x in con_lai_dgd]}")
                print(f"  ngày {ngay:>2}: ❌ không tìm được lời giải tách")
                continue
            if len(ds_loi_giai) > 1:
                canh_bao.append(f"{xa} ngày {ngay}: CÓ {len(ds_loi_giai)} LỜI GIẢI tách — "
                                f"cần xác nhận thủ công")
                print(f"  ngày {ngay:>2}: ⚠️ {len(ds_loi_giai)} lời giải tách khả dĩ:")
                for lg in ds_loi_giai:
                    print("      " + " | ".join(f"{k}: {sorted(v)}" for k, v in lg.items()))
            loi_giai = ds_loi_giai[0]
            for ten_dgd, mt_chon in loi_giai.items():
                pdf_row = next(x for x in con_lai_dgd if x[0] == ten_dgd)
                m_c = _gop(per_mt, mt_chon)
                ket_qua[xa][ten_dgd] = {"ngay_gdxa": ngay, "ma_thon": sorted(mt_chon),
                                        "m_hstd": m_c, "m_pdf": (pdf_row[1], pdf_row[2], pdf_row[3]),
                                        "cach": "tách tập con mã thôn khớp chỉ tiêu PDF"}
                nhat_ky.append(f"{xa} | ngày {ngay} -> {ten_dgd} (tách tập con)")
                con_lai_dgd = [x for x in con_lai_dgd if x[0] != ten_dgd]
                print(f"  ngày {ngay:>2} -> {ten_dgd:<13} tổ {m_c[0]}/{pdf_row[1]} | KH {m_c[1]}/{pdf_row[2]}"
                      f" | dư nợ {m_c[2]:>10,.2f}/{pdf_row[3]:>10,.2f} | TÁCH {sorted(mt_chon)}")
            for mt in ma_thon_du_no_0:
                g_mt = g_n[g_n["_mt"] == mt]
                ten = sorted({t for t in g_mt["Tên thôn"].astype("string").fillna("").str.strip()
                              if t and t.lower() not in {"nan", "<na>"}})
                chua_xd_ngay_trung.append({
                    "xa": xa, "ma_thon": mt, "ten_thon": ten[0] if ten else "", "ngay": ngay,
                    "ly_do": "dư nợ 0, ngày GDXA trùng nhiều Điểm GD — cần xác nhận thủ công",
                    "so_dong": len(g_mt), "du_no_trieu": round(float(g_mt["_dn"].sum() / 1e6), 2)})

        if con_lai_dgd:
            canh_bao.append(f"{xa}: chưa gán được {[x[0] for x in con_lai_dgd]}")
            print(f"  ❌ còn chưa gán: {[x[0] for x in con_lai_dgd]}")

    # ── Mã thôn dư nợ 0 / thiếu ngày GDXA: suy luận theo xã ─────────────────
    da_gan = {mt for v in ket_qua.values() for e in v.values() for mt in e["ma_thon"]}
    da_liet_ke = {r["ma_thon"] for r in chua_xd_ngay_trung}
    chua_xd: list[dict] = list(chua_xd_ngay_trung)
    for (xa, mt), g in d.groupby(["_xa", "_mt"]):
        if mt in da_gan or mt in da_liet_ke or xa not in ket_qua:
            continue
        # Mã thôn này chỉ có dòng dư nợ 0 / thiếu ngày -> không đủ căn cứ số liệu
        ten = sorted({t for t in g["Tên thôn"].astype("string").fillna("").str.strip()
                      if t and t.lower() not in {"nan", "<na>"}})
        chua_xd.append({"xa": xa, "ma_thon": mt, "ten_thon": ten[0] if ten else "",
                        "ngay": "", "ly_do": "chỉ có dòng dư nợ 0 / thiếu ngày GDXA",
                        "so_dong": len(g), "du_no_trieu": round(float(g["_dn"].sum() / 1e6), 2)})
    for r in chua_xd:
        r.setdefault("ten_thon", "")
        r.setdefault("ngay", "")
        r.setdefault("ly_do", "")
        r.setdefault("so_dong", 0)
        r.setdefault("du_no_trieu", 0.0)
    print(f"\n=== Mã thôn không đủ căn cứ gán Điểm GD: {len(chua_xd)} (dư nợ 0) ===")
    for r in chua_xd:
        print(f"  {r['xa']:<11} {r['ma_thon']} {str(r['ten_thon']):<25} ngày {r['ngay']} | {r['ly_do']}")

    # ── Xuất JSON kết quả ──────────────────────────────────────────────────
    out: dict[str, dict] = {}
    for xa, blk in ket_qua.items():
        out[xa] = {}
        for ten_dgd, e in blk.items():
            g = d[(d["_xa"] == xa) & (d["_mt"].isin(e["ma_thon"]))]
            ten_thons = sorted({t for t in g["Tên thôn"].astype("string").fillna("").str.strip()
                                if t and t.lower() not in {"nan", "<na>"}})
            out[xa][ten_dgd] = {
                "ngay_gdxa": e["ngay_gdxa"],
                "ma_thon": e["ma_thon"],
                "thon": ten_thons,
                "hstd_so_to": e["m_hstd"][0], "hstd_kh_vay": e["m_hstd"][1], "hstd_du_no_trieu": e["m_hstd"][2],
                "pdf_so_to": e["m_pdf"][0], "pdf_kh_vay": e["m_pdf"][1], "pdf_du_no_trieu": e["m_pdf"][2],
                "lech_du_no_trieu": round(e["m_hstd"][2] - e["m_pdf"][2], 2),
                "cach_xac_dinh": e["cach"],
            }
    (OUT / "06_ma_thon_dgd_hoi_so.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(chua_xd).to_csv(OUT / "07_ma_thon_chua_xac_dinh.csv", index=False, encoding="utf-8-sig")

    tong_dgd = sum(len(v) for v in out.values())
    tong_mt = len({mt for v in out.values() for e in v.values() for mt in e["ma_thon"]})
    tong_dn = sum(e["hstd_du_no_trieu"] for v in out.values() for e in v.values())
    print("\n=== TỔNG KẾT ===")
    print(f"Điểm GD gán được: {tong_dgd}/26 | Mã thôn gán được: {tong_mt}")
    print(f"Dư nợ đã gán: {tong_dn:,.2f} / PDF 681.418,00 triệu (lệch {tong_dn-681418:,.2f})")
    print(f"Lệch tuyệt đối theo từng Điểm GD: "
          f"{sum(abs(e['lech_du_no_trieu']) for v in out.values() for e in v.values()):,.2f} triệu")
    if canh_bao:
        print("\nCảnh báo:")
        for c in canh_bao:
            print("  - " + c)


if __name__ == "__main__":
    main()
