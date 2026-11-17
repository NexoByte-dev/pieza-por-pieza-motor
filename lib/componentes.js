// Biblioteca de Pieza por Pieza: componentes que conservan su identidad entre episodios.
// Cada función recibe el Stage (S) y devuelve un objeto con sus partes, para animarlas desde el episodio.
import * as THREE from 'three';
import { PAL, E } from '../engine.js';

export const BITS = { 16: PAL.sky, 8: PAL.lime, 4: '#ffb36b', 2: '#c9a0ff' };   // color = precisión, en todo el canal

// Textura "mosaico de números": representa parámetros sin fingir valores reales
export function mosaico(S, { w = 2, h = 1, seed = 1, cols = 12, rows = 6, palette = [PAL.sky, PAL.paper, PAL.gray, PAL.blue] } = {}) {
  const cv = document.createElement('canvas'); cv.width = 256; cv.height = Math.round(256 * h / w);
  const c = cv.getContext('2d'), cw = cv.width / cols, ch = cv.height / rows;
  const rnd = i => { const s = Math.sin((i + seed * 97) * 12.9898) * 43758.5453; return s - Math.floor(s); };
  for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
    c.fillStyle = palette[Math.floor(rnd(y * cols + x) * palette.length)];
    c.globalAlpha = .35 + rnd(y * 31 + x * 7) * .65; c.fillRect(x * cw + 1, y * ch + 1, cw - 2, ch - 2);
  }
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.magFilter = THREE.NearestFilter;
  return tex;
}

// ---------------------------------------------------------------------------------------------
// MEMORIA (RAM / VRAM): tanque transparente con regla en GB. La capacidad es literal: u unidades por GB.
export function memoria(S, { gb = 8, u = .8, pos = [0, 0, 0], ancho = 2.4, nombre = 'VRAM', placa = true, t = 0 } = {}) {
  const g = S.group({ pos });
  const base = placa ? .3 : 0;
  const parts = [];
  if (placa) {
    parts.push(S.box({ size: [ancho + 1.6, .3, ancho + 1.2], color: '#3a3d55', parent: g }));
    for (const x of [-1, 1]) parts.push(S.box({ size: [.5, .12, .7], pos: [x * (ancho / 2 + .45), .3, ancho / 2], color: PAL.dark, edge: null, parent: g }));
  }
  const tank = S.box({ size: [ancho, gb * u, ancho], pos: [0, base, 0], color: PAL.sky, opacity: .1, parent: g, shadow: false });
  parts.push(tank);
  const marks = [];
  for (let k = 1; k <= gb; k++) {
    const m = S.box({ size: [ancho + .04, .001, ancho + .04], pos: [0, base + k * u, 0], color: PAL.sky, opacity: 0, edge: k === gb ? PAL.paper : PAL.sky, ew: k === gb ? 3 : 1.5, parent: g, shadow: false });
    marks.push(m);
    if (k % 2 === 0) {
      const l = S.label({ text: k === gb ? `${k} GB` : `${k}`, w: 1.3, h: .42, pos: [ancho / 2 + .02, base + k * u - .22, ancho / 2 - .7], face: 'right', fg: k === gb ? PAL.paper : PAL.sky, parent: g, align: 'left' });
      marks.push(l);
    }
  }
  const tag = S.tag({ text: `${nombre} · ${gb} GB`, size: [ancho + .8, .5, .12], pos: [0, .02, ancho / 2 + .62], color: PAL.paper, parent: g, ts: .6 });
  parts.push(tag);
  return { g, tank, marks, tag, parts, base, u, gb, ancho, top: base + gb * u,
    entrar(t0) { S.appear(g, t0, 'pop', .5); } };
}

