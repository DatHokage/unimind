import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/layout/Sidebar";
import Header from "../components/layout/Header";

/**
 * Khung chung — frontend.md §3: sidebar trái cố định + nội dung chính bên phải,
 * nội dung giới hạn max-width 1280px, căn giữa, padding 24px.
 */
export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-app">
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((v) => !v)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <div
        className={`transition-all duration-200 ${collapsed ? "md:pl-[72px]" : "md:pl-[260px]"}`}
      >
        <Header onMenuClick={() => setMobileOpen(true)} />
        <main className="max-w-[1280px] mx-auto px-4 lg:px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
