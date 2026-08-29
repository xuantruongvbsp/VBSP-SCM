"""Tab Báo cáo Định kỳ — ROADMAP §2.1

Xem và tải báo cáo Excel được tạo tự động hằng ngày.
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from logger import get_logger
from tabs.base_tab import TabContext
from scripts.daily_report import list_reports, generate_daily_report
from scripts.daily_word_report import generate_word_report

logger = get_logger(__name__)


def _render_word_report(ctx: TabContext) -> None:
    st.caption("📄 Báo cáo Word tổng hợp — Tổng quan + NQH + KHTD")

    if st.button("🔄 Tạo báo cáo Word", type="primary", key="daily_word_gen", use_container_width=True):
        try:
            data = generate_word_report()
            st.download_button(
                "⬇️ Tải báo cáo Word (.docx)",
                data=data,
                file_name=f"BaoCao_Ngay_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="dl_word_report",
            )
            st.toast("✅ Đã tạo báo cáo Word!", icon="📄")
        except Exception as e:
            logger.error("word_report: %s", e, exc_info=True)
            st.error(f"❌ Lỗi tạo báo cáo Word: {e}")


def _render_daily_reports(ctx: TabContext) -> None:
    st.caption("📊 Báo cáo Excel được tạo tự động lúc 07:00 mỗi sáng (qua Task Scheduler)")
    st.caption("Nút tạo thủ công bên dưới chỉ tạo file Excel, không gửi Telegram.")

    reports = list_reports()

    col_gen, _ = st.columns([1, 3])
    with col_gen:
        if st.button("🔄 Tạo báo cáo ngay", type="primary", key="daily_report_gen"):
            try:
                result = generate_daily_report(notify=False)
                if result:
                    st.toast("✅ Đã tạo báo cáo mới!", icon="📊")
                else:
                    st.toast("⚠️ Lỗi tạo báo cáo — kiểm tra dữ liệu parquet", icon="⚠️")
            except Exception as e:
                logger.error("generate_daily_report: %s", e, exc_info=True)
                st.error(f"❌ Lỗi: {e}")
            st.rerun()

    if not reports:
        st.info("ℹ️ Chưa có báo cáo nào. Nhấn '🔄 Tạo báo cáo ngay' để tạo.")
        return

    st.markdown("---")
    st.markdown(f"#### 📁 {len(reports)} báo cáo đã tạo")

    for r in reports[:20]:
        col1, col2, col3 = st.columns([5, 2, 2])
        with col1:
            st.markdown(f"📊 **{r['file']}**")
        with col2:
            st.caption(f"🕐 {r['ts']} · {r['size_kb']} KB")
        with col3:
            try:
                with open(r["path"], "rb") as f:
                    st.download_button(
                        "⬇️ Tải",
                        data=f.read(),
                        file_name=r["file"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_{r['file']}",
                        use_container_width=True,
                    )
            except Exception:
                st.caption("⚠️ File lỗi")


def render(tab: DeltaGenerator | None = None, **kwargs) -> None:
    ctx = TabContext(tab, **kwargs)

    with ctx:
        st.title("📊 Báo cáo Định kỳ")
        st.caption("Báo cáo Excel + Word tự động hằng ngày — Tổng quan, NQH, Đến hạn, KHTD")

        if not (ctx.is_cn or ctx.is_exec):
            st.info(
                "Mục này chỉ dành cho Chi nhánh/Ban Giám đốc vì báo cáo được tạo từ dữ liệu toàn Chi nhánh. "
                "PGD vui lòng dùng **📥 Tiến độ nộp BC** để theo dõi báo cáo đã gửi và **📊 Báo cáo tín dụng** "
                "để xuất số liệu trong phạm vi đơn vị mình."
            )
            return

        col_excel, col_word = st.columns(2)
        with col_excel:
            _render_daily_reports(ctx)
        with col_word:
            _render_word_report(ctx)

        st.markdown("---")
        st.markdown("#### 📋 Hướng dẫn cài đặt tự động")
        st.code(r"scripts\setup_daily_report_task.bat  (chạy với Administrator)", language=None)
        st.caption("Sẽ tạo Task Scheduler chạy báo cáo lúc 07:00 mỗi sáng.")


__all__ = ["render"]
