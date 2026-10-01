import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, Bot, ChevronDown, Cpu, Paperclip, RotateCcw, Send } from "lucide-react";
import api from "../../api/client";
import { useAuth, initials } from "../../context/AuthContext";
import AiMarkdown from "../../components/ui/AiMarkdown";

/** Ghép nhãn trích dẫn gọn: "Điều 12 · Khoản 3 · Quy chế ... · tr.~45" */
const srcLabel = (s) => {
  const parts = [s.dieu, s.khoan, s.ten_dieu || s.muc, s.so_trang ? `tr.~${s.so_trang}` : ""].filter(Boolean);
  return parts.join(" · ") || "Quy chế";
};

const fmtTime = (ts) =>
  new Date(ts).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });

/** Nhãn gọn của model trong dropdown / chip tin nhắn (bỏ hậu tố ":free" cho gọn) */
const shortModel = (id) => (id || "").replace(/:free$/, "");

/**
 * Tách "<provider>/<model>" thành [provider, model].
 * KHÔNG dùng split("/", 2): tham số 2 của split là số phần tử tối đa, nên
 * "openrouter/nvidia/nemotron-…" sẽ bị cắt thành "nvidia" và mất phần còn lại.
 */
const splitSelection = (sel) => {
  const i = (sel || "").indexOf("/");
  return i < 0 ? ["", ""] : [sel.slice(0, i), sel.slice(i + 1)];
};

/** Nghịch đảo của splitSelection — nơi DUY NHẤT mã hóa khóa "<provider>/<model>" */
const selKey = (provider, model) => `${provider}/${model}`;

/**
 * Đọc SSE từ Response: event cách nhau bằng dòng trống, mỗi event một dòng
 * "data: {json}". Gọi onEvent(ev) cho từng event parse được; bỏ qua dòng khác
 * và event hỏng JSON. Tách riêng khỏi component vì đây thuần là chuyện
 * transport, không liên quan tới state của khung chat.
 *
 * Lỗi từ onEvent KHÔNG bị nuốt — để lọt lên caller (sendText hiển thị lỗi).
 */
const readSSE = async (res, onEvent) => {
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, sep).trim();
      buffer = buffer.slice(sep + 2);
      if (!raw.startsWith("data: ")) continue;
      let ev;
      try {
        ev = JSON.parse(raw.slice("data: ".length));
      } catch {
        continue; // event hỏng — bỏ qua, không làm chết cả stream
      }
      onEvent(ev);
    }
  }
};

/** Câu hỏi gợi ý — hiện ở màn hình chào, nhấn vào là gửi ngay */
const SUGGESTIONS = [
  "Người học có những quyền gì?",
  "Khi nào sinh viên bị cấm thi?",
  "Điều kiện xét học bổng khuyến khích?",
  "Các hình thức kỷ luật người học?",
  "Quy trình xử lý kỷ luật gồm mấy bước?",
  "Cách tính điểm học phần và GPA?",
];

function BotAvatar({ large = false }) {
  return (
    <span
      className={`${large ? "w-14 h-14" : "w-7 h-7"} rounded-full bg-primary text-white flex items-center justify-center shrink-0 shadow-sm`}
    >
      <Bot size={large ? 26 : 14} />
    </span>
  );
}

