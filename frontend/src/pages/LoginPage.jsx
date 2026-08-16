import { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  BookOpen,
  CalendarDays,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  LogIn,
  Sparkles,
  User,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { errMsg } from "../api/client";
import { Alert, Button } from "../components/ui";

const HOME_BY_ROLE = {
  student: "/student",
  lecturer: "/lecturer",
  advisor: "/advisor",
  training_office: "/office",
};

/** Điểm nhấn tính năng ở panel trái — đơn sắc, không minh họa màu mè (§9). */
const FEATURES = [
  {
    Icon: CalendarDays,
    title: "Thời khóa biểu & đăng ký học phần",
    desc: "Xem lịch học, đăng ký và theo dõi kết quả đăng ký học phần theo kỳ.",
  },
  {
    Icon: Sparkles,
    title: "Trợ lý AI hỗ trợ học tập",
    desc: "Tư vấn kế hoạch đăng ký, tóm tắt kết quả học tập và hỏi đáp quy chế.",
  },
  {
    Icon: BookOpen,
    title: "Bảng điểm & GPA theo thời gian thực",
    desc: "Điểm quá trình, điểm thi, GPA tích lũy cập nhật ngay khi giảng viên nhập điểm.",
  },
];

/**
 * Kiểu input nhất quán: bo tròn mềm (rounded-full), focus viền primary + ring êm.
 * Lỗi validate: viền đỏ, ring đỏ nhạt.
 */
const INPUT_CLS =
  "w-full border border-border rounded-full bg-app/60 pl-11 pr-4 py-3 text-sm placeholder:text-secondary/70 transition-colors duration-150 focus:outline-none focus:border-primary focus:bg-surface focus:ring-4 focus:ring-primary/10";
const INPUT_ERR_CLS =
  " border-danger/60 focus:border-danger focus:ring-danger/10";

/** Nút đăng nhập dạng pill gọn — bo tròn mềm, bóng nhẹ, canh giữa thẻ. */
function LoginButton({ children, ...rest }) {
  return (
    <Button {...rest} className="px-10 py-2 rounded-full shadow-sm">
      {children}
    </Button>
  );
}

/** Logo + tên thương hiệu — dùng chung cho panel trái (desktop) và góc mobile. */
function Brand({ size = "md" }) {
  const imgCls = size === "md" ? "w-16 h-16" : "w-11 h-11";
  const nameCls = size === "md" ? "text-2xl" : "text-xl";
  return (
    <div className="flex items-center gap-3.5">
      <img src="/favicon.svg" alt="UniMind" className={imgCls} />
      <div className="leading-tight">
        <div className={`${nameCls} font-semibold text-primary`}>UniMind</div>
        <div className="text-xs text-secondary">
          Hệ thống quản lý đào tạo tích hợp AI
        </div>
      </div>
    </div>
  );
}

/** Khối form đăng nhập — dùng chung cả desktop lẫn mobile. */
function LoginForm({
  usernameRef,
  username,
  setUsername,
  password,
  setPassword,
  showPass,
  setShowPass,
  showForgot,
  setShowForgot,
  error,
  setError,
  loading,
  touched,
  setTouched,
  usernameMissing,
  passwordMissing,
  onSubmit,
}) {
  return (
    <>
      <div className="text-center">
        <h2 className="text-2xl font-semibold">Chào mừng trở lại</h2>
        <p className="text-sm text-secondary mt-1.5">
          Đăng nhập để tiếp tục làm việc với hệ thống.
        </p>
      </div>

      {error && (
        <div className="mt-5 [&>div]:mb-0 [&>div]:rounded-2xl">
          <Alert kind="error" onClose={() => setError("")}>
            {error}
          </Alert>
        </div>
      )}

      <form onSubmit={onSubmit} noValidate className="mt-8 space-y-6">
        <div>
          <label className="block text-sm font-medium mb-1.5" htmlFor="username">
            Tên đăng nhập
          </label>
          <div className="relative">
            <User
              size={16}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary/70 pointer-events-none"
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
          {usernameMissing && (
            <p id="username-error" className="text-xs text-danger mt-1.5 ml-1">
              Vui lòng nhập tên đăng nhập.
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5" htmlFor="password">
            Mật khẩu
          </label>
          <div className="relative">
            <Lock
              size={16}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-secondary/70 pointer-events-none"
            />
            <input
              id="password"
              type={showPass ? "text" : "password"}
              className={INPUT_CLS + " pr-11" + (passwordMissing ? INPUT_ERR_CLS : "")}
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
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-full text-secondary hover:text-primary hover:bg-primary-soft transition-colors duration-150 cursor-pointer"
            >
              {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {passwordMissing && (
            <p id="password-error" className="text-xs text-danger mt-1.5 ml-1">
              Vui lòng nhập mật khẩu.
            </p>
          )}
        </div>

        <div className="flex justify-end -mt-2">
          <button
            type="button"
            onClick={() => {
              setError("");
              setShowForgot(true);
            }}
            className="text-xs text-secondary hover:text-primary transition-colors duration-150 cursor-pointer"
          >
            Quên mật khẩu?
          </button>
        </div>

        {/* Chưa có luồng tự đặt lại mật khẩu — hướng dẫn liên hệ email hỗ trợ */}
        {showForgot && (
          <div className="[&>div]:mb-0 [&>div]:rounded-2xl">
            <Alert kind="info" onClose={() => setShowForgot(false)}>
              Vui lòng liên hệ{" "}
              <a
                href="mailto:dat99@edu.vn"
                className="font-medium underline underline-offset-2"
              >
              dat99@.edu.vn
              </a>{" "}
              để được hỗ trợ.
            </Alert>
          </div>
        )}

        <div className="flex justify-center">
          <LoginButton type="submit" disabled={loading}>
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Đang đăng nhập…
              </>
            ) : (
              <>
                <LogIn size={16} />
                Đăng nhập
              </>
            )}
          </LoginButton>
        </div>
      </form>
    </>
  );
}

export default function LoginPage() {
  const { login, token, user } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [touched, setTouched] = useState({ username: false, password: false });
  const usernameRef = useRef(null);

  // Focus ô tên đăng nhập khi vào trang (§1: thao tác nhanh, quen tay)
  useEffect(() => {
    usernameRef.current?.focus();
  }, []);

  // Đã đăng nhập mà vào lại /login → đưa thẳng về trang chủ theo role
  if (token && user && HOME_BY_ROLE[user.role]) {
    return <Navigate to={HOME_BY_ROLE[user.role]} replace />;
  }

  // Validate phía client trước khi gọi API — thông báo lỗi gắn thẳng vào ô (§8)
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

  const formProps = {
    usernameRef,
    username,
    setUsername,
    password,
    setPassword,
    showPass,
    setShowPass,
    showForgot,
    setShowForgot,
    error,
    setError,
    loading,
    touched,
    setTouched,
    usernameMissing,
    passwordMissing,
    onSubmit: submit,
  };

  return (
    <div className="min-h-screen flex bg-app">
      {/* ===== Cột trái: branding + giới thiệu — nền trắng, full-height, ẩn dưới 1024px ===== */}
      <div className="hidden lg:flex w-1/2 xl:max-w-[620px] shrink-0 flex-col bg-surface border-r border-border px-12 pt-12 pb-6">
        <Brand />

        <div className="flex-1 flex flex-col justify-center py-8">
          <h1 className="text-2xl font-semibold leading-snug max-w-md">
            Một nơi duy nhất cho học tập, giảng dạy và quản lý đào tạo
          </h1>
          <p className="mt-3 text-sm text-secondary max-w-md leading-relaxed">
            Đăng ký học phần, theo dõi điểm số, nhận tư vấn từ trợ lý AI và tra
            cứu quy chế — tất cả trong cùng một hệ thống.
          </p>

          <ul className="mt-8 space-y-5">
            {FEATURES.map(({ Icon, title, desc }) => (
              <li key={title} className="flex gap-3.5">
                <span className="w-9 h-9 rounded-full bg-primary-soft text-primary flex items-center justify-center shrink-0">
                  <Icon size={18} />
                </span>
                <div>
                  <div className="text-sm font-medium">{title}</div>
                  <div className="text-xs text-secondary mt-0.5 leading-relaxed">
                    {desc}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="pt-10 text-xs text-secondary">
          © 2026 UniMind — Hệ thống quản lý đào tạo tích hợp AI.
        </p>
      </div>

      {/* ===== Cột phải: vùng đăng nhập — nền app, thẻ trắng nổi giữa ===== */}
      <div className="flex-1 flex flex-col">
        {/* Thương hiệu góc trên-trái — chỉ hiện mobile/tablet */}
        <div className="lg:hidden px-5 pt-5 pb-1">
          <Brand size="sm" />
        </div>

        <div className="flex-1 flex items-center justify-center px-4 py-10">
          <div className="w-full max-w-[480px] bg-surface rounded-[24px] shadow-[0_10px_32px_rgba(28,45,84,0.08)] px-10 py-12">
            <LoginForm {...formProps} />
          </div>
        </div>

        <p className="pb-6 text-xs text-secondary text-center lg:hidden">
          © 2026 UniMind — Hệ thống quản lý đào tạo tích hợp AI.
        </p>
      </div>
    </div>
  );
}
