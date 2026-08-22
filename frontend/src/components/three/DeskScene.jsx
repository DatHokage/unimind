import { useEffect, useRef } from "react";

/* ============ Nền "Bàn học flat-lay" — SVG vector, không WebGL ============
   Nhìn từ trên xuống một bàn học: ly cà phê, sách mở, bút chì xếp thành
   cụm tĩnh vật dưới trái — chừa trống cho chữ (trái) và card (phải).

   Tương tác:
   - Bánh xe chuột: thời gian trong ngày trôi 7:00 → 22:00 theo QUÁN TÍNH —
     lướt mạnh thì ngày "tuôn" qua vài giờ như time-lapse. Cả khung cảnh đổi
     theo: bầu trời chuyển màu (xanh mai → trưa sáng → cam hoàng hôn → đêm
     xanh đậm), mặt trời/mặt trăng bay ngang trời, sao lấp lánh về đêm, bóng
     đổ dài ngắn theo góc nắng, tối thì đèn bàn thắp "vũng sáng ấm" quanh
     khu vực nội dung, khói cà phê đậm hơn. Đồng hồ + cung nhật trình góc dưới.
   - Chuột: parallax 3 lớp chiều sâu + quầng sáng ấm theo con trỏ.
   - Click: gợn sóng mực lan nhẹ.
   - prefers-reduced-motion: khung tĩnh buổi sáng, không listener. */

// ----- Mốc ánh sáng theo thời gian trong ngày (t = 0 sáng → 1 tối) -----
// sky: [màu đỉnh trời, màu chân trời] (rgb arrays) — amb: lớp phủ toàn màn,
// sun: màu thiên thể, sx/sy: hướng bóng, ss: độ kéo dài bóng (hoàng hôn dài).
const DAY_STOPS = [
  { t: 0.0, sky: [[207, 232, 255], [253, 246, 232]], amb: [255, 250, 240, 0.0], sun: [255, 214, 138], sx: -24, sy: -14, ss: 1.18 },
  { t: 0.3, sky: [[186, 227, 255], [255, 249, 236]], amb: [255, 244, 220, 0.05], sun: [255, 222, 120], sx: -4, sy: -16, ss: 0.92 },
  { t: 0.62, sky: [[255, 178, 102], [255, 224, 180]], amb: [255, 148, 78, 0.15], sun: [255, 138, 66], sx: 24, sy: 8, ss: 1.45 },
  { t: 0.82, sky: [[122, 108, 176], [232, 164, 120]], amb: [104, 86, 156, 0.2], sun: [255, 172, 128], sx: 16, sy: 12, ss: 1.25 },
  { t: 1.0, sky: [[18, 26, 58], [43, 54, 96]], amb: [8, 14, 44, 0.3], sun: [170, 192, 255], sx: -10, sy: 14, ss: 1.1 },
];

// Bánh xe cộng vận tốc → quán tính: một cú lướt cuộn vài giờ đồng hồ
const WHEEL_VEL = 0.0025; // deltaY → vận tốc ngày (/s)
const VEL_DECAY = 3.0; // ma sát quán tính /s
const VEL_MAX = 1.4; // trần vận tốc (ngày/s)
const LERP = 3.2; // damping /s cho mọi giá trị nội suy
const CLOCK_START_H = 7;
const CLOCK_SPAN_H = 15; // 07:00 → 22:00

/** Nội suy tuyến tính giữa các mốc DAY_STOPS tại t. */
function dayAt(t) {
  let a = DAY_STOPS[0];
  let b = DAY_STOPS[DAY_STOPS.length - 1];
  for (let i = 0; i < DAY_STOPS.length - 1; i++) {
    if (t >= DAY_STOPS[i].t && t <= DAY_STOPS[i + 1].t) {
      a = DAY_STOPS[i];
      b = DAY_STOPS[i + 1];
      break;
    }
  }
  const span = b.t - a.t || 1;
  const k = (t - a.t) / span;
  const mix = (x, y) => x + (y - x) * k;
  return {
    sky: [0, 1].map((j) => a.sky[j].map((v, i) => Math.round(mix(v, b.sky[j][i])))),
    amb: a.amb.map((v, i) => mix(v, b.amb[i])),
    sun: a.sun.map((v, i) => Math.round(mix(v, b.sun[i]))),
    sx: mix(a.sx, b.sx),
    sy: mix(a.sy, b.sy),
    ss: mix(a.ss, b.ss),
  };
}

