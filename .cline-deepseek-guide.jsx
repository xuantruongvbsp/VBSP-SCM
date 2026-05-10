import { useState } from "react";

const CONFIG = {
  api: {
    title: "Cấu hình Cline + DeepSeek Official API",
    items: [
      {
        label: "Model khuyên dùng",
        value: "deepseek-chat (V3)",
        note: "Dùng V3 cho coding tasks. Chỉ dùng R1 khi cần reasoning phức tạp — R1 có thinking delay dài.",
        tag: "QUAN TRỌNG",
      },
      {
        label: "Context Window",
        value: "32,000 – 64,000 tokens",
        note: "Không để mặc định (128k). Project có .db/.accdb lớn rất dễ làm API timeout.",
        tag: "QUAN TRỌNG",
      },
      {
        label: "Max Output Tokens",
        value: "8,000 tokens",
        note: "Đủ cho hầu hết tasks. Tăng lên 16k nếu cần generate file dài.",
        tag: "",
      },
      {
        label: "API Endpoint",
        value: "https://api.deepseek.com",
        note: "Dùng Official API thay vì OpenRouter để tránh thêm 1 lớp latency.",
        tag: "",
      },
      {
        label: "Request Timeout",
        value: "120 – 180 giây",
        note: "Tăng nếu bạn thấy Cline báo lỗi timeout trước khi DeepSeek kịp trả lời.",
        tag: "",
      },
      {
        label: ".clineignore",
        value: "Bắt buộc có",
        note: "Chặn *.db, *.accdb, *.sqlite, node_modules/, .git/ — xem file .clineignore đã tạo kèm.",
        tag: "QUAN TRỌNG",
      },
    ],
  },
  debug: [
    {
      id: "d1",
      step: "Xác định bước bị treo",
      detail:
        'Nhìn vào label ngay trên progress bar của Cline: "Thinking", "Reading file: ...", hay "Executing: ..."',
      fix: 'Nếu "Thinking" → đổi sang V3. Nếu "Reading file" → kiểm tra .clineignore. Nếu "Executing" → xem Terminal tab.',
    },
    {
      id: "d2",
      step: "Kiểm tra Terminal tab trong VS Code",
      detail:
        "Mở Terminal panel, xem có process nào đang block (server đang chạy, script chờ input) không.",
      fix: "Ctrl+C để kill process đó. Sau đó bảo Cline: "Lệnh bị treo, hãy thực hiện lại và chia nhỏ các bước."",
    },
    {
      id: "d3",
      step: "Reload VS Code window",
      detail: "Giải phóng memory bị kẹt mà không mất session hiện tại.",
      fix: "F1 → gõ Developer: Reload Window → Enter. Nhanh nhất và an toàn nhất.",
    },
    {
      id: "d4",
      step: "Kiểm tra số dư API",
      detail:
        "Nếu hết credit giữa chừng, DeepSeek trả về lỗi 402/429 — Cline đôi khi không hiển thị lỗi rõ ràng mà chỉ đứng im.",
      fix: "Vào platform.deepseek.com → Usage → kiểm tra balance và rate limit.",
    },
    {
      id: "d5",
      step: "Giới hạn scope của task",
      detail:
        "Cline treo nhiều nhất khi task quá rộng: "refactor cả project" hay "đọc toàn bộ DB schema".",
      fix: 'Chia nhỏ: "Chỉ đọc file models.py, không đọc file khác" hoặc "Chỉ sửa hàm X trong file Y".',
    },
    {
      id: "d6",
      step: "File DB / binary lớn",
      detail:
        "Nếu Cline cố đọc .accdb/.db, nó sẽ gửi binary garbage lên API → treo hoặc lỗi ngay.",
      fix: 'Thêm vào yêu cầu: "Không đọc nội dung file database. Chỉ làm việc với file .py và .sql."',
    },
  ],
  prompts: [
    {
      title: "Làm việc với Database",
      text: "Chỉ đọc file schema.sql và models.py. Không mở hoặc đọc nội dung các file .db, .sqlite, .accdb. Nếu cần biết cấu trúc bảng, hỏi tôi trực tiếp.",
    },
    {
      title: "Khi bị treo giữa chừng",
      text: "Lệnh/bước trước đó bị treo. Hãy bỏ qua và tiếp tục từ bước tiếp theo. Chia nhỏ thành từng bước đơn lẻ, mỗi bước chỉ làm một việc.",
    },
    {
      title: "Giới hạn scope đọc file",
      text: "Chỉ đọc các file trong thư mục /src và /app. Bỏ qua hoàn toàn node_modules, .git, data/, logs/ và tất cả file binary.",
    },
    {
      title: "Refactor an toàn",
      text: "Chỉ sửa file [TÊN FILE]. Không tự ý đọc hoặc chỉnh sửa các file khác. Sau mỗi bước, dừng lại và báo cáo kết quả trước khi tiếp tục.",
    },
  ],
};

