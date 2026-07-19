"""
Theme management — Dark mode only.
Color system dựa theo Semantic Token Pattern (shadcn/Linear style).
"""
import streamlit as st

# ── Semantic Color Tokens (Dark Only) ────────────────────────────────────────
_TOKENS = {
    # Surfaces (elevation low → high)
    "bg":           "#0F1117",   # main canvas
    "bg_subtle":    "#161922",   # row stripe / subtle area
    "surface":      "#1E2130",   # card, expander, metric
    "surface_hi":   "#262B3D",   # input, hover state
    "overlay":      "#2A2F45",   # popover, tooltip bg
    # Borders
    "border":       "#2A2D3E",
    "border_focus": "#4ADE80",   # green focus ring
    # Text
    "text":         "#E0E6ED",   # primary body
    "text_sub":     "#94A3B8",   # secondary / labels
    "text_muted":   "#64748B",   # captions
    "text_heading": "#F0F4F8",   # h1/h2
    # Sidebar (fixed dark in both modes)
    "sidebar_bg":   "#1A1D2E",
    "sidebar_text": "#E0E6ED",
    "sidebar_sub":  "#94A3B8",
    "sidebar_border":"#2A2D3E",
    # Header
    "header_bg":    "#1E2130",
    "header_border":"#2E7D32",
    # Accent (brand green NHCSXH)
    "accent":       "#2E7D32",   # primary button
    "accent_hi":    "#43A047",   # hover
    "accent_soft":  "#0D2818",   # tinted bg (badge/chip)
    "accent_text":  "#81C784",   # text on soft bg
    "accent_glow":  "#66BB6A",   # active tab, bright icon
    # Semantic — success/info/warn/error
    "success_bg":   "#0D2818", "success_text": "#81C784", "success_border": "#2E7D32",
    "info_bg":      "#0D2137", "info_text":    "#90CAF9", "info_border":    "#42A5F5",
    "warn_bg":      "#2D1F0D", "warn_text":    "#FFD54F", "warn_border":    "#F57F17",
    "error_bg":     "#2D0D14", "error_text":   "#EF9A9A", "error_border":   "#C62828",
    # DataTable
    "table_header": "linear-gradient(135deg,#1B5E20 0%,#2E7D32 100%)",
    "table_hover":  "#1E2130",
    "table_stripe": "#161922",
    # Scrollbar
    "scroll_track": "#1E2130",
    "scroll_thumb": "#2E7D32",
    "scroll_hover": "#66BB6A",
    # Misc
    "spinner":      "#66BB6A",
    "chip_bg":      "#0D2818", "chip_text": "#81C784", "chip_border": "#2E7D32",
}


