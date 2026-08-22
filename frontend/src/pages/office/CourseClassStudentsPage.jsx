import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Search, UserPlus, Users } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Row, Spinner, Alert, Button } from "../../components/ui";
import { INPUT_CLS, SELECT_CLS } from "../../utils/forms";
import { fmtDate } from "../../utils/format";

/**
 * Quản lý sinh viên của MỘT lớp học phần (phòng đào tạo):
 * danh sách đăng ký, thêm sinh viên (tự kiểm tra sĩ số/tiên quyết/trùng lịch
 * phía backend) và xóa khỏi lớp.
 */
export default function CourseClassStudentsPage() {
  const { classId } = useParams();
  const [loading, setLoading] = useState(true);
  const [cc, setCc] = useState(null); // thông tin lớp học phần hiện tại
  const [rows, setRows] = useState([]);
  // Tìm sinh viên để thêm vào lớp
  const [stuSearch, setStuSearch] = useState("");
  const [stuResults, setStuResults] = useState([]);
  const [pickedStudent, setPickedStudent] = useState("");
  // id đăng ký đang chờ xác nhận xóa
  const [confirmEnrollId, setConfirmEnrollId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const loadClassInfo = () =>
    api.get(`/course-classes/${classId}`).then(({ data }) => setCc(data));

  const loadRows = () =>
    api.get(`/course-classes/${classId}/enrollments`).then(({ data }) => setRows(data));

  useEffect(() => {
    setLoading(true);
    Promise.all([loadClassInfo(), loadRows()])
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId]);

  // Nạp lại danh sách + sĩ số sau mỗi thao tác
  const reload = async () => {
    try {
      await Promise.all([loadClassInfo(), loadRows()]);
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const searchStudents = async () => {
    setError("");
    try {
      const { data } = await api.get("/students", {
        params: { page: 0, size: 20, ...(stuSearch.trim() ? { search: stuSearch.trim() } : {}) },
      });
      setStuResults(data.data);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const addStudentToClass = async () => {
    if (!pickedStudent) return;
    setError("");
    setSuccess("");
    try {
      await api.post("/enrollments", {
        course_class_id: Number(classId),
        student_id: Number(pickedStudent),
      });
      const picked = stuResults.find((s) => s.id === Number(pickedStudent));
      setSuccess(`Đã thêm ${picked?.code ?? "sinh viên"} vào lớp`);
      setPickedStudent("");
      setStuSearch("");
      setStuResults([]);
      await reload();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const removeEnrollment = async (id) => {
    setError("");
    setSuccess("");
    try {
      await api.delete(`/enrollments/${id}`);
      setSuccess("Đã xóa sinh viên khỏi lớp");
      setConfirmEnrollId(null);
      await reload();
    } catch (err) {
      setError(errMsg(err));
      setConfirmEnrollId(null);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to="/office/course-classes"
            className="inline-flex items-center gap-1 text-sm text-secondary hover:text-primary transition-colors duration-150"
          >
            <ArrowLeft size={14} /> Về danh sách lớp học phần
          </Link>
          <h2 className="text-lg font-semibold mt-1">
            Lớp {cc?.course_code ?? "#"} · HK{cc?.term}/{cc?.year}
          </h2>
        </div>
      </div>

      <p className="text-sm text-secondary num">
        {[
          cc?.course_name,
          cc?.lecturer_name ? `GV ${cc.lecturer_name}` : null,
          `${cc?.enrolled_count ?? rows.length}/${cc?.max_size ?? "—"} sinh viên`,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>

      {error && (
        <Alert kind="error" onClose={() => setError("")}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert kind="success" onClose={() => setSuccess("")}>
          {success}
        </Alert>
      )}

      <Card padded={false}>
        <div className="p-4 border-b border-border">
          <div className="flex flex-wrap gap-2">
            <div className="relative">
              <Search
                size={15}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary pointer-events-none"
              />
              <input
                className={`${INPUT_CLS} pl-9 w-72 max-w-full`}
                placeholder="Tìm theo mã hoặc tên sinh viên…"
                value={stuSearch}
                onChange={(e) => setStuSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && searchStudents()}
              />
            </div>
            <Button variant="secondary" onClick={searchStudents}>
              Tìm
            </Button>
            <select
              className={`${SELECT_CLS} w-72 max-w-full`}
              value={pickedStudent}
              onChange={(e) => setPickedStudent(e.target.value)}
            >
              <option value="">— Chọn sinh viên —</option>
              {stuResults.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                </option>
              ))}
            </select>
            <Button onClick={addStudentToClass} disabled={!pickedStudent}>
              <UserPlus size={15} /> Thêm vào lớp
            </Button>
          </div>
          <p className="text-xs text-secondary mt-2">
            Hệ thống tự kiểm tra sĩ số, điều kiện tiên quyết và trùng lịch khi thêm.
          </p>
        </div>

        <DataTable
          columns={[
            { key: "code", label: "Mã SV" },
            { key: "name", label: "Họ tên" },
            { key: "date", label: "Ngày đăng ký" },
            { key: "action", label: "" },
          ]}
          rows={rows}
          sttStart={1}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <Users size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Chưa có sinh viên nào đăng ký lớp này.</p>
              <p className="text-sm text-secondary mt-1">
                Dùng ô tìm kiếm phía trên để thêm sinh viên vào lớp.
              </p>
            </div>
          }
          renderRow={(r, _i, stt) => (
            <Row key={r.id}>
              {stt}
              <Cell className="font-medium num">{r.student_code}</Cell>
              <Cell>{r.student_name}</Cell>
              <Cell className="num">{fmtDate(r.enrolled_at)}</Cell>
              <Cell className="text-right">
                {confirmEnrollId === r.id ? (
                  <span className="inline-flex gap-2">
                    <Button size="sm" variant="danger" onClick={() => removeEnrollment(r.id)}>
                      Chắc chắn xóa
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmEnrollId(null)}>
                      Giữ lại
                    </Button>
                  </span>
                ) : (
                  <Button size="sm" variant="danger" onClick={() => setConfirmEnrollId(r.id)}>
                    Xóa khỏi lớp
                  </Button>
                )}
              </Cell>
            </Row>
          )}
        />
      </Card>
    </div>
  );
}
