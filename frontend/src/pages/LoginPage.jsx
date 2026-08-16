import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { errMsg } from "../api/client";
import { Alert, Button } from "../components/ui";

const HOME_BY_ROLE = {
  student: "/student",
  lecturer: "/lecturer",
  advisor: "/advisor",
  training_office: "/office",
};

const DEMO_ACCOUNTS = [
  ["ptdt", "Phòng đào tạo"],
  ["lecturer1", "Giảng viên (Trần Thị Bình)"],
  ["advisor1", "Cố vấn học tập (Nguyễn Văn An)"],
  ["student1", "Sinh viên Phạm Văn Nhất"],
  ["student2", "Sinh viên Lê Thị Nhị (trượt TH1)"],
  ["student3", "Sinh viên Hoàng Văn Tam"],
  ["student4", "Sinh viên Đỗ Thị Tư (CNTT2-K12)"],
];

const inputCls =
  "w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors duration-150";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await login(username.trim(), password);
      navigate(HOME_BY_ROLE[user.role] ?? "/login");
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-app flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-4xl grid md:grid-cols-2 gap-6">
        <div className="bg-surface border border-border rounded-lg shadow-sm p-8">
          <div className="flex items-center gap-2.5 mb-1">
            <img src="/favicon.svg" alt="UniMind" className="w-12 h-12" />
            <h1 className="text-3xl font-semibold">UniMind</h1>
          </div>
          <p className="text-sm text-secondary mb-6">
            Hệ thống quản lý đào tạo tích hợp AI
          </p>
          {error && <Alert kind="error">{error}</Alert>}
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="username">
                Tên đăng nhập
              </label>
              <input
                id="username"
                className={inputCls}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" htmlFor="password">
                Mật khẩu
              </label>
              <input
                id="password"
                type="password"
                className={inputCls}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            <Button type="submit" disabled={loading} className="w-full py-2.5">
              {loading ? "Đang đăng nhập…" : "Đăng nhập"}
            </Button>
          </form>
        </div>

        <div className="bg-surface border border-border rounded-lg shadow-sm p-8">
          <h2 className="text-lg font-semibold mb-1">Tài khoản demo</h2>
          <p className="text-sm text-secondary mb-4">
            Mật khẩu chung: <code className="text-primary font-medium">password123</code> — bấm
            vào tài khoản để điền nhanh.
          </p>
          <ul className="space-y-2">
            {DEMO_ACCOUNTS.map(([uname, desc]) => (
              <li key={uname}>
                <button
                  type="button"
                  onClick={() => {
                    setUsername(uname);
                    setPassword("password123");
                  }}
                  className="w-full text-left flex items-center gap-3 border border-border hover:border-primary/40 hover:bg-primary-soft rounded-lg px-3 py-2 transition-colors duration-150 cursor-pointer"
                >
                  <span className="font-mono text-sm text-primary w-24 shrink-0">{uname}</span>
                  <span className="text-xs text-secondary">{desc}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
