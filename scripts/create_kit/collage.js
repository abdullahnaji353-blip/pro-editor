// pro-editor /create: documentary collage (the Vox / video-essay look).
// Physical paper on a board: torn cards with thickness and shadow, tape, typewriter strips, rubber
// stamps, pins joined by red string, marker circles and underlines, halftone illustrations.
// Graphics move in stepped 12 fps like stop-motion; things drop in back to front and then hold.
//
//   const C = K.collage;                       // available at the top of a scene script
//   C.board("paper");                          // paper | cork | dark
//   C.card("c1", {x: 90, y: 300, w: 560, rot: -3, html: "<h2>...</h2>"});
//   C.art("a1", "capitol", {x: 600, y: 260, w: 380, rot: 4});   // halftone illustration card
//   C.strip("s1", "BORN OCT. 31, 1984", {x: 120, y: 900, rot: -2});
//   C.stamp("st", "ELECTED", {x: 640, y: 980, rot: -12});
//   C.tape("t1", {x: 300, y: 290, rot: -20});
//   C.pin("p1", 300, 600); C.pin("p2", 800, 1100); C.string("r1", "p1", "p2");
//   C.circle("m1", {x: 560, y: 400, w: 380, h: 160});  C.underline("u1", {x, y, w});
//   window.render = (t, d) => { C.in("c1", t, 0.2); C.in("a1", t, 0.6); C.draw("r1", t, 1.4); ... };
//
// C.in(id, t, start, from) drops a piece in (from: "drop" | "left" | "right" | "up" | "slap").
// C.settled(id) shows it already in place (for pieces carried over from an earlier beat).
(function () {
  const K = window.K;
  const FPS = 12;
  const step = (t) => Math.floor(t * FPS + 1e-6) / FPS;
  const rnd = (seed) => { let s = (seed * 9301 + 49297) % 233280 || 7; return () => (s = (s * 9301 + 49297) % 233280) / 233280; };
  const hash = (str) => { let h = 7; for (const c of String(str)) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h % 100000; };
  const pieces = {};

  function layer() {
    let L = document.getElementById("k-collage");
    if (!L) {
      L = document.createElement("div"); L.id = "k-collage";
      L.style.cssText = "position:absolute;inset:0;overflow:hidden";
      document.body.prepend(L);
    }
    return L;
  }

  // ---------------------------------------------------------------- textures
  function paperTexture(w, h, base, seed, o = {}) {
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    const x = c.getContext("2d"), r = rnd(seed);
    x.fillStyle = base; x.fillRect(0, 0, w, h);
    const img = x.getImageData(0, 0, w, h), d = img.data;
    for (let i = 0; i < d.length; i += 4) {            // fine grain
      const n = (r() - 0.5) * (o.grain ?? 14);
      d[i] += n; d[i + 1] += n; d[i + 2] += n * 0.9;
    }
    x.putImageData(img, 0, 0);
    for (let i = 0; i < (o.fibers ?? 160); i++) {      // paper fibres
      x.strokeStyle = `rgba(90,70,40,${0.03 + r() * 0.05})`; x.lineWidth = 0.6 + r();
      const sx = r() * w, sy = r() * h, a = r() * 6.28, L = 8 + r() * 26;
      x.beginPath(); x.moveTo(sx, sy); x.quadraticCurveTo(sx + Math.cos(a) * L * 0.5 + r() * 6, sy + Math.sin(a) * L * 0.5, sx + Math.cos(a) * L, sy + Math.sin(a) * L); x.stroke();
    }
    for (let i = 0; i < (o.stains ?? 5); i++) {         // tea stains / foxing
      const g = x.createRadialGradient(r() * w, r() * h, 0, r() * w, r() * h, 60 + r() * 220);
      g.addColorStop(0, `rgba(140,100,50,${0.05 + r() * 0.06})`); g.addColorStop(1, "rgba(140,100,50,0)");
      x.fillStyle = g; x.fillRect(0, 0, w, h);
    }
    return c.toDataURL("image/jpeg", 0.9);
  }

  function board(kind = "paper") {
    const L = layer();
    const base = { paper: "#e9dfcb", cork: "#b98d5c", dark: "#24211d" }[kind] || kind;
    L.style.background = `url(${paperTexture(1080, 1920, base, 11, kind === "cork" ? { grain: 40, fibers: 1400, stains: 2 } : kind === "dark" ? { grain: 10, fibers: 80, stains: 0 } : {})})`;
    L.style.backgroundSize = "cover";
    L.dataset.kind = kind;
    // a soft light from the top left, like a desk lamp
    const v = document.createElement("div");
    v.style.cssText = "position:absolute;inset:0;pointer-events:none;z-index:900;background:radial-gradient(ellipse at 30% 20%,rgba(255,250,235,.10),rgba(0,0,0,0) 45%,rgba(40,25,10,.28) 100%)";
    L.appendChild(v);
  }

  // jagged outline for torn paper (only the edges you name are torn)
  function tornClip(seed, edges = "tb", amt = 1.6) {
    const r = rnd(seed), pts = [], n = 22;
    const j = (on) => (on ? r() * amt : 0);
    for (let i = 0; i <= n; i++) pts.push(`${(i / n) * 100}% ${j(edges.includes("t"))}%`);
    for (let i = 0; i <= n; i++) pts.push(`${100 - j(edges.includes("r")) * 0.6}% ${(i / n) * 100}%`);
    for (let i = n; i >= 0; i--) pts.push(`${(i / n) * 100}% ${100 - j(edges.includes("b"))}%`);
    for (let i = n; i >= 0; i--) pts.push(`${j(edges.includes("l")) * 0.6}% ${(i / n) * 100}%`);
    return `polygon(${pts.join(",")})`;
  }

  // ---------------------------------------------------------------- pieces
  function stage() {
    const L = layer();
    let P = document.getElementById("k-pieces");
    if (!P) { P = document.createElement("div"); P.id = "k-pieces"; P.style.cssText = "position:absolute;left:0;top:0;width:1080px;height:1920px;transform-origin:0 0"; L.appendChild(P); }
    return P;
  }

  function place(id, html, o, z) {
    const L = stage();
    const wrap = document.createElement("div");
    wrap.id = id;
    wrap.style.cssText = `position:absolute;left:${o.x}px;top:${o.y}px;${o.w ? `width:${o.w}px;` : ""}z-index:${o.z ?? z};` +
      `filter:drop-shadow(0 ${o.lift ?? 6}px ${o.blur ?? 5}px rgba(30,20,10,.38)) drop-shadow(0 1px 0 rgba(30,20,10,.25));opacity:0;transform-origin:50% 40%`;
    wrap.innerHTML = html;
    L.appendChild(wrap);
    pieces[id] = { el: wrap, rot: o.rot || 0, kind: o.kind || "paper", svg: false };
    return wrap;
  }
  let Z = 10;

  function card(id, o) {
    const tex = paperTexture(300, 300, o.color || "#f6f0e2", hash(id), { grain: 10, fibers: 30, stains: 1 });
    const clip = o.torn === false ? "none" : tornClip(hash(id), o.edges || "tb", o.tear ?? 1.4);
    return place(id, `<div style="background:url(${tex});background-size:300px;clip-path:${clip};padding:${o.pad ?? "44px 48px"};color:#1c1a17;${o.style || ""}">${o.html || ""}</div>`, { ...o, kind: "paper" }, Z++);
  }

  function strip(id, text, o) {          // typewriter label on a slip of paper
    const tex = paperTexture(200, 60, o.color || "#fbf7ee", hash(id) + 3, { grain: 8, fibers: 6, stains: 0 });
    const clip = tornClip(hash(id), "lr", 4);
    return place(id, `<div style="background:url(${tex});clip-path:${clip};padding:14px 30px;font:400 ${o.size || 44}px/1.15 'Special Elite',monospace;color:#1c1a17;white-space:nowrap;letter-spacing:.02em">${text}</div>`,
      { ...o, kind: "type", lift: 3, blur: 3 }, Z++);
  }

  function stamp(id, text, o) {          // distressed rubber stamp
    const col = o.color || "#b3261e";
    const nid = `n${hash(id)}`;
    const svg = `<svg width="${o.w || 420}" height="${(o.w || 420) * 0.36}" viewBox="0 0 420 150" style="overflow:visible">
      <defs><filter id="${nid}"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="${hash(id) % 50}"/>
      <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.2 1.35"/><feComposite in="SourceGraphic" operator="in"/></filter></defs>
      <g filter="url(#${nid})"><rect x="8" y="8" width="404" height="134" rx="10" fill="none" stroke="${col}" stroke-width="10"/>
      <rect x="22" y="22" width="376" height="106" rx="6" fill="none" stroke="${col}" stroke-width="3"/>
      <text x="210" y="${o.sub ? 82 : 96}" text-anchor="middle" font-family="Anton,Impact,sans-serif" font-size="${o.size || 72}" letter-spacing="4" fill="${col}">${text}</text>
      ${o.sub ? `<text x="210" y="118" text-anchor="middle" font-family="Special Elite,monospace" font-size="24" fill="${col}">${o.sub}</text>` : ""}</g></svg>`;
    const el = place(id, svg, { ...o, kind: "stamp", lift: 0, blur: 0, z: o.z ?? 800 }, Z++);
    el.style.filter = "none"; el.style.mixBlendMode = "multiply";
    return el;
  }

  function tape(id, o) {
    const w = o.w || 190;
    return place(id, `<div style="width:${w}px;height:54px;background:linear-gradient(180deg,rgba(236,226,196,.82),rgba(222,208,170,.78));clip-path:${tornClip(hash(id), "lr", 6)};box-shadow:inset 0 0 12px rgba(255,255,255,.4)"></div>`,
      { ...o, kind: "tape", lift: 1, blur: 1, z: o.z ?? 700 }, Z++);
  }

  const pins = {};
  function pin(id, x, y, o = {}) {
    pins[id] = [x, y];
    return place(id, `<svg width="34" height="34" viewBox="0 0 34 34"><circle cx="17" cy="17" r="11" fill="${o.color || "#c0281f"}"/><circle cx="13" cy="13" r="4" fill="rgba(255,255,255,.55)"/></svg>`,
      { x: x - 17, y: y - 17, kind: "pin", lift: 4, blur: 2, z: o.z ?? 850 }, Z++);
  }

  function svgLayer(id, inner, z) {
    const el = place(id, `<svg width="1080" height="1920" viewBox="0 0 1080 1920" style="overflow:visible">${inner}</svg>`, { x: 0, y: 0, lift: 2, blur: 1.5, z }, Z++);
    el.style.pointerEvents = "none"; pieces[id].svg = true;
    return el;
  }

  function string(id, a, b, o = {}) {    // red string between two pins, with a little sag
    const [x1, y1] = pins[a], [x2, y2] = pins[b];
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 + (o.sag ?? 40);
    return svgLayer(id, `<path d="M${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}" fill="none" stroke="${o.color || "#c0281f"}" stroke-width="5" stroke-linecap="round"/>`, o.z ?? 840);
  }

  function rough(seed, pts, wob) {       // hand-drawn path through points
    const r = rnd(seed);
    return "M" + pts.map(([x, y]) => `${(x + (r() - 0.5) * wob).toFixed(1)} ${(y + (r() - 0.5) * wob).toFixed(1)}`).join(" L");
  }
  function circle(id, o) {               // marker loop around something
    const pts = [], n = 40, r = rnd(hash(id));
    for (let i = 0; i <= n + 6; i++) {
      const a = -1.9 + (i / n) * 6.5, k = 1 + (r() - 0.5) * 0.06;
      pts.push([o.x + o.w / 2 + Math.cos(a) * o.w / 2 * k, o.y + o.h / 2 + Math.sin(a) * o.h / 2 * k]);
    }
    return svgLayer(id, `<path d="${rough(hash(id), pts, 3)}" fill="none" stroke="${o.color || "#c0281f"}" stroke-width="${o.lw || 9}" stroke-linecap="round" stroke-linejoin="round" opacity=".9"/>`, 860);
  }
  function underline(id, o) {
    const pts = [[o.x, o.y], [o.x + o.w * 0.5, o.y + 4], [o.x + o.w, o.y - 3]];
    return svgLayer(id, `<path d="${rough(hash(id), pts, 4)}" fill="none" stroke="${o.color || "#c0281f"}" stroke-width="${o.lw || 10}" stroke-linecap="round" opacity=".9"/>`, 860);
  }
  function arrow(id, o) {
    const { x1, y1, x2, y2 } = o, a = Math.atan2(y2 - y1, x2 - x1), h = 34;
    const p = `M${x1} ${y1} Q ${(x1 + x2) / 2 + (o.bend ?? 60)} ${(y1 + y2) / 2 - (o.bend ?? 60)} ${x2} ${y2} M${x2} ${y2} L${x2 - h * Math.cos(a - 0.5)} ${y2 - h * Math.sin(a - 0.5)} M${x2} ${y2} L${x2 - h * Math.cos(a + 0.5)} ${y2 - h * Math.sin(a + 0.5)}`;
    return svgLayer(id, `<path d="${p}" fill="none" stroke="${o.color || "#c0281f"}" stroke-width="${o.lw || 9}" stroke-linecap="round" stroke-linejoin="round"/>`, 860);
  }

  // text straight on the board (marker notes, big numbers), no paper behind it
  function text(id, html, o) {
    const el = place(id, `<div style="${o.style || ""}">${html}</div>`, { ...o, kind: o.kind || "marker", lift: 0, blur: 0, z: o.z ?? 870 }, Z++);
    el.style.filter = "none";
    return el;
  }

  // halftone illustration on a torn card: art is drawn in greys, then printed as ink dots
  function art(id, name, o) {
    const W = o.w || 420, H = o.h || Math.round(W * (o.ratio || 0.85)), R = 2;   // printed at 2x so it stays crisp when scaled
    const src = document.createElement("canvas"); src.width = W * R; src.height = H * R;
    const sx = src.getContext("2d");
    sx.fillStyle = "#fff"; sx.fillRect(0, 0, W * R, H * R);
    (window.ART_ICONS[name] || window.ART_ICONS.box)(sx, W * R, H * R);
    const img = sx.getImageData(0, 0, W * R, H * R).data;
    const out = document.createElement("canvas"); out.width = W * R; out.height = H * R;
    const x = out.getContext("2d");
    const step = (o.dot || 7) * R, ink = o.ink || "#1c1a17", WW = W * R, HH = H * R;
    x.fillStyle = ink;
    for (let yy = step / 2; yy < HH; yy += step) for (let xx = ((yy / step) % 2 ? step / 2 : 0) + step / 2; xx < WW; xx += step) {
      const i = (Math.floor(yy) * WW + Math.floor(xx)) * 4, lum = (img[i] * 0.3 + img[i + 1] * 0.59 + img[i + 2] * 0.11) / 255;
      const rad = (1 - lum) * step * 0.62;
      if (rad > 0.6) { x.beginPath(); x.arc(xx, yy, rad, 0, 6.283); x.fill(); }
    }
    if (o.tint) {
      x.globalCompositeOperation = "multiply"; x.fillStyle = o.tint; x.globalAlpha = 0.85;
      x.fillRect(0, 0, WW, HH); x.globalAlpha = 1; x.globalCompositeOperation = "source-over";
    }
    const label = o.label ? `<div style="font:400 30px 'Special Elite',monospace;margin-top:14px;color:#1c1a17">${o.label}</div>` : "";
    return card(id, { ...o, w: W + 56, pad: "28px 28px 24px", html: `<img src="${out.toDataURL()}" style="display:block;width:${W}px;height:${H}px;mix-blend-mode:multiply">${label}` });
  }

  // ---------------------------------------------------------------- motion (stepped)
  function show(id, k, from, rot) {
    const p = pieces[id]; if (!p) return;
    const el = p.el;
    if (k <= 0) { el.style.opacity = 0; return; }
    el.style.opacity = 1;
    const e = K.ease.back(Math.min(1, k)), r = rot ?? p.rot;
    let tx = 0, ty = 0, sc = 1, rr = r;
    if (from === "left") tx = (1 - e) * -900;
    else if (from === "right") tx = (1 - e) * 900;
    else if (from === "up") ty = (1 - e) * -700;
    else if (from === "bottom") ty = (1 - e) * 900;
    else if (from === "slap") { sc = 1 + (1 - e) * 0.5; }
    else { sc = 1 + (1 - Math.min(1, k)) * 0.14; ty = (1 - e) * -40; rr = r + (1 - e) * (r >= 0 ? 7 : -7); }
    el.style.transform = `translate(${tx}px, ${ty}px) rotate(${rr}deg) scale(${sc})`;
    el.style.filter = el.style.filter && p.kind !== "stamp" ? el.style.filter.replace(/drop-shadow\(0 [\d.]+px/, `drop-shadow(0 ${6 + (1 - Math.min(1, k)) * 22}px`) : el.style.filter;
  }

  const SND = { paper: "paper", type: "type", stamp: "stamp", tape: "tape", pin: "click", marker: "marker" };
  function into(id, t, start, from = "drop", dur = 0.42) {
    ensureFit();
    const p = pieces[id]; if (!p) return;
    const ts = step(t);
    show(id, (ts - start) / dur, from);
    K.sfx(SND[p.kind] || "paper", start + (p.kind === "stamp" ? dur * 0.5 : 0.08), id);
  }
  function settled(id) { ensureFit(); show(id, 1); }
  function draw(id, t, start, dur = 0.6) {   // strings, circles, underlines, arrows draw on
    const p = pieces[id]; if (!p) return;
    const path = p.el.querySelector("path");
    if (!path.dataset.len) { path.dataset.len = path.getTotalLength(); path.style.strokeDasharray = path.dataset.len; }
    const k = Math.max(0, Math.min(1, (step(t) - start) / dur));
    p.el.style.opacity = k > 0 ? 1 : 0;
    path.style.strokeDashoffset = path.dataset.len * (1 - k);
    K.sfx("marker", start + 0.05, id);
  }
  // Scale and centre the whole board (every piece, shown or not yet) into an area of the frame,
  // so sparse boards fill the screen and nothing hangs off the edge. Same result on every beat of
  // a board, because it measures the finished arrangement.
  function bbox(ids) {
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (const id of ids || Object.keys(pieces)) {
      const p = pieces[id]; if (!p || p.svg) continue;
      const el = p.el, w = el.offsetWidth, h = el.offsetHeight, l = el.offsetLeft, t = el.offsetTop;
      const r = Math.abs(p.rot) * Math.PI / 180, ew = w * Math.cos(r) + h * Math.sin(r), eh = h * Math.cos(r) + w * Math.sin(r);
      const cx = l + w / 2, cy = t + h / 2;
      x0 = Math.min(x0, cx - ew / 2); x1 = Math.max(x1, cx + ew / 2); y0 = Math.min(y0, cy - eh / 2); y1 = Math.max(y1, cy + eh / 2);
    }
    return x1 > x0 ? [x0, y0, x1, y1] : null;
  }
  function framing(ids, a) {
    const b = bbox(ids); if (!b) return [1, 0, 0];
    const [x0, y0, x1, y1] = b;
    const k = Math.min(a.max, a.w / (x1 - x0), a.h / (y1 - y0));
    return [k, a.x + (a.w - (x1 - x0) * k) / 2 - x0 * k, a.y + (a.h - (y1 - y0) * k) / 2 - y0 * k];
  }
  const AREA = { x: 50, y: 200, w: 980, h: 1060, max: 1.7 };
  // Fit the whole board (every piece, shown or not yet) into the frame. Measured when first drawn,
  // after fonts load, so it matches what's on screen.
  function fit(area = {}) { fitArea = { ...AREA, ...area }; }
  let fitArea = null;
  // Camera that travels the board: from framing one set of pieces to another (Johnny Harris style).
  // from/to are lists of piece ids; null = the whole board.
  function frame(from, to, t, dur = 0.8, area = {}) {
    const a = { ...AREA, ...area };
    const A = framing(from, a), B = framing(to, a);
    const k = K.ease.inOut(Math.max(0, Math.min(1, t / dur)));
    const m = (i) => A[i] + (B[i] - A[i]) * k;
    stage().style.transform = `translate(${m(1)}px, ${m(2)}px) scale(${m(0)})`;
  }
  function ensureFit() {
    if (!fitArea) return;
    const [k, tx, ty] = framing(null, fitArea);
    stage().style.transform = `translate(${tx}px, ${ty}px) scale(${k})`;
    fitArea = null;
  }

  // after assembly: a slow push so the board stays alive (smooth, not stepped)
  function camera(t, d, o = {}) {
    const L = layer(), k = t / d;
    const z = (o.from ?? 1.0) + ((o.to ?? 1.04) - (o.from ?? 1.0)) * k;
    L.style.transformOrigin = `${o.ox ?? 50}% ${o.oy ?? 40}%`;
    L.style.transform = `scale(${z}) translate(${(o.x ?? 0) * k}px, ${(o.y ?? 0) * k}px)`;
  }

  K.collage = { fit, frame, bbox, board, text, card, strip, stamp, tape, pin, string, circle, underline, arrow, art, in: into, settled, draw, camera, step, paperTexture };
})();
