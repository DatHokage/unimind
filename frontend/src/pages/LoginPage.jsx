import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  LogIn,
  Mail,
  User,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { errMsg } from "../api/client";

const HOME_BY_ROLE = {
  student: "/student",
  lecturer: "/lecturer",
  advisor: "/advisor",
  training_office: "/office",
};

/**
 * Input bản warm-premium: cao 44px (khớp nút Đăng nhập), radius 12px,
 * nền trắng nổi trên card frost, focus viền brand blue (#0095FF) + ring nhẹ.
 * Transition 150ms.
 */
const INPUT_CLS =
  "w-full h-[44px] border border-[rgba(46,46,42,0.10)] rounded-[12px] bg-white pl-10 pr-4 text-[14px] text-[#2E2E2A] placeholder:text-[#8C8C82] shadow-[0_2px_6px_-2px_rgba(96,84,62,0.12)] transition-all duration-150 focus:outline-none focus:border-[#0095FF] focus:ring-4 focus:ring-[#0095FF]/15 focus:shadow-[0_6px_18px_-6px_rgba(0,149,255,0.25)]";
const INPUT_ERR_CLS =
  " border-danger/60 focus:border-danger focus:ring-danger/10";

/** Tôn trọng thiết lập giảm chuyển động của hệ điều hành. */
function usePrefersReducedMotion() {
  const [reduce, setReduce] = useState(() =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = (e) => setReduce(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduce;
}

/**
 * Nghiêng thẻ đăng nhập theo con trỏ (tối đa ±5°). Ghi transform trực tiếp qua ref
 * (không React state mỗi mousemove), rAF-throttle; rời chuột thì CSS transition
 * kéo về 0. Tự tắt khi reduced motion hoặc thiết bị cảm ứng.
 */
function useCardTilt({ enabled }) {
  const wrapRef = useRef(null);
  const cardRef = useRef(null);

  useEffect(() => {
    if (!enabled) return undefined;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches)
      return undefined;
    const wrap = wrapRef.current;
    const card = cardRef.current;
    if (!wrap || !card) return undefined;

    const MAX_TILT = 5; // độ
    let raf = 0;
    let lastMove = null;

    // Chạy đúng 1 lần/frame: lấy sự kiện mousemove mới nhất rồi tính góc nghiêng
    const flush = () => {
      raf = 0;
      if (!lastMove) return;
      const r = wrap.getBoundingClientRect();
      const nx = (lastMove.clientX - r.left) / r.width - 0.5;
      const ny = (lastMove.clientY - r.top) / r.height - 0.5;
      card.classList.remove("is-settling");
      card.style.transform = `rotateX(${(-ny * MAX_TILT).toFixed(2)}deg) rotateY(${(nx * MAX_TILT).toFixed(2)}deg)`;
    };
    const onMove = (e) => {
      lastMove = e;
      if (!raf) raf = requestAnimationFrame(flush);
    };
    const onLeave = () => {
      if (raf) {
        cancelAnimationFrame(raf);
        raf = 0;
      }
      lastMove = null;
      card.classList.add("is-settling");
      card.style.transform = "rotateX(0deg) rotateY(0deg)";
    };

    wrap.addEventListener("mousemove", onMove);
    wrap.addEventListener("mouseleave", onLeave);
    return () => {
      wrap.removeEventListener("mousemove", onMove);
      wrap.removeEventListener("mouseleave", onLeave);
      if (raf) cancelAnimationFrame(raf);
      card.style.transform = "";
    };
  }, [enabled]);

  return { wrapRef, cardRef };
}

/** Logo + thương hiệu UniMind — logo thô + wordmark, không tagline:
    tên đầy đủ đã có ở eyebrow (trên) và footer (dưới trang) — tránh trùng chữ. */
function Brand({ size = "md" }) {
  const imgCls = size === "md" ? "w-10 h-10" : "w-8 h-8";
  const nameCls = size === "md" ? "text-[22px]" : "text-lg";
  return (
    <div className="flex items-center gap-3">
      <img src="/favicon.svg" alt="Logo UniMind" className={`${imgCls} shrink-0`} />
      <span className={`${nameCls} night-shade font-bold tracking-tight text-[var(--inkline)]`}>
        UniMind
      </span>
    </div>
  );
}

/* ================= Nền "Bàn học flat-lay" — SVG vector =================
   Lớp 0 — gradient kem-ấm dịu (nền gốc).
   Lớp 1 — cảnh SVG bàn học nhìn từ trên xuống: bánh xe chuột làm thời gian
   trôi 7:00→22:00, chuột tạo parallax + quầng ấm, click gợn sóng mực. */
const DeskScene = lazy(() => import("../components/scene/DeskScene"));

function SceneBackdrop({ reduced }) {
  return (
    <div aria-hidden="true" className="fixed inset-0 overflow-hidden pointer-events-none">
      {/* Cảnh bàn học flat-lay (tự chốt 1 khung tĩnh khi reduced motion) */}
      <Suspense fallback={null}>
        <DeskScene reduced={reduced} />
      </Suspense>
      {/* Lớp glow trôi chậm — đặt TRÊN cảnh: trời (CSS lẫn GL) đặc sẽ chôn
          fog nếu nằm dưới, hai quầng ấm/lạnh này phải nổi trên nền trời */}
      <div className="login-fog absolute -left-[10%] -top-[15%] h-[55vh] w-[45vw] rounded-full" />
      <div className="login-fog login-fog-slow absolute -bottom-[18%] right-[-8%] h-[50vh] w-[40vw] rounded-full" />
      {/* Vignette mềm phủ trên cùng, không làm tối nền */}
      <div className="login-vignette absolute inset-0" />
    </div>
  );
}

/** Khối form đăng nhập — tự quản state, validate client-side và gọi API login. */
function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [touched, setTouched] = useState({ username: false, password: false });
  const usernameRef = useRef(null);

  // Focus ô tên đăng nhập khi vào trang — thao tác nhanh, quen tay
  useEffect(() => {
    usernameRef.current?.focus();
  }, []);

  // Validate phía client trước khi gọi API — thông báo lỗi gắn thẳng vào ô
  const usernameMissing = touched.username && !username.trim();
  const passwordMissing = touched.password && !password;

  const submit = async (e) => {
    e.preventDefault();
    setTouched({ username: true, password: true });
    if (!username.trim() || !password) return;
    setError("");
    setLoading(true);
    try {
      const logged = await login(username.trim(), password);
      navigate(HOME_BY_ROLE[logged.role] ?? "/login");
    } catch (err) {
      setError(errMsg(err));
      setLoading(false);
    }
  };

  return (
    <>
      {/* Header căn trái — cùng nhịp typo với cột chữ bên trái trang */}
      <div>
        <h2 className="text-[24px] font-bold tracking-tight text-[#2E2E2A]">
          Chào mừng trở lại
        </h2>
        <p className="mt-1.5 text-[13px] text-[#8C8C82]">
          Đăng nhập để tiếp tục với UniMind.
        </p>
        {/* Vạch phân cách gradient mềm — dẫn mắt vào form */}
        <div
          aria-hidden="true"
          className="mt-5 h-px bg-gradient-to-r from-[rgba(46,46,42,0.12)] via-[rgba(46,46,42,0.05)] to-transparent"
        />
      </div>

      {/* Slot lỗi chiều cao CỐ ĐỊNH (1 dòng) — sai mật khẩu/lỗi API hiện ra
          tại chỗ này mà không làm giãn thẻ, tự biến mất khi thử lại */}
      <div
        aria-live="assertive"
        className="mt-4 flex h-5 items-center gap-2 overflow-hidden whitespace-nowrap text-[13px] text-danger"
      >
        {error && (
          <>
            <AlertCircle size={14} className="shrink-0" />
            <span className="truncate">{error}</span>
          </>
        )}
      </div>

      {/* Không dùng space-y: khoảng cách giữa các khối do các slot chiều cao
          CỐ ĐỊNH tự giữ (16px) — thông báo lỗi hiện/tắt không đổi khoảng nào */}
      <form onSubmit={submit} noValidate className="mt-3">
        <div>
          <label className="block text-sm font-medium mb-2 text-[#2E2E2A]" htmlFor="username">
            Tên đăng nhập
          </label>
          <div className="relative">
            <User
              size={17}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#8C8C82] pointer-events-none"
            />
            <input
              id="username"
              ref={usernameRef}
              className={INPUT_CLS + (usernameMissing ? INPUT_ERR_CLS : "")}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, username: true }))}
              autoComplete="username"
              placeholder="Nhập tên đăng nhập"
              aria-invalid={!!usernameMissing}
              aria-describedby={usernameMissing ? "username-error" : undefined}
            />
          </div>
          {/* Slot lỗi chiều cao CỐ ĐỊNH — thông báo chỉ hiện/tắt bên trong,
              không bao giờ đẩy form giãn card (cùng cơ chế với slot lỗi API trên đầu);
              mt-1.5 tách chữ khỏi mép input cho thoáng, nhịp xuống khối Mật khẩu 22px */}
          <div className="mt-1.5 flex h-4 items-center overflow-hidden whitespace-nowrap text-xs text-danger">
            {usernameMissing && (
              <p id="username-error" className="ml-1 truncate">
                Vui lòng nhập tên đăng nhập.
              </p>
            )}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium text-[#2E2E2A]" htmlFor="password">
              Mật khẩu
            </label>
            <button
              type="button"
              onClick={() => {
                setError("");
                setShowForgot((v) => !v);
              }}
              className="text-[13px] font-medium text-[#0095FF] hover:text-[#0077CC] transition-colors duration-150 cursor-pointer"
            >
              Quên mật khẩu?
            </button>
          </div>
          <div className="relative">
            <Lock
              size={17}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[#8C8C82] pointer-events-none"
            />
            <input
              id="password"
              type={showPass ? "text" : "password"}
              className={INPUT_CLS + " pr-12" + (passwordMissing ? INPUT_ERR_CLS : "")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, password: true }))}
              autoComplete="current-password"
              placeholder="Nhập mật khẩu"
              aria-invalid={!!passwordMissing}
              aria-describedby={passwordMissing ? "password-error" : undefined}
            />
            <button
              type="button"
              onClick={() => setShowPass((v) => !v)}
              aria-label={showPass ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1.5 rounded-full text-[#8C8C82] hover:text-[#0095FF] hover:bg-[#0095FF]/10 transition-colors duration-150 cursor-pointer"
            >
              {showPass ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </div>
          {/* Slot lỗi chiều cao CỐ ĐỊNH như ô tên đăng nhập — mt-1.5 tách chữ
              khỏi mép input thay vì dán sát đáy ô */}
          <div className="mt-1.5 flex h-4 items-center overflow-hidden whitespace-nowrap text-xs text-danger">
            {passwordMissing && (
              <p id="password-error" className="ml-1 truncate">
                Vui lòng nhập mật khẩu.
              </p>
            )}
          </div>
        </div>

        {/* Chưa có luồng tự đặt lại mật khẩu — gợi ý 1 dòng trong slot chiều cao
            CỐ ĐỊNH: hiện/tắt không làm giãn card hay đẩy nút đăng nhập;
            mt-2 siết khoảng trống khi slot rỗng để nút không bị hụt hơi */}
        <div
          aria-live="polite"
          className="mt-2 flex h-5 items-center gap-2 whitespace-nowrap overflow-hidden text-[13px] text-[#5A5A50]"
        >
          {showForgot && (
            <>
              <Mail size={14} className="shrink-0 text-[#0095FF]" />
              <span>
                Liên hệ{" "}
                <a
                  href="mailto:dat99@edu.vn"
                  className="font-medium text-[#0095FF] underline underline-offset-2 hover:text-[#0077CC]"
                >
                  dat99@edu.vn
                </a>{" "}
                để được hỗ trợ.
              </span>
            </>
          )}
        </div>

        {/* Nút căn giữa — bọc flex vì nút là inline-flex, mx-auto không tác dụng;
            mt-4 giữ nút bám sát cụm form thay vì trôi lơ lửng dưới hai slot trống */}
        <div className="mt-4 flex justify-center">
          <button
            type="submit"
            disabled={loading}
            className="h-11 rounded-full bg-[#0095FF] px-10 hover:bg-[#0077CC] text-white font-semibold text-[13px] inline-flex items-center justify-center gap-2 shadow-[0_12px_30px_-12px_rgba(0,149,255,0.55)] hover:shadow-[0_16px_38px_-12px_rgba(0,160,255,0.65)] hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0"
          >
            {loading ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Đang đăng nhập…
              </>
            ) : (
              <>
                <LogIn size={18} />
                Đăng nhập
              </>
            )}
          </button>
        </div>
      </form>
    </>
  );
}

