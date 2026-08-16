import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Search, Users } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Row, Spinner, Alert, Button, Pagination } from "../../components/ui";
import { fmtDate } from "../../utils/format";

const inputCls =
  "border border-border rounded-lg px-3 py-2 text-sm bg-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors duration-150";

const PAGE_SIZE = 20;

/**
 * Danh sách sinh viên của cố vấn — 2 chế độ:
 * - thường: sinh viên trong lớp chủ nhiệm (classes/:classId/students)
 * - officeMode (route /advisor/results — "Kết quả sinh viên"): toàn trường, phân trang + tìm kiếm phía server
 */
export default function AdvisorStudentsPage({ officeMode = false }) {
  const { classId } = useParams();
  const [loading, setLoading] = useState(true);
  const [students, setStudents] = useState([]);
  const [className, setClassName] = useState("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [totalElements, setTotalElements] = useState(0);
  const [error, setError] = useState("");
  // Chống race: response của request cũ về sau bị bỏ qua
  const reqId = useRef(0);

  const load = async (q = "") => {
    if (officeMode) {
      const id = ++reqId.current;
      const { data } = await api.get("/students", {
        params: { page: 0, size: PAGE_SIZE, ...(q ? { search: q } : {}) },
      });
      if (id !== reqId.current) return false;
      setStudents(data.data);
      setPage(data.page);
      setTotalPages(data.totalPages);
      setTotalElements(data.totalElements);
      return true;
    }
    const { data } = await api.get(`/homeroom-classes/${classId}/students`);
    setStudents(data);
    setClassName(data[0]?.class_name ?? "");
    return true;
  };

  const goPage = async (p) => {
    const id = ++reqId.current;
    const { data } = await api.get("/students", {
      params: { page: p, size: PAGE_SIZE, ...(appliedSearch ? { search: appliedSearch } : {}) },
    });
    if (id !== reqId.current) return;
    setStudents(data.data);
    setPage(data.page);
    setTotalPages(data.totalPages);
    setTotalElements(data.totalElements);
  };

  const applySearch = () => {
    const q = search;
    load(q)
      .then((applied) => {
        if (applied) setAppliedSearch(q);
      })
      .catch((x) => setError(errMsg(x)));
  };

  useEffect(() => {
    setLoading(true);
    load()
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId, officeMode]);

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">
        {officeMode
          ? `${totalElements} sinh viên toàn trường`
          : `Lớp hành chính ${className || `#${classId}`} · ${students.length} sinh viên`}
      </p>

      {officeMode && (
        <div className="flex gap-2">
          <div className="relative">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary pointer-events-none"
            />
            <input
              className={`${inputCls} pl-9 w-72 max-w-full`}
              placeholder="Tìm theo mã hoặc tên…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applySearch()}
            />
          </div>
          <Button variant="secondary" onClick={applySearch}>
            Tìm
          </Button>
        </div>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã SV" },
            { key: "name", label: "Họ tên" },
            { key: "dob", label: "Ngày sinh" },
            { key: "major", label: "Ngành" },
            { key: "class", label: "Lớp" },
            { key: "action", label: "" },
          ]}
          rows={students}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <Users size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Chưa có sinh viên nào.</p>
              <p className="text-sm text-secondary mt-1">
                {officeMode
                  ? "Thử lại với từ khóa khác."
                  : "Lớp chưa có sinh viên — liên hệ phòng đào tạo để bổ sung."}
              </p>
            </div>
          }
          renderRow={(s) => (
            <Row key={s.id}>
              <Cell className="font-medium">{s.code}</Cell>
              <Cell>{s.name}</Cell>
              <Cell className="num">{fmtDate(s.dob)}</Cell>
              <Cell>{s.major_name ?? "—"}</Cell>
              <Cell>{s.class_name ?? "—"}</Cell>
              <Cell className="text-right">
                <Link to={`/advisor/students/${s.id}`}>
                  <Button size="sm" variant="secondary">
                    Kết quả & nhận xét AI →
                  </Button>
                </Link>
              </Cell>
            </Row>
          )}
        />
        {officeMode && <Pagination page={page} totalPages={totalPages} onPageChange={(p) => goPage(p).catch((x) => setError(errMsg(x)))} />}
      </Card>
    </div>
  );
}
