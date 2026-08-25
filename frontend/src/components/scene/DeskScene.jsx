import { useEffect, useRef } from "react";
import { createSkyGL, createSteamGL } from "./glLayers";

/* ============ Nền "Bàn học flat-lay" — SVG vector + lớp WebGL thuần ============
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
// sun: màu thiên thể. (Bóng đổ KHÔNG nằm ở đây nữa — tính hình học từ vị trí
// mặt trời mỗi khung, xem khối setRoot("--srot"…) trong frame.)
const DAY_STOPS = [
  { t: 0.0, sky: [[159, 208, 255], [234, 246, 255]], amb: [235, 244, 255, 0.0], sun: [255, 214, 138] },
  { t: 0.3, sky: [[168, 214, 255], [238, 248, 255]], amb: [228, 240, 255, 0.04], sun: [255, 222, 120] },
  { t: 0.62, sky: [[255, 178, 102], [255, 224, 180]], amb: [255, 148, 78, 0.15], sun: [255, 138, 66] },
  { t: 0.82, sky: [[122, 108, 176], [232, 164, 120]], amb: [104, 86, 156, 0.2], sun: [255, 172, 128] },
  { t: 1.0, sky: [[18, 26, 58], [43, 54, 96]], amb: [8, 14, 44, 0.3], sun: [170, 192, 255] },
];

// Bánh xe cộng vận tốc → quán tính: một cú lướt cuộn vài giờ đồng hồ
const WHEEL_VEL = 0.0025; // deltaY → vận tốc ngày (/s)
const VEL_DECAY = 3.0; // ma sát quán tính /s
const VEL_MAX = 1.4; // trần vận tốc (ngày/s)
const LERP = 3.2; // damping /s cho mọi giá trị nội suy
const SETTLE_EPS = 0.001; // lệch dưới ngưỡng này coi như đứng yên — rAF được phép ngủ
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
  };
}

/** Ease-out bậc hai — đường cong bật dần mềm dùng cho sao/đèn lên đêm. */
const easeOut = (p) => p * (2 - p);

