"""Tree navigation component cho tab báo cáo."""
from __future__ import annotations

import streamlit as st
from typing import TYPE_CHECKING, Dict, List, Callable

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator


# Cấu trúc cây báo cáo
REPORT_TREE = {
    "📊 Dashboard": {
        "key": "dashboard",
        "icon": "🏠",
        "reports": [],
    },
    "📁 Báo cáo Tổng hợp": {
        "key": "hstd_group",
        "icon": "📈",
        "reports": [
            {"key": "hstd_pgd", "label": "🏢 Theo PGD", "desc": "Tổng hợp theo Phòng Giao dịch"},
            {"key": "hstd_xa", "label": "🏘️ Theo Xã", "desc": "Tổng hợp theo đơn vị xã"},
            {"key": "hstd_thon", "label": "🏡 Theo Thôn/ấp", "desc": "Chi tiết đến cấp thôn"},
            {"key": "hstd_ct", "label": "📌 Theo Chương trình", "desc": "Phân loại theo chương trình vay"},
            {"key": "hstd_md", "label": "🎯 Theo Mục đích vốn", "desc": "Tổng hợp theo Tên PNKT51"},
            {"key": "hstd_nv", "label": "🏦 Theo Nguồn vốn", "desc": "TW vs Địa phương"},
            {"key": "hstd_dvut", "label": "🤝 Theo ĐVUT", "desc": "Theo hội đoàn thể"},
            {"key": "hstd_cbtd", "label": "👤 Theo CBTD", "desc": "Theo cán bộ tín dụng"},
        ],
    },
    "⚠️ Báo cáo Nợ xấu": {
        "key": "noruiro_group",
        "icon": "🚨",
        "reports": [
            {"key": "noruiro_qh", "label": "🔴 Nợ quá hạn", "desc": "Danh sách nợ quá hạn chi tiết"},
            {"key": "noruiro_kh", "label": "🟠 Nợ khoanh", "desc": "Dư nợ bị khoanh"},
            {"key": "noruiro_dh30", "label": "⏰ Đến hạn 30 ngày", "desc": "Dự báo nợ đến hạn"},
            {"key": "noruiro_dh60", "label": "⏰ Đến hạn 60 ngày", "desc": "Dự báo xa hơn"},
            {"key": "noruiro_noxau", "label": "📊 Tỷ lệ nợ xấu", "desc": "Phân tích rủi ro"},
        ],
    },
    "📑 Báo cáo NQ11": {
        "key": "nq11_group",
        "icon": "📜",
        "reports": [
            {"key": "nq11_th", "label": "📊 Tổng hợp theo CT", "desc": "DNO NQ11 theo chương trình"},
            {"key": "nq11_co", "label": "✅ Món có NQ11", "desc": "Danh sách chi tiết"},
            {"key": "nq11_khong", "label": "❌ Món không NQ11", "desc": "Cần bổ sung thông tin"},
        ],
    },
    "💼 Báo cáo GQVL": {
        "key": "gqvl_group",
        "icon": "💰",
        "reports": [
            {"key": "gqvl_pt", "label": "🏛️ Phân tầng TW/ĐP", "desc": "Theo nguồn vốn"},
            {"key": "gqvl_ndt", "label": "🏢 Theo nhà đầu tư", "desc": "Phân loại theo NĐT"},
            {"key": "gqvl_gn", "label": "📊 Giải ngân", "desc": "Tổng hợp giải ngân"},
        ],
    },
    "⭐ Chấm điểm Tổ TK&VV": {
        "key": "cdtotkvv_group",
        "icon": "🎯",
        "reports": [
            {"key": "cdtotkvv_xh", "label": "🏆 Xếp hạng", "desc": "Bảng xếp hạng tổng hợp"},
            {"key": "cdtotkvv_diem", "label": "📊 Phân tích điểm", "desc": "Điểm thành phần chi tiết"},
            {"key": "cdtotkvv_db", "label": "🏘️ Theo địa bàn", "desc": "Phân bổ theo xã/thôn"},
        ],
    },
}


def render_tree_navigation(
    container: DeltaGenerator | None = None,
    key: str = "tree_nav",
) -> str:
    """
    Render navigation dạng tree.
    
    Returns:
        str: Key của báo cáo được chọn
    """
    ctx = container if container is not None else st
    
    selected = None
    
    # CSS cho tree
    tree_css = """
    <style>
    .tree-node {
        padding: 8px 12px;
        margin: 2px 0;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s;
        font-size: 14px;
    }
    .tree-node:hover {
        background: #262B3D;
        color: #E0E6ED;
    }
    .tree-node.active {
        background: #1a2744;
        color: #E0E6ED;
        border-left: 3px solid #3b82f6;
        font-weight: 500;
    }
    .tree-parent {
        font-weight: 600;
        color: #E0E6ED;
        padding-left: 8px;
    }
    .tree-child {
        padding-left: 32px;
        color: #94A3B8;
        font-size: 13px;
    }
    .tree-desc {
        font-size: 11px;
        color: #9ca3af;
        margin-top: 2px;
    }
    </style>
    """
    ctx.markdown(tree_css, unsafe_allow_html=True)
    
    # Hiển thị cây
    for parent_name, parent_data in REPORT_TREE.items():
        # Parent node
        ctx.markdown(f"""
            <div class="tree-node tree-parent">
                {parent_data['icon']} {parent_name}
            </div>
        """, unsafe_allow_html=True)
        
        # Child nodes
        for report in parent_data.get("reports", []):
            # Tạo button cho mỗi report
            if ctx.button(
                f"{report['label']}",
                key=f"{key}_{report['key']}",
                help=report['desc'],
                use_container_width=True,
            ):
                selected = report['key']
                st.session_state[f"{key}_selected"] = selected
    
    # Lấy từ session state nếu có
    if f"{key}_selected" in st.session_state:
        selected = st.session_state[f"{key}_selected"]
    
    return selected or "dashboard"


def render_compact_navigation(
    container: DeltaGenerator | None = None,
    key: str = "compact_nav",
) -> str:
    """
    Render navigation dạng compact (dropdown với icon).
    
    Returns:
        str: Key của báo cáo được chọn
    """
    ctx = container if container is not None else st
    
    # Tạo flat list
    options = []
    option_keys = []
    
    for parent_name, parent_data in REPORT_TREE.items():
        if parent_data.get("reports"):
            for report in parent_data["reports"]:
                options.append(f"{parent_data['icon']} {report['label']}")
                option_keys.append(report['key'])
        else:
            options.append(f"{parent_data['icon']} {parent_name}")
            option_keys.append(parent_data['key'])
    
    selected_idx = ctx.selectbox(
        "📋 Chọn báo cáo",
        range(len(options)),
        format_func=lambda i: options[i],
        key=f"{key}_select",
    )
    
    return option_keys[selected_idx]


def get_report_info(report_key: str) -> dict:
    """Lấy thông tin báo cáo từ key."""
    for parent_data in REPORT_TREE.values():
        for report in parent_data.get("reports", []):
            if report["key"] == report_key:
                return {
                    "parent": parent_data['key'],
                    "parent_name": [k for k, v in REPORT_TREE.items() if v['key'] == parent_data['key']][0] if parent_data['key'] != 'dashboard' else None,
                    **report
                }
    return {}
