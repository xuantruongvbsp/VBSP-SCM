def render_sidebar_menu(role: str, username: str, **kwargs):
    """Render menu ĐIỀU HÀNH — gọi từ app.py bên trong with st.sidebar.
    Tối ưu: dùng st.radio() theo nhóm thay cho ~25 st.button() riêng lẻ."""

    GROUP_COLORS = {
        "Giám sát":                    {"bg": "#0D2137", "border": "#64B5F6", "text": "#90CAF9"},
        "Kiểm soát":                   {"bg": "#2D0D14", "border": "#EF9A9A", "text": "#F48FB1"},
        "Kế hoạch và Thực hiện KHTD": {"bg": "#0D2818", "border": "#A5D6A7", "text": "#A5D6A7"},
        "Báo cáo":                     {"bg": "#2D1F0D", "border": "#FFCC80", "text": "#FFD54F"},
        "Ủy Thác":                     {"bg": "#1A1040", "border": "#CE93D8", "text": "#CE93D8"},
        "Phối hợp với PGD":            {"bg": "#0D2818", "border": "#80CBC4", "text": "#80CBC4"},
        "Thông tin chung":             {"bg": "#0D2137", "border": "#90CAF9", "text": "#90CAF9"},
        "Hệ thống":                    {"bg": "#1E2130", "border": "#94A3B8", "text": "#B0BEC5"},
    }

    all_items = _build_all_items(role, username, **kwargs)
    if not all_items:
        return

    valid_labels = [x["label"] for x in all_items] + [
        c["label"] for x in all_items for c in x.get("children", [])
    ]

    if "ws_mgmt_menu" not in st.session_state:
        st.session_state["ws_mgmt_menu"] = all_items[0]["label"]
    if st.session_state["ws_mgmt_menu"] not in valid_labels:
        st.session_state["ws_mgmt_menu"] = all_items[0]["label"]

    active_label = st.session_state.get("ws_mgmt_menu", "")

    for key in list(st.session_state.keys()):
        if key.startswith("ws_mgmt_grp_"):
            val = st.session_state[key]
            if val and val != active_label and val in valid_labels:
                st.session_state["ws_mgmt_menu"] = val
                active_label = val

    st.markdown(
        "<p style='font-size:14px;font-weight:700;"
        "color:#94A3B8;margin-bottom:6px'>MENU ĐIỀU HÀNH</p>",
        unsafe_allow_html=True
    )

    groups = []
    current_grp = None
    cur_flat = []
    cur_acc = []
    for item in all_items:
        g = item["group"]
        if g != current_grp:
            if cur_flat or cur_acc:
                groups.append((current_grp, cur_flat, cur_acc))
            current_grp = g
            cur_flat = []
            cur_acc = []
        if item.get("children"):
            cur_acc.append(item)
        else:
            cur_flat.append(item)
    if cur_flat or cur_acc:
        groups.append((current_grp, cur_flat, cur_acc))

    for grp_name, flat_items, acc_items in groups:
        clr = GROUP_COLORS.get(grp_name, {"bg": "#F1EFE8", "border": "#888", "text": "#444"})

        st.markdown(
            f"<p style='font-size:11px;font-weight:700;"
            f"color:{clr['text']};text-transform:uppercase;"
            f"letter-spacing:0.06em;padding:12px 4px 4px;margin:0'>"
            f"{grp_name}</p>",
            unsafe_allow_html=True,
        )

        if flat_items:
            flat_labels = [it["label"] for it in flat_items]
            radio_key = f"ws_mgmt_grp_{grp_name}"

            try:
                idx = flat_labels.index(active_label)
            except ValueError:
                idx = None

            st.radio(
                grp_name,
                flat_labels,
                index=idx,
                key=radio_key,
                label_visibility="collapsed",
            )

        for item in acc_items:
            children = item.get("children", [])
            child_labels = [c["label"] for c in children]
            is_child_active = active_label in child_labels
            open_key = f"ws_mgmt_acc_{item['label']}"

            if is_child_active and not st.session_state.get(open_key):
                st.session_state[open_key] = True

            is_open = st.session_state.get(open_key, False)

            if is_child_active:
                st.markdown(
                    f"<div style='"
                    f"background:#E65100;"
                    f"border-left:3px solid #BF360C;"
                    f"color:#FFFFFF;"
                    f"font-size:14px;font-weight:700;"
                    f"padding:10px 12px 10px 14px;"
                    f"border-radius:0 6px 6px 0;"
                    f"margin-bottom:4px'>"
                    f"\u25be {item['label']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                arrow = "\u25be" if is_open else "\u25b8"
                if st.button(
                    f"{arrow} {item['label']}",
                    key=f"menu_acc_{item['label']}",
                    width="stretch",
                ):
                    st.session_state[open_key] = not is_open
                    st.rerun()

            if is_open:
                for child in children:
                    is_child_sel = active_label == child["label"]
                    if is_child_sel:
                        st.markdown(
                            f"<div style='background:#E65100;"
                            f"border-left:4px solid #BF360C;"
                            f"color:#FFFFFF;font-size:13px;font-weight:700;"
                            f"padding:8px 10px 8px 22px;"
                            f"border-radius:0 6px 6px 0;margin-bottom:3px'>"
                            f"\u25cf {child['label']}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        _, col = st.columns([0.06, 0.94])
                        with col:
                            if st.button(
                                f"\u21b3 {child['label']}",
                                key=f"menu_child_{child['label']}",
                                width="stretch",
                            ):
                                st.session_state["ws_mgmt_menu"] = child["label"]
                                st.rerun()

