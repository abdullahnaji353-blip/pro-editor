// pro-editor /create host: an original animated presenter for faceless videos.
// K.talk(t)  -> how loud the voice is at t (0-1), from the scene's real voiceover when it has one
// K.host(t, d, {style, pos, size, wave}) -> draws the presenter; its mouth follows K.talk
//   style: "orb" (hologram face, default) or "bot" (pro-editor's robot)
//   pos:   "br" (bottom right, default), "bl", "center"
(function () {
  const K = window.K;
  K.talk = (t) => {
    const a = window.AMP;
    if (a && a.length) return a[Math.min(a.length - 1, Math.max(0, Math.floor(t * (window.AMP_FPS || 30))))] || 0;
    return 0;
  };
  // without a voice, fake speech while there's narration on screen
  const fake = (t, d) => (t > 0.2 && t < d - 0.4 ? Math.abs(Math.sin(t * 13) * Math.sin(t * 5.3)) : 0);

  function orb(t, talk, size) {
    const bob = Math.sin(t * 2.2) * 10, blink = t % 3.3 < 0.1;
    let bars = "";
    for (let i = 0; i < 9; i++) {
      const h = 8 + talk * 70 * (0.4 + 0.6 * Math.abs(Math.sin(i * 1.7 + t * 20)));
      bars += `<rect x="${-72 + i * 18}" y="${30 - h / 2}" width="9" height="${h}" rx="4.5" fill="var(--host-light,#7ff3ff)"/>`;
    }
    const eye = blink ? `<rect x="-14" y="-3" width="28" height="6" rx="3" fill="#dffcff"/>` : `<ellipse rx="13" ry="20" fill="#dffcff"/>`;
    let scan = "";
    for (let i = 0; i < 6; i++) {
      const y = -75 + i * 30 + ((t * 40) % 30);
      scan += `<line x1="-96" x2="96" y1="${y}" y2="${y}" stroke="#7ff3ff" stroke-opacity=".12" stroke-width="2"/>`;
    }
    return `<svg width="${size}" height="${size * 1.1}" viewBox="-150 -170 300 330" style="overflow:visible">
      <defs><radialGradient id="khg"><stop offset="0" stop-color="var(--accent,#21d4ed)" stop-opacity=".55"/>
      <stop offset=".7" stop-color="#0b6d80" stop-opacity=".35"/><stop offset="1" stop-color="var(--accent,#21d4ed)" stop-opacity=".9"/></radialGradient></defs>
      <ellipse cx="0" cy="150" rx="${90 - bob}" ry="14" fill="var(--accent,#21d4ed)" opacity=".25"/>
      <g transform="translate(0 ${bob})">
        <circle r="${118 + talk * 6}" fill="none" stroke="var(--accent,#21d4ed)" stroke-opacity=".3" stroke-width="2" stroke-dasharray="6 10" transform="rotate(${t * 40})"/>
        <circle r="100" fill="url(#khg)" stroke="var(--host-light,#7ff3ff)" stroke-width="3"/>${scan}
        <g transform="translate(-34 -22)">${eye}</g><g transform="translate(34 -22)">${eye}</g>
        <g transform="translate(0 6)">${bars}</g></g></svg>`;
  }

  function bot(t, talk, size, wave) {
    // pro-editor's robot (scripts/avatar_art.py geometry), simplified
    const bob = Math.sin(t * 2.6) * 6, blink = t % 3.1 < 0.12;
    const arm = wave ? -50 + 22 * Math.sin(t * 14) : 20;
    const eyeH = blink ? 4 : 30;
    return `<svg width="${size}" height="${size * 1.18}" viewBox="-110 -250 220 260" style="overflow:visible">
      <g transform="translate(0 ${bob})">
      <rect x="-34" y="-40" width="18" height="38" rx="9" fill="#5C6170"/><rect x="16" y="-40" width="18" height="38" rx="9" fill="#5C6170"/>
      <rect x="-60" y="-110" width="120" height="78" rx="34" fill="#F2EDE3"/><circle cy="-72" r="10" fill="#21D4ED"/>
      <g transform="translate(64 -100) rotate(${arm})"><rect x="-8" y="0" width="16" height="52" rx="8" fill="#F2EDE3"/><circle cy="56" r="11" fill="#5C6170"/></g>
      <g transform="translate(-64 -100) rotate(-20)"><rect x="-8" y="0" width="16" height="52" rx="8" fill="#F2EDE3"/><circle cy="56" r="11" fill="#5C6170"/></g>
      <rect x="-14" y="-124" width="28" height="18" rx="6" fill="#5C6170"/>
      <rect x="-96" y="-230" width="192" height="114" rx="44" fill="#F2EDE3"/><rect x="-78" y="-216" width="156" height="88" rx="32" fill="#0F1421"/>
      <rect x="-40" y="${-180 - eyeH / 2}" width="20" height="${eyeH}" rx="9" fill="#21D4ED"/><rect x="20" y="${-180 - eyeH / 2}" width="20" height="${eyeH}" rx="9" fill="#21D4ED"/>
      <ellipse cy="-148" rx="14" ry="${2 + talk * 12}" fill="#21D4ED"/>
      <line x1="0" y1="-230" x2="0" y2="-250" stroke="#5C6170" stroke-width="5"/><circle cy="-252" r="8" fill="#21D4ED"/></g></svg>`;
  }

  K.host = (t, d, o = {}) => {
    let el = document.getElementById("k-host");
    if (!el) {
      el = document.createElement("div");
      el.id = "k-host";
      el.style.cssText = "position:absolute;z-index:5;transform-origin:center bottom;pointer-events:none";
      document.body.appendChild(el);
    }
    const v = document.body.classList.contains("v");
    const size = o.size || (v ? 300 : 240);
    const pos = o.pos || "br";
    el.style.left = el.style.right = "";
    el.style.bottom = (o.bottom != null ? o.bottom : v ? 250 : 60) + "px";
    if (pos === "bl") el.style.left = "40px";
    else if (pos === "center") el.style.left = `calc(50% - ${size / 2}px)`;
    else el.style.right = "40px";
    const talk = window.AMP ? K.talk(t) : fake(t, d);
    el.innerHTML = o.style === "bot" ? bot(t, talk, size, o.wave && t < 2) : orb(t, talk, size);
    const enter = K.p(t, 0, 0.5, K.ease.back);
    el.style.transform = `translateY(${(1 - enter) * 260}px)`;
    el.style.opacity = Math.min(1, enter * 2);
    return talk;
  };
})();
