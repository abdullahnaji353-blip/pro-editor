// Illustrations for collage art cards, drawn in greys (the halftone turns tone into ink dots).
// Each is (ctx, w, h) => void. Add your own: window.ART_ICONS.myThing = (x, w, h) => {...}.
(function () {
  const g = (x, x0, y0, x1, y1, stops) => { const gr = x.createLinearGradient(x0, y0, x1, y1); stops.forEach(([o, c]) => gr.addColorStop(o, c)); return gr; };
  const sky = (x, w, h, top = "#f4f4f4", bot = "#d0d0d0") => { x.fillStyle = g(x, 0, 0, 0, h, [[0, top], [1, bot]]); x.fillRect(0, 0, w, h); };
  const I = {};

  I.skyline = (x, w, h) => {              // Detroit riverfront: a cluster of round towers, river below
    sky(x, w, h, "#fafafa", "#bdbdbd");
    x.fillStyle = "#e9e9e9"; x.beginPath(); x.arc(w * 0.78, h * 0.25, h * 0.09, 0, 7); x.fill();
    const base = h * 0.72;
    const tower = (cx, tw, th, shade) => {
      x.fillStyle = g(x, cx - tw / 2, 0, cx + tw / 2, 0, [[0, "#555"], [0.45, shade], [1, "#2a2a2a"]]);
      x.fillRect(cx - tw / 2, base - th, tw, th);
      x.fillStyle = "rgba(255,255,255,.25)";
      for (let yy = base - th + 10; yy < base - 6; yy += 14) x.fillRect(cx - tw / 2 + 3, yy, tw - 6, 3);
    };
    const blocks = [[0.06, 0.12, 0.2], [0.17, 0.1, 0.32], [0.88, 0.12, 0.26], [0.97, 0.1, 0.18], [0.27, 0.07, 0.24], [0.71, 0.08, 0.3]];
    blocks.forEach(([cx, bw, bh]) => { x.fillStyle = "#6a6a6a"; x.fillRect(w * (cx - bw / 2), base - h * bh, w * bw, h * bh); });
    tower(w * 0.38, w * 0.09, h * 0.42, "#8a8a8a"); tower(w * 0.62, w * 0.09, h * 0.42, "#8a8a8a");
    tower(w * 0.44, w * 0.09, h * 0.36, "#7a7a7a"); tower(w * 0.56, w * 0.09, h * 0.36, "#7a7a7a");
    tower(w * 0.5, w * 0.12, h * 0.56, "#a5a5a5");
    x.fillStyle = g(x, 0, base, 0, h, [[0, "#4a4a4a"], [1, "#9a9a9a"]]); x.fillRect(0, base, w, h - base);
    x.fillStyle = "rgba(255,255,255,.35)";
    for (let i = 0; i < 14; i++) x.fillRect(w * (0.1 + (i * 0.37) % 0.8), base + 8 + (i % 5) * (h - base) / 6, w * 0.08, 2);
  };

  I.capitol = (x, w, h) => {             // a domed legislature building
    sky(x, w, h);
    const cx = w / 2, base = h * 0.86;
    x.fillStyle = "#8d8d8d"; x.fillRect(w * 0.06, base - h * 0.2, w * 0.88, h * 0.2);
    x.fillStyle = "#b5b5b5"; for (let i = 0; i < 16; i++) x.fillRect(w * 0.09 + i * w * 0.052, base - h * 0.18, w * 0.022, h * 0.16);
    x.fillStyle = "#707070"; x.fillRect(w * 0.3, base - h * 0.34, w * 0.4, h * 0.14);
    x.fillStyle = "#c4c4c4"; for (let i = 0; i < 8; i++) x.fillRect(w * 0.32 + i * w * 0.048, base - h * 0.32, w * 0.02, h * 0.11);
    x.fillStyle = g(x, cx - w * 0.17, 0, cx + w * 0.17, 0, [[0, "#3c3c3c"], [0.4, "#c8c8c8"], [1, "#2f2f2f"]]);
    x.beginPath(); x.ellipse(cx, base - h * 0.34, w * 0.17, h * 0.27, 0, Math.PI, 0); x.fill();
    x.fillStyle = "#666"; x.fillRect(cx - w * 0.19, base - h * 0.36, w * 0.38, h * 0.025);
    x.fillStyle = "#8a8a8a"; x.fillRect(cx - w * 0.03, base - h * 0.69, w * 0.06, h * 0.09);
    x.fillStyle = "#444"; x.beginPath(); x.arc(cx, base - h * 0.7, w * 0.02, 0, 7); x.fill();
    x.fillStyle = "#555"; x.fillRect(0, base, w, h - base);
  };

  I.spires = (x, w, h) => {              // college towers (Oxford)
    sky(x, w, h, "#fbfbfb", "#cfcfcf");
    const base = h * 0.9;
    const spire = (cx, sw, th, tip) => {
      x.fillStyle = g(x, cx - sw / 2, 0, cx + sw / 2, 0, [[0, "#3e3e3e"], [0.5, "#9c9c9c"], [1, "#333"]]);
      x.fillRect(cx - sw / 2, base - th, sw, th);
      x.beginPath(); x.moveTo(cx - sw / 2, base - th); x.lineTo(cx, base - th - tip); x.lineTo(cx + sw / 2, base - th); x.fill();
      x.fillStyle = "#222"; x.fillRect(cx - sw * 0.15, base - th * 0.7, sw * 0.3, th * 0.22);
    };
    x.fillStyle = "#777"; x.fillRect(0, base - h * 0.22, w, h * 0.22);
    x.fillStyle = "#555"; for (let i = 0; i < 12; i++) x.fillRect(i * w / 12 + 6, base - h * 0.17, w / 30, h * 0.08);
    spire(w * 0.22, w * 0.1, h * 0.38, h * 0.2); spire(w * 0.5, w * 0.13, h * 0.5, h * 0.3); spire(w * 0.78, w * 0.1, h * 0.34, h * 0.18);
    x.fillStyle = "#3a3a3a"; x.fillRect(0, base, w, h - base);
  };

  I.cap = (x, w, h) => {                 // graduation cap
    sky(x, w, h, "#f6f6f6", "#e0e0e0");
    const cx = w / 2, cy = h * 0.45;
    x.fillStyle = g(x, 0, cy, 0, cy + h * 0.3, [[0, "#3a3a3a"], [1, "#6a6a6a"]]);
    x.beginPath(); x.moveTo(cx - w * 0.22, cy + h * 0.05); x.lineTo(cx - w * 0.2, cy + h * 0.3); x.quadraticCurveTo(cx, cy + h * 0.38, cx + w * 0.2, cy + h * 0.3); x.lineTo(cx + w * 0.22, cy + h * 0.05); x.fill();
    x.fillStyle = g(x, cx - w * 0.4, 0, cx + w * 0.4, 0, [[0, "#222"], [0.5, "#5a5a5a"], [1, "#1a1a1a"]]);
    x.beginPath(); x.moveTo(cx, cy - h * 0.22); x.lineTo(cx + w * 0.42, cy); x.lineTo(cx, cy + h * 0.17); x.lineTo(cx - w * 0.42, cy); x.closePath(); x.fill();
    x.strokeStyle = "#888"; x.lineWidth = w * 0.012; x.beginPath(); x.moveTo(cx, cy); x.quadraticCurveTo(cx + w * 0.3, cy + h * 0.05, cx + w * 0.32, cy + h * 0.3); x.stroke();
    x.fillStyle = "#777"; x.fillRect(cx + w * 0.3, cy + h * 0.3, w * 0.04, h * 0.12);
  };

  I.stethoscope = (x, w, h) => {
    sky(x, w, h, "#f7f7f7", "#e2e2e2");
    x.strokeStyle = "#333"; x.lineCap = "round"; x.lineWidth = w * 0.04;
    x.beginPath(); x.moveTo(w * 0.3, h * 0.12); x.lineTo(w * 0.3, h * 0.4); x.quadraticCurveTo(w * 0.3, h * 0.62, w * 0.5, h * 0.62);
    x.quadraticCurveTo(w * 0.7, h * 0.62, w * 0.7, h * 0.4); x.lineTo(w * 0.7, h * 0.12); x.stroke();
    x.beginPath(); x.moveTo(w * 0.5, h * 0.62); x.quadraticCurveTo(w * 0.5, h * 0.85, w * 0.72, h * 0.8); x.stroke();
    x.fillStyle = g(x, w * 0.66, 0, w * 0.9, 0, [[0, "#2a2a2a"], [0.5, "#bdbdbd"], [1, "#333"]]);
    x.beginPath(); x.arc(w * 0.78, h * 0.76, w * 0.1, 0, 7); x.fill();
    x.fillStyle = "#555"; [0.3, 0.7].forEach((p) => { x.beginPath(); x.arc(w * p, h * 0.1, w * 0.035, 0, 7); x.fill(); });
  };

  I.books = (x, w, h) => {
    sky(x, w, h, "#f6f6f6", "#dedede");
    const bk = (y, bw, bh, shade, off) => {
      x.fillStyle = shade; x.fillRect(w / 2 - bw / 2 + off, y, bw, bh);
      x.fillStyle = "#f0f0f0"; x.fillRect(w / 2 + bw / 2 + off - 10, y + 4, 8, bh - 8);
      x.fillStyle = "rgba(255,255,255,.35)"; x.fillRect(w / 2 - bw / 2 + off + 14, y + bh * 0.35, bw * 0.4, 5);
    };
    bk(h * 0.72, w * 0.7, h * 0.13, "#3a3a3a", 0); bk(h * 0.59, w * 0.62, h * 0.13, "#7a7a7a", -12); bk(h * 0.46, w * 0.66, h * 0.13, "#2a2a2a", 10); bk(h * 0.33, w * 0.56, h * 0.13, "#9a9a9a", -6);
  };

  I.mic = (x, w, h) => {
    sky(x, w, h, "#f6f6f6", "#d8d8d8");
    const cx = w / 2;
    x.fillStyle = g(x, cx - w * 0.14, 0, cx + w * 0.14, 0, [[0, "#222"], [0.45, "#bbb"], [1, "#2a2a2a"]]);
    x.beginPath(); x.roundRect(cx - w * 0.13, h * 0.1, w * 0.26, h * 0.48, w * 0.13); x.fill();
    x.strokeStyle = "rgba(0,0,0,.35)"; x.lineWidth = 2; for (let i = 0; i < 9; i++) { x.beginPath(); x.moveTo(cx - w * 0.12, h * 0.16 + i * h * 0.035); x.lineTo(cx + w * 0.12, h * 0.16 + i * h * 0.035); x.stroke(); }
    x.strokeStyle = "#444"; x.lineWidth = w * 0.025; x.beginPath(); x.arc(cx, h * 0.42, w * 0.2, 0, Math.PI); x.stroke();
    x.fillStyle = "#444"; x.fillRect(cx - w * 0.015, h * 0.62, w * 0.03, h * 0.2); x.fillRect(cx - w * 0.16, h * 0.82, w * 0.32, h * 0.04);
  };

  I.glasses = (x, w, h) => {
    sky(x, w, h, "#f8f8f8", "#e4e4e4");
    x.strokeStyle = "#222"; x.lineWidth = w * 0.035;
    [0.3, 0.7].forEach((p) => {
      x.fillStyle = g(x, 0, h * 0.3, 0, h * 0.7, [[0, "#dcdcdc"], [1, "#a8a8a8"]]);
      x.beginPath(); x.roundRect(w * p - w * 0.17, h * 0.34, w * 0.34, h * 0.3, h * 0.12); x.fill(); x.stroke();
      x.fillStyle = "rgba(255,255,255,.7)"; x.fillRect(w * p - w * 0.12, h * 0.39, w * 0.05, h * 0.04);
    });
    x.beginPath(); x.moveTo(w * 0.47, h * 0.42); x.quadraticCurveTo(w * 0.5, h * 0.36, w * 0.53, h * 0.42); x.stroke();
    x.beginPath(); x.moveTo(w * 0.13, h * 0.42); x.lineTo(w * 0.04, h * 0.36); x.moveTo(w * 0.87, h * 0.42); x.lineTo(w * 0.96, h * 0.36); x.stroke();
  };

  I.pipe = (x, w, h) => {                // a school drinking fountain (lead testing)
    sky(x, w, h, "#f6f6f6", "#d6d6d6");
    x.fillStyle = "#c8c8c8"; x.fillRect(0, h * 0.2, w, h * 0.8);
    x.strokeStyle = "rgba(0,0,0,.12)"; x.lineWidth = 2;
    for (let yy = h * 0.2; yy < h; yy += 30) { x.beginPath(); x.moveTo(0, yy); x.lineTo(w, yy); x.stroke(); }
    x.fillStyle = g(x, w * 0.2, 0, w * 0.8, 0, [[0, "#555"], [0.5, "#e0e0e0"], [1, "#4a4a4a"]]);
    x.beginPath(); x.roundRect(w * 0.2, h * 0.45, w * 0.6, h * 0.16, 20); x.fill();
    x.fillStyle = "#333"; x.fillRect(w * 0.46, h * 0.38, w * 0.05, h * 0.09);
    x.strokeStyle = "#8a8a8a"; x.lineWidth = w * 0.02; x.beginPath(); x.moveTo(w * 0.5, h * 0.38); x.quadraticCurveTo(w * 0.58, h * 0.24, w * 0.66, h * 0.44); x.stroke();
    x.fillStyle = "#444"; x.fillRect(w * 0.44, h * 0.61, w * 0.12, h * 0.3);
  };

  I.factory = (x, w, h) => {
    sky(x, w, h, "#ededed", "#c2c2c2");
    const base = h * 0.82;
    for (let i = 0; i < 4; i++) {          // smoke
      x.fillStyle = `rgba(80,80,80,${0.25 - i * 0.04})`;
      x.beginPath(); x.arc(w * (0.32 + i * 0.09), h * (0.24 - i * 0.04), w * (0.07 + i * 0.03), 0, 7); x.fill();
    }
    x.fillStyle = g(x, 0, 0, w, 0, [[0, "#4a4a4a"], [0.5, "#7a7a7a"], [1, "#3a3a3a"]]);
    [[0.25, 0.06, 0.5], [0.4, 0.05, 0.42], [0.72, 0.07, 0.56]].forEach(([cx, cw, ch]) => x.fillRect(w * (cx - cw / 2), base - h * ch, w * cw, h * ch));
    x.fillStyle = "#3a3a3a"; x.fillRect(w * 0.05, base - h * 0.2, w * 0.9, h * 0.2);
    x.fillStyle = "#9a9a9a"; for (let i = 0; i < 8; i++) x.fillRect(w * (0.08 + i * 0.11), base - h * 0.15, w * 0.06, h * 0.06);
    x.fillStyle = "#555"; x.beginPath(); x.ellipse(w * 0.86, base - h * 0.24, w * 0.08, h * 0.08, 0, 0, 7); x.fill();
    x.fillStyle = "#222"; x.fillRect(0, base, w, h - base);
  };

  I.ballot = (x, w, h) => {
    sky(x, w, h, "#f4f4f4", "#dcdcdc");
    x.fillStyle = "#fbfbfb"; x.save(); x.translate(w * 0.5, h * 0.3); x.rotate(-0.12);
    x.fillRect(-w * 0.17, -h * 0.2, w * 0.34, h * 0.32);
    x.strokeStyle = "#555"; x.lineWidth = 3; x.strokeRect(-w * 0.17, -h * 0.2, w * 0.34, h * 0.32);
    x.fillStyle = "#444"; for (let i = 0; i < 3; i++) { x.strokeRect(-w * 0.13, -h * 0.13 + i * h * 0.08, w * 0.04, w * 0.04); x.fillRect(-w * 0.06, -h * 0.12 + i * h * 0.08, w * 0.16, 4); }
    x.lineWidth = 6; x.beginPath(); x.moveTo(-w * 0.13, -h * 0.12); x.lineTo(-w * 0.11, -h * 0.1); x.lineTo(-w * 0.08, -h * 0.15); x.stroke();
    x.restore();
    x.fillStyle = g(x, w * 0.15, 0, w * 0.85, 0, [[0, "#3a3a3a"], [0.5, "#8a8a8a"], [1, "#2e2e2e"]]);
    x.fillRect(w * 0.15, h * 0.42, w * 0.7, h * 0.48);
    x.fillStyle = "#1a1a1a"; x.fillRect(w * 0.32, h * 0.46, w * 0.36, h * 0.03);
    x.fillStyle = "#cfcfcf"; x.font = `bold ${h * 0.1}px Anton, sans-serif`; x.textAlign = "center"; x.fillText("VOTE", w / 2, h * 0.72);
  };

  I.money = (x, w, h) => {
    sky(x, w, h, "#f4f4f4", "#dcdcdc");
    for (let i = 0; i < 6; i++) {
      const y = h * 0.78 - i * h * 0.07;
      x.fillStyle = i % 2 ? "#8a8a8a" : "#a9a9a9"; x.fillRect(w * 0.14 + (i % 3) * 6, y, w * 0.72, h * 0.07);
      x.strokeStyle = "#555"; x.lineWidth = 2; x.strokeRect(w * 0.14 + (i % 3) * 6, y, w * 0.72, h * 0.07);
    }
    x.save(); x.translate(w / 2, h * 0.28); x.rotate(-0.08);
    x.fillStyle = "#c2c2c2"; x.fillRect(-w * 0.36, -h * 0.13, w * 0.72, h * 0.26);
    x.strokeStyle = "#444"; x.lineWidth = 4; x.strokeRect(-w * 0.33, -h * 0.1, w * 0.66, h * 0.2);
    x.fillStyle = "#3a3a3a"; x.beginPath(); x.arc(0, 0, h * 0.075, 0, 7); x.fill();
    x.fillStyle = "#e6e6e6"; x.font = `bold ${h * 0.1}px Anton, sans-serif`; x.textAlign = "center"; x.textBaseline = "middle"; x.fillText("$", 0, 2);
    x.restore();
  };

  I.jersey = (x, w, h) => {              // a team shirt with a captain's C
    sky(x, w, h, "#f5f5f5", "#dadada");
    x.fillStyle = g(x, 0, h * 0.15, 0, h * 0.9, [[0, "#5a5a5a"], [1, "#2e2e2e"]]);
    x.beginPath(); x.moveTo(w * 0.32, h * 0.12); x.lineTo(w * 0.1, h * 0.26); x.lineTo(w * 0.18, h * 0.42); x.lineTo(w * 0.28, h * 0.37);
    x.lineTo(w * 0.28, h * 0.9); x.lineTo(w * 0.72, h * 0.9); x.lineTo(w * 0.72, h * 0.37); x.lineTo(w * 0.82, h * 0.42); x.lineTo(w * 0.9, h * 0.26);
    x.lineTo(w * 0.68, h * 0.12); x.quadraticCurveTo(w * 0.5, h * 0.24, w * 0.32, h * 0.12); x.fill();
    x.fillStyle = "#e8e8e8"; x.font = `bold ${h * 0.32}px Anton, sans-serif`; x.textAlign = "center"; x.fillText("C", w / 2, h * 0.68);
  };

  I.health = (x, w, h) => {              // a public health building with a cross
    sky(x, w, h);
    const base = h * 0.88;
    x.fillStyle = g(x, 0, 0, w, 0, [[0, "#5e5e5e"], [0.5, "#a0a0a0"], [1, "#555"]]); x.fillRect(w * 0.12, base - h * 0.56, w * 0.76, h * 0.56);
    x.fillStyle = "#3a3a3a"; for (let r = 0; r < 4; r++) for (let c = 0; c < 6; c++) x.fillRect(w * (0.16 + c * 0.12), base - h * (0.5 - r * 0.1), w * 0.08, h * 0.06);
    x.fillStyle = "#2a2a2a"; x.fillRect(w * 0.43, base - h * 0.14, w * 0.14, h * 0.14);
    x.fillStyle = "#f0f0f0"; x.fillRect(w * 0.44, base - h * 0.8, w * 0.12, h * 0.22); x.fillRect(w * 0.39, base - h * 0.75, w * 0.22, h * 0.12);
    x.fillStyle = "#444"; x.fillRect(0, base, w, h - base);
  };

  I.podium = (x, w, h) => {              // a stage with a microphone and lights
    sky(x, w, h, "#3a3a3a", "#1e1e1e");
    for (let i = 0; i < 5; i++) { x.fillStyle = "rgba(255,255,255,.12)"; x.beginPath(); x.moveTo(w * (0.1 + i * 0.2), 0); x.lineTo(w * (0.25 + i * 0.12), h); x.lineTo(w * (0.35 + i * 0.12), h); x.closePath(); x.fill(); }
    x.fillStyle = g(x, w * 0.3, 0, w * 0.7, 0, [[0, "#666"], [0.5, "#d8d8d8"], [1, "#5a5a5a"]]);
    x.beginPath(); x.moveTo(w * 0.28, h * 0.5); x.lineTo(w * 0.72, h * 0.5); x.lineTo(w * 0.66, h * 0.95); x.lineTo(w * 0.34, h * 0.95); x.fill();
    x.fillStyle = "#888"; x.fillRect(w * 0.26, h * 0.46, w * 0.48, h * 0.05);
    x.strokeStyle = "#bbb"; x.lineWidth = w * 0.012; x.beginPath(); x.moveTo(w * 0.5, h * 0.46); x.quadraticCurveTo(w * 0.5, h * 0.36, w * 0.56, h * 0.32); x.stroke();
    x.fillStyle = "#ddd"; x.beginPath(); x.ellipse(w * 0.57, h * 0.31, w * 0.025, h * 0.03, 0.5, 0, 7); x.fill();
    x.fillStyle = "#cfcfcf"; x.beginPath(); x.arc(w * 0.5, h * 0.72, w * 0.07, 0, 7); x.fill();
  };

  I.michigan = (x, w, h) => {            // the Lower Peninsula, shaded
    sky(x, w, h, "#eeeeee", "#cfcfcf");
    const MI = [[-86.8, 41.76], [-84.8, 41.7], [-83.45, 41.73], [-83.1, 42.05], [-82.5, 42.6], [-82.4, 43.0], [-82.6, 43.6], [-82.9, 44.05], [-83.3, 43.95], [-83.9, 43.6], [-83.55, 44.3], [-83.3, 44.9], [-83.4, 45.3], [-84.0, 45.6], [-84.7, 45.8], [-85.4, 45.3], [-85.6, 45.15], [-86.0, 44.9], [-86.25, 44.5], [-86.45, 44.0], [-86.5, 43.5], [-86.25, 42.9], [-86.4, 42.3]];
    const k = Math.min(w / 5.2, h / (4.6 * 1.38)), ox = w / 2 - 2.4 * k, oy = h * 0.04;
    x.beginPath(); MI.forEach(([lo, la], i) => (i ? x.lineTo : x.moveTo).call(x, ox + (lo + 87) * k, oy + (46.1 - la) * k * 1.38)); x.closePath();
    x.fillStyle = g(x, 0, 0, w, h, [[0, "#9a9a9a"], [1, "#5a5a5a"]]); x.fill();
    x.strokeStyle = "#2a2a2a"; x.lineWidth = 3; x.stroke();
    I.__mi = { k, ox, oy };
  };

  I.box = (x, w, h) => { sky(x, w, h); x.fillStyle = "#777"; x.fillRect(w * 0.25, h * 0.25, w * 0.5, h * 0.5); };

  window.ART_ICONS = I;
})();
