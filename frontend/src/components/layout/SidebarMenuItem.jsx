import { NavLink } from "react-router-dom";

/**
 * Mục menu sidebar — frontend.md §5.2:
 * active = nền primary-soft, chữ + icon primary, thanh dọc 3px bên trái.
 * Icon lucide cố định 18px (§5.2).
 */
export default function SidebarMenuItem({ item, collapsed, onNavigate }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      state={item.state}
      title={collapsed ? item.label : undefined}
      onClick={onNavigate}
      className="relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-secondary hover:bg-app hover:text-primary transition-colors duration-150"
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-primary" />
          )}
          {Icon && <Icon size={18} className={`shrink-0 ${isActive ? "text-primary" : ""}`} />}
          {!collapsed && (
            <span className={`truncate ${isActive ? "text-primary" : ""}`}>{item.label}</span>
          )}
        </>
      )}
    </NavLink>
  );
}
