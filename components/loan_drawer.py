"""LoanDetailDrawer - Panel chi tiết khoản vay (trượt từ phải sang)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from config import (
    COT_MA_KH,
    COT_TEN_KH,
    COT_SO_KU,
    COT_TEN_CT,
    COT_NGAY_VAY,
    COT_NGAY_DEN_HAN,
    COT_TONG_DU_NO,
    COT_DU_NO_TH,
    COT_DU_NO_QH,
    COT_LAI_TON,
    COT_LAI_TON_QH,
    COT_PHAN_LOAI,
    COT_TEN_PGD,
    COT_TEN_XA,
    COT_TEN_TO,
    COT_SDT,
    COT_DIA_CHI,
    COT_CMND,
)

_DRAWER_HTML = """<div id="loan-drawer-overlay" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:999998;" onclick="closeLoanDrawer()"></div>
<div id="loan-drawer" style="display:none;position:fixed;top:0;right:-600px;width:580px;height:100vh;background:#1E2130;box-shadow:-4px 0 24px rgba(0,0,0,0.4);z-index:999999;overflow-y:auto;transition:right 0.3s ease;padding:0;">
  <div style="position:sticky;top:0;background:#2E7D32;color:white;padding:16px 20px;display:flex;align-items:center;justify-content:space-between;z-index:10;">
    <span style="font-weight:700;font-size:16px;" id="drawer-title">Chi tiết khoản vay</span>
    <button onclick="closeLoanDrawer()" style="background:none;border:none;color:white;font-size:24px;cursor:pointer;padding:0 4px;">&times;</button>
  </div>
  <div id="drawer-content" style="padding:16px 20px 40px;font-size:14px;color:#E0E6ED;"></div>
</div>
<script>
function openLoanDrawer(htmlContent, title) {
  document.getElementById('drawer-content').innerHTML = htmlContent;
  if(title) document.getElementById('drawer-title').textContent = title;
  document.getElementById('loan-drawer').style.display = 'block';
  document.getElementById('loan-drawer-overlay').style.display = 'block';
  setTimeout(function() {
    document.getElementById('loan-drawer').style.right = '0px';
  }, 10);
}
function closeLoanDrawer() {
  document.getElementById('loan-drawer').style.right = '-600px';
  setTimeout(function() {
    document.getElementById('loan-drawer').style.display = 'none';
    document.getElementById('loan-drawer-overlay').style.display = 'none';
  }, 300);
}
</script>"""


def _init_drawer():
    """Inject HTML/CSS/JS cho drawer (chạy 1 lần)."""
    if "_loan_drawer_injected" not in st.session_state:
        st.markdown(_DRAWER_HTML, unsafe_allow_html=True)
        st.session_state["_loan_drawer_injected"] = True


def _render_field(name: str, value: Any, fmt: str | None = None) -> str:
    """Render 1 dòng thông tin trong drawer."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        display = "—"
    elif fmt == "tien":
        try:
            display = f"{float(value):,.0f} đ"
        except (ValueError, TypeError):
            display = str(value)
    elif fmt == "pct":
        try:
            display = f"{float(value):.2f}%"
        except (ValueError, TypeError):
            display = str(value)
    else:
        display = str(value)

    return (
        f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
        f'border-bottom:1px solid #2A2D3E;">'
        f'<span style="color:#94A3B8;font-size:13px;">{name}</span>'
        f'<span style="font-weight:600;font-size:13px;color:#E0E6ED;">{display}</span>'
        f'</div>'
    )


def _field_groups() -> list[dict]:
    """Định nghĩa các nhóm trường hiển thị."""
    return [
        {
            "title": "📋 Thông tin khách hàng",
            "icon": "user",
            "fields": [
                ("Mã KH", COT_MA_KH),
                ("Tên KH", COT_TEN_KH),
                ("Địa chỉ", COT_DIA_CHI),
                ("Số CMND/CCCD", COT_CMND),
                ("Số điện thoại", COT_SDT),
            ],
        },
        {
            "title": "💰 Thông tin khoản vay",
            "icon": "dollar-sign",
            "fields": [
                ("Số KƯ", COT_SO_KU),
                ("Chương trình", COT_TEN_CT),
                ("Ngày giải ngân", COT_NGAY_VAY),
                ("Hạn trả cuối", COT_NGAY_DEN_HAN),
                ("Dư nợ gốc", COT_TONG_DU_NO, "tien"),
                ("Dư nợ trong hạn", COT_DU_NO_TH, "tien"),
                ("Dư nợ quá hạn", COT_DU_NO_QH, "tien"),
                ("Lãi tồn", COT_LAI_TON, "tien"),
                ("Lãi QH", COT_LAI_TON_QH, "tien"),
                ("Phân loại nợ", COT_PHAN_LOAI),
            ],
        },
        {
            "title": "📍 Đơn vị quản lý",
            "icon": "map-pin",
            "fields": [
                ("PGD", COT_TEN_PGD),
                ("Xã", COT_TEN_XA),
                ("Tổ TK&VV", COT_TEN_TO),
            ],
        },
    ]


def loan_detail_drawer(
    row: pd.Series | dict,
    title: str | None = None,
    extra_fields: list[tuple[str, str, str | None]] | None = None,
    field_configs: list[dict] | None = None,
):
    """Hiển thị drawer chi tiết khoản vay.

    Args:
        row: Dòng dữ liệu (pd.Series hoặc dict)
        title: Tiêu đề drawer (mặc định: tên khách hàng)
        extra_fields: Các trường bổ sung [(label, column, fmt)]
        field_configs: Định nghĩa nhóm trường (mặc định dùng _field_groups)
    """
    _init_drawer()

    row_dict = row.to_dict() if isinstance(row, pd.Series) else dict(row)
    ten_kh = str(row_dict.get(COT_TEN_KH, ""))
    drawer_title = title or f"KH: {ten_kh}" if ten_kh else "Chi tiết khoản vay"

    groups = field_configs or _field_groups()
    html_parts = []

    for group in groups:
        title = group.get("title", "")
        fields = group.get("fields", []) + (extra_fields or [])

        html_parts.append(
            f'<div style="font-weight:700;font-size:14px;color:#66BB6A;'
            f'margin:12px 0 6px;padding-bottom:4px;border-bottom:2px solid #1B5E20;">'
            f'{title}</div>'
        )

        for field_def in fields:
            if len(field_def) == 3:
                label, col, fmt = field_def
            else:
                label, col = field_def
                fmt = None

            val = row_dict.get(col)
            html_parts.append(_render_field(label, val, fmt))

    html_content = "".join(html_parts)
    safe_title = drawer_title.replace("'", "\\'").replace('"', "\\'")
    safe_html = html_content.replace("'", "\\'").replace("\n", " ")

    st.markdown(
        f'<button onclick="openLoanDrawer(\'{safe_html}\', \'{safe_title}\')" '
        f'style="background:none;border:1px solid #66BB6A;border-radius:6px;'
        f'color:#66BB6A;padding:4px 12px;font-size:13px;cursor:pointer;'
        f'transition:all 0.2s;" '
        f'onmouseover="this.style.background=\'#0D2818\'" '
        f'onmouseout="this.style.background=\'transparent\'">'
        f'📄 Chi tiết</button>',
        unsafe_allow_html=True,
    )
