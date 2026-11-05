// pro-editor /create 3D styles on three.js (bundled in vendor/, MIT). The renderer loads THREE
// before the scene runs; build on the first render() call.
//
//   let S;  window.render = (t, d) => {
//     S = S || K3.stage("lego");                 // ps2 | lego | cgi | toon
//     if (!S.car) { S.car = K3.car(S, 0xd8262c); S.scene.add(S.car); S.scene.add(K3.ground(S)); }
//     S.car.position.x = -6 + t * 3;
//     K3.orbit(S, t, d, {radius: 12, height: 4});  // a camera move, deterministic in t
//     S.draw();
//   };
//
// Presets:  ps2   low-res render scaled up with hard pixels, flat shading, fog, sunset sky
//           lego  bright plastic, studs on every brick, a green baseplate
//           cgi   physically based materials, soft shadows, filmic tone mapping, sky gradient
//           toon  soft cel shading with outlines and pastel light, like a 3D animated short
(function () {
  const PRE = {
    ps2: { res: 0.25, bg: [0xf2a65a, 0x6b3fa0], fog: [0xd98a6a, 18, 60], shade: "flat", shadows: false, ground: 0x6b6f5a },
    lego: { res: 1, bg: [0xbfe4ff, 0xeaf6ff], fog: null, shade: "plastic", shadows: true, ground: 0x2fa84f },
    cgi: { res: 1, bg: [0xcfd8e3, 0xf3efe9], fog: [0xe8e4de, 30, 90], shade: "pbr", shadows: true, ground: 0xb9b2a6 },
    toon: { res: 1, bg: [0x9fd3ff, 0xfde2c8], fog: [0xf7dcc8, 35, 100], shade: "toon", shadows: true, ground: 0x9ccf7f },
  };

  function stage(preset = "cgi", o = {}) {
    const T = window.THREE, P = { ...PRE[preset], ...o };
    if (!T) throw new Error("THREE isn't loaded");
    const W = window.innerWidth, H = window.innerHeight;
    const r = new T.WebGLRenderer({ antialias: preset !== "ps2", preserveDrawingBuffer: true });
    r.setPixelRatio(P.res);
    r.setSize(W, H);
    Object.assign(r.domElement.style, { position: "absolute", inset: 0, width: W + "px", height: H + "px",
      imageRendering: preset === "ps2" ? "pixelated" : "auto", zIndex: 0 });
    document.body.prepend(r.domElement);
    if (P.shadows) { r.shadowMap.enabled = true; r.shadowMap.type = T.PCFSoftShadowMap; }
    if (preset === "cgi") { r.toneMapping = T.ACESFilmicToneMapping; r.toneMappingExposure = 1.05; }
    r.outputColorSpace = T.SRGBColorSpace;
    const scene = new T.Scene();
    // vertical gradient sky
    const sky = document.createElement("canvas"); sky.width = 2; sky.height = 256;
    const g = sky.getContext("2d"), gr = g.createLinearGradient(0, 0, 0, 256);
    gr.addColorStop(0, "#" + P.bg[1].toString(16).padStart(6, "0")); gr.addColorStop(1, "#" + P.bg[0].toString(16).padStart(6, "0"));
    g.fillStyle = gr; g.fillRect(0, 0, 2, 256);
    const tex = new T.CanvasTexture(sky); tex.colorSpace = T.SRGBColorSpace; scene.background = tex;
    if (P.fog) scene.fog = new T.Fog(P.fog[0], P.fog[1], P.fog[2]);
    const camera = new T.PerspectiveCamera(o.fov || 38, W / H, 0.1, 400);
    camera.position.set(0, 4, 14);
    const hemi = new T.HemisphereLight(0xffffff, preset === "ps2" ? 0x553355 : 0x667788, preset === "toon" ? 1.6 : 1.1);
    scene.add(hemi);
    const sun = new T.DirectionalLight(preset === "ps2" ? 0xffc48a : 0xffffff, preset === "cgi" ? 2.4 : 1.8);
    sun.position.set(8, 14, 6);
    if (P.shadows) {
      sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
      Object.assign(sun.shadow.camera, { left: -20, right: 20, top: 20, bottom: -20, far: 60 });
      sun.shadow.radius = 4;
    }
    scene.add(sun);
    const S = { T, preset, P, renderer: r, scene, camera, sun, draw: () => r.render(scene, camera) };
    return S;
  }

  // a material in the preset's language
  function mat(S, color, o = {}) {
    const T = S.T;
    switch (S.P.shade) {
      case "flat": return new T.MeshLambertMaterial({ color, flatShading: true });
      case "plastic": return new T.MeshStandardMaterial({ color, roughness: 0.28, metalness: 0.0 });
      case "toon": {
        if (!S._grad) {
          const d = new Uint8Array([90, 170, 255]);
          S._grad = new T.DataTexture(d, 3, 1, T.RedFormat); S._grad.needsUpdate = true;
          S._grad.minFilter = S._grad.magFilter = T.NearestFilter;
        }
        return new T.MeshToonMaterial({ color, gradientMap: S._grad });
      }
      default: return new T.MeshPhysicalMaterial({ color, roughness: o.rough ?? 0.35, metalness: o.metal ?? 0.1,
        clearcoat: o.coat ?? 0.6, clearcoatRoughness: 0.15 });
    }
  }

  function mesh(S, geo, color, o = {}) {
    const m = new S.T.Mesh(geo, mat(S, color, o));
    m.castShadow = m.receiveShadow = !!S.P.shadows;
    if (S.preset === "toon" && o.outline !== false) {   // inverted hull outline
      const ol = new S.T.Mesh(geo, new S.T.MeshBasicMaterial({ color: 0x2a2233, side: S.T.BackSide }));
      ol.scale.setScalar(1.04); m.add(ol);
    }
    return m;
  }

  // a brick (lego) or a plain box elsewhere
  function block(S, w, h, d, color) {
    const T = S.T, g = new T.Group();
    const b = mesh(S, new T.BoxGeometry(w, h, d), color);
    g.add(b);
    if (S.preset === "lego") {
      const stud = new T.CylinderGeometry(0.24, 0.24, 0.18, 20);
      for (let x = -w / 2 + 0.4; x < w / 2; x += 0.8) for (let z = -d / 2 + 0.4; z < d / 2; z += 0.8) {
        const s = mesh(S, stud, color); s.position.set(x, h / 2 + 0.09, z); g.add(s);
      }
    }
    return g;
  }

  // side profile of a sporty car (x forward, y up), shared with the 2D styles (ART.carProfile)
  const PROFILE = [[-2.15, 0.38], [2.1, 0.38], [2.2, 0.72], [2.0, 0.98], [0.75, 1.1], [0.0, 1.72], [-1.25, 1.74],
    [-1.95, 1.18], [-2.2, 1.05]];
  const WINDOW = [[0.55, 1.14], [-0.05, 1.64], [-1.2, 1.66], [-1.72, 1.17]];

  function extrude(T, pts, depth, bevel) {
    const s = new T.Shape(); pts.forEach(([x, y], i) => (i ? s.lineTo(x, y) : s.moveTo(x, y)));
    const g = new T.ExtrudeGeometry(s, { depth, bevelEnabled: bevel > 0, bevelSize: bevel, bevelThickness: bevel, bevelSegments: 4, curveSegments: 8 });
    g.translate(0, 0, -depth / 2); g.computeVertexNormals();
    return g;
  }

  function car(S, color = 0xd8262c) {
    const T = S.T, g = new T.Group();
    const lego = S.preset === "lego";
    if (lego) {
      const body = block(S, 4.0, 0.8, 1.6, color); body.position.y = 0.85; g.add(body);
      const cab = block(S, 2.0, 0.8, 1.6, color); cab.position.set(-0.3, 1.65, 0); g.add(cab);
      const glass = mesh(S, new T.BoxGeometry(0.1, 0.6, 1.4), 0x9fd8ff, { outline: false }); glass.position.set(0.72, 1.62, 0); g.add(glass);
    } else {
      g.add(mesh(S, extrude(T, PROFILE, 1.6, S.preset === "ps2" ? 0 : 0.14), color));
      const glassC = S.preset === "ps2" ? 0x3df2ff : S.preset === "toon" ? 0x6f8fb3 : 0x10161f;
      g.add(mesh(S, extrude(T, WINDOW, 1.66, S.preset === "ps2" ? 0 : 0.06), glassC, { rough: 0.05, metal: 0.4, coat: 1, outline: false }));
    }
    const segs = S.preset === "ps2" ? 8 : 32;
    const tyre = new T.CylinderGeometry(0.46, 0.46, 0.36, segs), hub = new T.CylinderGeometry(0.24, 0.24, 0.38, segs);
    g.wheels = [];
    for (const [x, z] of [[-1.35, 0.82], [1.4, 0.82], [-1.35, -0.82], [1.4, -0.82]]) {
      const w = new T.Group();
      w.add(mesh(S, tyre, 0x17171b, { rough: 0.85, coat: 0 }));
      const h = mesh(S, hub, lego ? 0xdddddd : 0xb8bcc4, { metal: 0.8, rough: 0.3, outline: false }); w.add(h);
      w.rotation.x = Math.PI / 2; w.position.set(x, 0.46, z); g.add(w); g.wheels.push(w);
    }
    for (const z of [0.52, -0.52]) {        // headlights
      const l = new T.Mesh(new T.SphereGeometry(0.12, 12, 8), new T.MeshBasicMaterial({ color: 0xfff1c1 }));
      l.position.set(2.15, 0.82, z); g.add(l);
    }
    g.spin = (t, speed = 1) => g.wheels.forEach((w) => (w.rotation.y = -t * 8 * speed));
    return g;
  }

  function rounded(T, w, h, d, r) {
    const s = new T.Shape(), x = -w / 2, y = -h / 2;
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
    s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r); s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    const g = new T.ExtrudeGeometry(s, { depth: d, bevelEnabled: true, bevelSize: 0.08, bevelThickness: 0.08, bevelSegments: 3 });
    g.translate(0, 0, -d / 2);
    return g;
  }

  function ground(S, size = 80) {
    const T = S.T;
    if (S.preset === "lego") return block(S, 24, 0.3, 12, S.P.ground);
    const m = mesh(S, new T.PlaneGeometry(size, size, S.preset === "ps2" ? 8 : 1, S.preset === "ps2" ? 8 : 1), S.P.ground, { outline: false, rough: 0.9, coat: 0 });
    m.rotation.x = -Math.PI / 2;
    return m;
  }

  // simple city: rows of boxes/bricks behind the action
  function city(S, seed = 3) {
    const T = S.T, g = new T.Group();
    let s = seed;
    const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    const cols = { ps2: [0x5a4a7a, 0x7a5a8a, 0x3a3a5a], lego: [0xf2c12e, 0x2b6cd6, 0xd8262c, 0xffffff], cgi: [0xd9d4cc, 0xbfb7ab, 0xe8e2d8], toon: [0xf7b7a3, 0xa3d5f7, 0xf7e3a3] }[S.preset];
    for (let i = 0; i < 14; i++) {
      const w = 1.5 + r() * 2, h = 2 + r() * 7, d = 1.5 + r() * 2;
      const b = S.preset === "lego" ? block(S, Math.round(w / 0.8) * 0.8, Math.round(h / 0.96) * 0.96, 1.6, cols[i % cols.length])
                                     : mesh(S, new T.BoxGeometry(w, h, d), cols[i % cols.length], { coat: 0, rough: 0.8 });
      b.position.set(-16 + i * 2.4 + r(), h / 2, -6 - r() * 8);
      g.add(b);
    }
    return g;
  }

  // a camera move: arc around the target, deterministic in t
  function orbit(S, t, d, o = {}) {
    const tall = window.innerHeight > window.innerWidth;
    const a = (o.start ?? -0.5) + (o.sweep ?? 0.9) * (t / d), R = o.radius ?? (tall ? 17 : 12);
    S.camera.position.set(Math.sin(a) * R + (o.x ?? 0), o.height ?? 3.5, Math.cos(a) * R);
    S.camera.lookAt(o.tx ?? 0, o.ty ?? 1.2, o.tz ?? 0);
  }

  window.K3 = { PROFILE, WINDOW, stage, mat, mesh, block, car, ground, city, orbit, presets: Object.keys(PRE) };
})();
