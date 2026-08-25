/* ===== Nền WebGL thuần cho cảnh bàn học (không thư viện) =====
   Một canvas độc lập, DeskScene nuôi dữ liệu mỗi khung hình (vẽ cách nhau
   ≥33ms ≈ 30fps — sao nhấp nháy chậm nên mắt không phân biệt):

   • createSkyGL — bầu trời shader toàn màn THAY gradient .desk-sky:
     gradient theo mốc DAY_STOPS + tán xạ rộng quanh mặt trời/trăng (bổ sung
     cho halo DOM hẹp) + sao đêm lấp lánh lệch pha, có chớp nhiễu xạ và bị
     quầng thiên thể rửa đúng cảm giác khí quyển.

   • createSteamGL — hơi nước trên miệng cúp cà phê: canvas nhỏ trong suốt đè
     vùng khói, RAYMARCH THỂ TÍCH — mỗi pixel bắn tia xuyên khối mật độ fbm3D
     cuộn lên liên tục, bóng tự đổ theo đèn bàn cho hạt hơi có khối 3D; thay
     nhóm path .desk-steam (SVG vẫn giữ làm fallback khi thiếu WebGL).

   Mỗi lớp tạo bằng createXxxGL(canvas, onLost) — trả { ok, resize, render,
   dispose }: thiếu WebGL hay compile lỗi → ok:false, DeskScene bỏ qua và giữ
   nguyên fallback CSS/SVG; onLost chạy khi mất context giữa chừng để DeskScene
   rơi về fallback ngay lập tức. */

// ----- GLSL: bầu trời -----
const VERT_QUAD = `
attribute vec2 a_pos;
void main() {
  gl_Position = vec4(a_pos, 0.0, 1.0);
}
`;

const FRAG_SKY = `
precision highp float;

uniform vec2  u_res;     // kích thước CSS — toàn bộ toán shader làm việc ở px CSS
uniform float u_px;      // render px / CSS px (canvas vẽ nửa phân giải)
uniform float u_t;
uniform vec3  u_top;
uniform vec3  u_bot;
uniform vec4  u_amb;
uniform vec2  u_sun;     // px thiết bị, trục Y đã lật (gốc dưới-trái)
uniform vec3  u_suncol;
uniform float u_sunmode; // 1 ban ngày -> 0 đêm
uniform float u_stars;   // 0 ngày -> 1 đêm sâu
uniform float u_sunset;  // đỉnh quanh t~0.62 hoàng hôn

float hash21(vec2 p) {
  p = fract(p * vec2(233.34, 851.73));
  p += dot(p, p + 23.45);
  return fract(p.x * p.y);
}

void main() {
  // Quy về px CSS: hằng số tán xạ/sao tính theo px CSS nên phải chuyển trước,
  // nếu không canvas nửa phân giải làm mọi bán kính phình gấp đôi → trời bị rửa
  vec2 frag = gl_FragCoord.xy / u_px;
  vec2 uv = frag / u_res; // y: 0 dưới -> 1 đỉnh

  // Gradient trời — giữ đúng nhịp .desk-sky: màu chân trời chốt ở 78%
  float t = clamp((1.0 - uv.y) / 0.78, 0.0, 1.0);
  vec3 col = mix(u_top, u_bot, t);

  // ---- Tán xạ quanh thiên thể: rộng và mềm, bổ sung cho halo DOM hẹp ----
  // Ban ngày giữ MỎNG (trời xanh + halo DOM đã đủ, đậm quá mặt trời bị chói);
  // hoàng hôn/đêm đền hệ số riêng nên hai khung đó vẫn giữ độ ấm như cũ
  float dSun = length(frag - u_sun);
  float glow = exp(-dSun * dSun / 115200.0) * 0.18 + exp(-dSun / 480.0) * 0.09;
  col += u_suncol * glow * (0.40 + 0.35 * u_sunmode + u_stars * 0.45 + u_sunset * 0.60);

  // ---- Sao đêm trên lưới ô: lấp lánh lệch pha + chớp nhiễu xạ, mây che được ----
  float cell = max(u_res.y, 720.0) / 27.0;
  vec2 sc = frag / cell;
  vec2 cid = floor(sc);
  vec2 cf = fract(sc);
  float rnd = hash21(cid + 3.1);
  vec2 spos = vec2(hash21(cid + 11.7), hash21(cid + 27.9)) * 0.72 + 0.14;
  float sd = length(cf - spos);
  float mag = step(0.86, rnd); // ~14% ô có sao
  float tw = 0.5 + 0.5 * sin(u_t * (1.1 + rnd * 2.6) + rnd * 43.0);
  float core = 1.0 - smoothstep(0.0, 0.085, sd);
  float halo = exp(-sd * sd * 46.0) * 0.55;
  float flare = (exp(-abs(cf.x - spos.x) * 26.0) + exp(-abs(cf.y - spos.y) * 26.0))
              * exp(-sd * 5.5) * 0.30;
  float star = mag * (core * 1.25 + halo + flare) * (0.35 + 0.65 * tw);
  star *= 1.0 / (1.0 + glow * 6.0);    // quầng thiên thể rửa sao gần nó
  star *= smoothstep(0.42, 0.58, uv.y); // chỉ nửa trời trên (như bộ STARS cũ)
  col += vec3(1.0, 0.965, 0.88) * star * u_stars;

  // Phủ ánh sáng theo giờ — trùng lớp --ambient cũ của .desk-sky
  col = mix(col, u_amb.rgb, clamp(u_amb.a, 0.0, 1.0));

  // Dither chống băng màu trên gradient mềm
  col += (hash21(frag + fract(u_t) * 61.7) - 0.5) * 0.007;

  gl_FragColor = vec4(col, 1.0);
}
`;

