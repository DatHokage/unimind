/**
 * Card — khối nội dung chính trên nền app (§2.3: bo 8px, shadow-sm duy nhất).
 */
export function Card({ title, actions, children, className = "", padded = true }) {
  return (
    <section
      className={`bg-surface border border-border rounded-lg shadow-sm ${className}`}
    >
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 px-5 py-3 border-b border-border">
          <h2 className="text-lg font-semibold text-primary">{title}</h2>
          {actions}
        </header>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}
