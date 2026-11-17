// Motor "pieza por pieza": escena 3D determinista controlada por línea de tiempo.
// renderFrame(t) deja la escena exactamente en el estado del segundo t (sin depender del reloj).
import * as THREE from 'three';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';

export const PAL = {
  cream: '#ece7da', paper: '#f4f1e8', gray: '#b9b7c4', dark: '#2b2d42', ink: '#14151f',
  lime: '#cdf23a', red: '#ff4a36', blue: '#3d4cff', sky: '#9fd4ff', pcb: '#2f7a5c', silicon: '#4a4f73',
  alu: '#d7dbe3',
};

// ---------- easing ----------
export const E = {
  linear: x => x,
  out: x => 1 - Math.pow(1 - x, 3),
  inOut: x => (x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  back: x => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); },
  bounce: x => {
    const n = 7.5625, d = 2.75;
    if (x < 1 / d) return n * x * x;
    if (x < 2 / d) return n * (x -= 1.5 / d) * x + .75;
    if (x < 2.5 / d) return n * (x -= 2.25 / d) * x + .9375;
    return n * (x -= 2.625 / d) * x + .984375;
  },
};
const clamp01 = x => Math.max(0, Math.min(1, x));
const lerp = (a, b, k) => a + (b - a) * k;

// ---------- stage ----------
export class Stage {
  constructor(canvas, W = 1080, H = 1920) {
    this.W = W; this.H = H;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
    this.renderer.setSize(W, H, false);
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.scene = new THREE.Scene();
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -2000, 4000);
    this.nodes = []; this.hooks = []; this.camKeys = []; this.sfx = []; this.caps = [];
    this.cam0 = { zoom: 1, tx: 0, ty: 0, tz: 0, az: 40, el: 30, size: 12 };

    const g = new Uint8Array([90, 170, 255]);
    this.grad = new THREE.DataTexture(g, 3, 1, THREE.RedFormat);
    this.grad.minFilter = this.grad.magFilter = THREE.NearestFilter; this.grad.needsUpdate = true;