// ----- Dùng chung -----
function buildProgram(gl, vsSrc, fsSrc) {
  const compile = (type, src) => {
    const sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(sh);
      gl.deleteShader(sh);
      throw new Error(`Shader compile failed: ${log}`);
    }
    return sh;
  };
  const prog = gl.createProgram();
  gl.attachShader(prog, compile(gl.VERTEX_SHADER, vsSrc));
  gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, fsSrc));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    throw new Error(`Program link failed: ${gl.getProgramInfoLog(prog)}`);
  }
  return prog;
}

const NO_GL = { ok: false };

// Tam giác lớn phủ kín màn (3 đỉnh, nhanh hơn 2 tam giác của quad)
const FS_TRI = new Float32Array([-1, -1, 3, -1, -1, 3]);

/* Khung chung của mọi lớp GL: context + program + tam giác phủ màn + bảng
   uniform location. Trả null khi thiếu WebGL hoặc context đã mất (caller quy
   thành NO_GL); compile/link lỗi thì ném lên trên. onLost (nếu có) chạy đúng
   lúc sự kiện webglcontextlost — preventDefault giữ quyền khôi phục context. */
function initLayer(canvas, fragSrc, uniformNames, alpha, onLost) {
  const gl = canvas.getContext("webgl", {
    alpha,
    depth: false,
    stencil: false,
    antialias: false,
    powerPreference: "low-power",
  });
  if (!gl) return null;
  if (gl.isContextLost()) return null; // context cũ từ lần mount trước — dùng fallback

  const prog = buildProgram(gl, VERT_QUAD, fragSrc);
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, FS_TRI, gl.STATIC_DRAW);
  const aPos = gl.getAttribLocation(prog, "a_pos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

  const U = {};
  for (const n of uniformNames) U[n] = gl.getUniformLocation(prog, n);
  gl.useProgram(prog);

  // Gắn listener SAU khi dựng xong toàn bộ — compile/link lỗi thì chưa từng có
  // gì phải dọn; dispose sẽ gỡ nó cùng program/buffer
  let onContextLost = null;
  if (onLost) {
    onContextLost = (e) => {
      e.preventDefault();
      onLost();
    };
    canvas.addEventListener("webglcontextlost", onContextLost);
  }

  return {
    gl,
    prog,
    buf,
    U,
    dropLost: () => canvas.removeEventListener("webglcontextlost", onContextLost),
  };
}