@st.cache_resource
def _css_part1() -> str:
    """CSS chunk 1: typography, canvas, sidebar, header, tabs, expander, metric, dataframe, inputs."""
    c = _TOKENS
    return f"""<style>
/* VBSP-SCM UI — Dark Theme (1/2) */

/* ── 1. TYPOGRAPHY ── */
html, body, [class*="css"] {{
    font-size: 15px !important;
    font-family: "Inter", "Be Vietnam Pro", "Segoe UI", system-ui, sans-serif !important;
    line-height: 1.65 !important;
    color: {c['text']} !important;
}}
h1 {{ font-size: 1.55rem !important; font-weight: 700 !important;
     color: {c['text_heading']} !important; letter-spacing: -0.3px !important; }}
h2 {{ font-size: 1.3rem !important; font-weight: 700 !important;
     color: {c['text_heading']} !important; }}
h3 {{ font-size: 1.1rem !important; font-weight: 600 !important;
     color: {c['text']} !important; }}
[data-testid="stMarkdownContainer"] p {{ font-size: 0.97rem !important; color: {c['text']} !important; }}
[data-testid="stCaptionContainer"] p  {{ font-size: 0.84rem !important; color: {c['text_muted']} !important; }}

/* ── 2. CANVAS / MAIN AREA ── */
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
.main {{
    background-color: {c['bg']} !important;
}}
.block-container {{
    padding: 1.5rem 2rem 2rem !important;
    max-width: 1400px !important;
    background-color: {c['bg']} !important;
}}
.main .block-container {{ background-color: {c['bg']} !important; padding-top: 1.5rem; }}

/* ── 3. SIDEBAR ── */
[data-testid="stSidebar"] {{
    background: {c['sidebar_bg']} !important;
    border-right: 1px solid {c['sidebar_border']} !important;
    box-shadow: 4px 0 12px rgba(0,0,0,0.25) !important;
}}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{ color: {c['sidebar_text']} !important; font-weight: 700; }}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown p {{
    color: {c['sidebar_sub']} !important;
    font-size: 11px !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: 0.8px;
}}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: {c['sidebar_text']} !important; }}
section[data-testid="stSidebar"] p,
[data-testid="stSidebarContent"] p,
[data-testid="stSidebar"] [data-testid="stButton"] p {{ color: inherit; }}

/* Sidebar buttons */
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] [data-testid="stButton"] button {{
    background-color: #2E7D32 !important; color: #FFFFFF !important;
    border: 1.5px solid #1B5E20 !important; border-radius: 10px;
    width: 100%; text-align: left;
    padding: 12px 18px !important; font-size: 15px !important;
    font-weight: 700 !important; margin-bottom: 6px;
    transition: all 0.2s ease; box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    text-shadow: 0 1px 2px rgba(0,0,0,0.2) !important; letter-spacing: 0.3px;
}}
[data-testid="stSidebar"] .stButton > button span,
[data-testid="stSidebar"] .stButton > button p,
[data-testid="stSidebar"] button span,
[data-testid="stSidebar"] button p {{ color: #FFFFFF !important; font-weight: 700 !important; }}
[data-testid="stSidebar"] .stButton > button:hover,
[data-testid="stSidebar"] [data-testid="stButton"] button:hover {{
    background-color: #1B5E20 !important; border-color: #1B5E20 !important;
    color: #FFFFFF !important; box-shadow: 0 3px 10px rgba(0,0,0,0.2);
    transform: translateX(2px);
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
    background: #1B5E20 !important; color: #FFFFFF !important;
    border-color: #1B5E20 !important;
    box-shadow: 0 3px 10px rgba(27,94,32,0.35); font-weight: 700;
}}
[data-testid="stSidebar"] [data-testid="column"] .stButton > button,
[data-testid="stSidebar"] section .stButton > button,
[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] .stButton > button {{
    background-color: #2E7D32 !important; color: #FFFFFF !important;
    font-weight: 700 !important; border: 1px solid #1B5E20 !important;
    font-size: 13px !important; padding: 7px 12px !important;
    margin-bottom: 3px !important; box-shadow: none !important; transform: none !important;
}}
[data-testid="stSidebar"] hr {{ border-color: {c['sidebar_border']}; margin: 12px 0; }}
[data-testid="stSidebar"] .stAlert {{
    background-color: #1E2130; border: 1px solid #2A2D3E;
    border-radius: 8px; font-size: 12px;
}}

/* ── 4. HEADER ── */
header[data-testid="stHeader"] {{
    background-color: {c['header_bg']} !important;
    border-bottom: 2px solid {c['header_border']} !important;
}}

/* ── 5. TABS ── */
[data-testid="stTabs"] {{
    background: {c['surface']} !important; border-radius: 12px !important;
    padding: 0 8px !important; box-shadow: 0 1px 4px rgba(0,0,0,0.1) !important;
    border: 1px solid {c['border']} !important;
}}
[data-testid="stTabs"] button[role="tab"] {{
    font-size: 0.88rem !important; font-weight: 600 !important;
    padding: 10px 16px !important; color: {c['text_sub']} !important;
    border-radius: 0 !important; transition: color 0.2s !important;
}}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
    color: {c['accent_glow']} !important;
    border-bottom: 3px solid {c['accent_glow']} !important;
    background: transparent !important;
}}
[data-testid="stTabs"] button[role="tab"]:hover {{ color: {c['accent_glow']} !important; }}

/* ── 6. EXPANDER ── */
[data-testid="stExpander"] {{
    background: {c['surface']} !important;
    border: 1px solid {c['border']} !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    margin-bottom: 12px !important;
}}
[data-testid="stExpander"] summary {{
    font-size: 0.95rem !important; font-weight: 600 !important;
    color: {c['text']} !important; padding: 12px 16px !important;
}}

/* ── 7. METRIC / KPI CARD ── */
[data-testid="stMetric"] {{
    border-left: 4px solid {c['accent']} !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12) !important;
    transition: box-shadow 0.2s, transform 0.15s !important;
}}
[data-testid="stMetric"]:hover {{
    box-shadow: 0 4px 16px rgba(46,125,50,0.2) !important;
    transform: translateY(-1px) !important;
}}
[data-testid="stMetric"] label {{
    font-size: 0.78rem !important; color: {c['text_sub']} !important;
    font-weight: 600 !important; text-transform: uppercase !important;
    letter-spacing: 0.6px !important;
}}
[data-testid="stMetricValue"] {{
    font-size: 1.6rem !important; font-weight: 700 !important;
    color: {c['text_heading']} !important; letter-spacing: -0.5px !important;
}}
[data-testid="stMetric"]:has([data-testid="stMetricDelta"] svg[data-icon="arrow-down-right"]) {{
    border-left-color: {c['error_border']} !important;
}}
[data-testid="stMetric"]:has([data-testid="stMetricDelta"] svg[data-icon="arrow-up-right"]) {{
    border-left-color: {c['accent']} !important;
}}

/* ── 8. DATAFRAME ── */
[data-testid="stDataFrame"] {{
    border-radius: 10px !important; overflow: hidden !important;
    border: 1px solid {c['border']} !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
}}
[data-testid="stDataFrame"] th {{
    background: {c['table_header']} !important;
    color: white !important; font-size: 0.84rem !important; font-weight: 700 !important;
    padding: 10px 14px !important; letter-spacing: 0.4px !important;
    text-shadow: 0 1px 2px rgba(0,0,0,0.2) !important;
    border-bottom: 2px solid {c['accent']} !important;
}}
[data-testid="stDataFrame"] td {{
    font-size: 0.9rem !important; padding: 8px 14px !important;
    border-bottom: 1px solid {c['border']} !important;
    transition: background 0.15s !important;
}}
[data-testid="stDataFrame"] tr:hover td {{ background: {c['table_hover']} !important; }}
[data-testid="stDataFrame"] tr:nth-child(even) td {{ background: {c['table_stripe']} !important; }}
[data-testid="stDataFrame"] tr:nth-child(even):hover td {{ background: {c['table_hover']} !important; }}

/* ── 9. INPUTS ── */
[data-testid="stSelectbox"] label,
[data-testid="stNumberInput"] label,
[data-testid="stTextInput"] label,
[data-testid="stFileUploader"] label {{
    font-size: 0.88rem !important; font-weight: 600 !important;
    color: {c['text_sub']} !important; margin-bottom: 4px !important;
}}
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input {{
    border: 1.5px solid {c['border']} !important;
    border-radius: 8px !important; font-size: 0.95rem !important;
    padding: 8px 12px !important; background: {c['surface_hi']} !important;
    color: {c['text']} !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}}
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextInput"] input:focus {{
    border-color: {c['border_focus']} !important;
    box-shadow: 0 0 0 3px rgba(46,125,50,0.15) !important;
    outline: none !important; background: {c['surface']} !important;
}}
</style>"""


