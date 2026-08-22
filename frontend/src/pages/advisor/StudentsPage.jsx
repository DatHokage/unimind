import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Search, Users } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Button, Card, DataTable, Cell, Row, Spinner, Alert } from "../../components/ui";
import { fmtDate } from "../../utils/format";
import { INPUT_CLS } from "../../utils/forms";

/**
 * Danh sách sinh viên của lớp chủ nhiệm (route classes/:classId/students) —
 * thanh tìm kiếm như trang admin: nhập mã/tên rồi bấm "Tìm" (hoặc Enter).
 */
export default function AdvisorStudentsPage() {
  const { classId } = useParams();
  const [loading, setLoading] = useState(true);
  const [students, setStudents] = useState([]);
  const [className, setClassName] = useState("");
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get(`/homeroom-classes/${classId}/students`)
      .then(({ data }) => {
        setStudents(data);
        setClassName(data[0]?.class_name ?? "");
      })
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [classId]);

  // Lọc client-side theo mã hoặc tên trên danh sách lớp đã tải
  const filtered = useMemo(() => {
    const q = appliedSearch.trim().toLowerCase();
    if (!q) return students;
    return students.filter(
      (s) => s.name.toLowerCase().includes(q) || s.code.toLowerCase().includes(q)
    );
  }, [students, appliedSearch]);

  const applySearch = () => setAppliedSearch(search);

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  const filtering = appliedSearch.trim() !== "";

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">
        Lớp hành chính {className || `#${classId}`} ·{" "}
        {filtering ? `${filtered.length}/${students.length}` : students.length} sinh viên
      </p>

      <div className="flex gap-2">
        <div className="relative">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary pointer-events-none"
          />
          <input
            className={`${INPUT_CLS} pl-9 w-72 max-w-full`}
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

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã SV" },
            { key: "name", label: "Họ tên" },
            { key: "dob", label: "Ngày sinh" },
            { key: "major", label: "Ngành" },
          ]}
          rows={filtered}
          sttStart={1}
          empty={
            filtering ? (
              <div className="flex flex-col items-center py-12 text-center">
                <Search size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
                <p className="text-sm font-medium">Không có sinh viên nào khớp từ khóa.</p>
              </div>
            ) : (
              <div className="flex flex-col items-center py-12 text-center">
                <Users size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
                <p className="text-sm font-medium">Lớp chưa có sinh viên nào.</p>
                <p className="text-sm text-secondary mt-1">
                  Liên hệ phòng đào tạo để bổ sung sinh viên vào lớp.
                </p>
              </div>
            )
          }
          renderRow={(s, _i, stt) => (
            <Row key={s.id}>
              {stt}
              <Cell className="font-medium">{s.code}</Cell>
              <Cell>{s.name}</Cell>
              <Cell className="num">{fmtDate(s.dob)}</Cell>
              <Cell>{s.major_name ?? "—"}</Cell>
            </Row>
          )}
        />
      </Card>
    </div>
  );
}