// ---------------------------------------------------------------------------------------------
// BLOQUES DE MODELO: n bloques de 1 GB (a la precisión inicial). Cada uno con su mosaico de parámetros.
export function bloquesModelo(S, { n = 16, u = .8, ancho = 2.2, pos = [0, 0, 0], color = BITS[16] } = {}) {
  const tex = [1, 2, 3, 4].map(s => mosaico(S, { w: ancho, h: u, seed: s }));
  const bl = [];
  for (let i = 0; i < n; i++) {
    const b = S.box({ size: [ancho, u * .96, ancho], pos: [pos[0], pos[1] + i * u, pos[2]], color, ew: 2 });
    const face = new THREE.Mesh(new THREE.PlaneGeometry(ancho * .92, u * .8), new THREE.MeshBasicMaterial({ map: tex[i % 4], transparent: true, opacity: .55, depthWrite: false }));
    face.position.set(0, u * .48, ancho / 2 + .01); b.inner.add(face);
    const face2 = face.clone(); face2.rotation.y = Math.PI / 2; face2.position.set(ancho / 2 + .01, u * .48, 0); b.inner.add(face2);
    bl.push(b);
  }
  return bl;
}

// ---------------------------------------------------------------------------------------------
// FILA DE BITS: un número visto de cerca. Cubos = bits; se quitan para cuantizar.
export function filaBits(S, { bits = 16, pos = [0, 0, 0], paso = .27, lado = .22, color = BITS[16], parent = null } = {}) {
  const g = S.group({ pos, parent });
  const cubos = [];
  for (let i = 0; i < bits; i++) {
    const c = S.box({ size: [lado, lado, lado], pos: [i * paso, 0, 0], color, ew: 1.5, parent: g });
    cubos.push(c);
  }
  return { g, cubos,
    quitar(t, desde, hasta) {                 // ej. quitar(t, 8, 16) → deja 8 bits
      for (let i = desde; i < hasta; i++) cubos[i].to(t + (hasta - 1 - i) * .04, .25, { sx: .001, sy: .001, sz: .001 }, E.inOut);
      for (let i = 0; i < 4; i++) S.sfx.push({ t: t + i * .08, type: 'tick' });
    } };
}

// ---------------------------------------------------------------------------------------------
// MODELO (LLM) como bloque: mosaico de parámetros en sus caras, nombre al frente y brillo al "pensar".
// Grande o pequeño: misma pieza, distinto tamaño. m.brillo(t) lo controla el episodio desde onFrame.
export function modelo(S, { lado = 4, pos = [0, 0, 0], nombre = 'modelo', color = PAL.paper, seed = 1 } = {}) {
  const n = S.box({ size: [lado, lado, lado], pos, color, ew: lado > 2 ? 3 : 2.5 });
  const tex = mosaico(S, { w: lado, h: lado, seed, cols: Math.round(6 + lado * 2), rows: Math.round(6 + lado * 2) });
  const caras = [];
  for (const [rx, ry, p] of [[0, 0, [0, lado / 2, lado / 2 + .01]], [0, Math.PI / 2, [lado / 2 + .01, lado / 2, 0]], [-Math.PI / 2, 0, [0, lado + .01, 0]]]) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(lado * .9, lado * .9), new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: .5, depthWrite: false }));
    m.rotation.set(rx, ry, 0); m.position.set(...p); n.inner.add(m); caras.push(m);
  }
  const tag = S.tag({ text: nombre, size: [Math.max(lado * .9, nombre.length * .2 + .4), .46, .1], pos: [0, .03, lado / 2 + .12], color: PAL.ink, fg: PAL.paper, parent: n, ts: .6 });
  const base = new THREE.Color(color), lima = new THREE.Color(PAL.lime);
  n.brillo = k => {                       // k: 0..1
    n.mesh.material.color.copy(base).lerp(lima, k * .55);
    n.mesh.material.emissive.setRGB(k * .35, k * .42, 0);
    caras.forEach(c => c.material.opacity = .5 + k * .45);
  };
  n.lado = lado; n.tag = tag;
  return n;
}

// FICHA DE TOKEN: caja con texto, ancho según el texto. Su color se puede cambiar (m.pintar).
export function ficha(S, { text, pos = [0, 0, 0], color = PAL.paper, alto = .56, fondo = .5 }) {
  const w = .36 + [...text].length * .19;
  const n = S.box({ size: [w, alto, fondo], pos, color, ew: 2 });
  n.lab = S.label({ text, w: w * .96, h: alto * .9, pos: [0, alto / 2, fondo / 2 + .012], parent: n, fg: PAL.ink, size: .64 });
  n.ancho = w; n.pintar = c => n.mesh.material.color.set(c);
  return n;
}