const Tag = ({ text }) =>
  text ? (
    <span
      style={{
        background: "#ff4d4d22",
        color: "#ff6b6b",
        border: "1px solid #ff6b6b44",
        borderRadius: "4px",
        padding: "1px 7px",
        fontSize: "10px",
        fontWeight: 700,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        marginLeft: "8px",
        verticalAlign: "middle",
      }}
    >
      {text}
    </span>
  ) : null;

const CheckItem = ({ item }) => {
  const [done, setDone] = useState(false);
  const [open, setOpen] = useState(false);
  return (
    <div
      style={{
        borderLeft: `3px solid ${done ? "#4ade80" : "#3b82f6"}`,
        background: done ? "#0f1f0f" : "#0d1117",
        borderRadius: "0 8px 8px 0",
        marginBottom: "10px",
        transition: "all 0.2s",
        opacity: done ? 0.6 : 1,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: "12px",
          padding: "12px 14px",
          cursor: "pointer",
        }}
        onClick={() => setOpen((v) => !v)}
      >
        <div
          onClick={(e) => {
            e.stopPropagation();
            setDone((v) => !v);
          }}
          style={{
            width: "20px",
            height: "20px",
            borderRadius: "50%",
            border: `2px solid ${done ? "#4ade80" : "#3b82f6"}`,
            background: done ? "#4ade80" : "transparent",
            flexShrink: 0,
            marginTop: "1px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "all 0.2s",
            cursor: "pointer",
          }}
        >
          {done && (
            <svg width="11" height="9" viewBox="0 0 11 9" fill="none">
              <path
                d="M1 4.5L4 7.5L10 1"
                stroke="#0d1117"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
        <div style={{ flex: 1 }}>
          <div
            style={{
              color: done ? "#4ade80" : "#e2e8f0",
              fontWeight: 600,
              fontSize: "14px",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {item.step}
          </div>
          <div
            style={{
              color: "#64748b",
              fontSize: "12px",
              marginTop: "3px",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {item.detail}
          </div>
        </div>
        <div
          style={{
            color: "#475569",
            fontSize: "12px",
            transform: open ? "rotate(180deg)" : "rotate(0)",
            transition: "0.2s",
            marginTop: "2px",
          }}
        >
          ▼
        </div>
      </div>
      {open && (
        <div
          style={{
            padding: "0 14px 12px 46px",
            color: "#94a3b8",
            fontSize: "12px",
            fontFamily: "'JetBrains Mono', monospace",
            lineHeight: 1.7,
            borderTop: "1px solid #1e293b",
            paddingTop: "10px",
            marginTop: "0",
          }}
        >
          <span style={{ color: "#3b82f6", fontWeight: 700 }}>→ FIX: </span>
          {item.fix}
        </div>
      )}
    </div>
  );
};

const CopyButton = ({ text }) => {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      style={{
        background: copied ? "#4ade8022" : "#1e293b",
        color: copied ? "#4ade80" : "#94a3b8",
        border: `1px solid ${copied ? "#4ade8044" : "#334155"}`,
        borderRadius: "6px",
        padding: "4px 12px",
        fontSize: "11px",
        cursor: "pointer",
        fontFamily: "'JetBrains Mono', monospace",
        transition: "all 0.2s",
        whiteSpace: "nowrap",
      }}
    >
      {copied ? "✓ Copied" : "Copy"}
    </button>
  );
};

export default function App() {
  const [tab, setTab] = useState("config");
  const completedCount = CONFIG.debug.filter(() => false).length;

  const tabs = [
    { id: "config", label: "⚙️  Cấu hình" },
    { id: "debug", label: "🔍  Debug" },
    { id: "prompts", label: "💬  Prompt mẫu" },
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#080c12",
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        padding: "0",
        color: "#e2e8f0",
      }}
    >
      <link
        href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Space+Grotesk:wght@400;600;700&display=swap"
        rel="stylesheet"
      />

      {/* Header */}
      <div
        style={{
          background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)",
          borderBottom: "1px solid #1e293b",
          padding: "24px 28px 20px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            marginBottom: "6px",
          }}
        >
          <div
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: "#4ade80",
              boxShadow: "0 0 8px #4ade80",
              animation: "pulse 2s infinite",
            }}
          />
          <span style={{ color: "#64748b", fontSize: "11px", letterSpacing: "0.1em" }}>
            CLINE × DEEPSEEK OFFICIAL API
          </span>
        </div>
        <h1
          style={{
            margin: 0,
            fontSize: "22px",
            fontWeight: 700,
            color: "#f1f5f9",
            fontFamily: "'Space Grotesk', sans-serif",
            letterSpacing: "-0.02em",
          }}
        >
          Hướng dẫn tối ưu & Debug
        </h1>
        <p style={{ margin: "6px 0 0", color: "#475569", fontSize: "12px" }}>
          Python · SQL · Web · Config — DeepSeek V3 · Official API
        </p>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid #1e293b",
          background: "#0d1117",
          padding: "0 28px",
          gap: "0",
        }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              background: "transparent",
              border: "none",
              borderBottom: `2px solid ${tab === t.id ? "#3b82f6" : "transparent"}`,
              color: tab === t.id ? "#3b82f6" : "#475569",
              padding: "12px 18px",
              cursor: "pointer",
              fontSize: "12px",
              fontFamily: "'JetBrains Mono', monospace",
              fontWeight: tab === t.id ? 700 : 400,
              transition: "all 0.15s",
              letterSpacing: "0.02em",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ padding: "24px 28px", maxWidth: "720px" }}>
        {/* CONFIG TAB */}
        {tab === "config" && (
          <div>
            <p
              style={{
                color: "#475569",
                fontSize: "12px",
                marginBottom: "20px",
                lineHeight: 1.6,
              }}
            >
              Cài đặt tối ưu cho Cline Settings trong VS Code. Nhấn vào từng mục để xem giải thích.
            </p>
            {CONFIG.api.items.map((item, i) => (
              <ConfigRow key={i} item={item} />
            ))}
            <div
              style={{
                marginTop: "20px",
                background: "#0d1a0d",
                border: "1px solid #4ade8033",
                borderRadius: "8px",
                padding: "14px 16px",
              }}
            >
              <div
                style={{ color: "#4ade80", fontSize: "12px", fontWeight: 700, marginBottom: "8px" }}
              >
                ✓ File .clineignore đã được tạo kèm
              </div>
              <div style={{ color: "#64748b", fontSize: "11px", lineHeight: 1.7 }}>
                Đặt file <code style={{ color: "#94a3b8" }}>.clineignore</code> ở root của project.
                Đã chặn: <code style={{ color: "#f59e0b" }}>*.db</code>,{" "}
                <code style={{ color: "#f59e0b" }}>*.accdb</code>,{" "}
                <code style={{ color: "#f59e0b" }}>*.sqlite</code>,{" "}
                <code style={{ color: "#f59e0b" }}>node_modules/</code>,{" "}
                <code style={{ color: "#f59e0b" }}>.git/</code>, và các binary khác.
              </div>
            </div>
          </div>
        )}

        {/* DEBUG TAB */}
        {tab === "debug" && (
          <div>
            <p
              style={{
                color: "#475569",
                fontSize: "12px",
                marginBottom: "20px",
                lineHeight: 1.6,
              }}
            >
              Checklist debug theo thứ tự. Nhấn vào từng bước để xem cách fix. Tick khi đã xử lý xong.
            </p>
            {CONFIG.debug.map((item) => (
              <CheckItem key={item.id} item={item} />
            ))}
          </div>
        )}

        {/* PROMPTS TAB */}
        {tab === "prompts" && (
          <div>
            <p
              style={{
                color: "#475569",
                fontSize: "12px",
                marginBottom: "20px",
                lineHeight: 1.6,
              }}
            >
              Copy và dán vào đầu mỗi task trong Cline để tránh các lỗi phổ biến.
            </p>
            {CONFIG.prompts.map((p, i) => (
              <div
                key={i}
                style={{
                  background: "#0d1117",
                  border: "1px solid #1e293b",
                  borderRadius: "8px",
                  marginBottom: "14px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "10px 14px",
                    borderBottom: "1px solid #1e293b",
                    background: "#0a0f1a",
                  }}
                >
                  <span
                    style={{
                      color: "#94a3b8",
                      fontSize: "12px",
                      fontWeight: 700,
                    }}
                  >
                    {p.title}
                  </span>
                  <CopyButton text={p.text} />
                </div>
                <div
                  style={{
                    padding: "12px 14px",
                    color: "#64748b",
                    fontSize: "12px",
                    lineHeight: 1.8,
                    fontStyle: "italic",
                  }}
                >
                  "{p.text}"
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

function ConfigRow({ item }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      onClick={() => setOpen((v) => !v)}
      style={{
        background: "#0d1117",
        border: "1px solid #1e293b",
        borderRadius: "8px",
        marginBottom: "8px",
        cursor: "pointer",
        transition: "border-color 0.15s",
        borderColor: open ? "#3b82f644" : "#1e293b",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "11px 14px",
        }}
      >
        <div>
          <span style={{ color: "#64748b", fontSize: "11px" }}>{item.label}</span>
          <Tag text={item.tag} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span
            style={{
              color: "#f59e0b",
              fontSize: "13px",
              fontWeight: 700,
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {item.value}
          </span>
          <span
            style={{
              color: "#334155",
              fontSize: "11px",
              transform: open ? "rotate(180deg)" : "rotate(0)",
              transition: "0.2s",
            }}
          >
            ▼
          </span>
        </div>
      </div>
      {open && (
        <div
          style={{
            padding: "0 14px 12px",
            color: "#64748b",
            fontSize: "12px",
            lineHeight: 1.7,
            borderTop: "1px solid #1e293b",
            paddingTop: "10px",
          }}
        >
          {item.note}
        </div>
      )}
    </div>
  );
}