/* KHÔNG gọi loseContext khi dọn dẹp: React StrictMode (dev) mount→unmount→mount
   trên CÙNG canvas, getContext trả về context cũ đã mất mà không báo lỗi —
   class .is-gl vẫn được thêm nhưng render không bao giờ chạy → mất nền.
   Dispose chỉ gỡ listener + xoá program/buffer; context sống sót qua lần mount lại. */
function disposeGL(L) {
  L.dropLost();
  if (L.gl.isContextLost()) return;
  L.gl.deleteBuffer(L.buf);
  L.gl.deleteProgram(L.prog);
}

/** Bầu trời shader toàn màn — canvas opaque, không blend. */
export function createSkyGL(canvas, onLost) {
  try {
    const L = initLayer(
      canvas,
      FRAG_SKY,
      ["u_res", "u_px", "u_t", "u_top", "u_bot", "u_amb", "u_sun",
        "u_suncol", "u_sunmode", "u_stars", "u_sunset"],
      false,
      onLost,
    );
    if (!L) return NO_GL;
    const { gl, U } = L;

    let W = 1;
    let H = 1;
    let cssW = 1;
    let cssH = 1;
    let scale = 1;
    return {
      ok: true,
      resize(w, h, dpr) {
        // NỬA PHÂN GIẢI: gradient/tán xạ/sao là nội dung tần số thấp, render
        // 0.5×dpr giảm 75% chi phí fill; CSS phóng lên gần như không mất chất.
        scale = Math.max(0.5, dpr * 0.5);
        cssW = Math.max(1, w);
        cssH = Math.max(1, h);
        W = Math.max(1, Math.round(cssW * scale));
        H = Math.max(1, Math.round(cssH * scale));
        canvas.width = W;
        canvas.height = H;
        gl.viewport(0, 0, W, H);
      },
      render(u) {
        if (gl.isContextLost()) return;
        // Shader làm việc thuần px CSS (u_px để tự quy gl_FragCoord) — bán kính
        // tán xạ, cỡ ô sao… đúng thiết kế bất kể canvas vẽ ở phân giải nào
        gl.uniform2f(U.u_res, cssW, cssH);
        gl.uniform1f(U.u_px, scale);
        gl.uniform1f(U.u_t, u.t);
        gl.uniform3f(U.u_top, u.top[0] / 255, u.top[1] / 255, u.top[2] / 255);
        gl.uniform3f(U.u_bot, u.bot[0] / 255, u.bot[1] / 255, u.bot[2] / 255);
        gl.uniform4f(U.u_amb, u.amb[0] / 255, u.amb[1] / 255, u.amb[2] / 255, u.amb[3]);
        // Mặt trời đã ở px CSS (y tính từ đỉnh) — chỉ lật trục Y sang gốc dưới-trái
        gl.uniform2f(U.u_sun, u.sun[0], cssH - u.sun[1]);
        gl.uniform3f(U.u_suncol, u.suncol[0] / 255, u.suncol[1] / 255, u.suncol[2] / 255);
        gl.uniform1f(U.u_sunmode, u.sunmode);
        gl.uniform1f(U.u_stars, u.stars);
        gl.uniform1f(U.u_sunset, u.sunset);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      },
      dispose() {
        disposeGL(L);
      },
    };
  } catch (err) {
    if (import.meta.env?.DEV) console.warn("[DeskScene] Trời GL fallback:", err);
    return NO_GL;
  }
}