@st.cache_resource
def _css_part2() -> str:
    """CSS chunk 2: buttons, alerts, badges, form, scrollbar, progress, chip, spinner, pills."""
    c = _TOKENS
    return f"""<style>
/* VBSP-SCM UI — Dark Theme (2/2) */

/* ── 10. BUTTON (main content area) ── */
.stButton > button {{
    font-size: 0.9rem !important; font-weight: 600 !important;
    padding: 8px 20px !important; border-radius: 8px !important;
    border: 1.5px solid {c['border']} !important;
    background: {c['surface_hi']} !important; color: {c['text']} !important;
    transition: all 0.2s !important;
}}
.stButton > button:hover {{
    border-color: {c['accent_glow']} !important; color: {c['accent_glow']} !important;
    box-shadow: 0 2px 8px rgba(46,125,50,0.15) !important;
}}
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {c['accent']}, {c['accent_hi']}) !important;
    color: white !important; border: none !important;
    box-shadow: 0 3px 10px rgba(46,125,50,0.25) !important;
}}
.stButton > button[kind="primary"]:hover {{
    background: linear-gradient(135deg, {c['accent_hi']}, {c['accent']}) !important;
    box-shadow: 0 4px 14px rgba(46,125,50,0.35) !important;
}}

/* ── 11. ALERTS ── */
[data-testid="stAlert"] {{
    border-radius: 8px !important; font-size: 0.88rem !important;
    padding: 10px 14px !important; border: none !important;
    border-left: 4px solid transparent !important; margin: 6px 0 !important;
}}
div[data-testid="stAlert"] > div[class*="info"],
div[data-testid="stAlert"][kind="info"] {{
    background: {c['info_bg']} !important;
    border-left-color: {c['info_border']} !important;
    color: {c['info_text']} !important;
}}
div[data-testid="stAlert"] > div[class*="success"],
[data-testid="stAlert"][kind="success"] {{
    background: {c['success_bg']} !important;
    border-left-color: {c['success_border']} !important;
    color: {c['success_text']} !important;
}}
div[data-testid="stAlert"] > div[class*="warning"],
[data-testid="stAlert"][kind="warning"] {{
    background: {c['warn_bg']} !important;
    border-left-color: {c['warn_border']} !important;
    color: {c['warn_text']} !important;
}}
div[data-testid="stAlert"] > div[class*="error"],
[data-testid="stAlert"][kind="error"] {{
    background: {c['error_bg']} !important;
    border-left-color: {c['error_border']} !important;
    color: {c['error_text']} !important;
}}
[data-testid="stAlert"] p {{ font-size: 0.88rem !important; margin: 0 !important; }}

/* ── 12. ROLE BADGES ── */
.role-executive {{ background:#2D2B55; color:#B39DDB; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:700; }}
.role-admin     {{ background:{c['success_bg']}; color:{c['success_text']}; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:600; }}
.role-manager   {{ background:{c['warn_bg']}; color:{c['warn_text']}; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:600; }}
.role-user      {{ background:{c['info_bg']}; color:{c['info_text']}; padding:3px 12px;
    border-radius:20px; font-size:.82rem; font-weight:600; }}

/* ── 13. DIVIDER ── */
hr {{ border: none !important; border-top: 1px solid {c['border']} !important; margin: 1rem 0 !important; }}

/* ── 14. FORM ── */
[data-testid="stForm"] {{
    background: {c['surface']} !important; border-radius: 12px !important;
    border: 1px solid {c['border']} !important;
    padding: 20px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
}}

/* ── 15. SCROLLBAR ── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {c['scroll_track']}; border-radius: 4px; }}
::-webkit-scrollbar-thumb {{ background: {c['scroll_thumb']}; border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: {c['scroll_hover']}; }}

/* ── 16. PROGRESS BAR ── */
[data-testid="stProgressBar"] > div > div {{
    background: linear-gradient(90deg, {c['accent']}, {c['accent_glow']}) !important;
    border-radius: 4px !important;
}}

/* ── 17. CHIP / MULTISELECT ── */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {{
    background: {c['chip_bg']} !important; color: {c['chip_text']} !important;
    border: 1px solid {c['chip_border']} !important;
    border-radius: 20px !important; font-size: 0.82rem !important;
}}

/* ── 18. SPINNER ── */
[data-testid="stSpinner"] > div {{ border-top-color: {c['spinner']} !important; }}

/* ── 19. DATA SOURCE STATUS PILLS ── */
.ds-pill {{
    display: inline-flex; align-items: center; gap: 4px;
    padding: 6px 14px; border-radius: 20px;
    font-size: 0.82rem; font-weight: 500;
    border: 1px solid transparent;
    white-space: nowrap;
}}
.ds-pill.status-ok {{
    background: {c['success_bg']}; color: {c['success_text']};
    border-color: {c['success_border']};
}}
.ds-pill.status-warn {{
    background: {c['warn_bg']}; color: {c['warn_text']};
    border-color: {c['warn_border']};
}}
.ds-pill.status-error {{
    background: {c['error_bg']}; color: {c['error_text']};
    border-color: {c['error_border']};
}}
</style>"""


def get_theme_css() -> str:
    """Trả về CSS đầy đủ — giữ cho tương thích ngược."""
    return _css_part1() + _css_part2()


def init_theme() -> str:
    """Init theme — always dark."""
    st.session_state.theme = "dark"
    return "dark"

