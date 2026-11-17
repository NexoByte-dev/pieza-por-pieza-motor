// Intérprete de guion.json → escena del motor.
// Un video nuevo ya no necesita JavaScript a mano: se escribe videos/<id>/guion.json
// y el episodio.js genérico (3 líneas) llama a construir(S, G).
// El formato completo está en MANUAL.md.
import * as THREE from 'three';
import { PAL, E } from '../engine.js';
import * as C from './componentes.js';

const color = c => (c == null ? undefined : (PAL[c] || c));
const lista = x => (Array.isArray(x) ? x : [x]);
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, k) => a + (b - a) * k;
const KRAFT = '#ffd27a';
const COMPONENTES = new Set(['memoria', 'modelo', 'ficha', 'bits', 'bloques']);   // no reciben parent: se reparentan después

// Tiempos nominales: cada beat empieza donde termina el anterior.
export function inicios(G) {
  const t = [0];
  for (const b of G.beats) t.push(t[t.length - 1] + b.dur);
  return t;   // largo = beats + 1 (el último es la duración nominal)
}
export function duracion(G) {
  if (G.tiempos && G.tiempos.real) return G.tiempos.real[G.tiempos.real.length - 1];
  return inicios(G).pop();
}

const CREAR = {
  caja: (S, p) => S.box(p),
  cilindro: (S, p) => S.cyl({ ...p, axis: p.eje || 'y' }),
  esfera: (S, p) => S.sphere(p),
  etiqueta: (S, p) => S.tag(p),
  texto: (S, p) => S.label(p),
  cable: (S, p) => S.tube({ ...p, from: p.de, to: p.a }),
  cupula: (S, p) => S.dome(p),
  grupo: (S, p) => S.group(p),
  memoria: (S, p) => C.memoria(S, p),
  modelo: (S, p) => C.modelo(S, p),
  ficha: (S, p) => C.ficha(S, p),
  bits: (S, p) => C.filaBits(S, p),
  bloques: (S, p) => C.bloquesModelo(S, p),
  // ---- vocabulario de los videos de archivos (NEXORA) ----
  carpeta: (S, p) => {            // carpeta plana con nombre encima
    const { w = 2.6, d = 1.8, color = KRAFT, text = '', fg = PAL.ink } = p;
    const n = S.box({ size: [w, .5, d], pos: p.pos, color, ew: 2.5, parent: p.parent });
    n.lab = S.label({ text, w: w * .92, h: .55, pos: [0, .52, d * .5 - .5], face: 'top', parent: n, fg, size: .52 });
    return n;
  },
  archivo: (S, p) => {            // cubo de archivo, con nombre opcional en la cara frontal
    const { s = .85, color = PAL.paper, text = '', ts = .6 } = p;
    const n = S.box({ size: [s, s * .8, s], pos: p.pos, color, ew: 2, parent: p.parent });
    if (text) n.lab = S.label({ text, w: s * .98, h: s * .46, pos: [0, s * .4, s / 2 + .012], parent: n, fg: PAL.ink, size: ts });
    return n;
  },
  candado: (S, p) => {
    const { k = 1, color = PAL.lime } = p, g = S.group({ pos: p.pos, parent: p.parent });
    S.box({ size: [.9 * k, .7 * k, .5 * k], pos: [0, 0, 0], color, ew: 2.5, parent: g });
    S.box({ size: [.13 * k, .5 * k, .13 * k], pos: [-.27 * k, .7 * k, 0], color: PAL.alu, ew: 2, parent: g });
    S.box({ size: [.13 * k, .5 * k, .13 * k], pos: [.27 * k, .7 * k, 0], color: PAL.alu, ew: 2, parent: g });
    S.box({ size: [.67 * k, .13 * k, .13 * k], pos: [0, 1.2 * k, 0], color: PAL.alu, ew: 2, parent: g });
    return g;
  },
  compu: (S, p) => {              // pantalla + base, con texto en la pantalla
    const { k = 1, text = '', color = PAL.dark } = p, g = S.group({ pos: p.pos, parent: p.parent });
    S.box({ size: [1.6 * k, .16 * k, 1.0 * k], pos: [0, 0, 0], color: PAL.alu, ew: 2.5, parent: g });
    S.box({ size: [.28 * k, .7 * k, .28 * k], pos: [0, .16 * k, -.1 * k], color: PAL.alu, ew: 2, parent: g });
    S.box({ size: [2.6 * k, 1.6 * k, .2 * k], pos: [0, .86 * k, -.1 * k], color, ew: 2.5, parent: g });
    if (text) S.label({ text, w: 2.4 * k, h: .7 * k, pos: [0, 1.66 * k, .1 * k + .012], parent: g, fg: PAL.lime, size: .55 });
    return g;
  },
  foto: (S, p) => {               // lámina con imagen (si "img" existe en /recursos_dibujos/) o un color de relleno
    const { w = 1.5, d = 1.1, img = null, color = PAL.sky } = p;
    const n = S.box({ size: [w, .1, d], pos: p.pos, color: PAL.paper, ew: 2, parent: p.parent });
    let mat;
    if (img) { const t = new THREE.TextureLoader().load('/recursos_dibujos/' + img); t.colorSpace = THREE.SRGBColorSpace; mat = new THREE.MeshBasicMaterial({ map: t }); }
    else mat = new THREE.MeshBasicMaterial({ color });
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w * .9, d * .9), mat);
    m.rotation.x = -Math.PI / 2; m.position.y = .105; n.inner.add(m);
    return n;
  },
};

