// pro-editor /create art styles (2D). Draw a subject once with semantic colours; the style decides
// how it looks. ART.styles: pixel, chalk, glow, comic, flat, line.
//
//   const A = ART.canvas("#c", "comic");      // a full-frame <canvas id="c"> in the scene
//   A.begin(t);                                // background for this frame
//   A.shape(path2d, "hero");                   // fill + outline the style's way ("hero", "dark", "ground"...)
//   A.line(path2d, "ink", 0.6);                // a stroke, drawn on to 60%
//   A.text("WHOOSH!", 540, 300, 120, "pop");   // lettering in the style's face
//   A.end(t);                                  // grain, halftone, scanlines, pixel upscale...
//
// Everything is deterministic in t (seeded noise), so frames render the same every time.
(function () {
  const rnd = (seed) => { let s = seed >>> 0 || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); };

  const STYLES = {
    pixel: {
      scale: 8, font: "Press Start 2P",
      pal: { sky: "#2b1055", sky2: "#d53a9d", ground: "#1d1a3a", hero: "#ff3355", dark: "#120d24", light: "#ffe66d",
             accent: "#3df2ff", ink: "#120d24", text: "#ffe66d", glass: "#3df2ff", wheel: "#120d24" },
    },
    chalk: {
      font: "Cabin Sketch",
      pal: { sky: "#25392f", sky2: "#2c4437", ground: "#2c4437", hero: "#f4f1e6", dark: "#f4f1e6", light: "#fff6a8",
             accent: "#ffd27a", ink: "#f4f1e6", text: "#f4f1e6", glass: "#a8e6ff", wheel: "#f4f1e6" },
    },
    glow: {
      font: "Inter Tight",
      pal: { sky: "#020306", sky2: "#06080f", ground: "#0b0e16", hero: "#ffd27a", dark: "#ffd27a", light: "#fff3d6",
             accent: "#ffb347", ink: "#ffd27a", text: "#fff3d6", glass: "#fff3d6", wheel: "#ffd27a" },
    },
    comic: {
      font: "Bangers",
      pal: { sky: "#3a8dde", sky2: "#7fc4ff", ground: "#ffd23f", hero: "#e8322b", dark: "#1a1a1a", light: "#ffffff",
             accent: "#ffd23f", ink: "#111111", text: "#ffffff", glass: "#bfe7ff", wheel: "#1a1a1a" },
    },
    flat: {
      font: "Inter Tight",
      pal: { sky: "#9fd6ff", sky2: "#d9f0ff", ground: "#7bc96f", hero: "#e8423f", dark: "#2d3047", light: "#ffffff",
             accent: "#ffb703", ink: "#2d3047", text: "#2d3047", glass: "#cfeeff", wheel: "#2d3047" },
    },
    line: {
      font: "Instrument Serif",
      pal: { sky: "#000000", sky2: "#050505", ground: "#000000", hero: "#ffffff", dark: "#ffffff", light: "#ffffff",
             accent: "#ffffff", ink: "#ffffff", text: "#f2f2f2", glass: "#ffffff", wheel: "#ffffff" },
    },
  };

  function canvas(sel, style, o = {}) {
    const cv = typeof sel === "string" ? document.querySelector(sel) : sel;
    const W = cv.width, H = cv.height, S = STYLES[style];
    if (!S) throw new Error(`unknown art style ${style}: ${Object.keys(STYLES).join(", ")}`);
    const pal = { ...S.pal, ...(o.palette || {}) };
    // pixel art draws small and is scaled up with hard edges at the end
    const low = style === "pixel" ? Object.assign(document.createElement("canvas"), { width: W / S.scale, height: H / S.scale }) : null;
    const out = cv.getContext("2d");
    const c = low ? low.getContext("2d") : out;
    const k = low ? 1 / S.scale : 1;
    let frameT = 0, R = rnd(1);
    const A = { style, pal, c, W, H, k };

    A.begin = (t) => {
      frameT = t; R = rnd(Math.floor(t * 12) + 7);
      c.setTransform(k, 0, 0, k, 0, 0);
      c.globalAlpha = 1; c.shadowBlur = 0; c.filter = "none";
      const g = c.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, pal.sky); g.addColorStop(1, pal.sky2);
      c.fillStyle = style === "flat" || style === "comic" || style === "pixel" ? g : pal.sky;
      c.fillRect(0, 0, W, H);
      if (style === "chalk") {               // old chalk smudges on the board
        const r = rnd(3);
        for (let i = 0; i < 26; i++) {
          c.fillStyle = `rgba(244,241,230,${0.02 + r() * 0.035})`;
          c.beginPath(); c.ellipse(r() * W, r() * H, 120 + r() * 260, 30 + r() * 70, r() * 3, 0, 7); c.fill();
        }
      }
      if (style === "line") {                // a still night sky
        const r = rnd(9);
        for (let i = 0; i < 140; i++) {
          const tw = 0.4 + 0.6 * Math.abs(Math.sin(t * (0.6 + r() * 2) + i));
          c.fillStyle = `rgba(255,255,255,${(0.2 + r() * 0.6) * tw})`;
          c.fillRect(r() * W, r() * H * 0.75, 2.4, 2.4);
        }
      }
      if (style === "glow") {                // soft floor light
        const rg = c.createRadialGradient(W / 2, H * 0.62, 10, W / 2, H * 0.62, W * 0.7);
        rg.addColorStop(0, "rgba(255,190,90,.16)"); rg.addColorStop(1, "rgba(0,0,0,0)");
        c.fillStyle = rg; c.fillRect(0, 0, W, H);
      }
    };

    // wobble a path for hand-drawn styles: redraw it through jittered points
    const jitterPath = (p2, amt, seed) => {
      if (!p2.__pts) return p2;
      const r = rnd(seed), out = new Path2D();
      p2.__pts.forEach(([x, y], i) => (i ? out.lineTo : out.moveTo).call(out, x + (r() - 0.5) * amt, y + (r() - 0.5) * amt));
      if (p2.__closed) out.closePath();
      return out;
    };

    A.shape = (p2, role = "hero", o2 = {}) => {
      const fill = pal[role] || role;
      c.save();
      if (style === "flat") {
        c.fillStyle = fill; c.fill(p2);
      } else if (style === "comic") {
        c.fillStyle = fill; c.fill(p2);
        c.lineWidth = o2.lw || 12; c.strokeStyle = pal.ink; c.lineJoin = "round"; c.stroke(p2);
      } else if (style === "pixel") {
        c.fillStyle = fill; c.fill(p2); c.lineWidth = 8; c.strokeStyle = pal.ink; c.stroke(p2);
      } else if (style === "chalk") {
        // chalk: no solid fill, hatching and two wobbly passes of the outline
        c.globalAlpha = 0.16; c.fillStyle = fill; c.fill(p2); c.globalAlpha = 1;
        c.strokeStyle = fill; c.lineCap = "round"; c.lineJoin = "round";
        for (let pass = 0; pass < 2; pass++) {
          c.lineWidth = 6 - pass * 2; c.globalAlpha = 0.85 - pass * 0.3;
          c.setLineDash([22 + pass * 7, 3 + pass * 2]);
          c.stroke(jitterPath(p2, 7, 11 + pass * 5 + Math.floor(frameT * 4)));
        }
      } else if (style === "glow") {
        c.strokeStyle = fill; c.lineWidth = 4; c.shadowColor = fill; c.shadowBlur = 28;
        c.stroke(p2); c.shadowBlur = 10; c.stroke(p2);
      } else if (style === "line") {
        c.strokeStyle = fill; c.lineWidth = 2.6; c.stroke(p2);
      }
      c.restore();
    };

    A.line = (p2, role = "ink", amount = 1, lw = 6) => {
      c.save();
      const col = pal[role] || role;
      c.strokeStyle = col; c.lineCap = "round"; c.lineJoin = "round";
      c.lineWidth = { line: 2.6, glow: 4, chalk: 5, comic: lw + 4, pixel: 8 }[style] || lw;
      if (style === "glow") { c.shadowColor = col; c.shadowBlur = 26; }
      if (amount < 1) { c.setLineDash([4000 * amount, 4000]); }
      c.stroke(style === "chalk" ? jitterPath(p2, 5, 21) : p2);
      c.restore();
    };

    A.text = (str, x, y, size, role = "text", o2 = {}) => {
      c.save();
      c.font = `${o2.weight || (style === "flat" ? 800 : 400)} ${size}px "${o2.font || S.font}"`;
      c.textAlign = o2.align || "center"; c.textBaseline = "middle";
      const col = pal[role] || role;
      if (style === "comic" || o2.outline) {
        c.lineWidth = size * 0.16; c.strokeStyle = pal.ink; c.lineJoin = "round"; c.strokeText(str, x, y);
      }
      if (style === "glow") { c.shadowColor = col; c.shadowBlur = 24; }
      if (style === "chalk") { c.globalAlpha = 0.92; }
      c.fillStyle = col; c.fillText(str, x, y);
      c.restore();
    };

    // a comic "burst" behind a sound word
    A.burst = (x, y, r, role = "accent", spikes = 14) => {
      const p = new Path2D(), rr = rnd(5);
      for (let i = 0; i < spikes * 2; i++) {
        const a = (i / (spikes * 2)) * Math.PI * 2, R2 = i % 2 ? r * 0.62 : r * (0.9 + rr() * 0.25);
        (i ? p.lineTo : p.moveTo).call(p, x + Math.cos(a) * R2, y + Math.sin(a) * R2);
      }
      p.closePath(); A.shape(p, role);
    };

    A.end = (t) => {
      c.setTransform(1, 0, 0, 1, 0, 0);
      if (style === "comic") {                // halftone dots over the light areas
        out.save(); out.globalAlpha = 0.12; out.fillStyle = "#000";
        for (let y = 0; y < H; y += 18) for (let x = (y / 18) % 2 ? 9 : 0; x < W; x += 18) { out.beginPath(); out.arc(x, y, 3.2, 0, 7); out.fill(); }
        out.restore();
      }
      if (low) {
        out.imageSmoothingEnabled = false;
        out.drawImage(low, 0, 0, W, H);
        out.fillStyle = "rgba(0,0,0,.18)";      // scanlines
        for (let y = 0; y < H; y += S.scale) out.fillRect(0, y, W, 2);
      }
      if (style === "chalk") {                // chalk dust: random light specks
        const r = rnd(Math.floor(t * 8) + 3);
        out.fillStyle = "rgba(244,241,230,.08)";
        for (let i = 0; i < 900; i++) out.fillRect(r() * W, r() * H, 2, 2);
      }
    };
    return A;
  }

  // Path2D that remembers its points, so hand-drawn styles can wobble it
  function poly(pts, closed = true) {
    const p = new Path2D();
    pts.forEach(([x, y], i) => (i ? p.lineTo(x, y) : p.moveTo(x, y)));
    if (closed) p.closePath();
    p.__pts = pts; p.__closed = closed;
    return p;
  }
  function circle(x, y, r, n = 28) {
    const pts = [];
    for (let i = 0; i < n; i++) pts.push([x + Math.cos((i / n) * 6.283) * r, y + Math.sin((i / n) * 6.283) * r]);
    return poly(pts);
  }
  function rect(x, y, w, h, r = 0) {
    if (!r) return poly([[x, y], [x + w, y], [x + w, y + h], [x, y + h]]);
    const pts = [], seg = 6, corner = (cx, cy, a0) => { for (let i = 0; i <= seg; i++) { const a = a0 + (i / seg) * Math.PI / 2; pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } };
    corner(x + w - r, y + r, -Math.PI / 2); corner(x + w - r, y + h - r, 0); corner(x + r, y + h - r, Math.PI / 2); corner(x + r, y + r, Math.PI);
    return poly(pts);
  }

  window.ART = { styles: Object.keys(STYLES), STYLES, canvas, poly, circle, rect, rnd };
})();
