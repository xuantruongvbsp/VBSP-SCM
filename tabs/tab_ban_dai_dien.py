import streamlit as st


def _render_cap_xa(**kwargs):
    st.header("🏛️ Ban Đại Diện HĐQT")
    st.caption("Quản lý họp · Báo cáo kiểm tra · Tổng hợp số liệu · Lưu trữ văn bản")

    sub1, sub2, sub3, sub4 = st.tabs([
        "📅 Họp BĐD",
        "📝 Báo cáo kiểm tra BĐD",
        "📊 Tổng hợp số liệu BĐD",
        "📁 Lưu trữ văn bản",
    ])

    with sub1:
        st.info(
            "**📅 Họp Ban Đại Diện**\n\n"
            "Chức năng đang phát triển — sẽ bao gồm:\n"
            "- Lịch họp BĐD định kỳ\n"
            "- Biên bản cuộc họp\n"
            "- Theo dõi kết luận & nhiệm vụ sau họp"
        )

    with sub2:
        st.info(
            "**📝 Báo cáo kiểm tra BĐD**\n\n"
            "Chức năng đang phát triển — sẽ bao gồm:\n"
            "- Soạn thảo báo cáo kiểm tra trực tiếp trong hệ thống\n"
            "- Tự động lấy số liệu từ HSTD (dư nợ, NQH, KHĐ...)\n"
            "- Lưu nháp theo kỳ · Xuất Word & PDF"
        )

    with sub3:
        st.info(
            "**📊 Tổng hợp số liệu BĐD**\n\n"
            "Chức năng đang phát triển — sẽ bao gồm:\n"
            "- Bảng số liệu tổng hợp phục vụ họp BĐD\n"
            "- So sánh kỳ này / kỳ trước\n"
            "- Xuất Excel báo cáo"
        )

    with sub4:
        st.info(
            "**📁 Lưu trữ văn bản BĐD**\n\n"
            "Chức năng đang phát triển — sẽ bao gồm:\n"
            "- Upload & quản lý văn bản chỉ đạo của BĐD\n"
            "- Kết luận cuộc họp theo từng kỳ\n"
            "- Tra cứu văn bản theo ngày / chủ đề"
        )


def _render_cap_tinh(**kwargs):
    sub1, sub2, sub3, sub4 = st.tabs([
        "📅 Họp BĐD tỉnh",
        "📝 Báo cáo kiểm tra BĐD tỉnh",
        "📊 Tổng hợp số liệu BĐD tỉnh",
        "📁 Lưu trữ văn bản",
    ])

    with sub1:
        st.info(
            "**📅 Họp Ban Đại Diện cấp tỉnh**\n\n"
            "Chức năng đang phát triển — sẽ bao gồm:\n"
            "- Lịch họp BĐD tỉnh định kỳ (quý/năm)\n"
            "- Biên bản & nghị quyết cuộc họp\n"
            "- Theo dõi kết luận chỉ đạo của BĐD tỉnh"
        )

    with sub2:
        st.info(
            "**📝 Báo cáo kiểm tra BĐD tỉnh**\n\n"
            "Chức năng đang phát triển — sẽ bao gồm:\n"
            "- Soạn thảo báo cáo kiểm tra toàn Chi nhánh\n"
            "- Tự động tổng hợp số liệu từ 22 PGD\n"
            "- Lưu nháp theo kỳ · Xuất Word & PDF"
        )

    with sub3:
        st.info(
            "**📊 Tổng hợp số liệu BĐD tỉnh**\n\n"
            "Chức năng đang phát triển — sẽ bao gồm:\n"
            "- Bảng số liệu tổng hợp toàn CN phục vụ họp BĐD tỉnh\n"
            "- So sánh kỳ này / kỳ trước theo từng PGD\n"
            "- Xuất Excel & PDF báo cáo"
        )

    with sub4:
        st.info(
            "**📁 Lưu trữ văn bản BĐD tỉnh**\n\n"
            "Chức năng đang phát triển — sẽ bao gồm:\n"
            "- Upload & quản lý văn bản chỉ đạo BĐD tỉnh\n"
            "- Kết luận cuộc họp theo từng kỳ\n"
            "- Tra cứu văn bản theo ngày / chủ đề"
        )


from utils import get_tab_context

def render(tab, cap: str = "xa", **kwargs):
    import streamlit as _st
    _tab_ctx = tab if tab is not None else _st.container()
    with _tab_ctx:
        if cap == "tinh":
            _render_cap_tinh(**kwargs)
        else:
            _render_cap_xa(**kwargs)
