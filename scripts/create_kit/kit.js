// pro-editor /create kit. A scene defines window.render = (t, d) => {...}: t = seconds into the
// scene, d = its length. Everything on screen is set from t, so every frame is exact and repeatable.
// No requestAnimationFrame, CSS animations or timers: the renderer calls render() for each frame.
(function () {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const ease = {
    out: (x) => 1 - Math.pow(1 - x, 3),
    inOut: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    back: (x) => { const c = 1.6; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); },
    expo: (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x)),          // fast start, long settle: snappy
    quart: (x) => 1 - Math.pow(1 - x, 4),
    lin: (x) => x,
  };
  const $ = (s) => document.querySelector(s);
  const el = (x) => (typeof x === "string" ? $(x) : x);
  // every pop / reveal / draw is noted once, so the renderer can land a sound effect on it
  const sfx = (kind, t, sel) => { (window.__sfx = window.__sfx || {})[`${kind}|${sel}|${t.toFixed(3)}`] = { kind, t }; };
  const K = {
    clamp, ease, $, sfx,
    lerp: (a, b, x) => a + (b - a) * x,
    // progress 0..1 of an action that starts at `start` and lasts `dur`, eased
    p: (t, start, dur = 0.6, e = ease.out) => e(clamp((t - start) / dur)),
    // fade + slide in; out at the scene's end when d is given
    reveal(x, t, start, dur = 0.6, dy = 50, d = null) {
      sfx("swish", start + dur * 0.35, String(x));
      const n = el(x); if (!n) return;
      let k = K.p(t, start, dur);
      if (d !== null) k *= 1 - K.p(t, d - 0.35, 0.35, ease.inOut);
      n.style.opacity = k; n.style.transform = `translateY(${(1 - k) * dy}px)`;
    },
    pop(x, t, start, dur = 0.5) {
      sfx("pop", start + dur * 0.45, String(x));
      const n = el(x); if (!n) return;
      const k = K.p(t, start, dur, ease.back);
      n.style.opacity = clamp(k * 3); n.style.transform = `scale(${0.6 + 0.4 * k})`;
    },
    type(x, text, t, start, cps = 32) {
      const n = el(x); if (!n) return;
      n.textContent = text.slice(0, Math.floor(clamp((t - start) * cps, 0, text.length)));
    },
    count(x, to, t, start, dur = 1.2, fmt = (v) => Math.round(v).toLocaleString("en-US"), from = 0) {
      const n = el(x); if (!n) return;
      n.textContent = fmt(K.lerp(from, to, K.p(t, start, dur, ease.out)));
    },
    grow(x, frac, t, start, dur = 0.9, axis = "X") {
      const n = el(x); if (!n) return;
      n.style.transform = `scale${axis}(${frac * K.p(t, start, dur)})`;
    },
    draw(x, t, start, dur = 1.0) {           // stroke a path on, like a pen
      sfx("swish", start + 0.15, String(x));
      const n = el(x); if (!n) return;
      const L = n.getTotalLength(); n.style.strokeDasharray = L;
      n.style.strokeDashoffset = L * (1 - K.p(t, start, dur, ease.inOut));
    },
    // music: window.BEATS / DOWNBEATS / DROPS hold this scene's beat times (seconds from its start)
    beat(t, decay = 0.22, list = window.BEATS || []) {   // 1 on each beat, fading to 0
      let last = -1e9; for (const b of list) { if (b <= t) last = b; else break; }
      return Math.exp(-(t - last) / decay);
    },
    bar: (t, decay = 0.35) => K.beat(t, decay, window.DOWNBEATS || []),
    drop: (t, decay = 0.6) => K.beat(t, decay, window.DROPS || []),
    count_beats: (t) => (window.BEATS || []).filter((b) => b <= t).length,  // beats so far: word-per-beat text
    // a video file in the scene (AI footage, a screen recording, b-roll): paused and seeked to the
    // exact frame, so it renders in step with everything else. <video src="clip.mp4" muted></video>
    clip(x, t, start = 0, rate = 1) {
      const v = el(x); if (!v) return;
      v.muted = true; v.pause();
      const dur = v.duration || 1e9;
      const want = Math.max(0, Math.min(dur - 0.05, (t - start) * rate));
      if (Math.abs(v.currentTime - want) > 0.004 || v.readyState < 2) {
        (window.__pending = window.__pending || []).push(new Promise((ok) => {
          const done = () => { v.removeEventListener("seeked", done); ok(); };
          v.addEventListener("seeked", done);
          if (v.readyState < 1) v.addEventListener("loadedmetadata", () => { v.currentTime = want; }, { once: true });
          else v.currentTime = want;
          setTimeout(done, 3000);
        }));
      }
    },
    // ---- motion that doesn't look templated --------------------------------------------
    // split text into words once (keeps inner markup), then stagger them in: rise, unblur, fade
    words(x, t, start, stagger = 0.06, dur = 0.55, dy = 40) {
      const n = el(x); if (!n) return;
      if (!n.dataset.kw) {
        const walk = (node) => {
          for (const c of [...node.childNodes]) {
            if (c.nodeType === 3) {
              const frag = document.createDocumentFragment();
              c.textContent.split(/(\s+)/).forEach((w) => {
                if (!w) return;
                if (/^\s+$/.test(w)) { frag.appendChild(document.createTextNode(w)); return; }
                const sp = document.createElement("span"); sp.className = "kw"; sp.textContent = w;
                sp.style.display = "inline-block"; frag.appendChild(sp);
              });
              c.replaceWith(frag);
            } else if (c.nodeType === 1 && !c.classList.contains("kw")) walk(c);
          }
        };
        walk(n); n.dataset.kw = 1;
      }
      const ws = n.querySelectorAll(".kw");
      ws.forEach((w, i) => {
        const k = K.p(t, start + i * stagger, dur, ease.expo);
        w.style.opacity = Math.min(1, k * 1.4);
        w.style.transform = `translateY(${(1 - k) * dy}px)`;
        w.style.filter = k < 1 ? `blur(${(1 - k) * 10}px)` : "none";
      });
      sfx("swish", start + 0.1, String(x));
      return start + (ws.length - 1) * stagger + dur;  // when the last word lands
    },
    // reveal from behind an edge (dir: up, down, left, right) like a mask wipe
    mask(x, t, start, dur = 0.7, dir = "up") {
      const n = el(x); if (!n) return;
      const k = K.p(t, start, dur, ease.expo), r = (1 - k) * 100;
      const ins = { up: `${r}% 0 0 0`, down: `0 0 ${r}% 0`, left: `0 ${r}% 0 0`, right: `0 0 0 ${r}%` }[dir];
      n.style.clipPath = `inset(${dir === "up" ? `0 0 ${r}% 0` : ins})`;
      const off = { up: [0, 1], down: [0, -1], left: [1, 0], right: [-1, 0] }[dir];
      n.style.transform = `translate(${off[0] * (1 - k) * 60}px, ${off[1] * (1 - k) * 60}px)`;
      sfx("swish", start + dur * 0.2, String(x));
    },
    // highlighter sweep behind .mark text
    marker(x, t, start, dur = 0.5) {
      const n = el(x); if (!n) return;
      n.style.backgroundSize = `${K.p(t, start, dur, ease.inOut) * 100}% 38%`;
    },
    // scale in from big with blur and a little shake: for hype hits
    slam(x, t, start, dur = 0.35, from = 1.8) {
      const n = el(x); if (!n) return;
      const k = K.p(t, start, dur, ease.quart);
      const sh = t > start + dur ? Math.exp(-(t - start - dur) * 14) * 14 : 0;
      n.style.opacity = t < start ? 0 : 1;
      n.style.transform = `scale(${K.lerp(from, 1, k)}) translate(${Math.sin(t * 90) * sh}px, ${Math.cos(t * 77) * sh}px)`;
      n.style.filter = k < 1 ? `blur(${(1 - k) * 18}px)` : "none";
      sfx("impact", start + dur, String(x));
    },
    // decaying shake from `at`
    shake(x, t, at, amp = 18, decay = 9) {
      const n = el(x); if (!n || t < at) return;
      const a = amp * Math.exp(-(t - at) * decay);
      n.style.translate = `${Math.sin(t * 95) * a}px ${Math.cos(t * 83) * a}px`;
    },
    // the camera: a slow drift/push over the whole scene so nothing is ever perfectly still
    camera(x, t, d, o = {}) {
      const n = el(x); if (!n) return;
      const k = clamp(t / d), e = ease.inOut(k);
      const z = K.lerp(o.from ?? 1.0, o.to ?? 1.05, e), dx = (o.x ?? 0) * e, dy = (o.y ?? -20) * e;
      const r = (o.rot ?? 0) * e;
      n.style.transform = `translate(${dx}px, ${dy}px) scale(${z}) rotate(${r}deg)`;
    },
    // count with the number's width locked, so the layout doesn't jitter
    tally(x, to, t, start, dur = 1.4, fmt = (v) => Math.round(v).toLocaleString("en-US")) {
      const n = el(x); if (!n) return;
      if (!n.dataset.w) { n.textContent = fmt(to); n.style.display = "inline-block";
        n.style.minWidth = n.getBoundingClientRect().width + "px"; n.dataset.w = 1; }
      n.textContent = fmt(K.lerp(0, to, K.p(t, start, dur, ease.expo)));
      sfx("tick", start + dur, String(x));
    },
    zoom(x, t, d, from = 1.0, to = 1.06) {    // slow push-in across the whole scene
      const n = el(x); if (!n) return;
      n.style.transform = `scale(${K.lerp(from, to, clamp(t / d))})`;
    },
  };
  // film grain + vignette, re-seeded every frame (the renderer calls this after render)
  K.__post = (t) => {
    const look = document.body.dataset.look;
    if (!look || getComputedStyle(document.body).getPropertyValue("--grain").trim() === "0") return;
    let g = document.getElementById("k-texture");
    if (!g) {
      const c = document.createElement("canvas"); c.width = c.height = 256;
      const x = c.getContext("2d"), im = x.createImageData(256, 256);
      for (let i = 0; i < im.data.length; i += 4) { const v = Math.random() * 255; im.data[i] = im.data[i + 1] = im.data[i + 2] = v; im.data[i + 3] = 255; }
      x.putImageData(im, 0, 0);
      g = document.createElement("div"); g.id = "k-texture"; g.style.backgroundImage = `url(${c.toDataURL()})`;
      const v = document.createElement("div"); v.id = "k-vignette";
      document.body.append(v, g);
    }
    const f = Math.floor(t * 24);  // grain moves at 24 fps like film
    g.style.transform = `translate(${((f * 73) % 64) - 32}px, ${((f * 151) % 64) - 32}px)`;
  };
  // captions drawn in the scene, in the look's own type: groups of up to 3 words, current word lit
  K.__captions = (t) => {
    const ws = window.CAPS; if (!ws || !ws.length) return;
    let box = document.getElementById("k-cap");
    if (!box) { box = document.createElement("div"); box.id = "k-cap"; document.body.appendChild(box); }
    if (!window.__capGroups) {
      const gs = []; let cur = [];
      ws.forEach((w, i) => {
        cur.push(w);
        const nx = ws[i + 1];
        if (cur.length >= 3 || /[.,!?;:]$/.test(w.w) || !nx || nx.start - w.end > 0.35) { gs.push(cur); cur = []; }
      });
      window.__capGroups = gs;
    }
    const g = window.__capGroups.find((g) => t >= g[0].start - 0.05 && t < g[g.length - 1].end + 0.25);
    if (!g) { box.style.opacity = 0; return; }
    const k = K.p(t, g[0].start - 0.05, 0.18, ease.expo);
    box.style.opacity = 1;
    box.style.transform = `translateX(-50%) translateY(${(1 - k) * 18}px) scale(${0.94 + 0.06 * k})`;
    box.innerHTML = g.map((w) => `<span class="${t >= w.start && t < w.end + 0.08 ? "on" : ""}">${w.w.replace(/[<&]/g, "")}</span>`).join(" ");
  };
  window.K = K;
})();
