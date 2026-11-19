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

  // ------------------------------------------------------------------ the face (a canvas texture)
  function faceCanvas() {
    const c = document.createElement("canvas"); c.width = c.height = 128;
    return c;
  }
  function drawFace(c, skin, mouth, blink, mood) {
    const x = c.getContext("2d");
    x.fillStyle = skin; x.fillRect(0, 0, 128, 128);
    x.fillStyle = "#1a1a1a";
    const ey = mood === "tired" ? 54 : 50, eh = blink ? 2 : mood === "tired" ? 6 : 13;
    x.beginPath(); x.ellipse(44, ey, 6, eh / 2 + 0.5, 0, 0, 7); x.fill();
    x.beginPath(); x.ellipse(84, ey, 6, eh / 2 + 0.5, 0, 0, 7); x.fill();
    if (mood === "tired") {                       // heavy lids
      x.strokeStyle = "#1a1a1a"; x.lineWidth = 3;
      x.beginPath(); x.moveTo(36, ey - 7); x.lineTo(52, ey - 4); x.moveTo(76, ey - 4); x.lineTo(92, ey - 7); x.stroke();
    }
    if (mood === "smug") {
      x.strokeStyle = "#1a1a1a"; x.lineWidth = 3;
      x.beginPath(); x.moveTo(36, 38); x.lineTo(52, 40); x.moveTo(76, 40); x.lineTo(92, 36); x.stroke();
    }
    if (mouth > 0.06) {                           // talking: an open mouth sized by loudness
      x.fillStyle = "#3a1414";
      x.beginPath(); x.ellipse(64, 86, 10 + mouth * 6, 3 + mouth * 13, 0, 0, 7); x.fill();
      x.fillStyle = "#e86a6a"; x.beginPath(); x.ellipse(64, 90 + mouth * 6, 7, 2 + mouth * 4, 0, 0, Math.PI); x.fill();
    } else {                                      // resting: the classic little smile
      x.strokeStyle = "#1a1a1a"; x.lineWidth = 4; x.lineCap = "round";
      x.beginPath();
      if (mood === "tired") { x.moveTo(52, 92); x.lineTo(76, 90); }
      else x.arc(64, 74, 18, 0.25 * Math.PI, 0.75 * Math.PI);
      x.stroke();
    }
  }

  // ------------------------------------------------------------------ an avatar
  function avatar(S, o = {}) {
    const T = S.T, g = new T.Group();
    const skin = o.skin ?? 0xf3c99a;
    const M = (c, r = 0.55) => { const m = new T.MeshStandardMaterial({ color: c, roughness: r, metalness: 0 }); return m; };
    const box = (w, h, d, mat) => { const m = new T.Mesh(new T.BoxGeometry(w, h, d), mat); m.castShadow = m.receiveShadow = true; return m; };
    // proportions: legs 2, torso 2, head 1.2 (units ~ studs)
    const hips = new T.Group(); hips.position.y = 2; g.add(hips);
    const torso = box(2, 2, 1, M(o.shirt ?? 0xd8262c)); torso.position.y = 1; hips.add(torso);
    if (o.logo !== false) {                       // a simple shirt stripe so shirts read at a distance
      const st = box(2.02, 0.28, 1.02, M(o.stripe ?? 0xffffff)); st.position.y = 1.35; hips.add(st);
    }
    const neck = new T.Group(); neck.position.y = 2; hips.add(neck);
    const fc = faceCanvas(); const ft = new T.CanvasTexture(fc); ft.colorSpace = T.SRGBColorSpace;
    const headMats = [M(skin), M(skin), M(skin), M(skin), new T.MeshStandardMaterial({ map: ft, roughness: 0.55 }), M(skin)];
    const head = new T.Mesh(new T.BoxGeometry(1.25, 1.25, 1.25), headMats); head.castShadow = true; head.position.y = 0.66; neck.add(head);
    if (o.hair !== "none") {
      const hc = o.hairColor ?? 0x2b1a10;
      if (o.hair === "cap") {
        const cap = box(1.34, 0.42, 1.34, M(o.capColor ?? 0x1f4fbf)); cap.position.y = 1.22; neck.add(cap);
        const brim = box(1.34, 0.1, 0.6, M(o.capColor ?? 0x1f4fbf)); brim.position.set(0, 1.05, 0.9); neck.add(brim);
      } else if (o.hair === "long") {
        const top = box(1.36, 0.4, 1.36, M(hc)); top.position.y = 1.2; neck.add(top);
        const back = box(1.36, 1.3, 0.3, M(hc)); back.position.set(0, 0.55, -0.6); neck.add(back);
      } else {
        const top = box(1.34, 0.32, 1.34, M(hc)); top.position.y = 1.2; neck.add(top);
        const back = box(1.34, 0.6, 0.2, M(hc)); back.position.set(0, 0.95, -0.6); neck.add(back);
      }
    }
    const limb = (x, y, color, parent) => {
      const piv = new T.Group(); piv.position.set(x, y, 0); parent.add(piv);
      const m = box(1, 2, 1, M(color)); m.position.y = -1; piv.add(m);
      return piv;
    };
    const armL = limb(-1.5, 1.9, o.arms ?? skin, hips), armR = limb(1.5, 1.9, o.arms ?? skin, hips);
    const legL = new T.Group(); legL.position.set(-0.5, 0, 0); g.add(legL);
    const legR = new T.Group(); legR.position.set(0.5, 0, 0); g.add(legR);
    for (const L of [legL, legR]) {
      const m = box(1, 2, 1, M(o.pants ?? 0x1f2a44)); m.position.y = -1; L.add(m);
      const sh = box(1.04, 0.35, 1.1, M(o.shoes ?? 0xf2f2f2)); sh.position.set(0, -1.85, 0.05); L.add(sh);
    }
    legL.position.y = legR.position.y = 2;
    const A = { g, hips, torso, neck, head, armL, armR, legL, legR, fc, ft, skin: "#" + skin.toString(16).padStart(6, "0") };
    let mouth = 0, mood = o.mood || "neutral";
    g.say = (level) => { mouth = clamp(level || 0); };
    g.mood = (m) => { mood = m; };
    g.pose = (name, t, p = {}) => pose(A, name, t, p);
    g.face = (t) => { const blink = (t + (o.seed ?? 0)) % 3.4 < 0.12; drawFace(fc, A.skin, mouth, blink, mood); ft.needsUpdate = true; };
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

  // a whole night street: road, sidewalks, lawns, a party house, a quiet house with a hoop, lamps, trees
  function world(o = {}) {
    const S = K3.stage("cgi", { shadows: true, bg: [0x0b1026, 0x1d2a55], fog: [0x141c3a, 30, 90] });
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
    const party = house(S, { party: true, color: 0xd9c9e8, roof: 0x3a2a5a }); party.position.set(-6, 0, -12); g.add(party);
    const h2 = house(S, { color: 0xe8d8b0, lit: true }); h2.position.set(6, 0, -12); g.add(h2);
    const h3 = house(S, { color: 0xc8dce8, roof: 0x2a4a6a, lit: true }); h3.position.set(-18, 0, -12); g.add(h3);
    const home = house(S, { color: 0xf0e2c8, roof: 0x6a3a22, lit: true }); home.position.set(8, 0, 13); home.rotation.y = Math.PI; g.add(home);
    const h5 = house(S, { color: 0xd8e8c8, roof: 0x3a5a2a }); h5.position.set(-8, 0, 13); h5.rotation.y = Math.PI; g.add(h5);
    const drive = boxM(S, 4, 0.04, 6, 0x6a6a68, { cast: false }); drive.position.set(4, 0.03, 8.5); g.add(drive);
    const hp = hoop(S); hp.position.set(4, 0, 11.6); hp.rotation.y = Math.PI; g.add(hp);
    const lamps = [];
    for (const [x, z, r] of [[-12, -6, 0], [12, -6, 0], [0, 6, Math.PI], [16, 6, Math.PI]]) { const l = lamp(S); l.position.set(x, 0, z); l.rotation.y = r; g.add(l); lamps.push(l); }
    for (const [x, z, k] of [[-12, -16, 1.2], [14, -15, 1], [-2, 16, 1.1], [16, 14, 1.3], [-24, -10, 1.1], [24, 12, 1.2]]) { const tr = tree(S, k); tr.position.set(x, 0, z); g.add(tr); }
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
      S.sun.intensity = lerp(0.35, 2.6, k); S.sun.color.copy(k < 0.6 ? mix(0x8aa0ff, 0xffb070, k / 0.6) : mix(0xffb070, 0xffffff, (k - 0.6) / 0.4));
      S.sun.position.set(lerp(-14, 10, k), lerp(10, 18, k), lerp(-8, 8, k));
      S.scene.children.forEach((c) => { if (c.isHemisphereLight) c.intensity = lerp(0.35, 1.2, k); });
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

  // a basketball shot: ball flies from hands to the rim and drops through
  function arc(ballMesh, from, to, k) {
    k = clamp(k);
    const h = 3.2;
    ballMesh.position.set(lerp(from[0], to[0], k), lerp(from[1], to[1], k) + Math.sin(k * Math.PI) * h, lerp(from[2], to[2], k));
    ballMesh.rotation.x = k * 12;
  }

  Object.assign(K3, { avatar, ball, house, lamp, tree, hoop, world, shot, arc });
})();
