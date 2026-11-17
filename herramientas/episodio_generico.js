// Episodio genérico: toda la animación sale de guion.json (ver MANUAL.md). No hace falta editar este archivo.
import { construir, duracion, inicios } from '/lib/guion.js';
const G = await (await fetch(new URL('./guion.json', import.meta.url).pathname + '?v=' + Date.now())).json();
export const meta = { duration: duracion(G) };
export const beats = inicios(G);
export function build(S) { return construir(S, G); }