    this.scene.add(new THREE.AmbientLight(0xffffff, 1.1));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2);
    sun.position.set(-30, 60, 25); sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -40, right: 40, top: 40, bottom: -40, near: 1, far: 300 });
    this.sun = sun; this.scene.add(sun); this.scene.add(sun.target);

    const ground = new THREE.Mesh(new THREE.PlaneGeometry(4000, 4000),
      new THREE.ShadowMaterial({ color: 0x1a1f8a, opacity: 0.55 }));
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; this.scene.add(ground);

    this.unitBox = new THREE.BoxGeometry(1, 1, 1);
    this.unitBoxEdges = new LineSegmentsGeometry().fromEdgesGeometry(new THREE.EdgesGeometry(this.unitBox));
    this.lineMats = [];
  }

  mat(color, opacity = 1, emissive = 0x000000) {
    return new THREE.MeshToonMaterial({ color, gradientMap: this.grad, transparent: opacity < 1, opacity, emissive, depthWrite: opacity >= 1 });
  }
  lineMat(color = PAL.ink, width = 3, opacity = 1) {
    const m = new LineMaterial({ color, linewidth: width, transparent: true, opacity });
    m.resolution.set(this.W, this.H); this.lineMats.push(m); return m;
  }

  // Nodo genérico con pistas de animación (posición, escala, opacidad, rotación)
  node(obj3d, { pos = [0, 0, 0], scale = [1, 1, 1], parent = null, ry = 0 } = {}) {
    const holder = new THREE.Group(); holder.add(obj3d);
    (parent ? parent.g : this.scene).add(holder);
    const n = { g: holder, inner: obj3d, init: { px: pos[0], py: pos[1], pz: pos[2], sx: scale[0], sy: scale[1], sz: scale[2], op: 1, ry }, keys: [], mats: [] };
    obj3d.traverse(o => { if (o.material) n.mats.push({ m: o.material, base: o.material.opacity, keep: o.material.transparent && o.material.opacity >= 1 }); });
    n.to = (t, dur, vals, ease = E.inOut) => { n.keys.push({ t, dur, vals, ease }); n.keys.sort((a, b) => a.t - b.t); return n; };
    this.nodes.push(n); return n;
  }

  // Caja con contorno de tinta. size = [ancho, alto, fondo]; pos = centro de la BASE
  box({ size = [1, 1, 1], pos = [0, 0, 0], color = PAL.cream, opacity = 1, edge = PAL.ink, ew = 3, parent = null, shadow = true, emissive = 0 }) {
    const grp = new THREE.Group();
    const mesh = new THREE.Mesh(this.unitBox, this.mat(color, opacity, emissive));
    mesh.castShadow = shadow && opacity > 0.5; mesh.receiveShadow = true;
    mesh.scale.set(...size); mesh.position.y = size[1] / 2;
    grp.add(mesh);
    if (edge) {
      const l = new LineSegments2(this.unitBoxEdges, this.lineMat(edge, ew, Math.min(1, opacity + 0.35)));
      l.scale.copy(mesh.scale); l.position.copy(mesh.position); grp.add(l);
    }
    const n = this.node(grp, { pos, parent }); n.mesh = mesh; return n;
  }

  cyl({ r = 0.5, h = 1, pos = [0, 0, 0], color = PAL.cream, opacity = 1, seg = 24, parent = null, axis = 'y', edge = PAL.ink }) {
    const grp = new THREE.Group();
    const geo = new THREE.CylinderGeometry(r, r, h, seg);
    const mesh = new THREE.Mesh(geo, this.mat(color, opacity)); mesh.castShadow = opacity > .5;
    grp.add(mesh);
    if (edge) grp.add(new LineSegments2(new LineSegmentsGeometry().fromEdgesGeometry(new THREE.EdgesGeometry(geo, 30)), this.lineMat(edge, 3, Math.min(1, opacity + .35))));
    grp.children.forEach(c => { if (axis === 'y') c.position.y = h / 2; if (axis === 'x') c.rotation.z = Math.PI / 2; if (axis === 'z') c.rotation.x = Math.PI / 2; });
    const n = this.node(grp, { pos, parent }); n.mesh = mesh; return n;
  }

  sphere({ r = .2, pos = [0, 0, 0], color = PAL.blue, parent = null }) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), this.mat(color));
    m.castShadow = true;
    return this.node(m, { pos, parent });
  }

  group({ pos = [0, 0, 0], parent = null } = {}) { return this.node(new THREE.Group(), { pos, parent }); }

  // ---- texto pintado en una superficie (CanvasTexture). face: 'front' (+z) | 'top' (+y) | 'right' (+x)
  label({ text = '', w = 2, h = .6, pos = [0, 0, 0], face = 'front', parent = null, bg = null, fg = PAL.ink, size = 0.62, align = 'center' }) {
    const px = 256, cv = document.createElement('canvas');
    cv.width = Math.round(px * w); cv.height = Math.round(px * h);
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
    const draw = s => {
      const c = cv.getContext('2d'); c.clearRect(0, 0, cv.width, cv.height);
      if (bg) { c.fillStyle = bg; c.fillRect(0, 0, cv.width, cv.height); }
      c.fillStyle = fg; c.font = `700 ${Math.round(cv.height * size)}px SG, sans-serif`;
      c.textBaseline = 'middle'; c.textAlign = align;
      c.fillText(s, align === 'center' ? cv.width / 2 : cv.height * .2, cv.height * .54);
      tex.needsUpdate = true;
    };
    draw(text);
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false }));
    if (face === 'top') m.rotation.x = -Math.PI / 2;
    if (face === 'right') m.rotation.y = Math.PI / 2;
    m.renderOrder = 2;
    const n = this.node(m, { pos, parent }); n.setText = s => { if (n._txt !== s) { n._txt = s; draw(s); } }; n._txt = text;
    return n;
  }

  // Caja con texto en su cara frontal (tokens, archivos, etiquetas)
  tag({ text, size = [1.2, .5, .5], pos = [0, 0, 0], color = PAL.cream, fg = PAL.ink, parent = null, ew = 2, ts = .62 }) {
    const n = this.box({ size, pos, color, parent, ew });
    n.lab = this.label({ text, w: size[0] * .96, h: size[1] * .9, pos: [0, size[1] / 2, size[2] / 2 + .012], parent: n, fg, size: ts });
    return n;
  }

  // Tubo/cable entre dos puntos
  tube({ from, to, r = .08, color = PAL.dark, parent = null, opacity = 1 }) {
    const a = new THREE.Vector3(...from), b = new THREE.Vector3(...to), len = a.distanceTo(b);
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, 12), this.mat(color, opacity));
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    mesh.castShadow = true;
    const mid = a.clone().add(b).multiplyScalar(.5);
    const n = this.node(mesh, { pos: [mid.x, mid.y, mid.z], parent }); n.mesh = mesh; return n;
  }

  // Cúpula transparente con malla (barrera)
  dome({ r = 5, pos = [0, 0, 0], color = PAL.lime, opacity = .1, parent = null }) {
    const grp = new THREE.Group();
    const geo = new THREE.SphereGeometry(r, 28, 10, 0, Math.PI * 2, 0, Math.PI / 2);
    const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide }));
    grp.add(mesh);
    const wire = new LineSegments2(new LineSegmentsGeometry().fromEdgesGeometry(new THREE.EdgesGeometry(geo, 1)), this.lineMat(color, 2, .55));
    grp.add(wire);
    const n = this.node(grp, { pos, parent }); n.mesh = mesh; return n;
  }

  // Flujo de partículas en arco entre puntos. from/to: lista de puntos (se reparten entre partículas)
  flow({ from, to, count = 16, t0, t1, rate = .8, r = .08, color = PAL.blue, arc = 1, shape = 'sphere', fadeEnds = true }) {
    const geo = shape === 'cube' ? this.unitBox : new THREE.SphereGeometry(1, 10, 8);
    const ps = [];
    for (let i = 0; i < count; i++) {
      const m = new THREE.Mesh(geo, this.mat(color, 1, new THREE.Color(color).multiplyScalar(.35)));
      m.scale.setScalar(shape === 'cube' ? r * 1.6 : r); m.visible = false; this.scene.add(m);
      ps.push({ m, a: from[i % from.length], b: to[(i * 7) % to.length], ph: (i * .618) % 1 });
    }
    const rr = shape === 'cube' ? r * 1.6 : r;
    this.onFrame(t => {
      for (const p of ps) {
        p.m.visible = t > t0 && t < t1;
        if (!p.m.visible) continue;
        const u = ((t - t0) * rate + p.ph) % 1, k = E.inOut(u);
        p.m.position.set(lerp(p.a[0], p.b[0], k), lerp(p.a[1], p.b[1], k) + Math.sin(u * Math.PI) * arc, lerp(p.a[2], p.b[2], k));
        p.m.scale.setScalar(rr * (fadeEnds ? Math.min(1, Math.sin(u * Math.PI) * 3) : 1) + 1e-4);
      }
    });
    return ps;
  }

  // Nota pequeña bajo el caption (aclaraciones) y tarjeta final con el nombre del canal
  note(t, dur, text) { (this.notes ||= []).push({ t, dur, text }); }
  brand(t, title, sub = '') { this.brandCard = { t, title, sub }; this.sfx.push({ t, type: 'ding' }); }

  // ---- animaciones de entrada (mantienen todo lo anterior: solo se agregan piezas) ----
  appear(n, t, how = 'drop', dur = 0.6, sfx = 'pop') {
    const i = n.init;
    if (how === 'drop') { const y = i.py; i.py = y + 6; i.op = 0; n.to(t, 0.01, { op: 1 }).to(t, dur, { py: y }, E.bounce); }
    if (how === 'pop') { const s = [i.sx, i.sy, i.sz]; i.sx = i.sy = i.sz = 0.001; n.to(t, dur, { sx: s[0], sy: s[1], sz: s[2] }, E.back); }
    if (how === 'grow') { const sy = i.sy; i.sy = 0.001; i.op = 0; n.to(t, .01, { op: 1 }).to(t, dur, { sy }, E.out); }
    if (how === 'fade') { i.op = 0; n.to(t, dur, { op: 1 }, E.out); }
    if (sfx) this.sfx.push({ t: t + (how === 'drop' ? dur * .35 : 0), type: sfx });
    return n;
  }

  onFrame(fn) { this.hooks.push(fn); }
  cam(t, dur, vals, ease = E.inOut) { this.camKeys.push({ t, dur, vals, ease }); this.camKeys.sort((a, b) => a.t - b.t); if (dur > .6) this.sfx.push({ t, type: 'whoosh', src: 'cam' }); }
  // Captions: texto con *clave* (lima) y !problema! (rojo)
  cap(t, dur, text) {
    this.caps.push({ t, dur, text });
    if (text.includes('!')) this.sfx.push({ t: t + 0.05 + text.split('!')[0].trim().split(/\s+/).filter(Boolean).length * 0.11, type: 'err', src: 'cap' });
    else if (/\*/.test(text)) this.sfx.push({ t: t + 0.05 + text.split('*')[0].trim().split(/\s+/).filter(Boolean).length * 0.11, type: 'ding', src: 'cap' });
  }

  evalTrack(init, keys, T) {
    const s = { ...init };
    for (const k of keys) {
      if (T <= k.t) break;
      const p = k.ease(clamp01((T - k.t) / Math.max(k.dur, 1e-4)));
      const from = { ...s };
      for (const key in k.vals) s[key] = lerp(from[key], k.vals[key], p);
    }
    return s;
  }

  // Mapa de tiempo: real (voz) -> nominal (animación). Lineal por tramos, un tramo por beat.
  setWarp(nom, real) { this.warp = { nom, real }; }
  toNominal(T) {
    if (!this.warp) return T;
    const { nom, real } = this.warp;
    for (let i = 0; i < real.length - 1; i++)
      if (T < real[i + 1]) return nom[i] + (T - real[i]) / (real[i + 1] - real[i]) * (nom[i + 1] - nom[i]);
    return nom[nom.length - 1] + (T - real[real.length - 1]);
  }

  renderFrame(Treal) {
    const T = this.toNominal(Treal);
    for (const n of this.nodes) {
      const s = this.evalTrack(n.init, n.keys, T);
      n.g.position.set(s.px, s.py, s.pz); n.g.scale.set(s.sx, s.sy, s.sz); n.g.rotation.y = s.ry;
      n.g.visible = s.op > 0.003 && s.sx * s.sy * s.sz > 1e-8;
      for (const { m, base, keep } of n.mats) {
        const o = base * s.op; m.opacity = o;
        const tr = keep || o < 0.999; if (m.transparent !== tr && !m.isLineMaterial) { m.transparent = tr; m.depthWrite = !tr; m.needsUpdate = true; }
      }
    }
    for (const h of this.hooks) h(T);
    // cámara isométrica (ortográfica) que orbita y hace zoom
    const c = this.evalTrack(this.cam0, this.camKeys, T);
    const half = c.size / 2, aspect = this.W / this.H;
    Object.assign(this.camera, { left: -half * aspect, right: half * aspect, top: half, bottom: -half });
    this.camera.updateProjectionMatrix();
    const az = THREE.MathUtils.degToRad(c.az), el = THREE.MathUtils.degToRad(c.el), R = 500;
    this.camera.position.set(c.tx + R * Math.cos(el) * Math.sin(az), c.ty + R * Math.sin(el), c.tz + R * Math.cos(el) * Math.cos(az));
    this.camera.lookAt(c.tx, c.ty, c.tz);
    const sc = Math.max(40, c.size * 1.2);
    Object.assign(this.sun.shadow.camera, { left: -sc, right: sc, top: sc, bottom: -sc, far: sc * 8 });
    this.sun.position.set(c.tx - sc * .8, sc * 2, c.tz + sc * .6); this.sun.target.position.set(c.tx, 0, c.tz);
    this.sun.shadow.camera.updateProjectionMatrix();
    this.renderer.render(this.scene, this.camera);
    this.renderCaps(T);
  }

  renderCaps(T) {
    const nt = document.getElementById('nota'), n = (this.notes || []).find(c => T >= c.t && T < c.t + c.dur);
    if (nt) { nt.textContent = n ? n.text : ''; nt.style.opacity = n ? Math.min(1, (T - n.t) / .25, (n.t + n.dur - T) / .2) : 0; }
    const bd = document.getElementById('brand'), b = this.brandCard;
    if (bd && b) {
      const k = clamp01((T - b.t) / .5);
      bd.innerHTML = `<div class="bt">${b.title}</div><div class="bs">${b.sub}</div>`;
      bd.style.opacity = k; bd.style.transform = `translateY(${(1 - E.out(k)) * 60}px) scale(${.8 + .2 * E.back(k)})`;
    }
    this._renderMainCap(T);
  }

  _renderMainCap(T) {
    const el = document.getElementById('cap');
    const c = this.caps.find(c => T >= c.t && T < c.t + c.dur);
    if (!c) { el.innerHTML = ''; el._id = null; return; }
    if (el._id !== c) {
      el._id = c;
      const words = []; let mode = '';
      for (const tok of c.text.match(/[*!]|[^*!\s]+|\s+/g)) {
        if (tok === '*') { mode = mode === 'k' ? '' : 'k'; continue; }
        if (tok === '!') { mode = mode === 'r' ? '' : 'r'; continue; }
        if (/^\s+$/.test(tok)) continue;
        if (/^[?.,:;…]+$/.test(tok) && words.length) { words[words.length - 1].t += tok; continue; }
        words.push({ t: tok, mode });
      }
      el.innerHTML = words.map(w => `<span class="w ${w.mode}">${w.t}</span>`).join(' ');
    }
    [...el.children].forEach((w, i) => {
      const k = clamp01((T - c.t - i * 0.11) / 0.18), out = clamp01((c.t + c.dur - T) / 0.12);
      const s = k <= 0 ? 0 : E.back(k);
      w.style.transform = `scale(${s}) translateY(${(1 - out) * -20}px)`; w.style.opacity = Math.min(k * 3, out);
    });
  }
}
