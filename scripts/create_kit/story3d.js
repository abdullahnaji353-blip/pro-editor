// pro-editor /story: blocky 3D characters in a little town, for "In this town..." style stories.
// Builds on K3 (three.js). Everything is a pure function of t, so frames render the same every time.
//
//   let W;  window.render = (t, d) => {
//     W = W || K3.world({ time: 0 });                 // night town: street, houses, lamps, trees
//     if (!W.kid) {
//       W.kid = K3.avatar(W.S, { shirt: 0xd8262c, pants: 0x1f2a44, hair: "short" }); W.S.scene.add(W.kid);
//       W.kid.position.set(6, 0, 4);
//       W.ball = K3.ball(W.S); W.S.scene.add(W.ball);
//     }
//     W.kid.pose("dribble", t, { ball: W.ball });     // idle walk dribble talk shrug dance tired point cheer shoot
//     W.kid.say(K.talk(t));                           // mouth follows the scene's voice line
//     K3.shot(W.S, t, d, { from: [10, 3, 12], to: [8, 2.4, 8], look: [6, 2.5, 4] });
//     W.draw(t);
//   };
//
// Characters are original blocky figures (no game's logos or official avatars).
(function () {
  const K3 = window.K3;
  const lerp = (a, b, k) => a + (b - a) * k;
  const ease = (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2);
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));

  // ------------------------------------------------------------------ shapes
  // a box with soft rounded edges (plastic toy look)
  function rbox(T, w, h, d, r = 0.12) {
    const s = new T.Shape(), x = -(w - 2 * r) / 2, y = -(h - 2 * r) / 2;
    s.moveTo(x, y); s.lineTo(-x, y); s.lineTo(-x, -y); s.lineTo(x, -y); s.closePath();
    const g = new T.ExtrudeGeometry(s, { depth: Math.max(0.01, d - 2 * r), bevelEnabled: true, bevelSize: r, bevelThickness: r, bevelSegments: 4, curveSegments: 2 });
    g.translate(0, 0, -(d - 2 * r) / 2); g.computeVertexNormals();
    return g;
  }
  // the rounded head: a squat cylinder with soft top and bottom edges
  function headGeo(T, r = 0.66, h = 1.22, c = 0.26) {
    const pts = [new T.Vector2(0, -h / 2)];
    for (let i = 0; i <= 6; i++) { const a = -Math.PI / 2 + (i / 6) * Math.PI / 2; pts.push(new T.Vector2(r - c + Math.cos(a) * c, -h / 2 + c + Math.sin(a) * c)); }
    for (let i = 0; i <= 6; i++) { const a = (i / 6) * Math.PI / 2; pts.push(new T.Vector2(r - c + Math.cos(a) * c, h / 2 - c + Math.sin(a) * c)); }
    pts.push(new T.Vector2(0, h / 2));
    return new T.LatheGeometry(pts, 40);
  }

  // ------------------------------------------------------------------ faces (decals on a transparent canvas)
  function drawFace(c, mouth, blink, mood) {
    const x = c.getContext("2d");
    x.clearRect(0, 0, 256, 256);
    const ink = "#1b1b1b";
    const eye = (cx, cy, open, wink) => {
      if (wink || blink) { x.strokeStyle = ink; x.lineWidth = 9; x.lineCap = "round"; x.beginPath(); x.arc(cx, cy + 6, 16, 1.15 * Math.PI, 1.85 * Math.PI); x.stroke(); return; }
      if (mood === "shocked") {
        x.fillStyle = "#fff"; x.beginPath(); x.arc(cx, cy, 26, 0, 7); x.fill();
        x.lineWidth = 7; x.strokeStyle = ink; x.stroke();
        x.fillStyle = ink; x.beginPath(); x.arc(cx, cy, 13, 0, 7); x.fill();
        return;
      }
      const h = mood === "tired" ? 9 : 19 * open;
      x.fillStyle = ink; x.beginPath(); x.ellipse(cx, cy, 10, Math.max(3, h), 0, 0, 7); x.fill();
      if (mood !== "tired") { x.fillStyle = "#fff"; x.beginPath(); x.arc(cx - 3, cy - h * 0.45, 3.4, 0, 7); x.fill(); }
    };
    const ey = mood === "tired" ? 112 : 104;
    eye(92, ey, 1, false); eye(164, ey, 1, mood === "wink");
    x.strokeStyle = ink; x.lineCap = "round"; x.lineWidth = 7;
    if (mood === "smug") { x.beginPath(); x.moveTo(74, 76); x.lineTo(108, 82); x.moveTo(148, 82); x.lineTo(184, 72); x.stroke(); }
    if (mood === "tired") { x.beginPath(); x.moveTo(74, 98); x.lineTo(110, 104); x.moveTo(146, 104); x.lineTo(182, 98); x.stroke(); }
    if (mood === "shocked" && mouth < 0.06) mouth = 0.55;
    if (mouth > 0.06 || mood === "grin" || mood === "wink") {
      // the talking grin: a D-shaped open mouth, teeth on top, tongue below
      const m = Math.max(mouth, mood === "grin" || mood === "wink" ? 0.7 : 0);
      const w = mood === "shocked" ? 22 + m * 8 : 34 + m * 10, h = 10 + m * 34, cy = 158;
      x.save(); x.beginPath();
      if (mood === "shocked") x.ellipse(128, cy + 6, w * 0.7, h * 0.6, 0, 0, 7);
      else { x.moveTo(128 - w, cy - 6); x.quadraticCurveTo(128, cy - 2, 128 + w, cy - 6); x.quadraticCurveTo(128 + w * 0.9, cy + h, 128, cy + h); x.quadraticCurveTo(128 - w * 0.9, cy + h, 128 - w, cy - 6); }
      x.closePath(); x.fillStyle = "#2a0d0d"; x.fill(); x.clip();
      if (mood !== "shocked") { x.fillStyle = "#fff"; x.fillRect(128 - w, cy - 10, w * 2, 10 + h * 0.22); }
      x.fillStyle = "#e0505a"; x.beginPath(); x.ellipse(128, cy + h * 1.05, w * 0.6, h * 0.45, 0, 0, 7); x.fill();
      x.restore();
      x.lineWidth = 6; x.strokeStyle = ink; x.stroke();
    } else if (mood === "tired") {
      x.lineWidth = 7; x.beginPath(); x.moveTo(104, 166); x.quadraticCurveTo(128, 160, 152, 168); x.stroke();
    } else {
      // the classic smile
      x.lineWidth = 8; x.beginPath(); x.arc(128, 128, 40, 0.22 * Math.PI, 0.78 * Math.PI); x.stroke();
    }
  }

  // shirt prints: hoodie drawstrings, a pocket, optional text and confetti stars
  function drawShirt(c, o) {
    const x = c.getContext("2d"), W = c.width, H = c.height;
    x.clearRect(0, 0, W, H);
    if (o.hoodie !== false) {
      for (const sx of [0.4, 0.6]) {
        x.strokeStyle = o.strings ?? "#e8c43a"; x.lineWidth = W * 0.035; x.lineCap = "round";
        x.beginPath(); x.moveTo(W * sx, H * 0.02); x.lineTo(W * sx, H * 0.28); x.stroke();
        x.fillStyle = "#c9c9c9"; x.fillRect(W * sx - W * 0.022, H * 0.28, W * 0.044, H * 0.06);
      }
      x.strokeStyle = "rgba(0,0,0,.18)"; x.lineWidth = 4;
      x.beginPath(); x.moveTo(W * 0.25, H * 0.98); x.lineTo(W * 0.3, H * 0.72); x.lineTo(W * 0.7, H * 0.72); x.lineTo(W * 0.75, H * 0.98); x.stroke();
    }
    if (o.stars) {
      let sd = 5; const r = () => ((sd = (sd * 16807) % 2147483647) / 2147483647);
      for (let i = 0; i < 26; i++) { x.fillStyle = ["#ffffff", "#ffd84a", "#ff8ad8"][i % 3]; const px = r() * W, py = r() * H; x.font = `${10 + r() * 10}px sans-serif`; x.fillText("✦", px, py); }
    }
    if (o.text) {
      x.fillStyle = o.textColor ?? "#ffd84a"; x.textAlign = "center";
      x.font = `bold ${W * 0.13}px "DM Serif Display", Georgia, serif`; x.fillText(o.text, W / 2, H * 0.6);
      if (o.subtext) { x.font = `${W * 0.05}px "Inter Tight", sans-serif`; x.fillText(o.subtext, W / 2, H * 0.68); }
    }
    if (o.pattern === "check") {
      for (let yy = 0; yy < H; yy += 32) for (let xx = 0; xx < W; xx += 32) if (((xx + yy) / 32) % 2 === 0) { x.fillStyle = "rgba(0,0,0,.28)"; x.fillRect(xx, yy, 32, 32); }
    }
  }

  // ------------------------------------------------------------------ an avatar
  function avatar(S, o = {}) {
    const T = S.T, g = new T.Group();
    const skin = o.skin ?? 0xf2cfa5;
    const M = (c, r = 0.42) => new T.MeshStandardMaterial({ color: c, roughness: r, metalness: 0 });
    const mesh = (geo, mat) => { const m = new T.Mesh(geo, mat); m.castShadow = m.receiveShadow = true; return m; };
    const decal = (w, h, canvas, z) => {
      const tx = new T.CanvasTexture(canvas); tx.colorSpace = T.SRGBColorSpace; tx.anisotropy = 4;
      const m = new T.Mesh(new T.PlaneGeometry(w, h), new T.MeshStandardMaterial({ map: tx, transparent: true, roughness: 0.5, depthWrite: false }));
      m.position.z = z; m.renderOrder = 2; m.tex = tx; return m;
    };
    const shirt = o.shirt ?? 0x2f55d4;
    const hips = new T.Group(); hips.position.y = 2; g.add(hips);
    const torso = mesh(rbox(T, 2, 2, 1, 0.14), M(shirt)); torso.position.y = 1; hips.add(torso);
    const sc = document.createElement("canvas"); sc.width = 256; sc.height = 256;
    drawShirt(sc, { hoodie: o.hoodie, text: o.text, subtext: o.subtext, stars: o.stars, strings: o.strings, textColor: o.textColor, pattern: o.pattern });
    const print = decal(1.96, 1.96, sc, 0.505); print.position.y = 1; hips.add(print);
    if (o.stripe) { const st = mesh(rbox(T, 2.02, 0.26, 1.02, 0.05), M(o.stripe)); st.position.y = 1.35; hips.add(st); }
    const neck = new T.Group(); neck.position.y = 2; hips.add(neck);
    const head = mesh(headGeo(T), M(skin, 0.5)); head.position.y = 0.64; neck.add(head);
    // the face: a decal wrapped on the front of the head
    const fc = document.createElement("canvas"); fc.width = fc.height = 256;
    const ft = new T.CanvasTexture(fc); ft.colorSpace = T.SRGBColorSpace; ft.anisotropy = 4;
    const face = new T.Mesh(new T.CylinderGeometry(0.665, 0.665, 1.0, 24, 1, true, -1.15, 2.3), new T.MeshStandardMaterial({ map: ft, transparent: true, roughness: 0.5, depthWrite: false }));
    face.position.y = 0.64; face.renderOrder = 2; neck.add(face);
    const hat = o.hat ?? (o.hair === "cap" ? "cap" : null), hc = o.hairColor ?? 0x2b1a10;
    if (o.hair && o.hair !== "none" && o.hair !== "cap") {               // chunky hair blocks
      const top = mesh(rbox(T, 1.42, 0.42, 1.42, 0.16), M(hc, 0.6)); top.position.y = 1.32; neck.add(top);
      const back = mesh(rbox(T, 1.42, o.hair === "long" ? 1.5 : 0.8, 0.36, 0.14), M(hc, 0.6)); back.position.set(0, o.hair === "long" ? 0.62 : 0.98, -0.56); neck.add(back);
      if (o.hair === "long") for (const sx of [-0.64, 0.64]) { const sd = mesh(rbox(T, 0.26, 1.1, 1.0, 0.1), M(hc, 0.6)); sd.position.set(sx, 0.8, -0.1); neck.add(sd); }
      const fr = mesh(rbox(T, 1.42, 0.24, 0.4, 0.1), M(hc, 0.6)); fr.position.set(0, 1.18, 0.5); neck.add(fr);
    }
    if (hat === "beanie") {
      const col = o.hatColor ?? shirt;
      const dome = mesh(new T.SphereGeometry(0.72, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), M(col, 0.85)); dome.scale.set(1, 0.72, 1); dome.position.y = 1.08; neck.add(dome);
      const cuff = mesh(new T.CylinderGeometry(0.735, 0.735, 0.34, 32), M(col, 0.9)); cuff.position.y = 1.08; neck.add(cuff);
      if (o.star !== false) {
        const stc = document.createElement("canvas"); stc.width = stc.height = 64; const sx = stc.getContext("2d");
        sx.fillStyle = o.starColor ?? "#ffd84a"; sx.font = "54px sans-serif"; sx.textAlign = "center"; sx.textBaseline = "middle"; sx.fillText("★", 32, 34);
        const st = decal(0.34, 0.34, stc, 0.745); st.position.y = 1.08; neck.add(st);
      }
    } else if (hat === "party") {
      const pc = document.createElement("canvas"); pc.width = 64; pc.height = 128; const px = pc.getContext("2d");
      for (let i = 0; i < 8; i++) { px.fillStyle = i % 2 ? (o.hatColor2 ?? "#ffffff") : (o.hatColorCss ?? "#3fb0ff"); px.fillRect(0, i * 16, 64, 16); }
      const tx = new T.CanvasTexture(pc); tx.colorSpace = T.SRGBColorSpace;
      const cone = mesh(new T.ConeGeometry(0.42, 1.0, 24), new T.MeshStandardMaterial({ map: tx, roughness: 0.6 })); cone.position.set(0.12, 1.72, 0); cone.rotation.z = -0.15; neck.add(cone);
      const pom = mesh(new T.SphereGeometry(0.12, 12, 8), M(0xffd84a)); pom.position.set(0.2, 2.22, 0); neck.add(pom);
    } else if (hat === "cap") {
      const col = o.capColor ?? 0x1f4fbf;
      const dome = mesh(new T.SphereGeometry(0.71, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), M(col, 0.7)); dome.scale.set(1, 0.6, 1); dome.position.y = 1.12; neck.add(dome);
      const brim = mesh(rbox(T, 1.1, 0.08, 0.7, 0.03), M(col, 0.7)); brim.position.set(0, 1.12, 0.78); neck.add(brim);
    }
    if (o.glasses) {
      const gc = document.createElement("canvas"); gc.width = 256; gc.height = 96; const gx = gc.getContext("2d");
      gx.strokeStyle = "#111"; gx.lineWidth = 9; gx.strokeRect(40, 18, 72, 56); gx.strokeRect(144, 18, 72, 56); gx.beginPath(); gx.moveTo(112, 40); gx.lineTo(144, 40); gx.stroke();
      const gl = new T.Mesh(new T.CylinderGeometry(0.672, 0.672, 0.38, 24, 1, true, -0.95, 1.9), new T.MeshStandardMaterial({ map: new T.CanvasTexture(gc), transparent: true, depthWrite: false }));
      gl.position.y = 0.7; gl.renderOrder = 3; neck.add(gl);
    }
    const limb = (x, y, color, parent) => {
      const piv = new T.Group(); piv.position.set(x, y, 0); parent.add(piv);
      const m = mesh(rbox(T, 0.98, 2, 0.98, 0.14), M(color)); m.position.y = -1; piv.add(m);
      if (o.sleeves && color === (o.arms ?? shirt)) { const hand = mesh(rbox(T, 0.98, 0.5, 0.98, 0.14), M(skin, 0.5)); hand.position.y = -1.76; piv.add(hand); }
      return piv;
    };
    const armL = limb(-1.5, 1.95, o.arms ?? shirt, hips), armR = limb(1.5, 1.95, o.arms ?? shirt, hips);
    const legL = new T.Group(), legR = new T.Group(); legL.position.set(-0.5, 2, 0); legR.position.set(0.5, 2, 0); g.add(legL, legR);
    for (const L of [legL, legR]) {
      const m = mesh(rbox(T, 0.98, 2, 0.98, 0.14), M(o.pants ?? shirt)); m.position.y = -1; L.add(m);
      if (o.shoes) { const sh = mesh(rbox(T, 1.0, 0.32, 1.06, 0.1), M(o.shoes)); sh.position.set(0, -1.84, 0.04); L.add(sh); }
    }
    const A = { g, hips, torso, neck, head, armL, armR, legL, legR };
    let mouth = 0, mood = o.mood || "neutral", lastKey = "";
    g.say = (level) => { mouth = clamp(level || 0); };
    g.mood = (m) => { mood = m; };
    // poses blend over 0.3 s when you pass {from: "previous pose", at: switchTime}, instead of snapping
    const KEYS = ["armL", "armR", "legL", "legR", "neck", "hips"];
    const snap = () => KEYS.map((k) => [A[k].rotation.x, A[k].rotation.y, A[k].rotation.z]).concat([[A.hips.position.y, 0, 0]]);
    g.pose = (name, t, p = {}) => {
      const k = p.from && p.at != null ? clamp((t - p.at) / (p.blend ?? 0.3)) : 1;
      if (k >= 1) return pose(A, name, t, p);
      pose(A, p.from, t, p); const a = snap();
      pose(A, name, t, p); const b = snap(), e = ease(k);
      KEYS.forEach((key, i) => A[key].rotation.set(lerp(a[i][0], b[i][0], e), lerp(a[i][1], b[i][1], e), lerp(a[i][2], b[i][2], e)));
      A.hips.position.y = lerp(a[6][0], b[6][0], e);
    };
    // turn the head toward a point in the world (a little, like people do when they talk)
    g.look = (x, z, amount = 0.6) => {
      const ang = Math.atan2(x - g.position.x, z - g.position.z) - g.rotation.y;
      const wrap = Math.atan2(Math.sin(ang), Math.cos(ang));
      A.neck.rotation.y += clamp(wrap, -1.0, 1.0) * amount;
    };
    g.face = (t) => {
      const blink = (t + (o.seed ?? 0)) % 3.4 < 0.12;
      const key = `${Math.round(mouth * 12)}|${blink}|${mood}`;
      if (key !== lastKey) { drawFace(fc, mouth, blink, mood); ft.needsUpdate = true; lastKey = key; }
    };
    g.parts = A;
    g.scale.setScalar(o.scale ?? 0.5);
    return g;
  }

  function reset(A) {
    for (const k of ["armL", "armR", "legL", "legR", "neck", "hips"]) A[k].rotation.set(0, 0, 0);
    A.hips.position.y = 2;
  }
  function pose(A, name, t, p) {
    reset(A);
    const s = Math.sin, br = s(t * 2.2) * 0.03;
    A.neck.rotation.x = br;
    if (name === "idle") {
      A.armL.rotation.z = 0.08; A.armR.rotation.z = -0.08; A.hips.position.y = 2 + br * 0.5;
    } else if (name === "walk") {
      const w = t * (p.speed ?? 7);
      A.legL.rotation.x = s(w) * 0.7; A.legR.rotation.x = -s(w) * 0.7;
      A.armL.rotation.x = -s(w) * 0.7; A.armR.rotation.x = s(w) * 0.7;
      A.hips.position.y = 2 + Math.abs(s(w)) * 0.08;
    } else if (name === "dribble") {
      const f = p.rate ?? 2.2, ph = (t * f) % 1;     // one bounce per cycle; hand low when the ball comes up
      A.armR.rotation.x = -0.9 - Math.cos(ph * 2 * Math.PI) * 0.35;
      A.armL.rotation.x = -0.3; A.armL.rotation.z = 0.15;
      A.legL.rotation.x = 0.25; A.legR.rotation.x = -0.15; A.hips.position.y = 1.9;
      A.neck.rotation.x = 0.25;
      if (p.ball) {
        const b = p.ball, h = Math.abs(Math.cos(ph * Math.PI)) * 1.55;
        const sc = A.g.scale.x, base = A.g.position;
        const fw = A.g.rotation.y;
        b.position.set(base.x + (Math.cos(fw) * 1.5 + Math.sin(fw) * 1.0) * sc, base.y + (0.5 + h * 1.4) * sc, base.z + (-Math.sin(fw) * 1.5 + Math.cos(fw) * 1.0) * sc);
        b.rotation.x = t * 6;
      }
    } else if (name === "talk") {
      const k = p.level ?? 0.5;
      A.armR.rotation.x = -0.5 - s(t * 5) * 0.25 * k; A.armR.rotation.z = -0.25;
      A.armL.rotation.z = 0.1; A.neck.rotation.x = br + s(t * 7) * 0.05 * k; A.neck.rotation.y = s(t * 1.3) * 0.12;
    } else if (name === "shrug") {
      A.armL.rotation.z = 0.9; A.armR.rotation.z = -0.9; A.armL.rotation.x = A.armR.rotation.x = -0.5;
      A.neck.rotation.z = 0.15;
    } else if (name === "dance") {
      const b = t * (p.bpm ?? 124) / 60 * Math.PI * 2;
      A.hips.position.y = 2 + Math.abs(s(b / 2)) * 0.35; A.hips.rotation.y = s(b / 2) * 0.4;
      A.armL.rotation.z = 2.4 + s(b) * 0.4; A.armR.rotation.z = -2.4 - s(b + 1) * 0.4;
      A.legL.rotation.z = s(b / 2) * 0.2; A.legR.rotation.z = s(b / 2) * 0.2; A.neck.rotation.x = s(b) * 0.2;
    } else if (name === "tired") {
      A.hips.position.y = 1.85; A.neck.rotation.x = 0.28; A.hips.rotation.x = 0.22;
      A.armL.rotation.x = 0.35; A.armR.rotation.x = 0.35; A.armL.rotation.z = 0.05; A.armR.rotation.z = -0.05;
      const w = t * (p.speed ?? 3);
      if (p.walking) { A.legL.rotation.x = s(w) * 0.35; A.legR.rotation.x = -s(w) * 0.35; }
      A.hips.position.y += s(t * 6) * 0.03;    // panting
    } else if (name === "point") {
      A.armR.rotation.x = -1.5; A.armR.rotation.y = -0.4; A.armL.rotation.z = 0.08;
    } else if (name === "cheer") {
      A.armL.rotation.z = 2.8; A.armR.rotation.z = -2.8; A.hips.position.y = 2 + Math.abs(s(t * 9)) * 0.3;
    } else if (name === "shoot") {
      const k = clamp(p.k ?? 0);              // 0 crouch, 1 release
      A.armR.rotation.x = lerp(-1.2, -2.9, k); A.armL.rotation.x = lerp(-1.0, -2.5, k);
      A.legL.rotation.x = A.legR.rotation.x = lerp(0.35, 0, k); A.hips.position.y = lerp(1.75, 2.15, k);
      A.neck.rotation.x = -0.25;
    }
  }

  // ------------------------------------------------------------------ props and the town
  function ball(S) {
    const T = S.T, c = document.createElement("canvas"); c.width = 256; c.height = 128;
    const x = c.getContext("2d"); x.fillStyle = "#e0661c"; x.fillRect(0, 0, 256, 128);
    x.strokeStyle = "#2a1406"; x.lineWidth = 5;
    x.beginPath(); x.moveTo(0, 64); x.lineTo(256, 64); x.moveTo(64, 0); x.lineTo(64, 128); x.moveTo(192, 0); x.lineTo(192, 128); x.stroke();
    const tx = new T.CanvasTexture(c); tx.colorSpace = T.SRGBColorSpace;
    const m = new T.Mesh(new T.SphereGeometry(0.32, 24, 16), new T.MeshStandardMaterial({ map: tx, roughness: 0.7 }));
    m.castShadow = true;
    return m;
  }
  function boxM(S, w, h, d, color, o = {}) {
    const T = S.T;
    const m = new T.Mesh(new T.BoxGeometry(w, h, d), new T.MeshStandardMaterial({ color, roughness: o.rough ?? 0.7, emissive: o.emissive ?? 0x000000, emissiveIntensity: o.ei ?? 1 }));
    m.castShadow = o.cast ?? true; m.receiveShadow = true;
    return m;
  }
  function house(S, o = {}) {
    const T = S.T, g = new T.Group();
    const w = o.w ?? 7, d = o.d ?? 6, h = o.h ?? 4;
    const body = boxM(S, w, h, d, o.color ?? 0xe8dcc8); body.position.y = h / 2; g.add(body);
    const roof = new T.Mesh(new T.ConeGeometry(Math.max(w, d) * 0.78, 2.6, 4), new T.MeshStandardMaterial({ color: o.roof ?? 0x7a2e24, roughness: 0.8 }));
    roof.rotation.y = Math.PI / 4; roof.position.y = h + 1.3; roof.scale.set(w / Math.max(w, d), 1, d / Math.max(w, d)); roof.castShadow = true; g.add(roof);
    const door = boxM(S, 1.2, 2.2, 0.1, 0x5a3a22); door.position.set(0, 1.1, d / 2 + 0.05); g.add(door);
    g.windows = [];
    for (const [wx, wy] of [[-2.2, 2.4], [2.2, 2.4]]) {
      const win = boxM(S, 1.4, 1.2, 0.1, 0x223040, { emissive: o.party ? 0xff2ad4 : (o.lit ? 0xffd27a : 0x000000), ei: o.party ? 1.6 : 0.9 });
      win.position.set(wx, wy, d / 2 + 0.06); g.add(win); g.windows.push(win);
    }
    g.party = !!o.party;
    if (o.party) {                              // coloured light spilling out of the party house
      g.light = new T.PointLight(0xff2ad4, 18, 16, 1.6); g.light.position.set(0, 2.4, d / 2 + 1.5); g.add(g.light);
    }
    g.tick = (t) => {
      if (!g.party) return;
      const cols = [0xff2ad4, 0x2ad4ff, 0xffe12a, 0x7a2aff];
      const c = cols[Math.floor(t * 124 / 60) % cols.length];   // changes on every beat at 124 bpm
      g.windows.forEach((w) => w.material.emissive.setHex(c));
      g.light.color.setHex(c); g.light.intensity = 14 + 8 * Math.abs(Math.sin(t * 124 / 60 * Math.PI));
    };
    return g;
  }
  function lamp(S, light = true) {
    const T = S.T, g = new T.Group();
    const pole = boxM(S, 0.18, 4.6, 0.18, 0x30343a); pole.position.y = 2.3; g.add(pole);
    const arm = boxM(S, 1.1, 0.14, 0.14, 0x30343a); arm.position.set(0.5, 4.55, 0); g.add(arm);
    const bulb = new T.Mesh(new T.BoxGeometry(0.5, 0.2, 0.4), new T.MeshBasicMaterial({ color: 0xffe2a8 })); bulb.position.set(0.95, 4.42, 0); g.add(bulb);
    if (light) { g.light = new T.PointLight(0xffd59a, 10, 12, 1.5); g.light.position.set(0.95, 4.1, 0); g.add(g.light); }
    return g;
  }
  function tree(S, k = 1) {
    const T = S.T, g = new T.Group();
    const tr = boxM(S, 0.5, 2, 0.5, 0x5a3d26); tr.position.y = 1; g.add(tr);
    const l1 = boxM(S, 2.4, 1.6, 2.4, 0x2f7a3a); l1.position.y = 2.6; g.add(l1);
    const l2 = boxM(S, 1.6, 1.0, 1.6, 0x3a8f45); l2.position.y = 3.7; g.add(l2);
    g.scale.setScalar(k);
    return g;
  }
  function hoop(S) {
    const T = S.T, g = new T.Group();
    const pole = boxM(S, 0.25, 5.2, 0.25, 0x5a5f66); pole.position.y = 2.6; g.add(pole);
    const board = boxM(S, 2.4, 1.5, 0.12, 0xf4f4f4); board.position.set(0, 5.4, 0.45); g.add(board);
    const sq = boxM(S, 0.9, 0.6, 0.13, 0xd8262c); sq.position.set(0, 5.15, 0.46); g.add(sq);
    const rim = new T.Mesh(new T.TorusGeometry(0.42, 0.05, 8, 24), new T.MeshStandardMaterial({ color: 0xe0561c })); rim.rotation.x = Math.PI / 2; rim.position.set(0, 4.85, 1.0); g.add(rim);
    const net = new T.Mesh(new T.CylinderGeometry(0.42, 0.28, 0.7, 12, 1, true), new T.MeshBasicMaterial({ color: 0xffffff, wireframe: true })); net.position.set(0, 4.5, 1.0); g.add(net);
    g.rim = rim;
    return g;
  }

  function roundTree(S, k = 1, seed = 1) {
    const T = S.T, g = new T.Group();
    const tr = boxM(S, 0.45, 2.2, 0.45, 0x6a4a2e); tr.position.y = 1.1; g.add(tr);
    const greens = [0x3f9a46, 0x4caf50, 0x2f8a3e];
    for (const [x, y, z, r] of [[0, 3.0, 0, 1.4], [0.7, 2.6, 0.3, 1.0], [-0.7, 2.7, -0.2, 1.05], [0.1, 3.8, 0.1, 0.95]]) {
      const b = new T.Mesh(new T.SphereGeometry(r, 18, 12), new T.MeshStandardMaterial({ color: greens[(seed + Math.round(r * 10)) % 3], roughness: 0.8 }));
      b.position.set(x, y, z); b.castShadow = b.receiveShadow = true; g.add(b);
    }
    g.scale.setScalar(k);
    return g;
  }
  function fence(S, len, o = {}) {
    const T = S.T, g = new T.Group(), col = o.color ?? 0x8a5a36;
    const rail = boxM(S, len, 0.16, 0.1, col); rail.position.y = 0.9; g.add(rail);
    const rail2 = boxM(S, len, 0.16, 0.1, col); rail2.position.y = 0.4; g.add(rail2);
    for (let x = -len / 2; x <= len / 2; x += 0.5) { const pl = boxM(S, 0.38, 1.3, 0.08, col); pl.position.set(x, 0.65, 0.07); g.add(pl); }
    return g;
  }
  function car(S, color, o = {}) {
    const T = S.T, g = new T.Group();
    const body = new T.Mesh(rbox(T, 3.6, 0.8, 1.7, 0.25), new T.MeshStandardMaterial({ color, roughness: 0.35 })); body.position.y = 0.75; body.castShadow = true; g.add(body);
    const cab = new T.Mesh(rbox(T, 2.0, 0.7, 1.55, 0.22), new T.MeshStandardMaterial({ color, roughness: 0.35 })); cab.position.set(-0.2, 1.45, 0); cab.castShadow = true; g.add(cab);
    const glass = new T.Mesh(rbox(T, 1.9, 0.5, 1.6, 0.18), new T.MeshStandardMaterial({ color: 0x1c2a3a, roughness: 0.1, metalness: 0.3 })); glass.position.set(-0.2, 1.47, 0); g.add(glass);
    for (const [x, z] of [[-1.15, 0.8], [1.15, 0.8], [-1.15, -0.8], [1.15, -0.8]]) {
      const w = new T.Mesh(new T.CylinderGeometry(0.38, 0.38, 0.3, 18), new T.MeshStandardMaterial({ color: 0x1a1a1e, roughness: 0.9 })); w.rotation.x = Math.PI / 2; w.position.set(x, 0.38, z); g.add(w);
    }
    for (const z of [0.55, -0.55]) { const l = new T.Mesh(new T.BoxGeometry(0.06, 0.18, 0.32), new T.MeshBasicMaterial({ color: 0xfff1c1 })); l.position.set(1.8, 0.85, z); g.add(l); }
    return g;
  }
  // bunting flags and string lights hung between two points, with a little sag
  function bunting(S, a, b, o = {}) {
    const T = S.T, g = new T.Group(), n = o.n ?? 14, cols = [0xff4a6a, 0xffd84a, 0x4ad0ff, 0x7aff7a, 0xb07aff, 0xff9a3a];
    const sag = o.sag ?? 0.8;
    const pt = (k) => new T.Vector3(a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k - Math.sin(k * Math.PI) * sag, a[2] + (b[2] - a[2]) * k);
    const pts = []; for (let i = 0; i <= 24; i++) pts.push(pt(i / 24));
    g.add(new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: 0x333333 })));
    for (let i = 1; i < n; i++) {
      const p = pt(i / n);
      if (o.lights) {
        const bulb = new T.Mesh(new T.SphereGeometry(0.09, 8, 6), new T.MeshBasicMaterial({ color: 0xfff0b8 })); bulb.position.copy(p); bulb.position.y -= 0.08; g.add(bulb);
      } else {
        const f = new T.Mesh(new T.ConeGeometry(0.22, 0.45, 3), new T.MeshStandardMaterial({ color: cols[i % cols.length], roughness: 0.7, side: T.DoubleSide }));
        f.rotation.x = Math.PI; f.position.copy(p); f.position.y -= 0.24; f.scale.z = 0.15; g.add(f);
      }
    }
    return g;
  }
  function balloons(S, o = {}) {
    const T = S.T, g = new T.Group(), cols = [0xff4a8a, 0x4ad0ff, 0xffd84a, 0xb07aff, 0xff7a3a];
    for (let i = 0; i < 5; i++) {
      const b = new T.Mesh(new T.SphereGeometry(0.34, 16, 12), new T.MeshStandardMaterial({ color: cols[i], roughness: 0.25 }));
      b.scale.y = 1.2; b.position.set((i - 2) * 0.32, 2.4 + (i % 2) * 0.4, (i % 3) * 0.15); b.castShadow = true; g.add(b);
      g.add(new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(0, 0.4, 0), b.position.clone()]), new T.LineBasicMaterial({ color: 0xdddddd })));
    }
    return g;
  }

  // a whole night street: road, sidewalks, lawns, a party house, a quiet house with a hoop, lamps, trees
  function world(o = {}) {
    const S = K3.stage("cgi", { shadows: true, bg: [0x1b2a5a, 0x3a4f8a], fog: [0x2a3a6a, 40, 120] });
    const T = S.T;
    S.renderer.toneMappingExposure = 1.1;
    const g = new T.Group(); S.scene.add(g);
    const ground = new T.Mesh(new T.PlaneGeometry(200, 200), new T.MeshStandardMaterial({ color: 0x3f7a3a, roughness: 1 }));
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; g.add(ground);
    const road = new T.Mesh(new T.PlaneGeometry(200, 8), new T.MeshStandardMaterial({ color: 0x2a2c30, roughness: 0.95 }));
    road.rotation.x = -Math.PI / 2; road.position.y = 0.01; road.receiveShadow = true; g.add(road);
    for (let x = -60; x < 60; x += 4) { const dash = boxM(S, 2, 0.02, 0.18, 0xe8d36a, { cast: false }); dash.position.set(x, 0.02, 0); g.add(dash); }
    for (const z of [-5, 5]) { const sw = boxM(S, 200, 0.12, 2, 0x9a9a95, { cast: false }); sw.position.set(0, 0.06, z); g.add(sw); }
    // north side (z < 0): the party house; south side: our kid's house and driveway
    const party = house(S, { party: true, color: 0xe86a7a, roof: 0x3a3a48 }); party.position.set(-6, 0, -12); g.add(party);
    const h2 = house(S, { color: 0x4a6ad8, roof: 0x2a2a38, lit: true }); h2.position.set(6, 0, -12); g.add(h2);
    const h3 = house(S, { color: 0xf2c84a, roof: 0x5a2a22, lit: true }); h3.position.set(-18, 0, -12); g.add(h3);
    const home = house(S, { color: 0xc8463a, roof: 0x2a2a30, lit: true }); home.position.set(8, 0, 13); home.rotation.y = Math.PI; g.add(home);
    const h5 = house(S, { color: 0x6ab8e8, roof: 0x2a3a4a }); h5.position.set(-8, 0, 13); h5.rotation.y = Math.PI; g.add(h5);
    for (const hs of [party, h2, h3, home, h5]) { const ch = boxM(S, 0.8, 2.4, 0.8, 0x8a4a3a); ch.position.set(2, 5.2, -1); hs.add(ch); }
    // yards: fences, the party's bunting, string lights and balloons, parked cars
    for (const [x, z, len, r] of [[-12, -8.2, 4, 0], [0, -8.2, 4, 0], [12, -8.2, 4, 0], [-2, 9.6, 6, 0], [14, 9.6, 6, 0]]) { const f = fence(S, len); f.position.set(x, 0, z); f.rotation.y = r; g.add(f); }
    g.add(bunting(S, [-10, 4.2, -8.6], [-2, 4.2, -8.6], { sag: 0.6 }));
    g.add(bunting(S, [-10, 3.6, -8.4], [-2, 3.6, -8.4], { sag: 0.9, lights: true, n: 22 }));
    for (const x of [-10, -2]) { const pole = boxM(S, 0.14, 4.4, 0.14, 0x5a4a3a); pole.position.set(x, 2.2, -8.6); g.add(pole); }
    const bl = balloons(S); bl.position.set(-2.4, 0, -8.6); g.add(bl);
    const bl2 = balloons(S); bl2.position.set(-9.6, 0, -8.6); g.add(bl2);
    for (const [x, z, c, r] of [[-14, -3, 0x2fa84f, 0], [18, -3, 0xd8262c, Math.PI], [-20, 3, 0x2b6cd6, 0], [12, 3, 0xf2c12e, Math.PI]]) { const cr = car(S, c); cr.position.set(x, 0, z); cr.rotation.y = r; g.add(cr); }
    // a big moon
    const moon = new T.Mesh(new T.CircleGeometry(5, 40), new T.MeshBasicMaterial({ color: 0xfff8e8, fog: false }));
    moon.position.set(-40, 48, -90); moon.lookAt(0, 0, 0); S.scene.add(moon);
    const drive = boxM(S, 4, 0.04, 6, 0x6a6a68, { cast: false }); drive.position.set(4, 0.03, 8.5); g.add(drive);
    const hp = hoop(S); hp.position.set(4, 0, 11.6); hp.rotation.y = Math.PI; g.add(hp);
    const lamps = [];
    for (const [x, z, r] of [[-12, -6, 0], [12, -6, 0], [0, 6, Math.PI], [16, 6, Math.PI]]) { const l = lamp(S); l.position.set(x, 0, z); l.rotation.y = r; g.add(l); lamps.push(l); }
    for (const [x, z, k, sd] of [[-12, -16, 1.2, 1], [14, -15, 1, 2], [-2, 16, 1.1, 3], [16, 14, 1.3, 4], [-24, -10, 1.1, 5], [24, 12, 1.2, 6], [-26, 14, 1.4, 7], [0, -20, 1.3, 8]]) { const tr = roundTree(S, k, sd); tr.position.set(x, 0, z); g.add(tr); }
    // stars
    const starG = new T.BufferGeometry(), pts = [];
    let sd = 7; const r = () => ((sd = (sd * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 500; i++) { const a = r() * 6.283, e = 0.15 + r() * 1.2, R = 150; pts.push(Math.cos(a) * Math.cos(e) * R, Math.sin(e) * R, Math.sin(a) * Math.cos(e) * R); }
    starG.setAttribute("position", new T.Float32BufferAttribute(pts, 3));
    const stars = new T.Points(starG, new T.PointsMaterial({ color: 0xffffff, size: 0.6, transparent: true, opacity: 0.9, fog: false }));
    S.scene.add(stars);
    const W = { S, T, party, home, hoop: hp, lamps, stars, time: o.time ?? 0 };
    // the sky: 0 = night, 1 = full morning
    const skyCanvas = document.createElement("canvas"); skyCanvas.width = 2; skyCanvas.height = 256;
    const skyTex = new T.CanvasTexture(skyCanvas); skyTex.colorSpace = T.SRGBColorSpace; S.scene.background = skyTex;
    const mix = (a, b, k) => { const ca = new T.Color(a), cb = new T.Color(b); return ca.lerp(cb, k); };
    W.setTime = (k) => {
      k = clamp(k);
      const top = k < 0.5 ? mix(0x0b1026, 0x3a4a8a, k * 2) : mix(0x3a4a8a, 0x7ec0ff, (k - 0.5) * 2);
      const bot = k < 0.5 ? mix(0x1d2a55, 0xff9a5a, k * 2) : mix(0xff9a5a, 0xdff1ff, (k - 0.5) * 2);
      const x = skyCanvas.getContext("2d"), gr = x.createLinearGradient(0, 0, 0, 256);
      gr.addColorStop(0, "#" + top.getHexString()); gr.addColorStop(1, "#" + bot.getHexString());
      x.fillStyle = gr; x.fillRect(0, 0, 2, 256); skyTex.needsUpdate = true;
      S.scene.fog.color.copy(bot);
      S.sun.intensity = lerp(0.9, 2.6, k); S.sun.color.copy(k < 0.6 ? mix(0x8aa0ff, 0xffb070, k / 0.6) : mix(0xffb070, 0xffffff, (k - 0.6) / 0.4));
      S.sun.position.set(lerp(-14, 10, k), lerp(10, 18, k), lerp(-8, 8, k));
      S.scene.children.forEach((c) => { if (c.isHemisphereLight) { c.intensity = lerp(1.25, 1.5, k); c.color.copy(mix(0x9ab0ff, 0xffffff, k)); c.groundColor.copy(mix(0x3a3a5a, 0x7a8a6a, k)); } });
      moon.material.opacity = 1 - k; moon.material.transparent = true;
      stars.material.opacity = clamp(1 - k * 2.2);
      lamps.forEach((l) => { if (l.light) l.light.intensity = lerp(10, 0, clamp(k * 1.6)); });
      if (W.fill) W.fill.intensity = lerp(6, 1.5, k);
    };
    // a soft fill light that rides with the camera, so faces read even at night (like a key light on set)
    W.fill = new T.PointLight(0xfff1dc, 6, 14, 1.4); W.fill.position.set(0.6, 0.4, 0); S.camera.add(W.fill); S.scene.add(S.camera);
    W.setTime(W.time);
    W.draw = (t) => {
      party.tick(t);
      S.scene.traverse((o2) => { if (o2.face) o2.face(t); });
      S.draw();
    };
    return W;
  }

  // a camera move from one spot to another over the scene (eased), looking at a point that can move too
  function shot(S, t, d, o) {
    const k = ease(clamp((t - (o.start ?? 0)) / (o.dur ?? d)));
    const f = o.from, to = o.to ?? o.from, la = o.look, lb = o.lookTo ?? o.look;
    S.camera.position.set(lerp(f[0], to[0], k), lerp(f[1], to[1], k), lerp(f[2], to[2], k));
    if (o.fov) { S.camera.fov = o.fov; S.camera.updateProjectionMatrix(); }
    const sh = o.shake ? Math.sin(t * 40) * o.shake : 0;
    S.camera.lookAt(lerp(la[0], lb[0], k) + sh, lerp(la[1], lb[1], k) + sh * 0.5, lerp(la[2], lb[2], k));
  }

  // an edit inside one scene: hard cuts between shots. Each shot: {at, from, to, look, lookTo, fov,
  // punch: zoom-in amount at its start, shake: seconds of shake at its start}
  function cuts(S, t, d, list) {
    let i = 0;
    while (i + 1 < list.length && t >= list[i + 1].at) i++;
    const c = list[i], end = i + 1 < list.length ? list[i + 1].at : d, lt = t - c.at, ld = end - c.at;
    const punch = c.punch ? c.punch * Math.exp(-lt * 9) : 0;
    const shake = c.shake && lt < c.shake ? (1 - lt / c.shake) * 0.06 : 0;
    shot(S, lt, ld, { ...c, start: 0, dur: ld, shake });
    if (punch) {
      const cam = S.camera.position, la = c.lookTo ?? c.look;
      cam.set(lerp(cam.x, la[0], punch), lerp(cam.y, la[1], punch), lerp(cam.z, la[2], punch));
    }
    return { index: i, local: lt, cut: lt < 1 / 30 };
  }

  // a basketball shot: ball flies from hands to the rim and drops through
  function arc(ballMesh, from, to, k) {
    k = clamp(k);
    const h = 3.2;
    ballMesh.position.set(lerp(from[0], to[0], k), lerp(from[1], to[1], k) + Math.sin(k * Math.PI) * h, lerp(from[2], to[2], k));
    ballMesh.rotation.x = k * 12;
  }

  Object.assign(K3, { cuts, rbox, roundTree, fence, car, bunting, balloons, avatar, ball, house, lamp, tree, hoop, world, shot, arc });
})();