export default function DeskScene({ reduced = false }) {
  const rootRef = useRef(null);
  const clockRef = useRef(null);
  const orbitRef = useRef(null);
  const lampRef = useRef(null);
  const sunRef = useRef(null);
  const starWrapRef = useRef(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return undefined;

    // Viewport đọc 1 lần, cập nhật qua resize — tránh đo layout trong mỗi khung
    let vw = window.innerWidth;
    let vh = window.innerHeight;

    // Trạng thái mượt: mục tiêu ← input, giá trị thực lerp theo rAF
    const st = {
      day: 0.08, // ~08:15 sáng — khung mở đầu
      tDay: 0.08,
      vel: 0, // vận tốc quán tính của thời gian (ngày/s)
      mx: 0,
      my: 0,
      tmx: 0,
      tmy: 0,
      lampX: vw * 0.5,
      lampY: vh * 0.5,
      tlampX: vw * 0.5,
      tlampY: vh * 0.5,
    };

    // Ngưỡng coi như "đã đứng yên" — dưới ngưỡng thì ngừng hẹn khung kế (ngủ)
    const DAY_EPS = 0.0004; // ~6 phút đồng hồ trên quãng 15h
    const VEL_EPS = 0.002;
    const MOUSE_EPS = 0.001;
    const LAMP_EPS = 0.5; // px

    // Ghi biến CSS chỉ khi giá trị thật sự đổi: ghi trùng giá trị vẫn làm bẩn
    // style của cả cây — nguồn tốn CPU chính khi cảnh đứng yên
    const mkWriter = (style) => {
      const cache = new Map();
      return (name, val) => {
        if (cache.get(name) === val) return;
        cache.set(name, val);
        style.setProperty(name, val);
      };
    };
    const setRoot = mkWriter(root.style);
    const setDoc = mkWriter(document.documentElement.style);

    let rafId = 0;
    let running = false;
    let last = 0;

    // Bánh xe KHÔNG đặt thẳng thời gian mà cộng vận tốc — lướt mạnh thì
    // ngày cuộn qua nhanh (time-lapse), thả tay trôi dần rồi đứng.
    const onWheel = (e) => {
      const norm = e.deltaMode === 1 ? e.deltaY * 24 : e.deltaY;
      st.vel = Math.max(-VEL_MAX, Math.min(VEL_MAX, st.vel + norm * WHEEL_VEL));
      wake();
    };
    const onPointerMove = (e) => {
      st.tmx = (e.clientX / vw - 0.5) * 2;
      st.tmy = (e.clientY / vh - 0.5) * 2;
      st.tlampX = e.clientX;
      st.tlampY = e.clientY;
      wake();
    };

    // Gợn sóng mực khi click — chèn div, tự hủy sau animation
    const onClick = (e) => {
      const ring = document.createElement("span");
      ring.className = "desk-ripple";
      ring.style.left = `${e.clientX}px`;
      ring.style.top = `${e.clientY}px`;
      root.appendChild(ring);
      setTimeout(() => ring.remove(), 900);
    };

    const onResize = () => {
      vw = window.innerWidth;
      vh = window.innerHeight;
      wake(); // vị trí mặt trời theo viewport — vẽ lại ngay
    };

    if (!reduced) {
      window.addEventListener("wheel", onWheel, { passive: true });
      window.addEventListener("pointermove", onPointerMove, { passive: true });
      window.addEventListener("pointerdown", onClick, { passive: true });
      window.addEventListener("resize", onResize, { passive: true });
    }

    const frame = (now) => {
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;

      // Quán tính thời gian: tích phân vận tốc + ma sát; chạm biên thì dừng
      if (!reduced) {
        st.tDay = Math.max(0, Math.min(1, st.tDay + st.vel * dt));
        if (st.tDay <= 0 || st.tDay >= 1) st.vel = 0;
        st.vel *= Math.exp(-dt * VEL_DECAY);
      }
      const k = 1 - Math.exp(-dt * LERP);
      st.day += (st.tDay - st.day) * k;
      st.mx += (st.tmx - st.mx) * k;
      st.my += (st.tmy - st.my) * k;
      st.lampX += (st.tlampX - st.lampX) * k;
      st.lampY += (st.tlampY - st.lampY) * k;

      const d = dayAt(st.day);
      // Bầu trời toàn màn + ánh sáng phủ + bóng đổ theo góc nắng
      setRoot("--skytop", `rgb(${d.sky[0].join(",")})`);
      setRoot("--skybot", `rgb(${d.sky[1].join(",")})`);
      setRoot("--mx", st.mx.toFixed(3));
      setRoot("--my", st.my.toFixed(3));
      setRoot("--sx", `${d.sx.toFixed(1)}px`);
      setRoot("--sy", `${d.sy.toFixed(1)}px`);
      setRoot("--sscale", d.ss.toFixed(3));
      setRoot(
        "--ambient",
        `rgba(${d.amb[0].toFixed(0)},${d.amb[1].toFixed(0)},${d.amb[2].toFixed(0)},${d.amb[3].toFixed(3)})`
      );
      // Đêm về: sao hiện (t≥0.72), đèn bàn thắp vũng sáng giữ chữ dễ đọc,
      // đèn đọc sách quanh cụm đồ vật bật dần từ t=0.62 (mạnh hơn để đồ vật
      // luôn "đang được chiếu sáng", không chìm vào nền tối)
      const easeOut = (p) => p * (2 - p);
      const stars = Math.max(0, Math.min(1, (st.day - 0.72) / 0.2));
      const pool = easeOut(Math.max(0, Math.min(1, (st.day - 0.64) / 0.22))) * 0.95;
      const lampOn = Math.max(0, Math.min(1, (st.day - 0.62) / 0.3));
      setRoot("--stars", stars.toFixed(3));
      setRoot("--pool", pool.toFixed(3));
      setRoot("--lampbook", (lampOn * 0.55).toFixed(3));
      setRoot("--steam", (0.35 + lampOn * 0.65).toFixed(3));
      setRoot("--dustglow", (0.45 + st.day * 0.55).toFixed(3));
      // Ban ngày sao ẩn hẳn khỏi cây composite — 42 ngôi sao đỡ được vẽ vô ích
      if (starWrapRef.current) {
        const vis = stars <= 0.001 ? "hidden" : "visible";
        if (starWrapRef.current.style.visibility !== vis)
          starWrapRef.current.style.visibility = vis;
      }
      // Khối chữ cột trái đổi cả nhóm khi trời tối theo tông "ánh trăng ấm":
      // dẫn xám be → chính ngà sáng → nhấn vàng gilt (cùng họ với sao/mặt trăng/
      // đèn bàn thay vì xanh băng lạnh) — dịu mắt mà vẫn đủ thứ bậc
      const nk = Math.max(0, Math.min(1, (st.day - 0.55) / 0.28));
      const mixc = (a, b) => Math.round(a + (b - a) * nk);
      setDoc("--eyebrow", `rgb(${mixc(107, 196)},${mixc(107, 191)},${mixc(96, 178)})`);
      setDoc("--inkline", `rgb(${mixc(46, 245)},${mixc(46, 241)},${mixc(42, 229)})`);
      setDoc("--blueline", `rgb(${mixc(0, 233)},${mixc(149, 199)},${mixc(255, 140)})`);
      // Đêm về thêm bóng mềm sau chữ (class .night-shade) để chữ sáng tách
      // khỏi vệt sáng mờ phía sau, dễ đọc trên mọi vùng nền
      setDoc("--nightshade", nk.toFixed(3));

      if (lampRef.current) {
        const lt = `translate(${st.lampX.toFixed(1)}px, ${st.lampY.toFixed(1)}px)`;
        if (lampRef.current.style.transform !== lt)
          lampRef.current.style.transform = lt;
        const lo = (0.06 + st.day * 0.08).toFixed(3);
        if (lampRef.current.style.opacity !== lo)
          lampRef.current.style.opacity = lo;
      }

      // Mặt trời → mặt trăng: cung phẳng trên DẢI TRỜI TRÊN cùng, luôn chạy
      // PHÍA TRÊN thẻ login (thẻ chiếm nửa phải từ ~20vh xuống) nên đêm về
      // mặt trăng đỗ góc trên phải vẫn nguyên vẹn, không bị che.
      if (sunRef.current) {
        const arcH = Math.sin(Math.PI * st.day); // 0 → 1 giữa trưa → 0
        const tf = `translate(${(vw * (0.36 + 0.52 * st.day)).toFixed(0)}px, ${(vh * (0.125 - 0.07 * arcH)).toFixed(0)}px)`;
        if (sunRef.current.style.transform !== tf)
          sunRef.current.style.transform = tf;
      }
      const [sr, sg, sb] = d.sun;
      setRoot("--suncolor", `rgb(${sr},${sg},${sb})`);
      setRoot("--sunglow", `rgba(${sr},${sg},${sb},0.5)`);
      // Tia nắng rõ ban ngày, tan khi chiều xuống; đêm về hố trăng hiện ra
      setRoot("--sunmode", Math.max(0, Math.min(1, 1.15 - st.day * 1.35)).toFixed(3));
      setRoot("--moonn", Math.max(0, Math.min(1, (st.day - 0.74) / 0.2)).toFixed(3));

      // Đồng hồ + quả cầu trên vạch cung nhật trình — chỉ đụng DOM khi đổi giá trị
      const totalMin = CLOCK_START_H * 60 + st.day * CLOCK_SPAN_H * 60;
      if (clockRef.current) {
        const clk = `${String(Math.floor(totalMin / 60)).padStart(2, "0")}:${String(Math.floor(totalMin % 60)).padStart(2, "0")}`;
        if (clockRef.current.textContent !== clk) clockRef.current.textContent = clk;
      }
      if (orbitRef.current) {
        const ang = Math.PI * (1 - st.day); // trái → phải qua đỉnh
        const ox = (46 + Math.cos(ang) * 38).toFixed(1);
        const oy = (40 - Math.sin(ang) * 26).toFixed(1);
        const oc = `rgb(${d.sun.join(",")})`;
        const o = orbitRef.current;
        if (o.getAttribute("cx") !== ox) o.setAttribute("cx", ox);
        if (o.getAttribute("cy") !== oy) o.setAttribute("cy", oy);
        if (o.getAttribute("fill") !== oc) o.setAttribute("fill", oc);
      }

      // Mọi giá trị đã hội tụ → ngủ: không hẹn khung kế cho tới khi có input mới.
      // Đây là tối ưu lớn nhất — trước đây loop chạy mãi mãi kể cả khi tĩnh.
      const settled =
        Math.abs(st.vel) < VEL_EPS &&
        Math.abs(st.tDay - st.day) < DAY_EPS &&
        Math.abs(st.tmx - st.mx) < MOUSE_EPS &&
        Math.abs(st.tmy - st.my) < MOUSE_EPS &&
        Math.abs(st.tlampX - st.lampX) < LAMP_EPS &&
        Math.abs(st.tlampY - st.lampY) < LAMP_EPS;
      rafId = settled ? 0 : requestAnimationFrame(frame);
    };

    // Đánh thức vòng lặp sau khi ngủ (wheel/pointermove/resize gọi vào đây)
    const wake = () => {
      if (!running || rafId) return;
      last = performance.now();
      rafId = requestAnimationFrame(frame);
    };

    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(rafId);
        rafId = 0;
      } else {
        running = true;
        wake();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    // Vẽ khung đầu tiên ngay; reduced motion thì dừng hẳn (không listener, không loop)
    if (reduced) {
      frame(performance.now());
    } else {
      running = true;
      wake();
    }

    return () => {
      running = false;
      cancelAnimationFrame(rafId);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerdown", onClick);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      document.documentElement.style.removeProperty("--eyebrow");
      document.documentElement.style.removeProperty("--inkline");
      document.documentElement.style.removeProperty("--blueline");
      document.documentElement.style.removeProperty("--nightshade");
    };
  }, [reduced]);

  // Vị trí bụi sáng / sao gieo hạt cố định — không nhảy giữa các lần mount
  const dusts = DUST;
  const stars = STARS;

  return (
    <div ref={rootRef} className="desk-scene absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* ===== Bầu trời đổi màu theo giờ trong ngày ===== */}
      <div className="desk-sky" />

      {/* Sao lấp lánh — chỉ hiện về đêm (--stars); ban ngày ẩn hẳn qua visibility */}
      <div ref={starWrapRef} className="desk-starwrap">
        {stars.map(([x, y, s, dur, delay], i) => (
          <span
            key={i}
            className="desk-star"
            style={{
              left: `${x}%`,
              top: `${y}%`,
              width: s,
              height: s,
              animationDuration: `${dur}s`,
              animationDelay: `${delay}s`,
            }}
          />
        ))}
      </div>

      {/* Vũng đèn ấm giữ vùng nội dung dễ đọc khi trời tối — đặt DƯỚI đồ vật
          để sách/bút chì/cà phê không bị phủ kem mà nhìn mờ đi */}
      <div className="desk-pool" />

      {/* ===== Lớp sâu nhất — parallax yếu ===== */}
      <div className="desk-layer" style={{ "--depth": 6 }}>
        {/* Mặt trời → mặt trăng bay cung ngang trời (transform ghi từ rAF):
            tia nắng quay chậm + quầng thở, đêm về hố mặt trăng hiện ra */}
        <div ref={sunRef} className="desk-sunmoon">
          <span className="desk-sun-rays" />
          <span className="desk-sun-halo" />
          <span className="desk-sun-core" />
          <span className="desk-moon"><i /><i /><i /></span>
        </div>
        <svg className="desk-svg desk-item-book" viewBox="0 0 320 200">
          <defs>
            <filter id="deskSoft" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="7" />
            </filter>
            {/* Trang tối dần về gáy sách như ánh sáng thật */}
            <linearGradient id="deskPageL" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#EAE2CE" />
              <stop offset="0.22" stopColor="#FAF6EA" />
              <stop offset="1" stopColor="#FFFDF6" />
            </linearGradient>
            <linearGradient id="deskPageR" x1="1" y1="0" x2="0" y2="0">
              <stop offset="0" stopColor="#EAE2CE" />
              <stop offset="0.22" stopColor="#F8F3E4" />
              <stop offset="1" stopColor="#FCF8EE" />
            </linearGradient>
            <linearGradient id="deskGutter" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="rgba(96,84,62,0)" />
              <stop offset="0.5" stopColor="rgba(96,84,62,0.18)" />
              <stop offset="1" stopColor="rgba(96,84,62,0)" />
            </linearGradient>
          </defs>
          {/* Bóng đổ — xoay theo --sx/--sy do wheel điều khiển */}
          <ellipse
            className="desk-shadow"
            cx="160" cy="114" rx="140" ry="54"
            fill="rgba(96,84,62,0.20)" filter="url(#deskSoft)"
          />
          {/* Mép bìa lộ ra dưới đáy — quyển sách có độ dày thật */}
          <path
            d="M160 58 C124 36 72 30 34 40 C25 42 20 48 20 56 L20 148 C20 157 25 162 35 161 C77 155 123 161 160 178 C197 161 243 155 285 161 C295 162 300 157 300 148 L300 56 C300 48 295 42 286 40 C248 30 196 36 160 58 Z"
            fill="#DCD2B8"
          />
          {/* Hai tầng trang giấy phía dưới — hiệu ứng xòe trang */}
          <path
            d="M160 52 C126 32 76 26 38 35 C30 37 26 42 26 50 L26 139 C26 147 30 152 39 151 C79 145 124 151 160 168 Z"
            fill="#EFE8D6"
          />
          <path
            d="M160 52 C194 32 244 26 282 35 C290 37 294 42 294 50 L294 139 C294 147 290 152 281 151 C241 145 196 151 160 168 Z"
            fill="#ECE4D0"
          />
          {/* Trang trái — cong lên từ gáy, gradient sáng dần ra ngoài */}
          <path
            d="M160 48 C128 29 80 23 42 32 C34 34 30 39 30 47 L30 133 C30 141 34 146 43 145 C82 139 126 145 160 162 Z"
            fill="url(#deskPageL)" stroke="rgba(46,46,42,0.07)" strokeWidth="1.5"
          />
          {/* Trang phải */}
          <path
            d="M160 48 C192 29 240 23 278 32 C286 34 290 39 290 47 L290 133 C290 141 286 146 277 145 C238 139 194 145 160 162 Z"
            fill="url(#deskPageR)" stroke="rgba(46,46,42,0.07)" strokeWidth="1.5"
          />
          {/* Bóng rãnh giữa hai trang */}
          <rect x="142" y="46" width="36" height="118" fill="url(#deskGutter)" />
          {/* Dòng chữ mờ nghiêng nhẹ theo độ cong trang */}
          {[62, 77, 92, 107].map((y, i) => (
            <rect
              key={`bl${y}`} x="48" y={y} width={[86, 92, 88, 62][i]} height="5" rx="2.5"
              fill="rgba(46,46,42,0.10)"
              transform={`rotate(-1.1 ${48 + [86, 92, 88, 62][i] / 2} ${y})`}
            />
          ))}
          {[62, 77, 92, 107].map((y, i) => (
            <rect
              key={`br${y}`} x="184" y={y} width={[82, 88, 84, 56][i]} height="5" rx="2.5"
              fill="rgba(46,46,42,0.09)"
              transform={`rotate(1.1 ${184 + [82, 88, 84, 56][i] / 2} ${y})`}
            />
          ))}
          {/* Gáy giữa */}
          <path d="M160 48 L160 162" stroke="rgba(46,46,42,0.10)" strokeWidth="2.5" />
          {/* Góc trang lay nhẹ */}
          <path className="desk-flutter" d="M278 32 C286 44 287 60 280 74 C272 62 270 46 274 33 Z" fill="#F3ECDB" />
        </svg>

      </div>

      {/* ===== Lớp giữa — parallax vừa ===== */}
      <div className="desk-layer" style={{ "--depth": 11 }}>
        {/* Cà phê — dưới trái: bộ sứ men trắng có latte art, hạt cà phê rơi cạnh,
            khói ba dải uốn lượn bay lệch pha */}
        <svg className="desk-svg desk-item-coffee" viewBox="0 0 200 240">
          <defs>
            {/* Men sứ khối nhẹ — đón sáng góc trên trái */}
            <linearGradient id="deskPorcelain" x1="0" y1="0" x2="0.9" y2="1">
              <stop offset="0" stopColor="#FFFDF8" />
              <stop offset="0.65" stopColor="#F4EEDF" />
              <stop offset="1" stopColor="#E2D8C1" />
            </linearGradient>
            {/* Mặt cà phê — crema sáng giữa, viền sẫm màu */}
            <radialGradient id="deskCrema" cx="0.42" cy="0.38" r="0.75">
              <stop offset="0" stopColor="#8A6242" />
              <stop offset="0.62" stopColor="#6F4B31" />
              <stop offset="1" stopColor="#52361E" />
            </radialGradient>
            {/* Đĩa lót — lòng đĩa trũng tối, vành ngoài đón sáng */}
            <radialGradient id="deskSaucer" cx="0.5" cy="0.42" r="0.62">
              <stop offset="0" stopColor="#E5DCC5" />
              <stop offset="0.72" stopColor="#EFE8D6" />
              <stop offset="1" stopColor="#FCF8ED" />
            </radialGradient>
            {/* Nhoè nhẹ riêng cho khói — mềm như hơi nước thật */}
            <filter id="deskMist" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="1.4" />
            </filter>
          </defs>

          {/* Bóng đổ xoay theo góc nắng */}
          <ellipse className="desk-shadow" cx="104" cy="152" rx="78" ry="28" fill="rgba(96,84,62,0.22)" filter="url(#deskSoft)" />

          {/* Đĩa lót: đáy dày → mặt đĩa → lòng trũng hai tầng */}
          <ellipse cx="100" cy="143" rx="70" ry="27" fill="#E7DECB" />
          <ellipse cx="100" cy="139" rx="70" ry="27" fill="url(#deskSaucer)" stroke="rgba(46,46,42,0.06)" strokeWidth="1.5" />
          <ellipse cx="100" cy="137" rx="52" ry="19" fill="rgba(122,106,80,0.10)" />
          <ellipse cx="100" cy="136" rx="47" ry="16.5" fill="rgba(255,252,244,0.55)" />

          {/* Bóng cúp ép lên đĩa */}
          <ellipse cx="100" cy="134" rx="49" ry="18" fill="rgba(96,84,62,0.14)" />

          {/* Thân cúp men trắng + thành trong hai tầng */}
          <circle cx="100" cy="131" r="46" fill="url(#deskPorcelain)" />
          <circle cx="100" cy="131" r="46" fill="none" stroke="rgba(46,46,42,0.07)" strokeWidth="2" />
          <circle cx="100" cy="131" r="39" fill="#EAE1CD" />
          <circle cx="100" cy="131" r="36.5" fill="#F6F0E1" />

          {/* Mặt cà phê + vành crema bám mép */}
          <circle cx="100" cy="130" r="33" fill="url(#deskCrema)" />
          <circle cx="100" cy="130" r="33" fill="none" stroke="rgba(222,188,138,0.42)" strokeWidth="2.5" />

          {/* Latte art trái tim + nét rửa sữa */}
          <path
            d="M100 146 C86.5 136 82.5 127 89.5 120.5 C94 116.5 99 119.5 100 125 C101 119.5 106 116.5 110.5 120.5 C117.5 127 113.5 136 100 146 Z"
            fill="#EFDFBF" opacity="0.92"
          />
          <path d="M93 123 Q100 118.5 107 123" fill="none" stroke="rgba(122,82,52,0.5)" strokeWidth="1.6" strokeLinecap="round" />

          {/* Điểm sáng men sứ góc trên trái + quai cúp hai lớp tạo khối */}
          <path d="M58 112 A46 46 0 0 1 81 89" fill="none" stroke="rgba(255,255,255,0.9)" strokeWidth="4" strokeLinecap="round" />
          <path d="M144 121 q24 5 18 24 q-5.5 17 -25 13" fill="none" stroke="url(#deskPorcelain)" strokeWidth="10" strokeLinecap="round" />
          <path d="M145 124.5 q19.5 5.5 14.5 20" fill="none" stroke="rgba(46,46,42,0.10)" strokeWidth="3" strokeLinecap="round" />

          {/* Hai hạt cà phê rơi cạnh đĩa — chi tiết nhỏ cho cảnh sống */}
          <g transform="rotate(26 36 182)">
            <ellipse cx="36" cy="182" rx="10.5" ry="7" fill="#7A5539" />
            <path d="M28 181.5 Q36 177.5 44 181.5" fill="none" stroke="rgba(56,37,21,0.75)" strokeWidth="1.8" strokeLinecap="round" />
          </g>
          <g transform="rotate(-18 60 197)">
            <ellipse cx="60" cy="197" rx="9.5" ry="6.4" fill="#8A6242" />
            <path d="M52.8 196.6 Q60 193 67.2 196.6" fill="none" stroke="rgba(56,37,21,0.7)" strokeWidth="1.6" strokeLinecap="round" />
          </g>

          {/* Khói ba dải uốn lượn — nhịp bay lệch pha (delay trong CSS) */}
          <g className="desk-steam" filter="url(#deskMist)">
            <path d="M84 100 C74 84 94 76 84 58 C78 47 90 40 86 26" fill="none" stroke="rgba(122,106,88,0.42)" strokeWidth="5.5" strokeLinecap="round" />
            <path d="M103 96 C113 82 93 72 104 54 C111 43 98 36 103 20" fill="none" stroke="rgba(122,106,88,0.36)" strokeWidth="4.5" strokeLinecap="round" />
            <path d="M119 102 C129 90 113 80 122 64 C128 54 118 46 123 34" fill="none" stroke="rgba(122,106,88,0.30)" strokeWidth="4" strokeLinecap="round" />
          </g>
        </svg>

        {/* Bút chì — dưới phải */}
        <svg className="desk-svg desk-item-pencil" viewBox="0 0 300 54">
          <ellipse className="desk-shadow" cx="152" cy="40" rx="130" ry="12" fill="rgba(96,84,62,0.18)" filter="url(#deskSoft)" />
          <g transform="rotate(-6 150 27)">
            <rect x="52" y="17" width="192" height="21" rx="4" fill="#D9A441" />
            <rect x="52" y="17" width="192" height="7" rx="3.5" fill="rgba(255,255,255,0.22)" />
            <polygon points="52,17 20,27.5 52,38" fill="#EAD9B8" />
            <polygon points="30,24.5 20,27.5 30,30.5" fill="#4A4A42" />
            <rect x="246" y="15" width="14" height="25" rx="3" fill="#9AA7B8" />
            <rect x="260" y="16" width="18" height="23" rx="8" fill="#C98F70" />
          </g>
        </svg>
      </div>

      {/* ===== Lớp gần — bụi sáng + đèn theo chuột ===== */}
      <div className="desk-layer" style={{ "--depth": 16 }}>
        <div className="desk-dustwrap" style={{ "--dust": 1 }}>
          {dusts.map(([x, y, s, dur, delay], i) => (
            <span
              key={i}
              className="desk-dust"
              style={{
                left: `${x}%`,
                top: `${y}%`,
                width: s,
                height: s,
                animationDuration: `${dur}s`,
                animationDelay: `${delay}s`,
              }}
            />
          ))}
        </div>
      </div>

      {/* Đèn đọc sách buổi tối — quầng ấm chiếu thẳng lên cụm đồ vật */}
      <div className="desk-lampbook" />

      {/* Quầng sáng ấm theo con trỏ */}
      <div ref={lampRef} className="desk-cursorlamp" />

      {/* Nhật trình: cung + quả cầu mặt trời/mặt trăng + đồng hồ */}
      <div className="desk-orbit">
        <svg viewBox="0 0 92 48" width="92" height="48">
          <path d="M8 40 Q46 2 84 40" fill="none" stroke="rgba(46,46,42,0.18)" strokeWidth="2" strokeDasharray="1 5" strokeLinecap="round" />
          <line x1="4" y1="41" x2="88" y2="41" stroke="rgba(46,46,42,0.14)" strokeWidth="2" strokeLinecap="round" />
          <circle ref={orbitRef} cx="8" cy="40" r="5" fill="#FFD88A" />
        </svg>
        <span ref={clockRef} className="num desk-clock">07:00</span>
      </div>
    </div>
  );
}

/* Bụi sáng: [x%, y%, kích thước px, chu kỳ bay, delay] — seed cứng */
const DUST = Array.from({ length: 18 }, (_, i) => {
  const r = mulberryLite(i * 7919 + 13);
  return [
    +(r() * 96).toFixed(2),
    +(r() * 92).toFixed(2),
    +(3 + r() * 4).toFixed(1),
    +(9 + r() * 10).toFixed(1),
    +(r() * -12).toFixed(1),
  ];
});

/* Sao đêm: [x%, y% (nửa trên trời), kích thước px, chu kỳ lấp lánh, delay] */
const STARS = Array.from({ length: 42 }, (_, i) => {
  const r = mulberryLite(i * 104729 + 7);
  return [
    +(r() * 100).toFixed(2),
    +(r() * 52).toFixed(2),
    +(1.4 + r() * 1.8).toFixed(1),
    +(2.4 + r() * 3.2).toFixed(1),
    +(r() * -5).toFixed(1),
  ];
});

function mulberryLite(seed) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
