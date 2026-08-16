import { useEffect, useRef, useState } from "react";
import { Sparkles, CalendarX, Lightbulb, TriangleAlert } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { Card, DataTable, Cell, NumCell, Row, Badge, Spinner, Alert, Button } from "../../components/ui";
import { fmtSchedule, fmtTerm } from "../../utils/format";

export default function RegistrationPage() {
  const { user } = useAuth();
  const adviceRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [myEnrollmentIds, setMyEnrollmentIds] = useState(new Set());
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [enrollingId, setEnrollingId] = useState(null);
  // AI panel
  const [advice, setAdvice] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  const load = async () => {
    const [cc, en] = await Promise.all([
      api.get("/course-classes/all", { params: { status: "open" } }),
      api.get(`/enrollments/student/${user.student_id}`),
    ]);
    setClasses(cc.data);
    setMyEnrollmentIds(new Set(en.data.map((e) => e.course_class_id)));
  };

  useEffect(() => {
    load()
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  const askAI = async () => {
    setAiError("");
    setAiLoading(true);
    try {
      const { data } = await api.post("/ai/course-advice", {
        student_id: user.student_id,
      });
      setAdvice(data);
    } catch (e) {
      setAiError(errMsg(e));
    } finally {
      setAiLoading(false);
    }
  };

  // Chỉ phân tích khi người dùng nhấn nút "Nhận tư vấn"; cuộn tới kết quả khi có
  useEffect(() => {
    if (advice) adviceRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [advice]);

  const enroll = async (courseClassId) => {
    setError("");
    setSuccess("");
    setEnrollingId(courseClassId);
    try {
      await api.post("/enrollments", { course_class_id: courseClassId });
      const cls = classes.find((c) => c.id === courseClassId);
      // §8 — thông báo nhất quán với hành động: "Đã đăng ký học phần ..."
      setSuccess(`Đã đăng ký học phần ${cls?.course_code ?? courseClassId}`);
      await load();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setEnrollingId(null);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
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

      <Card
        title={
          <span className="inline-flex items-center gap-2">
            <Sparkles size={18} className="text-primary" /> Tư vấn đăng ký (AI)
          </span>
        }
        actions={
          <Button onClick={askAI} disabled={aiLoading} size="sm">
            {aiLoading ? "AI đang phân tích…" : "Nhận tư vấn"}
          </Button>
        }
        className="scroll-mt-20"
      >
        <div ref={adviceRef} />
        {aiError && <Alert kind="error">{aiError}</Alert>}
        {!advice && !aiError && (
          <p className="text-sm text-secondary">
            AI sẽ phân tích kết quả học tập và đề xuất lớp phù hợp với bạn trong kỳ này.
          </p>
        )}
        {advice && (
          <div className="space-y-4">
            {advice.fallback && (
              <Alert kind="warn">
                AI tạm thời không khả dụng — hiển thị danh sách lớp bạn đủ điều kiện đăng ký
                (tính từ dữ liệu hệ thống).
              </Alert>
            )}
            {advice.overview && (
              <div className="bg-app border border-border rounded-lg p-3.5">
                <h3 className="text-sm font-semibold mb-1.5 inline-flex items-center gap-1.5">
                  <Sparkles size={14} className="text-primary" /> Nhận xét của AI
                </h3>
                <p className="text-sm text-secondary whitespace-pre-line leading-relaxed">
                  {advice.overview}
                </p>
              </div>
            )}
            {advice.recommendations?.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">Gợi ý của AI</h3>
                <ul className="space-y-2">
                  {advice.recommendations.map((r) => {
                    const cls = classes.find((c) => c.id === r.course_class_id);
                    const enrolled = myEnrollmentIds.has(r.course_class_id);
                    return (
                      <li
                        key={r.course_class_id}
                        className="flex items-start justify-between gap-3 bg-primary-soft border border-primary/20 rounded-lg p-3"
                      >
                        <div>
                          <div className="font-medium text-sm">
                            {r.course_code}
                            {cls ? ` — ${cls.course_name}` : ""}
                          </div>
                          <div className="text-xs text-secondary mt-0.5">{r.reason}</div>
                        </div>
                        <Button
                          size="sm"
                          onClick={() => enroll(r.course_class_id)}
                          disabled={enrolled || enrollingId != null || !cls}
                          variant={enrolled ? "secondary" : "primary"}
                          className="shrink-0"
                        >
                          {enrolled ? "Đã đăng ký" : "Đăng ký học phần"}
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
            {advice.notes && <p className="text-sm text-secondary italic">{advice.notes}</p>}
            {advice.warnings?.length > 0 && (
              <div className="bg-warning/5 border border-warning/30 rounded-lg p-3.5">
                <h3 className="text-sm font-semibold mb-1.5 inline-flex items-center gap-1.5 text-warning">
                  <TriangleAlert size={14} /> Lưu ý từ AI
                </h3>
                <ul className="list-disc pl-5 space-y-1 text-sm text-secondary">
                  {advice.warnings.map((w, i) => (
                    <li key={i} className="leading-relaxed">{w}</li>
                  ))}
                </ul>
              </div>
            )}
            {advice.suggestions?.length > 0 && (
              <div className="bg-success/5 border border-success/30 rounded-lg p-3.5">
                <h3 className="text-sm font-semibold mb-1.5 inline-flex items-center gap-1.5 text-success">
                  <Lightbulb size={14} /> Gợi ý của AI
                </h3>
                <ul className="list-disc pl-5 space-y-1 text-sm text-secondary">
                  {advice.suggestions.map((s, i) => (
                    <li key={i} className="leading-relaxed">{s}</li>
                  ))}
                </ul>
              </div>
            )}
            {advice.eligible_classes?.length > 0 && (
              <details className="text-sm">
                <summary className="cursor-pointer text-primary font-medium">
                  Danh sách {advice.eligible_classes.length} lớp bạn đủ điều kiện đăng ký
                </summary>
                <ul className="mt-2 space-y-1">
                  {advice.eligible_classes.map((c) => (
                    <li key={c.class_id} className="text-secondary">
                      <b className="text-primary">{c.course_code}</b> {c.course_name} ({c.credits} tc) —{" "}
                      {fmtSchedule(c.schedule)} — còn {c.remaining_slots} chỗ
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </Card>

      <Card title={`Lớp đang mở (${classes.length})`} padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã HP" },
            { key: "name", label: "Học phần" },
            { key: "credits", label: "TC", align: "right" },
            { key: "lecturer", label: "Giảng viên" },
            { key: "schedule", label: "Lịch học" },
            { key: "size", label: "Sĩ số", align: "right" },
            { key: "prereq", label: "Tiên quyết" },
            { key: "action", label: "" },
          ]}
          rows={classes}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <CalendarX size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Hiện chưa có lớp nào mở đăng ký.</p>
              <p className="text-sm text-secondary mt-1">
                Vui lòng quay lại khi phòng đào tạo mở lớp, hoặc liên hệ phòng đào tạo để biết lịch đăng ký.
              </p>
            </div>
          }
          renderRow={(c) => {
            const enrolled = myEnrollmentIds.has(c.id);
            const full = c.enrolled_count >= c.max_size;
            return (
              <Row key={c.id}>
                <Cell className="font-medium">
                  {c.course_code}
                  <span className="text-secondary text-xs"> · {fmtTerm(c.year, c.term)}</span>
                </Cell>
                <Cell className="whitespace-normal min-w-40">{c.course_name}</Cell>
                <NumCell>{c.credits}</NumCell>
                <Cell>{c.lecturer_name ?? "—"}</Cell>
                <Cell className="text-xs whitespace-normal">{fmtSchedule(c.schedule)}</Cell>
                <NumCell>
                  {c.enrolled_count}/{c.max_size}
                  {full && (
                    <Badge tone="danger" className="ml-2">
                      đầy
                    </Badge>
                  )}
                </NumCell>
                <Cell className="text-xs whitespace-normal">
                  {c.prerequisite_codes?.length ? c.prerequisite_codes.join(", ") : "—"}
                </Cell>
                <Cell className="text-right">
                  <Button
                    size="sm"
                    variant={enrolled ? "secondary" : "primary"}
                    onClick={() => enroll(c.id)}
                    disabled={enrolled || enrollingId != null}
                  >
                    {enrolled ? "Đã đăng ký" : "Đăng ký"}
                  </Button>
                </Cell>
              </Row>
            );
          }}
        />
      </Card>
    </div>
  );
}