export default function LoginPage() {
  const { token, user } = useAuth();
  const reduce = usePrefersReducedMotion();
  const { wrapRef, cardRef } = useCardTilt({ enabled: !reduce });

  // Đã đăng nhập mà vào lại /login → đưa thẳng về trang chủ theo role
  if (token && user && HOME_BY_ROLE[user.role]) {
    return <Navigate to={HOME_BY_ROLE[user.role]} replace />;
  }

  return (
    <div className="login-root relative h-screen overflow-hidden">
      {/* Nền chuyển động "Bàn học flat-lay": cảnh SVG/WebGL → fog trôi → vignette */}
      <SceneBackdrop reduced={reduce} />

      {/* h-screen khoá đúng 1 màn hình — hết cảnh trang giãn ra tạo thanh cuộn dọc */}
      <div className="relative z-10 flex h-full min-h-0 flex-col lg:flex-row">
        {/* ===== Cột trái: giới thiệu hệ thống — ẩn dưới 1024px ===== */}
        <div className="hidden lg:flex w-[50%] shrink-0 flex-col px-14 pb-8 pt-4">
          {/* Logo neo góc trên trái — tiêu đề lên ngay vùng cũ của quyển sách */}
          <div className="login-rise" style={{ animationDelay: "0.05s" }}>
            <Brand />
          </div>

          {/* Khối chữ neo CAO (mt nhỏ): cụm cà phê + sách chiếm góc dưới trái từ
              ~60vh xuống, hạ khối chữ sâu dễ đè lên tĩnh vật trên màn thấp */}
          <div className="login-rise mt-[3vh] max-w-[560px]" style={{ animationDelay: "0.15s" }}>
            {/* Tháp ba dòng — mỗi dòng một cụm từ trọn vẹn: ngắn / dài / ngắn,
                dòng xanh "Thông minh" đứng riêng được nhấn tối đa. Cỡ chữ clamp để
                dòng dài nhất không bao giờ xuống dòng lệch khối ở vùng màn
                1024–1280px; leading 1.18 chừa chỗ cho dấu chồng tiếng Việt
                (ô, ế, ỗ…). Mọi màu đi qua biến nên đêm về tự đổi tông ánh trăng;
                --blueline-strong là sắc xanh đậm hơn cho chữ lớn đủ tương phản AA. */}
            <span
              aria-hidden="true"
              className="mb-5 block h-[3px] w-10 rounded-full"
              style={{ background: "linear-gradient(90deg, var(--blueline), transparent)" }}
            />
            <h1>
              <span className="night-shade block text-[clamp(34px,3.5vw,54px)] font-bold leading-[1.18] tracking-tight text-[var(--inkline)]">
                Hệ thống
              </span>
              <span className="night-shade block text-[clamp(34px,3.5vw,54px)] font-bold leading-[1.18] tracking-tight text-[var(--inkline)]">
                Quản lý Đào tạo
              </span>
              <span className="night-shade block text-[clamp(34px,3.5vw,54px)] font-bold leading-[1.18] tracking-tight text-[var(--blueline-strong)]">
                Thông minh
              </span>
            </h1>
            <p className="night-shade mt-6 max-w-[430px] text-[15px] leading-relaxed text-[var(--eyebrow)]">
              Vận hành nhẹ nhàng hơn. Đào tạo hiệu quả hơn.
            </p>
          </div>
        </div>

        {/* ===== Cột phải: đăng nhập — card trắng đặc nổi giữa nền sáng ===== */}
        <div className="flex-1 flex flex-col">
          {/* Thương hiệu — chỉ hiện mobile/tablet */}
          <div className="lg:hidden px-5 pt-6 login-rise">
            <Brand size="sm" />
          </div>

          <div className="flex min-h-0 flex-1 items-center justify-center px-4 py-5">
            {/* 3 lớp: perspective (tilt) → login-rise (entrance) → card (nghiêng theo con trỏ).
                Animation CSS đè inline transform nên tilt phải nằm trên element riêng. */}
            <div
              ref={wrapRef}
              className="flex w-full justify-center [perspective:1100px]"
            >
              <div
                className="login-rise w-full max-w-[384px]"
                style={{ animationDelay: "0.12s" }}
              >
                <div
                  ref={cardRef}
                  className="login-tilt-card rounded-[22px] border border-white/70 bg-white/85 shadow-[0_30px_72px_-26px_rgba(96,84,62,0.30)] backdrop-blur-md sm:backdrop-blur-xl px-6 py-6 sm:px-8 sm:py-7"
                >
                  <LoginForm />
                </div>
              </div>
            </div>
          </div>

          {/* Footer cột phải — căn giữa dưới card, hiện ở mọi kích thước màn hình */}
          <p className="shrink-0 pb-4 text-xs text-[#8C8C82] text-center">
            © 2026 UniMind — Hệ thống quản lý đào tạo thông minh.
          </p>
        </div>
      </div>
    </div>
  );
}
