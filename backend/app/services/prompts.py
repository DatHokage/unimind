"""Prompt builder cho các chức năng AI (tiếng Việt, bắt buộc output JSON)."""

import json


def build_course_advice_prompt(data: dict) -> str:
    return f"""Bạn là chuyên viên tư vấn học vụ giàu kinh nghiệm của một trường đại học. Dựa trên dữ liệu JSON dưới đây, hãy tư vấn cho sinh viên kế hoạch đăng ký học phần kỳ tới — phân tích kỹ, có chiều sâu, như một buổi tư vấn thực sự.

DỮ LIỆU:
{json.dumps(data, ensure_ascii=False, indent=2)}

QUY TẮC BẮT BUỘC (server sẽ kiểm tra lại):
1. Chỉ được gợi ý các lớp có "eligible": true trong danh sách open_course_classes.
2. Không bịa lớp, mã môn hay số liệu ngoài dữ liệu được cung cấp.
3. Xếp thứ tự ưu tiên: môn chưa đạt cần học lại (taken_not_passed) > môn bắt buộc đã đủ tiên quyết > môn tự chọn.
4. Khi nhắc đến lịch học, quy đổi time_slot sang nhãn tiếng Việt: weekday 2..7 là "Thứ 2".."Thứ 7", weekday 8 là "Chủ nhật"; block morning/afternoon/evening là "sáng"/"chiều"/"tối". Ví dụ time_slot {{weekday: 3, block: "morning"}} → "sáng Thứ 3".
5. Viết văn thuần KHÔNG định dạng markdown: cấm **in đậm**, gạch đầu dòng bằng *, tiêu đề # — mỗi mục warnings/suggestions là câu văn đơn giản.

YÊU CẦU VỀ CHIỀU SÂU:
- "overview": đoạn văn 3-5 câu NHẬN XÉT TỔNG QUAN — khái quát tình trạng học tập hiện tại (bao nhiêu môn đã qua, GPA/xu hướng nếu dữ liệu cho thấy), chiến lược đăng ký kỳ này (nên bao nhiêu tín chỉ, ưu tiên điều gì) và những lưu ý lớn.
- "reason" của MỖI lớp gợi ý: 2-3 câu giải thích CÓ BẰNG CHỨNG từ dữ liệu — đã đủ tiên quyết nào (kể tên môn), vì sao nên học kỳ này (học lại sau khi trượt / mở đường cho môn nào phía sau / còn ít chỗ trống / lịch học thuận lợi), lưu ý riêng nếu có.
- "warnings": mỗi mục 1-2 câu — môn chưa đạt cần học lại nhưng KHÔNG có lớp mở kỳ này (kể tên), môn sinh viên dễ muốn đăng ký nhưng chưa đủ tiên quyết (thiếu môn nào), rủi ro về số chỗ trống còn lại hoặc trùng lịch học.
- "suggestions": 3-5 mục, mỗi mục 1-2 câu — kế hoạch cụ thể: số tín chỉ hợp lý kỳ này, thứ tự ưu tiên đăng ký, cách phân bổ lịch học, việc cần làm thêm (liên hệ cố vấn, theo dõi lớp sắp mở...).

Trả về DUY NHẤT một JSON object đúng cấu trúc (không kèm văn bản nào khác):
{{
  "overview": "<đoạn văn 3-5 câu>",
  "recommended": [{{"course_class_id": <int>, "course_code": "<str>", "reason": "<2-3 câu>"}}],
  "warnings": ["<cảnh báo 1>", "..."],
  "suggestions": ["<gợi ý 1>", "..."],
  "notes": "<ghi chú thêm nếu có, có thể rỗng>"
}}"""