export function construir(S, G) {
  const N = {};      // id → nodo animable
  const O = {};      // id → objeto completo del componente (memoria, bits…)
  if (G.camara) Object.assign(S.cam0, G.camara);

  for (const pz of G.piezas || []) {
    const { id, tipo, padre, ry, ...props } = pz;
    const f = CREAR[tipo];
    if (!f) throw new Error(`guion: tipo de pieza desconocido "${tipo}" (pieza "${id}")`);
    for (const k of ['color', 'fg', 'bg', 'edge']) if (k in props) props[k] = color(props[k]);
    if (padre) { if (!N[padre]) throw new Error(`guion: la pieza "${id}" usa un padre que no existe todavía: "${padre}"`); if (!COMPONENTES.has(tipo)) props.parent = N[padre]; }
    const o = f(S, props);
    O[id] = o;
    if (Array.isArray(o)) o.forEach((n, i) => { N[`${id}.${i}`] = n; });
    else N[id] = o.g && o.g.to ? o.g : o;
    if (padre && COMPONENTES.has(tipo) && N[id] && N[id].g) N[padre].g.add(N[id].g);   // los componentes no aceptan parent: se cuelgan después
    if (ry != null && N[id] && N[id].init) N[id].init.ry = ry;
  }

  // "a" → nodos. Acepta un id, una lista, o "id.*" (todas las partes de un componente de varias piezas).
  const nodos = ref => lista(ref).flatMap(r => {
    if (typeof r === 'string' && r.endsWith('.*')) {
      const pre = r.slice(0, -1), ks = Object.keys(N).filter(k => k.startsWith(pre));
      if (!ks.length) throw new Error(`guion: nada coincide con "${r}"`);
      return ks.map(k => N[k]);
    }
    if (!N[r]) throw new Error(`guion: no existe la pieza "${r}"`);
    return [N[r]];
  });
  // punto(s) para flujos: id de pieza (usa su posición), [x,y,z] o lista de puntos
  const puntos = ref => {
    if (typeof ref === 'string') { const i = N[ref].init; return [[i.px, i.py, i.pz]]; }
    return Array.isArray(ref[0]) ? ref : [ref];
  };

  const t0s = inicios(G);
  G.beats.forEach((b, i) => {
    const T = t0s[i];
    if (b.cap) {
      if (typeof b.cap === 'string') S.cap(T, b.dur - 0.05, b.cap);
      else for (const c of b.cap) S.cap(T + (c.en || 0), c.dur, c.texto);
    }
    for (const a of b.acciones || []) {
      const t = T + (a.en || 0), ease = E[a.ease] || E.inOut;
      if ('aparece' in a) {
        nodos(a.aparece).forEach((n, k) => S.appear(n, t + k * (a.escalon ?? 0.08), a.como || 'drop', a.dur ?? 0.6, a.sfx === undefined ? 'pop' : a.sfx));
      } else if ('mueve' in a) {
        nodos(a.mueve).forEach((n, k) => n.to(t + k * (a.escalon || 0), a.dur ?? 0.6, a.a, ease));
      } else if ('oculta' in a) {
        nodos(a.oculta).forEach(n => n.to(t, a.dur ?? 0.3, { op: 0 }, E.out));
      } else if ('cam' in a) {
        S.cam(t, a.dur ?? 1, a.cam, ease);
      } else if ('nota' in a) {
        S.note(t, a.dur ?? 2.5, a.nota);
      } else if ('flujo' in a) {
        const f = a.flujo;
        S.flow({ ...f, from: puntos(f.de), to: puntos(f.a), color: color(f.color) || PAL.blue, t0: t, t1: t + (a.dur ?? 2), shape: f.forma || 'sphere' });
      } else if ('brillo' in a) {
        const m = O[a.brillo], d = a.dur ?? 1.5;
        if (!m || !m.brillo) throw new Error(`guion: "brillo" solo funciona con piezas de tipo modelo ("${a.brillo}")`);
        S.onFrame(tt => { const u = (tt - t) / d; m.brillo(u > 0 && u < 1 ? Math.sin(u * Math.PI) : 0); });
      } else if ('quita_bits' in a) {
        O[a.quita_bits].quitar(t, a.desde, a.hasta);
      } else if ('texto' in a) {
        const n = N[a.texto], lab = n.setText ? n : (n.lab || (O[a.texto].tag && O[a.texto].tag.lab));
        if (!lab) throw new Error(`guion: la pieza "${a.texto}" no tiene texto`);
        const antes = lab._txt;
        S.onFrame(tt => { if (tt >= t) lab.setText(a.valor); else if (lab._txt === a.valor) lab.setText(antes); });
      } else if ('color' in a) {
        nodos(a.color).forEach(n => {
          if (!n.mesh) return;
          if (!n._colores) {                 // una sola lista por pieza: manda el último cambio ya ocurrido
            const base = '#' + n.mesh.material.color.getHexString(); n._colores = [];
            S.onFrame(tt => { let c = base; for (const k of n._colores) if (tt >= k.t) c = k.c; n.mesh.material.color.set(c); });
          }
          n._colores.push({ t, c: color(a.valor) }); n._colores.sort((x, y) => x.t - y.t);
        });
      } else if ('cuenta' in a) {      // número que sube de "de" a "a" en "dur" segundos, dentro de una etiqueta
        const n = N[a.cuenta], lab = n && n.lab, suf = a.sufijo || '', d = a.dur ?? 2;
        if (!lab) throw new Error(`guion: "cuenta" necesita una etiqueta (tipo etiqueta): "${a.cuenta}"`);
        S.onFrame(T => lab.setText(Math.round(lerp(a.de ?? 0, a.a, E.out(clamp((T - t) / d)))) + suf));
      } else if ('parpadea' in a) {    // alterna entre su color y "valor" durante "dur" segundos
        const ns = nodos(a.parpadea).filter(n => n.mesh), hz = a.hz || 4, cc = new THREE.Color(color(a.valor || 'red'));
        const base = ns.map(n => n.mesh.material.color.clone()), t1 = t + (a.dur ?? 2);
        S.onFrame(T => ns.forEach((n, i) => n.mesh.material.color.copy(T >= t && T < t1 && Math.floor((T - t) * hz) % 2 === 0 ? cc : base[i])));
      } else if ('marca' in a) {
        S.brand(t, a.marca, a.sub || '');
      } else if ('sfx' in a) {
        S.sfx.push({ t, type: a.sfx });
      } else {
        throw new Error(`guion: acción desconocida en el beat "${b.id}": ${JSON.stringify(a)}`);
      }
    }
  });

  if (G.tiempos && G.tiempos.real) S.setWarp(G.tiempos.nom, G.tiempos.real);
  return { N, O };
}