function SourceList({ sources }) {
  if (!sources?.length) return null;
  return (
    <details className="mt-2 pt-2 border-t border-border text-xs">
      <summary className="cursor-pointer select-none inline-flex items-center gap-1 text-primary hover:text-primary-hover font-medium">
        <Paperclip size={12} />
        {sources.length} nguồn trích dẫn
      </summary>
      <ul className="mt-2 space-y-1.5">
        {sources.map((s, i) => (
          <li
            key={i}
            className="bg-primary-soft border-l-2 border-primary rounded-r-md px-3 py-2"
          >
            <div className="font-semibold text-primary">{srcLabel(s)}</div>
            {s.text && (
              <div className="mt-0.5 text-secondary whitespace-pre-line">{s.text}</div>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Ba chấm nhún nhảy trong lúc chờ bot trả lời */
function TypingBubble() {
  return (
    <div className="flex items-end gap-2.5">
      <BotAvatar />
      <div className="bg-surface border border-border rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1">
          {[0, 150, 300].map((d) => (
            <span
              key={d}
              className="w-1.5 h-1.5 rounded-full bg-secondary/50 animate-bounce"
              style={{ animationDelay: `${d}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/** Dropdown chọn model AI (đầu khung chat). Model lỗi tự fallback sang model khác. */
function ModelSelect({ models, loading, selected, onChange, disabled }) {
  if (!models.length) return null;
  return (
    <div className="relative ml-auto">
      <Cpu size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-secondary pointer-events-none" />
      <select
        value={selected}
        onChange={onChange}
        disabled={disabled || loading}
        title="Chọn model AI trả lời — model lỗi sẽ tự động chuyển sang model khác"
        className="max-w-[190px] text-xs border border-border rounded-md pl-7 pr-7 py-1.5 bg-app focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed appearance-none truncate"
      >
        {loading && <option>Đang tải model…</option>}
        {models.map((m) => (
          <option key={selKey(m.provider, m.model)} value={selKey(m.provider, m.model)}>
            {shortModel(m.model)}
          </option>
        ))}
      </select>
      <ChevronDown size={13} className="absolute right-2 top-1/2 -translate-y-1/2 text-secondary pointer-events-none" />
    </div>
  );
}

export default function RegulationChatPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  // true khi chữ đang chảy dần vào bong bóng bot (ẩn bong bóng "đang gõ")
  const [streaming, setStreaming] = useState(false);
  const [models, setModels] = useState([]);
  const [selected, setSelected] = useState(""); // "<provider>/<model>"
  const [modelsLoading, setModelsLoading] = useState(true);
  // session_id phân biệt ngữ cảnh hội thoại phía server; đổi khi xóa hội thoại
  const sessionIdRef = useRef(`web-${Math.random().toString(36).slice(2, 10)}`);
  // id tin nhắn bot đang stream trong lượt gửi hiện tại (null = chưa tạo)
  const streamIdRef = useRef(null);
  // hủy kết nối stream khi rời trang
  const abortRef = useRef(null);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () =>
    requestAnimationFrame(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }));

  // Lấy danh sách model miễn phí khả dụng cho dropdown (GET /ai/regulation-chat/models)
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get("/ai/regulation-chat/models");
        if (!alive) return;
        const list = data.models || [];
        setModels(list);
        const def = data.default;
        if (def?.provider && def?.model) setSelected(selKey(def.provider, def.model));
        else if (list[0]) setSelected(selKey(list[0].provider, list[0].model));
      } catch {
        // 503 / lỗi mạng: không có model nào -> ẩn dropdown, server tự dùng mặc định
        if (alive) setModels([]);
      } finally {
        if (alive) setModelsLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // Tự cuộn xuống cuối khi có tin nhắn mới hoặc bot đang gõ
  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  // Hủy stream đang chạy nếu rời trang
  useEffect(() => () => abortRef.current?.abort(), []);

  const sendText = async (q) => {
    const text = q.trim();
    if (!text || sending) return;
    setSending(true);
    setStreaming(false);
    streamIdRef.current = null;
    setMessages((m) => [...m, { role: "user", text, at: Date.now() }]);
    const [provider, model] = splitSelection(selected);

    // Cập nhật bong bóng bot đang stream — mọi nhánh (flush/done/error) dùng chung
    const updateBot = (fn) =>
      setMessages((m) =>
        m.map((x) => (x.id === streamIdRef.current ? fn(x) : x))
      );

    // Gom delta theo nhịp 50ms — không re-render markdown mỗi token
    let pending = "";
    let flushTimer = null;
    const flush = () => {
      flushTimer = null;
      if (!pending) return;
      const chunk = pending;
      pending = "";
      updateBot((x) => ({ ...x, text: x.text + chunk }));
    };
    // Bỏ phần chữ đang chờ flush — gọi khi done/error sẽ thay hoặc ghi đè text
    const dropPending = () => {
      if (flushTimer) {
        clearTimeout(flushTimer);
        flushTimer = null;
      }
      pending = "";
    };

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const token = localStorage.getItem("ql_token");
      const res = await fetch(`${api.defaults.baseURL}/ai/regulation-chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          question: text,
          session_id: sessionIdRef.current,
          provider,
          model,
        }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        let detail = `HTTP ${res.status}`;
        try {
          const data = await res.json();
          if (typeof data.detail === "string") detail = data.detail;
        } catch {
          /* giữ detail mặc định */
        }
        throw Object.assign(new Error(detail), { status: res.status });
      }

      // Đọc SSE: event cách nhau bằng dòng trống, mỗi event một dòng "data: {json}"
      const handleEvent = (ev) => {
        if (ev.type === "meta") {
          // Tạo bong bóng bot rỗng kèm trích dẫn — chữ sẽ chảy vào sau
          const id = `bot-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
          streamIdRef.current = id;
          setMessages((m) => [
            ...m,
            { id, role: "bot", text: "", sources: ev.sources, at: Date.now() },
          ]);
          setStreaming(true);
        } else if (ev.type === "delta") {
          pending += ev.text;
          if (!flushTimer) flushTimer = setTimeout(flush, 50);
        } else if (ev.type === "done") {
          // Câu hoàn chỉnh đã qua clean_answer — thay text đang chảy bằng nó
          dropPending();
          updateBot((x) => ({
            ...x, text: ev.answer, provider: ev.provider, model: ev.model, complete: true,
          }));
          // Model được chọn bị lỗi, server tự fallback — cập nhật dropdown theo
          // model thực tế trả lời để câu sau khỏi gọi lại model đang lỗi
          if (provider && ev.provider && ev.model && ev.model !== model) {
            const next = selKey(ev.provider, ev.model);
            if (models.some((m) => selKey(m.provider, m.model) === next)) setSelected(next);
          }
        } else if (ev.type === "error") {
          dropPending();
          updateBot((x) => ({
            ...x, text: x.text ? `${x.text}\n\n${ev.message}` : ev.message,
          }));
        }
      };
      await readSSE(res, handleEvent);
      flush();
    } catch (err) {
      const status = err?.status;
      const hint =
        status === 503
          ? " — Chatbot quy chế chưa được bật: cần vector store (tài liệu quy chế) và API key trong backend/.env."
          : "";
      const msgText = `Có lỗi khi gọi chatbot: ${err.message}${hint}`;
      // Chưa tạo bong bóng bot (lỗi trước event meta) -> thêm mới; đã có thì ghi vào
      if (streamIdRef.current == null) {
        setMessages((m) => [...m, { role: "bot", text: msgText, at: Date.now() }]);
      } else {
        updateBot((x) => ({
          ...x, text: x.text ? `${x.text}\n\n${msgText}` : msgText,
        }));
      }
    } finally {
      dropPending();
      abortRef.current = null;
      setStreaming(false);
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const submit = (e) => {
    e.preventDefault();
    const q = question;
    setQuestion("");
    // Đặt lại chiều cao textarea sau khi gửi
    if (inputRef.current) inputRef.current.style.height = "auto";
    sendText(q);
  };

  const resetConversation = () => {
    setMessages([]);
    sessionIdRef.current = `web-${Math.random().toString(36).slice(2, 10)}`;
  };

  // Enter để gửi, Shift+Enter xuống dòng; textarea tự giãn theo nội dung
  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(e);
    }
  };
  const autoResize = (e) => {
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 128) + "px";
  };

  return (
    <section className="bg-surface border border-border rounded-lg shadow-sm flex flex-col h-[calc(100vh-6.5rem)] min-h-[26rem]">
      {/* Đầu khung chat — tên bot + trạng thái + chọn model + xóa hội thoại */}
      <header className="flex items-center gap-3 px-5 py-3 border-b border-border shrink-0">
        <div className="relative shrink-0">
          <span className="w-10 h-10 rounded-full bg-primary-soft text-primary flex items-center justify-center">
            <Bot size={20} />
          </span>
          <span
            className="absolute bottom-0 right-0 w-3 h-3 rounded-full bg-success border-2 border-surface"
            title="Trực tuyến"
          />
        </div>
        <div className="font-semibold text-sm">Trợ lý quy chế</div>
        <ModelSelect
          models={models}
          loading={modelsLoading}
          selected={selected}
          onChange={(e) => setSelected(e.target.value)}
          disabled={sending}
        />
        {messages.length > 0 && (
          <button
            onClick={resetConversation}
            disabled={sending}
            title="Xóa hội thoại"
            className={`${models.length ? "" : "ml-auto "}p-2 rounded-md text-secondary hover:bg-app hover:text-danger transition-colors duration-150 cursor-pointer disabled:opacity-50`}
          >
            <RotateCcw size={16} />
          </button>
        )}
      </header>

      {/* Vùng tin nhắn */}
      <div className="flex-1 overflow-y-auto bg-app px-4 py-4 space-y-4">
        {messages.length === 0 && !sending && (
          <div className="flex flex-col items-center justify-start h-full text-center px-4 pt-[7vh]">
            <BotAvatar large />
            <p className="mt-3 font-semibold">Chào bạn, mình là trợ lý quy chế</p>
            <div className="mt-5 w-full max-w-xl grid grid-cols-1 sm:grid-cols-2 gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendText(s)}
                  className="group flex items-center justify-between gap-3 text-left text-sm bg-surface border border-border rounded-xl px-3.5 py-2.5 text-primary shadow-sm hover:border-primary/50 hover:bg-primary-soft transition-colors duration-150 cursor-pointer"
                >
                  <span className="truncate">{s}</span>
                  <ArrowUpRight
                    size={15}
                    className="shrink-0 text-secondary opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                  />
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex items-end justify-end gap-2.5">
              <div className="flex flex-col items-end max-w-[80%] md:max-w-[70%]">
                <div className="whitespace-pre-line text-sm text-white bg-primary rounded-2xl rounded-br-md px-4 py-2.5 shadow-sm">
                  {m.text}
                </div>
                <span className="mt-1 text-[10px] text-secondary">{fmtTime(m.at)}</span>
              </div>
              <span
                className="w-7 h-7 rounded-full bg-primary-soft text-primary text-[10px] font-semibold flex items-center justify-center shrink-0"
                title={user?.name || user?.username}
              >
                {initials(user?.name || user?.username || "")}
              </span>
            </div>
          ) : (
            <div key={i} className="flex items-end gap-2.5">
              <BotAvatar />
              <div className="flex flex-col items-start max-w-[85%] md:max-w-[75%]">
                <div className="text-sm bg-surface border border-border rounded-2xl rounded-bl-md px-4 py-2.5 shadow-sm">
                  <div className="[&>*:first-child]:mt-0">
                    <AiMarkdown text={m.text} />
                  </div>
                  {m.complete && <SourceList sources={m.sources} />}
                  {m.model && (
                    <div className="mt-1.5 text-[10px] text-secondary truncate max-w-full">
                      {shortModel(m.model)}
                    </div>
                  )}
                </div>
                <span className="mt-1 text-[10px] text-secondary">{fmtTime(m.at)}</span>
              </div>
            </div>
          )
        )}

        {sending && !streaming && <TypingBubble />}
        <div ref={bottomRef} />
      </div>

      {/* Ô nhập tin */}
      <form onSubmit={submit} className="flex items-end gap-2 px-4 py-3 border-t border-border shrink-0">
        <textarea
          ref={inputRef}
          rows={1}
          className="flex-1 resize-none max-h-32 border border-border rounded-2xl px-4 py-2.5 text-sm bg-app focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors duration-150"
          placeholder="Nhập câu hỏi về quy chế đào tạo… (Enter để gửi)"
          value={question}
          onChange={(e) => {
            setQuestion(e.target.value);
            autoResize(e);
          }}
          onKeyDown={onKeyDown}
        />
        <button
          type="submit"
          disabled={sending || !question.trim()}
          title="Gửi câu hỏi"
          className="w-10 h-10 rounded-full bg-primary text-white flex items-center justify-center shrink-0 shadow-sm hover:bg-primary-hover transition-colors duration-150 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send size={17} />
        </button>
      </form>
    </section>
  );
}