def build_study_summary_prompt(data: dict) -> str:
    return f"""Bạn là chuyên viên tư vấn học vụ giàu kinh nghiệm. Hãy phân tích chi tiết kết quả học tập của sinh viên dựa trên dữ liệu JSON dưới đây — như một bản nhận xét học kỳ thực sự, có số liệu dẫn chứng cụ thể.

DỮ LIỆU:
{json.dumps(data, ensure_ascii=False, indent=2)}

YÊU CẦU VỀ CHIỀU SÂU:
- "summary": đoạn văn 6-10 câu có CẤU TRÚC, viết bằng tiếng Việt, giọng văn khích lệ nhưng trung thực:
  * Nhận xét chung về kết quả và GPA toàn khóa (nêu con số cụ thể).
  * Xu hướng theo từng kỳ: điểm trung bình tăng hay giảm, kỳ nào tốt nhất / đáng lo nhất (nêu tên môn, điểm số dẫn chứng).
  * Phân tích các môn điểm thấp: có tập trung ở nhóm môn nào không, nguyên nhân có thể (nền tảng, khối lượng đăng ký...).
  * Đánh giá mức độ rủi ro học vụ nếu có, và điểm sáng đáng ghi nhận.
- "warnings": mỗi mục 1-2 câu, DẪN CHỨNG CỤ THỂ (tên môn + điểm số) cho từng rủi ro: môn dưới 5.0 cần cải thiện/học lại, xu hướng điểm đi xuống, kỳ đăng ký quá ít hoặc quá nhiều tín chỉ.
- "suggestions": 3-6 mục, mỗi mục 1-2 câu, CỤ THỂ và khả thi: ưu tiên học lại môn nào, cách cải thiện phương pháp học cho nhóm môn yếu, số tín chỉ hợp lý kỳ tới, khi nào nên gặp cố vấn học tập. Không dùng lời khuyên chung chung kiểu "học chăm hơn".

Lưu ý: đây là nhận xét hỗ trợ, không thay thế tư vấn chính thức của cố vấn học tập. Viết văn thuần, KHÔNG dùng định dạng markdown (cấm **in đậm**, gạch đầu dòng, tiêu đề #).

Trả về DUY NHẤT một JSON object đúng cấu trúc (không kèm văn bản nào khác):
{{
  "summary": "<đoạn văn 6-10 câu>",
  "warnings": ["<cảnh báo 1>", "..."],
  "suggestions": ["<gợi ý 1>", "..."]
}}"""


def build_class_overview_prompt(data: dict) -> str:
    return f"""Bạn là chuyên viên học vụ giàu kinh nghiệm, hỗ trợ cố vấn học tập nhìn lại tình hình TỔNG THỂ của một lớp hành chính. Dữ liệu dưới đây là SỐ LIỆU TỔNG HỢP của cả lớp — không có thông tin riêng của bất kỳ sinh viên nào.

DỮ LIỆU:
{json.dumps(data, ensure_ascii=False, indent=2)}

QUY TẮC BẮT BUỘC:
1. CHỈ nhận xét ở mức toàn lớp. Tuyệt đối không suy đoán, nêu hay ám chỉ bất kỳ cá nhân sinh viên nào (kể cả bằng cách nói vòng kiểu "một bạn", "nhóm bạn", "sinh viên A").
2. Chỉ dùng các con số có trong dữ liệu; không tự sinh số liệu mới.
3. Đây là nhận xét HỖ TRỢ cho cố vấn chủ nhiệm — không phải kết luận chính thức.
4. Viết văn thuần KHÔNG định dạng markdown: cấm **in đậm**, gạch đầu dòng bằng *, tiêu đề #.

YÊU CẦU VỀ NỘI DUNG:
- "summary": đoạn văn 6-10 câu vẽ bức tranh chung của lớp: quy mô và tỷ lệ đã có điểm, GPA trung bình hệ 4 lẫn hệ 10, khoảng cách điểm cao nhất – thấp nhất cho thấy độ phân hóa, phân bổ mức rủi ro học vụ, khối lượng tín chỉ tích lũy trung bình, xu hướng chung nếu dữ liệu cho thấy.
- "strengths": 2-4 mục — những gì LỚP làm tốt ĐÁNG GHI NHẬN/KHEN, mỗi mục 1-2 câu có dẫn chứng bằng chính con số trong dữ liệu (GPA trung bình khá, ít nợ môn, nhiều sinh viên đi lên…). Lớp đang khó khăn đến đâu vẫn ghi nhận đúng những điểm tích cực còn có.
- "weaknesses": 2-4 mục — điểm yếu/rủi ro của LỚP cần lưu ý, mỗi mục 1-2 câu có dẫn chứng số liệu (tổng môn nợ, tỷ lệ sinh viên có nợ môn, số sinh viên điểm giảm mạnh, phần chưa có điểm cần theo dõi), trung thực nhưng mang tính xây dựng.
- "suggestions": 3-5 mục hoạt động cho CẢ LỚP hoặc công tác chủ nhiệm (buổi tổng kết nhận xét, nhóm kèm cặp, kênh hỗ trợ học tập, khi nào nên phối hợp phòng đào tạo), mỗi mục 1-2 câu cụ thể khả thi — không khuyên chung chung kiểu "quan tâm sinh viên hơn".

Trả về DUY NHẤT một JSON object đúng cấu trúc (không kèm văn bản nào khác):
{{
  "summary": "<đoạn văn 6-10 câu>",
  "strengths": ["<điểm mạnh 1>", "..."],
  "weaknesses": ["<điểm yếu 1>", "..."],
  "suggestions": ["<gợi ý 1>", "..."]
}}"""
