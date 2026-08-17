import { createContext, useContext, useEffect, useState } from "react";
import api from "../api/client";

const TOKEN_KEY = "ql_token";
const USER_KEY = "ql_user";
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY));
    } catch {
      return null;
    }
  });

  const persist = (u) => {
    setUser(u);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
  };

  // Bổ sung tên người dùng cho vùng user sidebar (§5.1) — API login chỉ trả về username.
  useEffect(() => {
    if (!token || !user || user.name) return;
    if (user.student_id) {
      api
        .get(`/students/${user.student_id}`)
        .then(({ data }) => data?.name && persist({ ...user, name: data.name }))
        .catch(() => {}); // tên chỉ để hiển thị — lỗi thì dùng username
    } else if (user.advisor_id) {
      // Cố vấn học tập: backend cho advisor đọc hồ sơ của chính mình
      api
        .get(`/advisors/${user.advisor_id}`)
        .then(({ data }) => data?.name && persist({ ...user, name: data.name }))
        .catch(() => {});
    } else if (user.lecturer_id) {
      // Backend không có GET /lecturers/{id} → lấy danh sách rồi tìm theo id
      api
        .get("/lecturers/all")
        .then(({ data }) => {
          const me = data.find((l) => l.id === user.lecturer_id);
          if (me?.name) persist({ ...user, name: me.name });
        })
        .catch(() => {});
    }
  }, [token, user]);

  const login = async (username, password) => {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);
    const { data } = await api.post("/auth/login", form);
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

export const ROLE_LABELS = {
  student: "Sinh viên",
  lecturer: "Giảng viên",
  advisor: "Cố vấn học tập",
  training_office: "Phòng đào tạo",
};

/** §5.1 — badge vai trò giúp người dùng luôn biết mình đang thao tác với quyền nào. */
export const ROLE_TONES = {
  student: "info",
  lecturer: "success",
  advisor: "warning",
  training_office: "danger",
};

/** Chữ cái đầu cho avatar khi không có ảnh. */
export const initials = (name = "") => {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return parts.length === 1 ? parts[0][0].toUpperCase() : (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
};
