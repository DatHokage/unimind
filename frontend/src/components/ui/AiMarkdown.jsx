import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Style cho markdown trong văn bản AI — render thay vì in dấu ** raw ra màn hình.
 *  Dùng chung bởi 2 mặt AI: Tư vấn đăng ký (RegistrationPage) + Chatbot quy chế
 *  (RegulationChatPage) để kiểu chữ/link/code không trôi dần theo từng trang. */
const MD_COMPONENTS = {
  p: ({ children }) => <p className="mb-2 last:mb-0 whitespace-pre-line">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="whitespace-pre-line">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-primary underline break-all">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full text-xs border border-border">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border border-border px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border border-border px-2 py-1">{children}</td>,
  code: ({ children }) => (
    <code className="bg-app border border-border rounded px-1 py-0.5 text-[0.85em]">{children}</code>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-primary/50 pl-3 my-2 text-secondary">{children}</blockquote>
  ),
};

/**
 * Renderer markdown cho văn bản LLM trả về.
 * LƯU Ý: chủ tình KHÔNG export qua ui/index.js — react-markdown/remark-gfm nặng,
 * chỉ 2 trang AI (đã lazy-load theo route) import trực tiếp để khỏi lọt vào
 * bundle khởi đầu của shell.
 */
export default function AiMarkdown({ text }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
      {text ?? ""}
    </ReactMarkdown>
  );
}
