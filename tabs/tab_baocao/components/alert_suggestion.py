"""Alert và suggestion component cho báo cáo."""
from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import TYPE_CHECKING, List, Dict, Any
from datetime import datetime

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


# Ngưỡng cảnh báo mặc định
DEFAULT_THRESHOLDS = {
    "ty_le_qh_cao": 10.0,  # Tỷ lệ QH > 10%
    "ty_le_no_xau_cao": 15.0,  # Tỷ lệ nợ xấu > 15%
    "tang_truong_am": -5.0,  # Tăng trưởng dư nợ âm > 5%
    "nhieu_mon_den_han": 50,  # > 50 món đến hạn
}


def check_alerts(
    df: pd.DataFrame,
    df_prev: pd.DataFrame | None = None,
    thresholds: Dict[str, float] | None = None,
) -> List[Dict[str, Any]]:
    """
    Kiểm tra các điều kiện cảnh báo.
    
    Args:
        df: DataFrame hiện tại
        df_prev: DataFrame kỳ trước (optional)
        thresholds: Ngưỡng cảnh báo (optional)
    
    Returns:
        List các cảnh báo
    """
    from config import COT_TONG_DU_NO, COT_DU_NO_QH, COT_DU_NO_KHOANH
    
    alerts = []
    th = thresholds or DEFAULT_THRESHOLDS
    
    if df is None or df.empty:
        return alerts
    
    # Tính toán các chỉ số
    tong_du_no = df[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df.columns else 0
    no_qh = df[COT_DU_NO_QH].sum() if COT_DU_NO_QH in df.columns else 0
    no_khoanh = df[COT_DU_NO_KHOANH].sum() if COT_DU_NO_KHOANH in df.columns else 0
    
    # Tỷ lệ nợ quá hạn
    if tong_du_no > 0:
        ty_le_qh = (no_qh / tong_du_no) * 100
        if ty_le_qh > th["ty_le_qh_cao"]:
            alerts.append({
                "level": "high",
                "type": "ty_le_qh",
                "title": "⚠️ Tỷ lệ nợ quá hạn cao",
                "message": f"Tỷ lệ nợ quá hạn đạt {ty_le_qh:.2f}%, vượt ngưỡng {th['ty_le_qh_cao']}%",
                "value": ty_le_qh,
                "threshold": th["ty_le_qh_cao"],
            })
    
    # Tỷ lệ nợ xấu
    if tong_du_no > 0:
        ty_le_no_xau = ((no_qh + no_khoanh) / tong_du_no) * 100
        if ty_le_no_xau > th["ty_le_no_xau_cao"]:
            alerts.append({
                "level": "high",
                "type": "ty_le_no_xau",
                "title": "🚨 Tỷ lệ nợ xấu cao",
                "message": f"Tỷ lệ nợ xấu (QH + Khoanh) đạt {ty_le_no_xau:.2f}%, vượt ngưỡng {th['ty_le_no_xau_cao']}%",
                "value": ty_le_no_xau,
                "threshold": th["ty_le_no_xau_cao"],
            })
    
    # So sánh kỳ trước
    if df_prev is not None and not df_prev.empty:
        tong_du_no_prev = df_prev[COT_TONG_DU_NO].sum() if COT_TONG_DU_NO in df_prev.columns else 0
        if tong_du_no_prev > 0:
            tang_truong = ((tong_du_no - tong_du_no_prev) / tong_du_no_prev) * 100
            if tang_truong < th["tang_truong_am"]:
                alerts.append({
                    "level": "medium",
                    "type": "tang_truong_am",
                    "title": "📉 Tăng trưởng âm",
                    "message": f"Dư nợ giảm {abs(tang_truong):.2f}% so với kỳ trước",
                    "value": tang_truong,
                    "threshold": th["tang_truong_am"],
                })
    
    return alerts


def get_suggestions(alerts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Tạo gợi ý hành động từ các cảnh báo.
    
    Args:
        alerts: List các cảnh báo
    
    Returns:
        List các gợi ý
    """
    suggestions = []
    
    for alert in alerts:
        if alert["type"] == "ty_le_qh":
            suggestions.append({
                "icon": "📋",
                "title": "Đôn đốc thu nợ quá hạn",
                "action": "Lập danh sách các KH nợ quá hạn và gửi thông báo đôn đốc",
                "priority": "Cao",
            })
            suggestions.append({
                "icon": "📞",
                "title": "Liên hệ KH nợ QH",
                "action": "Gọi điện/sms cho KH có nợ quá hạn > 30 ngày",
                "priority": "Cao",
            })
        
        elif alert["type"] == "ty_le_no_xau":
            suggestions.append({
                "icon": "⚖️",
                "title": "Xử lý nợ khoanh",
                "action": "Rà soát hồ sơ nợ khoanh, chuẩn bị hồ sơ xử lý rủi ro",
                "priority": "Cao",
            })
            suggestions.append({
                "icon": "🤝",
                "title": "Thương lượng phương án trả nợ",
                "action": "Làm việc với KH để thống nhất phương án trả nợ mới",
                "priority": "Trung bình",
            })
        
        elif alert["type"] == "tang_truong_am":
            suggestions.append({
                "icon": "📢",
                "title": "Tăng cường tín dụng",
                "action": "Rà soát nhu cầu vay vốn, đẩy mạnh giải ngân",
                "priority": "Trung bình",
            })
    
    return suggestions


def render_alert_card(
    alert: Dict[str, Any],
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị một cảnh báo.
    
    Args:
        alert: Thông tin cảnh báo
        container: Streamlit container
    """
    ctx = container if container is not None else st
    
    # Màu theo mức độ
    colors = {
        "high": {"bg": "#2d1b1b", "border": "#ef4444", "icon": "🚨"},
        "medium": {"bg": "#2d2410", "border": "#f59e0b", "icon": "⚠️"},
        "low": {"bg": "#1a2332", "border": "#3b82f6", "icon": "ℹ️"},
    }
    
    color = colors.get(alert["level"], colors["medium"])
    
    alert_html = f"""
        <div style="background:{color['bg']};color:#E0E6ED;border-left:4px solid {color['border']};
                    border-radius:4px;padding:12px;margin:8px 0;">
            <div style="font-weight:600;margin-bottom:4px;">
                {alert['title']}
            </div>
            <div style="font-size:14px;color:#94A3B8;">
                {alert['message']}
            </div>
        </div>
    """
    
    ctx.markdown(alert_html, unsafe_allow_html=True)


def render_alerts_panel(
    df: pd.DataFrame,
    df_prev: pd.DataFrame | None = None,
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị panel cảnh báo.
    
    Args:
        df: DataFrame hiện tại
        df_prev: DataFrame kỳ trước
        container: Streamlit container
    """
    ctx = container if container is not None else st
    
    alerts = check_alerts(df, df_prev)
    
    if not alerts:
        ctx.success("✅ Không có cảnh báo nào - Tình hình tín dụng ổn định!")
        return
    
    ctx.markdown(f"#### 🔔 Cảnh báo ({len(alerts)})")
    
    for alert in alerts:
        render_alert_card(alert, container=ctx)


def render_suggestions_panel(
    alerts: List[Dict[str, Any]],
    container: DeltaGenerator | None = None,
) -> None:
    """
    Hiển thị panel gợi ý hành động.
    
    Args:
        alerts: List các cảnh báo
        container: Streamlit container
    """
    ctx = container if container is not None else st
    
    suggestions = get_suggestions(alerts)
    
    if not suggestions:
        return
    
    ctx.markdown(f"#### 💡 Gợi ý hành động ({len(suggestions)})")
    
    for sugg in suggestions:
        sugg_html = f"""
            <div style="background:#1a2e1a;color:#E0E6ED;border-left:4px solid #22c55e;
                        border-radius:4px;padding:12px;margin:8px 0;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <span style="font-size:18px;">{sugg['icon']}</span>
                    <span style="font-weight:600;">{sugg['title']}</span>
                    <span style="background:#1a3a2a;color:#4ade80;padding:2px 8px;
                               border-radius:12px;font-size:12px;font-weight:500;">
                        {sugg['priority']}
                    </span>
                </div>
                <div style="font-size:14px;margin-left:26px;color:#94A3B8;">
                    {sugg['action']}
                </div>
            </div>
        """
        ctx.markdown(sugg_html, unsafe_allow_html=True)


def render_combined_alerts_suggestions(
    df: pd.DataFrame,
    df_prev: pd.DataFrame | None = None,
    container: DeltaGenerator | None = None,
) -> List[Dict[str, Any]]:
    """
    Hiển thị cả cảnh báo và gợi ý.
    
    Returns:
        List các cảnh báo để dùng sau nếu cần
    """
    ctx = container if container is not None else st
    
    alerts = check_alerts(df, df_prev)
    
    if alerts:
        col1, col2 = ctx.columns(2)
        
        with col1:
            render_alerts_panel(df, df_prev, container=col1)
        
        with col2:
            render_suggestions_panel(alerts, container=col2)
    else:
        render_alerts_panel(df, df_prev, container=ctx)
    
    return alerts
