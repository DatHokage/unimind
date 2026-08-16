import axios from "axios";

// Dev: baseURL /api → vite proxy chuyển sang http://localhost:8000 (bỏ tiền tố /api).
// Deploy: đặt VITE_API_BASE_URL = domain backend (VD https://unimind.onrender.com)
// trên Vercel (Settings → Environment Variables) — gọi thẳng sang backend, không qua proxy.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ql_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !err.config?.url?.includes("/auth/login")) {
      localStorage.removeItem("ql_token");
      localStorage.removeItem("ql_user");
      if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

/** Lấy message lỗi tiếng Việt từ FastAPI (detail string hoặc mảng validate). */
export const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join("; ");
  return e?.message || "Có lỗi xảy ra";
};

export default api;
