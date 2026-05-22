export function modifyConfig(config: Config): Config {
  config.name = "VBSP-SCM";
  config.version = "1.0.0";

  config.systemMessage = [
    "Bạn là trợ lý code cho dự án VBSP-SCM — Hệ thống Quản trị Tín dụng Nội bộ NHCSXH Chi nhánh Đồng Nai.",
    "Stack: Streamlit + Python 3 + SQLite + PyArrow/Parquet.",
    "TUYỆT ĐỐI không tự git commit/push. Không thêm dependency mới.",
    "Luôn dùng COT_* từ config.py, không hardcode tên cột tiếng Việt.",
    "Dùng db.ghi_kv()/db.doc_kv() để lưu/đọc, KHÔNG dùng json.dump/open().",
    "Tiền tệ: nhập triệu → lưu VND ×1.000.000 → hiển thị fmt_ty().",
    "Luôn gọi db.ghi_audit() sau mỗi db.ghi_kv().",
    "Luôn st.cache_data.clear() sau upload/lưu.",
  ].join("\n");

  config.rules = [
    { path: ".trae/rules/rules.md" },
  ];

  config.context = [
    {
      name: "project",
      type: "file",
      params: { file: "CLAUDE.md" },
    },
    {
      name: "schema",
      type: "file",
      params: { file: "SCHEMA.md" },
    },
    {
      name: "bugmap",
      type: "file",
      params: { file: "BUGMAP.md" },
    },
  ];

  config.models = [
    {
      title: "📐 PLAN - qwen-max",
      provider: "openai",
      model: "qwen-max",
      apiBase: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
      apiKey: process.env.DASHSCOPE_API_KEY,
      contextLength: 32768,
      maxTokens: 4096,
    },
    {
      title: "🛠️ BUILD - qwen-coder-plus",
      provider: "openai",
      model: "qwen-coder-plus",
      apiBase: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
      apiKey: process.env.DASHSCOPE_API_KEY,
      contextLength: 131072,
      maxTokens: 4096,
    },
    {
      title: "💡 ASK - qwen-plus",
      provider: "openai",
      model: "qwen-plus",
      apiBase: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
      apiKey: process.env.DASHSCOPE_API_KEY,
      contextLength: 131072,
      maxTokens: 2048,
    },
  ];

  config.tabAutocompleteModel = {
    title: "⚡ AutoTab - qwen-turbo",
    provider: "openai",
    model: "qwen-turbo",
    apiBase: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    apiKey: process.env.DASHSCOPE_API_KEY,
    contextLength: 4096,
    maxTokens: 256,
  };

  config.tabAutocompleteOptions = {
    disable: false,
    maxPromptTokens: 100,
    maxSuffixPercentage: 0.1,
  };

  config.customCommands = [
    {
      name: "plan",
      prompt: "Đóng vai kiến trúc sư dự án VBSP-SCM (Streamlit + SQLite + Parquet). Lập kế hoạch cho: {{selection}}. Output: 1.File cần tạo/sửa 2.Structure code 3.Logic xử lý 4.Rủi ro & cách tránh. Ngắn gọn, tiếng Việt. Lưu ý: dùng COT_* từ config.py, db.ghi_kv()/db.doc_kv(), fmt_ty() cho tiền tệ.",
      description: "📐 Lập kế hoạch code",
    },
    {
      name: "build",
      prompt: "Viết code cho: {{selection}}. Chỉ trả code hoàn chỉnh. Không giải thích trừ khi được hỏi. Tuân thủ convention VBSP-SCM: COT_* từ config.py, db.ghi_kv()/db.doc_kv(), fmt_ty(), ghi_audit() sau ghi_kv(). Giữ nguyên signature nếu sửa hàm có sẵn.",
      description: "🛠️ Viết/sửa code",
    },
    {
      name: "ask",
      prompt: "Giải thích ngắn gọn {{selection}} bằng tiếng Việt. Chỉ nêu cú pháp, cách dùng và 1 ví dụ nhỏ. Không lan man.",
      description: "💡 Hỏi nhanh cú pháp",
    },
    {
      name: "bugfix",
      prompt: "Bugfix: {{selection}}. Quy tắc: Chỉ sửa đúng hàm bị lỗi, không thay đổi logic xung quanh. Không import dependency mới. Không sửa signature hàm. Xem BUGMAP.md trước khi sửa. Dùng COT_* từ config.py.",
      description: "🐛 Fix bug theo traceback",
    },
    {
      name: "review",
      prompt: "Review code VBSP-SCM: {{selection}}. Kiểm tra: 1)COT_* thay vì hardcode? 2)db.ghi_audit() sau ghi_kv()? 3)st.cache_data.clear() sau upload? 4)Widget key unique? 5)Signature khớp rules.md? 6)Import dependency mới?",
      description: "🔍 Review code",
    },
  ];

  return config;
}