// ----- GLSL: hơi nước cà phê — RAYMARCH THỂ TÍCH -----
// Mỗi pixel bắn một tia đi SÂU VÀO khối hơi nước, tích lũy mật độ dọc đường —
// hạt hơi có lõi đặc/vành mỏng, mặt đón sáng/bụng đổ bóng: cảm giác KHỐI 3D
// thay vì texture nhiễu phẳng. Khối hơi = trường mật độ fbm3D cuộn lên liên tục.
const FRAG_STEAM = `
precision highp float;

uniform vec2  u_res;
uniform float u_t;
uniform float u_strength; // 0.35 ban ngày -> 1.0 đêm đèn bàn (đồng bộ --steam)
uniform float u_sway;     // nghiêng cột hơi theo con trỏ, rất nhẹ
uniform float u_day;      // 1 ban ngày -> 0 đêm: quyết định sắc hơi (xám/trắng)

// ---- Noise giá trị 3D + fbm 3 tầng (nội suy tam tuyến 8 góc) ----
float hash31(vec3 p) {
  p = fract(p * 0.1031);
  p += dot(p, p.zyx + 31.32);
  return fract((p.x + p.y) * p.z);
}

float vnoise3(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  vec3 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(hash31(i), hash31(i + vec3(1.0, 0.0, 0.0)), u.x),
        mix(hash31(i + vec3(0.0, 1.0, 0.0)), hash31(i + vec3(1.0, 1.0, 0.0)), u.x), u.y),
    mix(mix(hash31(i + vec3(0.0, 0.0, 1.0)), hash31(i + vec3(1.0, 0.0, 1.0)), u.x),
        mix(hash31(i + vec3(0.0, 1.0, 1.0)), hash31(i + vec3(1.0, 1.0, 1.0)), u.x), u.y),
    u.z
  );
}

float fbm3(vec3 p) {
  float s = 0.0;
  float a = 0.5;
  for (int i = 0; i < 3; i++) {
    s += a * vnoise3(p);
    p = p * 2.15 + vec3(11.3, 7.7, 5.1);
    a *= 0.52;
  }
  return s;
}

// Mật độ hơi tại một điểm KHỐI LƯỢNG (khối: x,z ∈ ±1.2, y ∈ 0..2.6 — y=0 sát miệng cúp)
float density(vec3 p) {
  // Cột hơi: gốc chụm sau vành cúp, nở loãng dần khi lên cao — bán kính luôn
  // nhỏ hơn nhiều so với biên khối (±1.2) để mật độ về ~0 trước mép vẽ
  float grow = clamp(p.y / 2.6, 0.0, 1.0);
  float rad = mix(0.18, 0.72, pow(grow, 0.8));
  float column = exp(-dot(p.xz, p.xz) / (rad * rad));

  // Trường nhiễu CUỘN LÊN chậm rãi, warp dịu — hơi nước lười bồng bềnh chứ
  // không cuộn dữ như khói; tần số thấp để tạo BỒNG tròn lớn, không gợn li ti
  vec3 q = p - vec3(0.0, u_t * 0.42, 0.0);
  q.xz += 0.26 * vec2(
    vnoise3(q * 0.9 + vec3(0.0, u_t * 0.08, 0.0)) - 0.5,
    vnoise3(q * 0.9 + vec3(4.7, u_t * 0.06, 2.3)) - 0.5
  );
  float n = fbm3(q * vec3(1.15, 0.75, 1.15));

  float d = smoothstep(0.33, 0.75, n) * column;

  // Tan hai đầu: nhú từ sau vành cúp, ngọn tan HẾT trước đỉnh khối
  d *= smoothstep(0.02, 0.35, p.y) * (1.0 - smoothstep(1.45, 2.35, p.y));
  return d;
}

void main() {
  // Camera trực giao nhìn thẳng: mỗi pixel là một tia xuyên khối hơi
  vec2 frag = gl_FragCoord.xy / u_res;            // 0..1, y=0 đáy canvas
  vec3 ro = vec3((frag.x - 0.5) * 2.4, frag.y * 2.6, 1.3);
  ro.x -= u_sway * frag.y * frag.y * 0.35;        // "gật" nhẹ theo hướng nhìn
  vec3 rd = normalize(vec3(0.0, -0.16, -1.0));    // hơi chúi khi đi vào chiều sâu

  const int STEPS = 26;
  float dt = 3.4 / float(STEPS);
  // Jitter điểm xuất phát từng pixel chống vân cọc của bước dài
  float t0 = dt * hash31(vec3(gl_FragCoord.xy, fract(u_t) * 17.0));

  vec3 L = normalize(vec3(-0.45, 0.72, -0.35));   // đèn bàn trên-trái-trước

  vec3 acc = vec3(0.0);
  float T = 1.0;                                  // độ truyền sáng còn lại
  for (int i = 0; i < STEPS; i++) {
    if (T < 0.04) break;                          // đặc kín rồi — dừng sớm
    vec3 pos = ro + rd * (t0 + dt * float(i));
    float d = density(pos);
    if (d > 0.008) {
      // Bóng tự đổ: lấy thêm mật độ lệch về phía đèn — hơi dày chặn sáng, bụng tối
      float sh = density(pos + L * 0.42);
      float lit = clamp(1.0 - sh * 1.6, 0.30, 1.0);
      // Sắc hơi nước THEO GIỜ: ban ngày nền giấy trắng ngời, hơi TRẮNG sẽ tan
      // hình — pha XÁM đậm để tách khỏi nền; đêm về nền tối, hơi quay lại
      // TRẮNG sáng rực dưới đèn bàn (u_day: 1 ngày -> 0 đêm)
      vec3 litCol = mix(vec3(1.0, 0.99, 0.95), vec3(0.60, 0.59, 0.57), u_day);
      vec3 shadCol = mix(vec3(0.72, 0.68, 0.62), vec3(0.42, 0.41, 0.40), u_day);
      vec3 alb = mix(shadCol, litCol, lit);
      float a = 1.0 - exp(-d * dt * 6.5);
      acc += T * a * alb;
      T *= 1.0 - a;
    }
  }

  // Mặt nạ mép canvas: hơi tan dần về 0 trước biên theo cả 4 hướng — dù mật độ
  // hay tia march thế nào cũng KHÔNG bao giờ chạm cạnh, hết cảnh "khung hình dán"
  float edge = smoothstep(0.0, 0.16, frag.x) * smoothstep(1.0, 0.84, frag.x)
             * smoothstep(0.0, 0.10, frag.y) * smoothstep(1.0, 0.88, frag.y);

  // Xuất premultiplied (canvas mặc định): acc đã nhân sẵn T*a — nhân strength và
  // edge ĐỒNG THỜI lên cả màu lẫn alpha để fade không lệch sắc
  float alpha = (1.0 - T) * u_strength * edge;
  gl_FragColor = vec4(acc * u_strength * edge, alpha);
}
`;