export default function DeskScene({ reduced = false }) {
  const rootRef = useRef(null);
  const skyCanvasRef = useRef(null);
  const steamCanvasRef = useRef(null);
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

    // ----- Lớp WebGL: tạo 1 lần sau mount. Nhà máy tự bắt mọi lỗi nội bộ nên
    // chỉ trả { ok:false } khi thất bại — im lặng giữ fallback CSS/SVG, không
    // bao giờ chặn đăng nhập. Mất context giữa chừng (tab nền lâu / GPU reset)
    // báo về qua onLost: khoá lớp + gỡ class để CSS/SVG tiếp quản ngay.
    let glDead = false;
    let steamDead = false;
    const glSky = createSkyGL(skyCanvasRef.current, () => {
      glDead = true;
      root.classList.remove("is-gl");
    });
    const glReady = glSky.ok;

    // Hơi nước shader — chỉ tạo khi không reduced-motion; thiếu WebGL thì giữ
    // nguyên làn khói SVG mây làm fallback
    let glSteam = null;
    if (!reduced) {
      glSteam = createSteamGL(steamCanvasRef.current, () => {
        steamDead = true;
        root.classList.remove("is-steamgl"); // rớt về làn khói SVG mây
      });
    }
    const glSteamReady = Boolean(glSteam?.ok);

    let sizeDirty = false; // resize tới nhiều lần/khung — gom lại làm 1 lần trong frame
    let lastGlDraw = 0; // mốc chặn nhịp vẽ GL ~30fps (xem cổng trong frame)
    const applySize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2); // chặn DPR quá cao cho màn retina
      // Hai canvas độc lập nhau: trời lỗi vẫn phải resize hơi nước và ngược lại
      if (glReady && !glDead) glSky.resize(vw, vh, dpr);
      if (glSteamReady && !steamDead) {
        const sc = steamCanvasRef.current;
        if (sc) glSteam.resize(sc.clientWidth || 1, sc.clientHeight || 1, dpr);
      }
    };
    applySize();
    if (glReady) root.classList.add("is-gl");
    if (glSteamReady) root.classList.add("is-steamgl"); // CSS ẩn làn khói SVG, hiện canvas shader

    // Vẽ 1 khung GL với các giá trị đã nội suy của khung đó — tách riêng để
    // vòng lặp bọc try/catch: mọi lỗi GL chỉ được phép rơi về fallback CSS.
    // Vị trí mặt trời truyền vào đã tính MỘT LẦN trong frame (xem khối bóng đổ)
    const drawGL = (nowMs, d, stars, sunmodeV, sunX, sunY) => {
      const sunset = Math.exp(-(((st.day - 0.62) / 0.14) ** 2));
      glSky.render({
        t: nowMs / 1000,
        top: d.sky[0],
        bot: d.sky[1],
        amb: d.amb,
        sun: [sunX, sunY],
        suncol: d.sun,
        sunmode: sunmodeV,
        stars,
        sunset,
      });
    };

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
      sizeDirty = true; // canvas GL đổi kích thước trong frame kế — tránh dồn cụp khi kéo cửa sổ
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

      // Canvas GL đổi kích thước tối đa 1 lần/khung bất kể resize nổ bao nhiêu event
      if (sizeDirty) {
        sizeDirty = false;
        applySize();
      }

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
      // Bầu trời toàn màn + ánh sáng phủ
      setRoot("--skytop", `rgb(${d.sky[0].join(",")})`);
      setRoot("--skybot", `rgb(${d.sky[1].join(",")})`);
      setRoot("--mx", st.mx.toFixed(3));
      setRoot("--my", st.my.toFixed(3));

      // ----- Vị trí mặt trời trên màn hình (px CSS, y từ đỉnh): MỘT nguồn duy nhất
      // cho cả ba lớp — quầng shader (drawGL), khối DOM .desk-sunmoon và hướng
      // bóng đổ dưới đây; sửa quỹ đạo chỉ cần sửa tại đây
      const elev = Math.sin(Math.PI * st.day); // 0 chân trời → 1 đỉnh trời
      const sunX = vw * (0.36 + 0.52 * st.day);
      const sunY = vh * (0.125 - 0.07 * elev);
      // ----- Bóng đổ theo HÌNH HỌC MẶT TRỜI: véc-tơ từ thiên thể tới tâm cụm
      // đồ vật quyết định HƯỚNG bóng. Cả ba vật (cà phê, sách, bút chì) dùng
      // CHUNG một bộ tham số nên ba bóng luôn ĐỒNG NHẤT — cùng hướng nắng,
      // cùng nhịp dài/ngắn, cùng độ đậm; chỉ hình elip gốc khác nhau theo
      // từng vật. Ghi 3 đại lượng thô: --srot góc hướng bóng, --sgrow 0..1
      // độ thấp trời (bóng càng dài càng nhạt), --scot lệch tâm theo cot góc
      // nắng. Mép gần (phía nắng) được CSS neo tại chỗ tiếp xúc bàn, chỉ
      // ĐUÔI kéo dài ra xa nắng nên bóng không bao giờ bong khỏi chân vật.
      const objX = vw * 0.17; // tâm cụm tĩnh vật: cà phê + sách + bút chì
      const objY = vh * 0.8;
      const shadDx = objX - sunX;
      const shadDy = (objY - sunY) * 0.35; // nén trục đứng — mặt bàn nhìn từ trên
      const shadLen = Math.hypot(shadDx, shadDy) || 1;
      const low = 1 - elev; // 0 trưa (bóng sát đáy vật) → 1 rìa trời (dài, nhạt)
      setRoot("--srot", `${((Math.atan2(shadDy / shadLen, shadDx / shadLen) * 180) / Math.PI).toFixed(2)}deg`);
      setRoot("--sgrow", low.toFixed(3));
      setRoot("--scot", (low * 1.2).toFixed(3));
      setRoot(
        "--ambient",
        `rgba(${d.amb[0].toFixed(0)},${d.amb[1].toFixed(0)},${d.amb[2].toFixed(0)},${d.amb[3].toFixed(3)})`
      );
      // Đêm về: sao hiện (t≥0.72), đèn bàn thắp vũng sáng giữ chữ dễ đọc,
      // đèn đọc sách quanh cụm đồ vật bật dần từ t=0.62 (mạnh hơn để đồ vật
      // luôn "đang được chiếu sáng", không chìm vào nền tối)
      const stars = Math.max(0, Math.min(1, (st.day - 0.72) / 0.2));
      const pool = easeOut(Math.max(0, Math.min(1, (st.day - 0.64) / 0.22))) * 0.6;
      const lampOn = Math.max(0, Math.min(1, (st.day - 0.62) / 0.3));
      setRoot("--stars", stars.toFixed(3));
      setRoot("--pool", pool.toFixed(3));
      setRoot("--lampbook", (lampOn * 0.55).toFixed(3));
      // Độ phủ hơi nước: ngày 0.45 nhạt, đêm đèn bàn lên 1.0 (dùng cả cho shader + SVG fallback)
      const steamV = 0.45 + lampOn * 0.55;
      setRoot("--steam", steamV.toFixed(3));
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
      // Dòng headline xanh đậm ban ngày → đêm về gilt SÁNG hơn --blueline một
      // bậc để dòng "Thông minh" đứng một mình vẫn là điểm nhấn mạnh nhất
      setDoc("--blueline-strong", `rgb(${mixc(0, 245)},${mixc(135, 211)},${mixc(232, 152)})`);
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
        const tf = `translate(${sunX.toFixed(0)}px, ${sunY.toFixed(0)}px)`;
        if (sunRef.current.style.transform !== tf)
          sunRef.current.style.transform = tf;
      }
      const [sr, sg, sb] = d.sun;
      setRoot("--suncolor", `rgb(${sr},${sg},${sb})`);
      setRoot("--sunglow", `rgba(${sr},${sg},${sb},0.5)`);
      // Tia nắng rõ ban ngày, tan khi chiều xuống; đêm về hố trăng hiện ra
      const sunmodeV = Math.max(0, Math.min(1, 1.15 - st.day * 1.35));
      const moonnV = Math.max(0, Math.min(1, (st.day - 0.74) / 0.2));
      setRoot("--sunmode", sunmodeV.toFixed(3));
      setRoot("--moonn", moonnV.toFixed(3));

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

      // ----- Vẽ lớp WebGL (cách nhau ≥33ms ≈ 30fps: sao/tia sáng chuyển động
      // chậm nên mắt không phân biệt mà tiết kiệm hơn nửa GPU). reduced-motion chỉ vẽ 1 lần.
      if (reduced || now - lastGlDraw >= 33) {
        lastGlDraw = now;
        if (glReady && !glDead) {
          try {
            drawGL(now, d, stars, sunmodeV, sunX, sunY);
          } catch {
            // Mọi lỗi GL bất ngờ chỉ được phép RƠI VỀ fallback CSS — không bao giờ mất nền
            glDead = true;
            root.classList.remove("is-gl");
          }
        }
        // Hơi nước shader cùng nhịp 30fps — strength đồng bộ --steam; day = 1-lampOn
        // để shader tự chọn sắc hơi: ngày xám nổi trên nền sáng, đêm trắng nổi trên nền tối
        if (glSteamReady && !steamDead) {
          try {
            glSteam.render({
              t: now / 1000,
              strength: steamV,
              sway: st.mx * 0.25,
              day: 1 - lampOn,
            });
          } catch {
            steamDead = true;
            root.classList.remove("is-steamgl");
          }
        }
      }

      // Ngủ khi cảnh đứng yên và không còn lớp GL sống: sao/tia/hơi trong shader
      // chuyển động liên tục nên còn GL thì loop chạy mãi (nhẹ nhờ ghi DOM chặn
      // qua mkWriter + GL vẽ tối đa ~30fps); máy KHÔNG có WebGL thì mọi chuyển
      // động còn lại là keyframes CSS tự chạy trên compositor — rAF ngủ sâu tiết
      // kiệm pin, wheel/pointer/resize đánh thức lại qua wake()
      const settled =
        Math.abs(st.tDay - st.day) < SETTLE_EPS &&
        Math.abs(st.tmx - st.mx) < SETTLE_EPS &&
        Math.abs(st.tmy - st.my) < SETTLE_EPS &&
        Math.abs(st.tlampX - st.lampX) < 0.5 &&
        Math.abs(st.tlampY - st.lampY) < 0.5;
      const glAlive = (glReady && !glDead) || (glSteamReady && !steamDead);
      rafId = !reduced && (glAlive || !settled) ? requestAnimationFrame(frame) : 0;
    };

    // Đánh thức vòng lặp sau khi ngủ (wheel/pointermove/resize gọi vào đây)
    const wake = () => {
      if (!running || rafId) return;
      last = performance.now();
      rafId = requestAnimationFrame(frame);
    };

    // Hook chỉnh giờ bằng tay — chỉ có ở dev: __deskScene.setDay(0.62) = hoàng hôn.
    // Dùng cho chụp ảnh/tinh chỉnh cảnh, không tồn tại trong bản build.
    if (import.meta.env.DEV) {
      window.__deskScene = {
        setDay: (v) => {
          st.tDay = Math.max(0, Math.min(1, Number(v) || 0));
          st.vel = 0;
          wake();
        },
      };
    }

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
      delete window.__deskScene;
      root.classList.remove("is-gl");
      root.classList.remove("is-steamgl");
      if (glSky.ok) glSky.dispose();
      if (glSteam) glSteam.dispose();
      document.documentElement.style.removeProperty("--eyebrow");
      document.documentElement.style.removeProperty("--inkline");
      document.documentElement.style.removeProperty("--blueline");
      document.documentElement.style.removeProperty("--blueline-strong");
      document.documentElement.style.removeProperty("--nightshade");
    };
  }, [reduced]);

  // Bụi sáng / sao gieo hạt cố định lúc load module — không nhảy giữa các lần mount

  return (
    <div ref={rootRef} className="desk-scene absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* Lớp WebGL dưới cùng — bầu trời shader (đè .desk-sky khi .is-gl) */}
      <canvas ref={skyCanvasRef} className="desk-canvas" />
      {/* ===== Bầu trời đổi màu theo giờ trong ngày (fallback khi không WebGL) ===== */}
      <div className="desk-sky" />

      {/* Sao lấp lánh — chỉ hiện về đêm (--stars); ban ngày ẩn hẳn qua visibility */}
      <div ref={starWrapRef} className="desk-starwrap">
        {STARS.map(([x, y, s, dur, delay], i) => (
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
            {/* Dải sáng trang giấy — sheen mềm theo chiều cong trang */}
            <linearGradient id="deskSheenL" x1="0" y1="0" x2="1" y2="0.35">
              <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.38" />
              <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="deskSheenR" x1="1" y1="0" x2="0" y2="0.35">
              <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.32" />
              <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
            </linearGradient>
            {/* Hình trang giấy đặt MỘT lần — trang thật và dải sheen cùng dùng
                chung đường cong nên không bao giờ lệch nhau khi sửa d="…" */}
            <path id="deskPageShapeL" d="M160 48 C128 29 80 23 42 32 C34 34 30 39 30 47 L30 133 C30 141 34 146 43 145 C82 139 126 145 160 162 Z" />
            <path id="deskPageShapeR" d="M160 48 C192 29 240 23 278 32 C286 34 290 39 290 47 L290 133 C290 141 286 146 277 145 C238 139 194 145 160 162 Z" />
          </defs>
          {/* Bóng đổ — hướng/độ dài theo nắng, neo mép gần tại chân sách (xem .desk-shadow) */}
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
          {/* Ba tầng trang giấy phía dưới — hiệu ứng xòe trang */}
          <path
            d="M160 56 C128 34 78 28 40 37 C32 39 28 44 28 52 L28 143 C28 151 32 156 41 155 C81 149 124 155 160 172 Z"
            fill="#E7DDC7"
          />
          <path
            d="M160 56 C192 34 242 28 280 37 C288 39 292 44 292 52 L292 143 C292 151 288 156 279 155 C239 149 196 155 160 172 Z"
            fill="#E4D9C2"
          />
          <path
            d="M160 52 C126 32 76 26 38 35 C30 37 26 42 26 50 L26 139 C26 147 30 152 39 151 C79 145 124 151 160 168 Z"
            fill="#EFE8D6"
          />
          <path
            d="M160 52 C194 32 244 26 282 35 C290 37 294 42 294 50 L294 139 C294 147 290 152 281 151 C241 145 196 151 160 168 Z"
            fill="#ECE4D0"
          />
          {/* Khe hở từng tờ giấy dọc mép dưới — gợi chồng trang thật */}
          <path d="M34 146 C76 140 120 146 156 162" fill="none" stroke="rgba(139,122,92,0.30)" strokeWidth="1.2" />
          <path d="M286 146 C244 140 200 146 164 162" fill="none" stroke="rgba(139,122,92,0.26)" strokeWidth="1.2" />
          {/* Trang trái — cong lên từ gáy, gradient sáng dần ra ngoài */}
          <use href="#deskPageShapeL" fill="url(#deskPageL)" stroke="rgba(46,46,42,0.07)" strokeWidth="1.5" />
          {/* Trang phải */}
          <use href="#deskPageShapeR" fill="url(#deskPageR)" stroke="rgba(46,46,42,0.07)" strokeWidth="1.5" />
          {/* Bóng rãnh giữa hai trang */}
          <rect x="142" y="46" width="36" height="118" fill="url(#deskGutter)" />
          {/* Sheen trang giấy — phủ dưới dòng chữ để chữ vẫn đọc được */}
          <use href="#deskPageShapeL" fill="url(#deskSheenL)" />
          <use href="#deskPageShapeR" fill="url(#deskSheenR)" />
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
          {/* Bookmark xanh rút từ gáy dưới — điểm nhấn màu thương hiệu */}
          <path d="M153 154 L167 154 L169 186 L160 179 L151 186 Z" fill="#5B9BD5" />
          <path d="M153 154 L167 154" stroke="rgba(46,46,42,0.18)" strokeWidth="1.6" />
          <path d="M160 155 L160 178" stroke="rgba(255,255,255,0.35)" strokeWidth="1.1" />
          {/* Góc trang lay nhẹ */}
          <path className="desk-flutter" d="M278 32 C286 44 287 60 280 74 C272 62 270 46 274 33 Z" fill="#F3ECDB" />
        </svg>

      </div>

      {/* ===== Lớp giữa — parallax vừa ===== */}
      <div className="desk-layer" style={{ "--depth": 11 }}>
        {/* Hơi nước shader — canvas trong suốt đè vùng trên miệng cúp; đặt TRƯỚC
            svg cà phê để phần canvas chìm thấp xuống bị porcelain che, hơi nhú ra
            SAU vành cúp như thật. SVG .desk-steam chỉ còn là fallback WebGL */}
        <canvas ref={steamCanvasRef} className="desk-steam-gl" />

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
            {/* Nhoè mềm riêng cho khói — mù mờ như mây, không gân góc */}
            <filter id="deskMist" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="1.4" />
            </filter>
          </defs>

          {/* Bóng đổ xoay theo góc nắng — nằm dưới trọn bộ sứ */}
          <ellipse className="desk-shadow" cx="100" cy="157" rx="86" ry="30" fill="rgba(96,84,62,0.20)" filter="url(#deskSoft)" />

          {/* ===== Bộ sứ nhìn XIÊN TỪ TRÊN XUỐNG (thấy thành cúp) — MỌI đường
              tròn nằm ngang cùng tỷ lệ nén dọc ~0.34 nên đĩa/cúp/mặt cà phê
              thống nhất một phối cảnh. Tầng vẽ: đĩa → bóng chân cúp → quai
              (chui sau thân) → thân cúp → vành → thành trong → mặt cà phê ===== */}

          {/* Đĩa lót: đáy dày lệch 4px tạo thể tích, mặt đĩa, vành men sáng,
              lòng trũng hai tầng */}
          <ellipse cx="100" cy="154" rx="72" ry="26" fill="#E7DECB" />
          <ellipse cx="100" cy="150" rx="72" ry="26" fill="url(#deskSaucer)" stroke="rgba(46,46,42,0.06)" strokeWidth="1.5" />
          <ellipse cx="100" cy="150" rx="66" ry="23" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="1.2" />
          <ellipse cx="100" cy="149" rx="52" ry="17.5" fill="rgba(122,106,80,0.10)" />
          <ellipse cx="100" cy="148.5" rx="48" ry="15.5" fill="rgba(255,252,244,0.55)" />

          {/* Bóng chân cúp ép lên lòng đĩa */}
          <ellipse cx="100" cy="145" rx="40" ry="13" fill="rgba(96,84,62,0.14)" />

          {/* Quai cúp vẽ TRƯỚC thân để mối nối chui sau thành cúp */}
          <path d="M136 110 q23 4 18.5 22 q-5 16 -24.5 12.5" fill="none" stroke="url(#deskPorcelain)" strokeWidth="10" strokeLinecap="round" />
          <path d="M137 112 q21 4 17 20" fill="none" stroke="rgba(46,46,42,0.10)" strokeWidth="3" strokeLinecap="round" />
          <path d="M139 114 q12.5 4.5 10.5 15" fill="none" stroke="rgba(255,255,255,0.55)" strokeWidth="1.6" strokeLinecap="round" />

          {/* Thân cúp trụ: hai biên đứng + đáy/vành cong theo ellipse nén */}
          <path
            d="M62 96 L62 144 C79 156.5 121 156.5 138 144 L138 96 C121 108.5 79 108.5 62 96 Z"
            fill="url(#deskPorcelain)"
          />
          {/* Vát sáng men sứ vai trái + lõi tối vai phải — khối trụ có hướng sáng */}
          <path d="M66 103 C63.5 118 64.5 133 68 142" fill="none" stroke="rgba(255,255,255,0.85)" strokeWidth="3.5" strokeLinecap="round" />
          <path d="M133.5 104 C136 119 135 133 131.5 142" fill="none" stroke="rgba(96,84,62,0.16)" strokeWidth="4.5" strokeLinecap="round" />

          {/* Vành cúp: miệng ngoài → độ dày thành → thành trong tối dần */}
          <ellipse cx="100" cy="96" rx="44" ry="15" fill="url(#deskPorcelain)" stroke="rgba(46,46,42,0.07)" strokeWidth="2" />
          <ellipse cx="100" cy="96" rx="39" ry="12.8" fill="#EAE1CD" />
          <ellipse cx="100" cy="96.6" rx="37" ry="11.8" fill="#D5C9AF" />
          {/* Sáng mép trước vành — ánh sáng vuông góc mặt bàn */}
          <path d="M66 101 Q100 112 134 101" fill="none" stroke="rgba(255,255,255,0.45)" strokeWidth="1.6" strokeLinecap="round" />
          <circle cx="74" cy="89.5" r="1.8" fill="rgba(255,255,255,0.85)" />

          {/* Mặt cà phê elip + vành crema bám mép */}
          <ellipse cx="100" cy="97" rx="33" ry="11" fill="url(#deskCrema)" />
          <ellipse cx="100" cy="97" rx="33" ry="11" fill="none" stroke="rgba(222,188,138,0.42)" strokeWidth="2" />

          {/* Latte art trái tim + bọt crema: nhóm gốc toạ độ hình tròn cũ được
              NÉN DỌC 0.367 quanh tâm mặt phẳng mới — giữ nguyên nét vẽ mà khớp
              phối cảnh xiên của mặt cà phê */}
          <g transform="translate(100 97) scale(1 0.367) translate(-100 -131)">
            <path
              d="M100 146 C86.5 136 82.5 127 89.5 120.5 C94 116.5 99 119.5 100 125 C101 119.5 106 116.5 110.5 120.5 C117.5 127 113.5 136 100 146 Z"
              fill="#EFDFBF" opacity="0.92"
            />
            <path d="M93 123 Q100 118.5 107 123" fill="none" stroke="rgba(122,82,52,0.5)" strokeWidth="1.6" strokeLinecap="round" />
            <path d="M87 131 Q83 127 86.5 123.5" fill="none" stroke="rgba(239,223,191,0.55)" strokeWidth="1.3" strokeLinecap="round" />
            <path d="M113 131 Q117 127 113.5 123.5" fill="none" stroke="rgba(239,223,191,0.55)" strokeWidth="1.3" strokeLinecap="round" />
            <circle cx="76" cy="120" r="1.6" fill="rgba(222,188,138,0.55)" />
            <circle cx="125" cy="115" r="1.3" fill="rgba(222,188,138,0.5)" />
            <circle cx="126" cy="141" r="1.5" fill="rgba(222,188,138,0.5)" />
            <circle cx="72" cy="141" r="1.2" fill="rgba(222,188,138,0.45)" />
          </g>

          {/* Hai hạt cà phê rơi cạnh đĩa — chi tiết nhỏ cho cảnh sống */}
          <g transform="rotate(26 36 182)">
            <ellipse cx="36" cy="182" rx="10.5" ry="7" fill="#7A5539" />
            <path d="M28 181.5 Q36 177.5 44 181.5" fill="none" stroke="rgba(56,37,21,0.75)" strokeWidth="1.8" strokeLinecap="round" />
          </g>
          <g transform="rotate(-18 60 197)">
            <ellipse cx="60" cy="197" rx="9.5" ry="6.4" fill="#8A6242" />
            <path d="M52.8 196.6 Q60 193 67.2 196.6" fill="none" stroke="rgba(56,37,21,0.7)" strokeWidth="1.6" strokeLinecap="round" />
          </g>

          {/* Khói ba dải uốn lượn mềm mại — nét dày nhoè mù như mây, nhịp bay
              lệch pha (delay trong CSS). Gốc nhú ngay trên vành cúp mới (y≈90) */}
          <g className="desk-steam" filter="url(#deskMist)">
            <path d="M84 92 C76 80 94 74 84 58 C78 47 90 40 86 26" fill="none" stroke="rgba(122,106,88,0.42)" strokeWidth="5.5" strokeLinecap="round" />
            <path d="M103 88 C112 76 93 68 104 54 C111 43 98 36 103 20" fill="none" stroke="rgba(122,106,88,0.36)" strokeWidth="4.5" strokeLinecap="round" />
            <path d="M119 94 C128 84 113 76 122 62 C128 53 118 46 123 34" fill="none" stroke="rgba(122,106,88,0.30)" strokeWidth="4" strokeLinecap="round" />
          </g>
        </svg>

        {/* Bút chì — dưới phải */}
        <svg className="desk-svg desk-item-pencil" viewBox="0 0 300 54">
          <defs>
            {/* Khối 6 cạnh gợi bằng gradient 3 nấc mềm — nét gân cứng ở kích
                thước render nhỏ sẽ hoá thành nhiễu sọc làm bút nhìn bẩn */}
            <linearGradient id="deskPencilBody" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#F2C05C" />
              <stop offset="0.3" stopColor="#E2AC43" />
              <stop offset="0.62" stopColor="#D09833" />
              <stop offset="1" stopColor="#B57F28" />
            </linearGradient>
            <linearGradient id="deskPencilWood" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#F6EBCE" />
              <stop offset="0.55" stopColor="#EBDAB9" />
              <stop offset="1" stopColor="#D8C298" />
            </linearGradient>
            <linearGradient id="deskPencilMetal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#C9D3E0" />
              <stop offset="0.45" stopColor="#9FACBE" />
              <stop offset="1" stopColor="#7C8AA0" />
            </linearGradient>
            <linearGradient id="deskPencilEraser" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#E5AC90" />
              <stop offset="0.55" stopColor="#D29377" />
              <stop offset="1" stopColor="#B8785C" />
            </linearGradient>
          </defs>
          <ellipse className="desk-shadow" cx="152" cy="40" rx="130" ry="12" fill="rgba(96,84,62,0.20)" filter="url(#deskSoft)" />
          <g transform="rotate(-6 150 27)">
            {/* Thân sơn vàng — mép trái VUÔNG khớp kín mép gỗ (bo tròn ở tiếp giáp sẽ
                hở khe trời hình lưỡi liềm), đuôi chui thẳng dưới vòng kim; vệt sáng trên
                vai chạy liên tục tới vòng kim + vệt phản sáng ấm ở bụng dưới cho khối 6
                cạnh có trọng lượng */}
            <path d="M52 17 H252 V38 H52 Z" fill="url(#deskPencilBody)" />
            <rect x="55" y="19" width="193" height="3.6" rx="1.8" fill="rgba(255,255,255,0.38)" />
            <rect x="58" y="34.4" width="188" height="1.5" rx="0.75" fill="rgba(255,236,196,0.26)" />
            {/* Mũi gỗ: vạch sơn đứt nơi bắt đầu vót + hai nét chuyển mặt mềm +
                hai đường vân gỗ mảnh chạy theo chiều côn */}
            <polygon points="52,17 20,27.5 52,38" fill="url(#deskPencilWood)" />
            <path d="M52 17 L52 38" stroke="rgba(122,84,28,0.25)" strokeWidth="1.4" />
            <path d="M50.8 21.5 L30 26.2" stroke="rgba(122,84,28,0.14)" strokeWidth="0.9" strokeLinecap="round" />
            <path d="M50.8 33.5 L30 28.8" stroke="rgba(122,84,28,0.11)" strokeWidth="0.9" strokeLinecap="round" />
            <path d="M42 22.9 Q33 25.7 27.2 27" fill="none" stroke="rgba(122,84,28,0.13)" strokeWidth="0.7" strokeLinecap="round" />
            <path d="M42.5 32.2 Q34 29.8 27.4 28.3" fill="none" stroke="rgba(122,84,28,0.10)" strokeWidth="0.7" strokeLinecap="round" />
            {/* Than chì vút qua mép gỗ một nhịp + chấm specular nhỏ ở lưỡi cắt */}
            <polygon points="31.5,24.6 19.5,27.5 31.5,30.4" fill="#44443C" />
            <polygon points="27.5,25.8 21,27.5 27.5,29.2" fill="rgba(255,255,255,0.22)" />
            {/* Tẩy: mép trái phẳng chui dưới vòng kim, vòm phải bo tròn + hai lớp
                sáng (dải đứng giữa và đường cong bám theo vòm) */}
            <path
              d="M256 16 L268 16 C275.2 16 278.5 20.6 278.5 27.5 C278.5 34.4 275.2 39 268 39 L256 39 Z"
              fill="url(#deskPencilEraser)"
            />
            <rect x="265" y="18.5" width="3.2" height="17.5" rx="1.6" fill="rgba(255,255,255,0.32)" />
            <path d="M272.5 21 Q276 24.2 276 27.5 Q276 30.8 272.5 34" fill="none" stroke="rgba(255,255,255,0.26)" strokeWidth="1.3" strokeLinecap="round" />
            {/* Bóng hầm nơi tẩy chui ra khỏi vòng kim — hai bậc tối loãng dần */}
            <rect x="260" y="17.5" width="2.6" height="20" fill="rgba(112,52,38,0.30)" />
            <rect x="262.6" y="17.5" width="1.8" height="20" fill="rgba(112,52,38,0.14)" />
            {/* Vòng kim vẽ SAU tẩy để đè kín mép tẩy: gân se là từng CẶP rãnh tối +
                viền sáng (kim loại ép nổi), phủ thêm bóng đáy và cạnh phải bắt sáng
                nơi vòng kim ôm lấy tẩy */}
            <rect x="246" y="15" width="14" height="25" rx="2.5" fill="url(#deskPencilMetal)" />
            <rect x="247.5" y="36.6" width="11" height="2.6" rx="1.3" fill="rgba(47,58,74,0.26)" />
            <rect x="249.8" y="15.5" width="1.3" height="24" fill="rgba(47,58,74,0.20)" />
            <rect x="251.1" y="15.5" width="0.7" height="24" fill="rgba(255,255,255,0.22)" />
            <rect x="255.4" y="15.5" width="1.3" height="24" fill="rgba(47,58,74,0.20)" />
            <rect x="256.7" y="15.5" width="0.7" height="24" fill="rgba(255,255,255,0.22)" />
            <rect x="258.9" y="16.2" width="0.9" height="22.6" rx="0.45" fill="rgba(255,255,255,0.32)" />
            <rect x="246.8" y="16" width="12.4" height="2.6" rx="1.3" fill="rgba(255,255,255,0.36)" />
          </g>
        </svg>
      </div>

      {/* ===== Lớp gần — bụi sáng + đèn theo chuột ===== */}
      <div className="desk-layer" style={{ "--depth": 16 }}>
        <div className="desk-dustwrap" style={{ "--dust": 1 }}>
          {DUST.map(([x, y, s, dur, delay], i) => (
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
