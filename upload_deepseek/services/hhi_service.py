"""Giám sát tập trung rủi ro — Chỉ số Herfindahl-Hirschman (HHI)."""
from __future__ import annotations

import pandas as pd


def tinh_hhi(
    df: pd.DataFrame,
    nhom_theo: str,
    cot_tien: str = "",
) -> float:
    """
    Tính chỉ số Herfindahl-Hirschman Index.

    HHI = Σ(S_i²)  với S_i = tỷ trọng dư nợ của nhóm i / tổng dư nợ.

    Giá trị từ 0 (đa dạng hóa tuyệt đối) đến 1 (tập trung hoàn toàn).
    Trong thực tế: nhân với 10000 để đọc theo thang HHI truyền thống.

    Returns:
        float: HHI ∈ [0, 1]
    """
    if df.empty:
        return 0.0

    col = cot_tien if cot_tien else _tim_cot_tien(df)
    if col not in df.columns:
        return 0.0

    ti_trong = df.groupby(nhom_theo)[col].sum()
    tong = ti_trong.sum()
    if tong == 0:
        return 0.0

    ti_trong = ti_trong / tong
    return float((ti_trong ** 2).sum())


def tinh_hhi_breakdown(
    df: pd.DataFrame,
    nhom_theo: str,
    cot_tien: str = "",
) -> pd.DataFrame:
    """
    Trả về bảng breakdown HHI: mỗi nhóm có tỷ trọng và đóng góp vào HHI.

    Returns:
        DataFrame với cột: nhom, du_no, ty_trong_pct, dong_gop_hhi
    """
    if df.empty:
        return pd.DataFrame()

    col = cot_tien if cot_tien else _tim_cot_tien(df)
    if col not in df.columns:
        return pd.DataFrame(columns=[nhom_theo, "du_no", "ty_trong_pct", "dong_gop_hhi"])

    du_no = df.groupby(nhom_theo)[col].sum().sort_values(ascending=False)
    tong = du_no.sum()
    if tong == 0:
        return pd.DataFrame()

    ty_trong = du_no / tong
    dong_gop = ty_trong ** 2

    result = pd.DataFrame({
        nhom_theo: du_no.index,
        "du_no": du_no.values,
        "ty_trong_pct": (ty_trong * 100).round(2).values,
        "dong_gop_hhi": (dong_gop * 10000).round(1).values,
    })
    return result


def danh_gia_hhi(hhi: float) -> tuple[str, str, str]:
    """
    Đánh giá mức độ tập trung rủi ro dựa trên HHI.

    Theo thang HHI chuẩn (×10000):
        < 1000  → Không tập trung (Đa dạng hóa tốt)
        1000–2500 → Tập trung vừa phải
        > 2500 → Tập trung cao (Cảnh báo rủi ro)

    Returns:
        (muc_do, icon, mau) — hiển thị trên UI
    """
    hhi_x10000 = hhi * 10000

    if hhi_x10000 < 1000:
        return "Đa dạng hóa tốt", "✅", "#2e7d32"
    elif hhi_x10000 < 2500:
        return "Tập trung vừa phải", "⚠️", "#f57f17"
    else:
        return "Tập trung cao — Cảnh báo rủi ro", "🚨", "#c62828"


def _tim_cot_tien(df: pd.DataFrame) -> str:
    for c in ["Tổng dư nợ", "Dư nợ", "Tổng_dư_nợ", "du_no"]:
        if c in df.columns:
            return c
    return ""