/** Hơi nước trên miệng cúp — canvas nhỏ trong suốt, browser tự composite qua alpha. */
export function createSteamGL(canvas, onLost) {
  try {
    const L = initLayer(
      canvas,
      FRAG_STEAM,
      ["u_res", "u_t", "u_strength", "u_sway", "u_day"],
      true,
      onLost,
    );
    if (!L) return NO_GL;
    const { gl, U } = L;
    gl.clearColor(0, 0, 0, 0);

    let W = 1;
    let H = 1;
    return {
      ok: true,
      resize(w, h, dpr) {
        // Raymarch thể tích đắt hơn shader phẳng — vẽ 0.75×dpr (trần 1.5): nội dung
        // mù mờ nên upscale hầu như không mất chất, tiết kiệm ~2/3 chi phí fill.
        // Resize theo spec tự xoá drawing buffer nên không cần clear riêng ở đây
        const s = Math.min(Math.max((dpr || 1) * 0.75, 0.75), 1.5);
        W = Math.max(1, Math.round(Math.max(1, w) * s));
        H = Math.max(1, Math.round(Math.max(1, h) * s));
        canvas.width = W;
        canvas.height = H;
        gl.viewport(0, 0, W, H);
      },
      render(u) {
        if (gl.isContextLost()) return;
        gl.uniform2f(U.u_res, W, H);
        gl.uniform1f(U.u_t, u.t);
        gl.uniform1f(U.u_strength, u.strength);
        gl.uniform1f(U.u_sway, u.sway ?? 0);
        gl.uniform1f(U.u_day, u.day ?? 0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      },
      dispose() {
        disposeGL(L);
      },
    };
  } catch (err) {
    if (import.meta.env?.DEV) console.warn("[DeskScene] Hơi nước GL fallback:", err);
    return NO_GL;
  }
}
