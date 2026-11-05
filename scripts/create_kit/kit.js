// pro-editor /create kit. A scene defines window.render = (t, d) => {...}: t = seconds into the
// scene, d = its length. Everything on screen is set from t, so every frame is exact and repeatable.
// No requestAnimationFrame, CSS animations or timers: the renderer calls render() for each frame.
(function () {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const ease = {
    out: (x) => 1 - Math.pow(1 - x, 3),
    inOut: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
    back: (x) => { const c = 1.6; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); },
    lin: (x) => x,
  };
  const $ = (s) => document.querySelector(s);
  const el = (x) => (typeof x === "string" ? $(x) : x);
  const K = {
    clamp, ease, $,
    lerp: (a, b, x) => a + (b - a) * x,
    // progress 0..1 of an action that starts at `start` and lasts `dur`, eased
    p: (t, start, dur = 0.6, e = ease.out) => e(clamp((t - start) / dur)),
    // fade + slide in; out at the scene's end when d is given
    reveal(x, t, start, dur = 0.6, dy = 50, d = null) {
      const n = el(x); if (!n) return;
      let k = K.p(t, start, dur);
      if (d !== null) k *= 1 - K.p(t, d - 0.35, 0.35, ease.inOut);
      n.style.opacity = k; n.style.transform = `translateY(${(1 - k) * dy}px)`;
    },
    pop(x, t, start, dur = 0.5) {
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
    zoom(x, t, d, from = 1.0, to = 1.06) {    // slow push-in across the whole scene
      const n = el(x); if (!n) return;
      n.style.transform = `scale(${K.lerp(from, to, clamp(t / d))})`;
    },
  };
  window.K = K;
})();
