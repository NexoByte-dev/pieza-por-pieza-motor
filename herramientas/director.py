#!/usr/bin/env python3
"""Director de Pieza por Pieza: un comando por etapa, o todo de una vez.

  python3 herramientas/director.py nuevo   <id>     crea videos/<id>/ con un guion de plantilla
  python3 herramientas/director.py validar <id>     revisa guion.json (errores claros, sin renderizar)
  python3 herramientas/director.py voz     <id>     genera la voz por beat y calcula los tiempos reales
  python3 herramientas/director.py mezcla  <id>     voz + efectos (+ música) → audio.flac y video.json
  python3 herramientas/director.py render  <id>     MP4 con el motor (usa renderizar.sh)
  python3 herramientas/director.py hoja    <id>     hoja de contactos: 1 imagen con un cuadro por beat
  python3 herramientas/director.py cortes  <id>     recorta los Shorts definidos en "cortes"
  python3 herramientas/director.py todo    <id>     validar → voz → mezcla → render → hoja → cortes

Versión realista con Blender (después de "todo"; funciona también con episodios viejos escritos a mano):
  python3 herramientas/director.py horno    <id>    exporta la animación → salida/<id>.bake.json
  python3 herramientas/director.py blender  <id>    renderiza los cuadros en Blender → salida/blender/<id>/
  python3 herramientas/director.py componer <id>    cuadros de Blender + textos + audio → salida/…_blender.mp4
  python3 herramientas/director.py realista <id>    horno → blender → componer
  Prueba rápida de 2 cuadros:  BL="--cuadros 60,300 --escala 50" python3 herramientas/director.py blender <id>

Solo usa la biblioteca estándar de Python + ffmpeg. Pillow es opcional (rotula la hoja de contactos).
Configuración en kit.json (raíz del repo). Formato del guion: MANUAL.md.
"""
import array, hashlib, json, math, os, random, shlex, subprocess, sys, wave

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
CFG_DEF = {
    "tts": "",              # ej.: "piper --model voces/es.onnx --output_file {salida}"  (el texto entra por stdin)
                            #      o con {texto} dentro del comando si tu TTS lo recibe como argumento
    "pausa": 0.35,          # silencio después de cada frase (s)
    "vol_sfx": 0.5, "vol_musica": 0.12, "musica": "",
    "gpu": sys.platform == "darwin",   # GPU=1 al renderizar (solo Mac por defecto: en Linux ARM el Chromium con GPU pinta mal)
    "blender": "blender",   # ruta al ejecutable de Blender
    "blender_args": "",     # opciones fijas para blender/render_blender.py, ej.: "--muestras 96"
}
TIPOS = {"caja", "cilindro", "esfera", "etiqueta", "texto", "cable", "cupula", "grupo",
         "memoria", "modelo", "ficha", "bits", "bloques",
         "carpeta", "archivo", "candado", "compu", "foto"}
ACCIONES = {"aparece", "mueve", "oculta", "cam", "nota", "flujo", "brillo", "quita_bits", "texto", "color", "marca", "sfx", "cuenta", "parpadea"}
COMO = {"drop", "pop", "grow", "fade"}
EASES = {"linear", "out", "inOut", "back", "bounce"}
PISTAS = {"px", "py", "pz", "sx", "sy", "sz", "op", "ry"}
CAM = {"zoom", "tx", "ty", "tz", "az", "el", "size"}


def cfg():
    c = dict(CFG_DEF)
    p = os.path.join(RAIZ, "kit.json")
    if os.path.exists(p):
        c.update(json.load(open(p, encoding="utf-8")))
    return c


def carpeta(vid):
    return os.path.join(RAIZ, "videos", vid)


def leer(vid):
    p = os.path.join(carpeta(vid), "guion.json")
    if not os.path.exists(p):
        sys.exit(f"✘ no existe {p}  (crealo con: director.py nuevo {vid})")
    try:
        return json.load(open(p, encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"✘ guion.json no es JSON válido: línea {e.lineno}, columna {e.colno}: {e.msg}")


def guardar(vid, G):
    with open(os.path.join(carpeta(vid), "guion.json"), "w", encoding="utf-8") as f:
        json.dump(G, f, ensure_ascii=False, indent=2)
        f.write("\n")


def inicios(G):
    t = [0.0]
    for b in G["beats"]:
        t.append(t[-1] + b["dur"])
    return t


def a_real(G, tn):
    """nominal → real (inversa del warp del motor)."""
    tm = G.get("tiempos")
    if not tm:
        return tn
    nom, real = tm["nom"], tm["real"]
    for i in range(len(nom) - 1):
        if tn < nom[i + 1]:
            return real[i] + (tn - nom[i]) / max(nom[i + 1] - nom[i], 1e-6) * (real[i + 1] - real[i])
    return real[-1] + (tn - nom[-1])


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


# ───────────────────────────── validar ─────────────────────────────
def validar(vid, G=None, callar=False):
    G = G or leer(vid)
    err, avi = [], []
    for k in ("titulo", "beats"):
        if k not in G:
            err.append(f"falta la clave \"{k}\" en la raíz")
    ids, tipo_de = set(), {}
    for i, p in enumerate(G.get("piezas", [])):
        donde = f"piezas[{i}]"
        pid = p.get("id")
        if not pid:
            err.append(f"{donde}: falta \"id\""); continue
        donde = f"pieza \"{pid}\""
        if pid in ids:
            err.append(f"{donde}: id repetido")
        if p.get("tipo") not in TIPOS:
            err.append(f"{donde}: tipo \"{p.get('tipo')}\" no existe. Tipos: {', '.join(sorted(TIPOS))}")
        if p.get("padre") and p["padre"] not in ids:
            err.append(f"{donde}: el padre \"{p['padre']}\" debe definirse antes")
        if p.get("tipo") in ("etiqueta", "texto", "ficha") and "text" not in p:
            err.append(f"{donde}: falta \"text\"")
        if p.get("tipo") == "cable" and not ("de" in p and "a" in p):
            err.append(f"{donde}: un cable necesita \"de\" y \"a\" ([x,y,z])")
        for k in ("pos", "size"):
            if k == "size" and p.get("tipo") not in ("caja", "etiqueta"):
                continue          # en texto/archivo/foto "size" no es una caja
            if k in p and not (isinstance(p[k], list) and len(p[k]) == 3):
                err.append(f"{donde}: \"{k}\" debe ser [x, y, z]")
        ids.add(pid); tipo_de[pid] = p.get("tipo")

    def existe(ref, donde):
        for r in (ref if isinstance(ref, list) else [ref]):
            base = r[:-2] if isinstance(r, str) and r.endswith(".*") else r
            if isinstance(r, str) and r.endswith(".*"):
                if tipo_de.get(base) != "bloques":
                    err.append(f"{donde}: \"{r}\" solo sirve con piezas de tipo bloques")
            elif isinstance(r, str) and "." in r and r.split(".")[0] in ids:
                pass
            elif r not in ids:
                err.append(f"{donde}: no existe la pieza \"{r}\"")

    bids, aparecidas = set(), {}
    for i, b in enumerate(G.get("beats", [])):
        bid = b.get("id") or f"#{i}"
        donde = f"beat \"{bid}\""
        if "id" not in b:
            err.append(f"beats[{i}]: falta \"id\"")
        if bid in bids:
            err.append(f"{donde}: id repetido")
        bids.add(bid)
        d = b.get("dur")
        if not isinstance(d, (int, float)) or d <= 0:
            err.append(f"{donde}: \"dur\" debe ser un número > 0"); d = 1
        cap = b.get("cap")
        if isinstance(cap, str):
            if cap.count("*") % 2 or cap.count("!") % 2:
                err.append(f"{donde}: en \"cap\" los * y ! van en pares (*clave*, !problema!)")
            n = len(cap.replace("*", "").replace("!", "").split())
            if n > 7:
                avi.append(f"{donde}: el caption tiene {n} palabras (ideal ≤ 6; se lee en un vistazo)")
            if d < 0.6 + n * 0.11 + 0.8:
                avi.append(f"{donde}: {d}s es poco para leer {n} palabras en pantalla")
        voz = b.get("voz", "")
        if voz and not G.get("tiempos"):
            nec = len(voz.split()) / 2.7
            if d < nec * 0.75:
                avi.append(f"{donde}: la voz ({len(voz.split())} palabras) dura ~{nec:.1f}s y el beat {d}s; la animación se estirará")
        for j, a in enumerate(b.get("acciones", [])):
            dd = f"{donde}, acción {j + 1}"
            ks = [k for k in a if k in ACCIONES]
            if len(ks) > 1 and "sfx" in ks:       # "sfx" también es una opción de "aparece"
                ks.remove("sfx")
            if len(ks) != 1:
                err.append(f"{dd}: debe tener exactamente una de: {', '.join(sorted(ACCIONES))} (tiene {ks or 'ninguna'})"); continue
            k = ks[0]
            if a.get("en", 0) < 0 or a.get("en", 0) > d:
                avi.append(f"{dd}: \"en\"={a.get('en')} cae fuera del beat (dura {d}s)")
            if "ease" in a and a["ease"] not in EASES:
                err.append(f"{dd}: ease \"{a['ease']}\" no existe ({', '.join(sorted(EASES))})")
            if k in ("cuenta", "parpadea"):
                existe(a[k], dd)
                if k == "cuenta" and "a" not in a:
                    err.append(f"{dd}: cuenta necesita \"a\" (número final)")
            if k in ("aparece", "mueve", "oculta", "color"):
                existe(a[k], dd)
            if k == "aparece":
                if a.get("como", "drop") not in COMO:
                    err.append(f"{dd}: como=\"{a.get('como')}\" no existe ({', '.join(sorted(COMO))})")
                for r in (a[k] if isinstance(a[k], list) else [a[k]]):
                    if r in aparecidas:
                        err.append(f"{dd}: \"{r}\" ya apareció en el beat \"{aparecidas[r]}\"; una pieza solo aparece una vez")
                    aparecidas[r] = bid
            if k == "mueve":
                malas = set(a.get("a", {})) - PISTAS
                if malas or not a.get("a"):
                    err.append(f"{dd}: \"a\" solo admite {', '.join(sorted(PISTAS))} (sobran: {sorted(malas)})")
            if k == "cam":
                malas = set(a["cam"]) - CAM
                if malas:
                    err.append(f"{dd}: cam solo admite {', '.join(sorted(CAM))} (sobran: {sorted(malas)})")
            if k == "brillo" and tipo_de.get(a[k]) != "modelo":
                err.append(f"{dd}: brillo solo funciona con piezas de tipo modelo")
            if k == "quita_bits":
                if tipo_de.get(a[k]) != "bits":
                    err.append(f"{dd}: quita_bits solo funciona con piezas de tipo bits")
                if not ("desde" in a and "hasta" in a):
                    err.append(f"{dd}: quita_bits necesita \"desde\" y \"hasta\"")
            if k == "texto":
                existe(a[k], dd)
                if "valor" not in a:
                    err.append(f"{dd}: falta \"valor\"")
            if k == "flujo":
                f = a[k]
                for e in ("de", "a"):
                    if e not in f:
                        err.append(f"{dd}: flujo necesita \"{e}\"")
                    elif isinstance(f[e], str):
                        existe(f[e], dd)
    for c in G.get("cortes", []):
        for e in ("desde", "hasta"):
            if c.get(e) not in bids:
                err.append(f"corte \"{c.get('nombre')}\": el beat \"{c.get(e)}\" no existe")
    if not callar or err:
        for a in avi:
            print("  aviso:", a)
        for e in err:
            print("  ✘", e)
    if err:
        sys.exit(f"✘ {vid}: {len(err)} error(es) en guion.json")
    if not callar:
        print(f"✔ {vid}: guion válido · {len(G['beats'])} beats · {inicios(G)[-1]:.1f}s nominales · {len(avi)} aviso(s)")
    return G


# ───────────────────────────── audio básico ─────────────────────────────
def leer_pcm(path):
    """Cualquier audio → array de int16 mono a 48 kHz (vía ffmpeg)."""
    r = run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], stdout=subprocess.PIPE)
    a = array.array("h"); a.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    return a


def escribir_wav(path, a):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())


def sumar(dest, src, t, vol=1.0):
    i0 = int(t * SR)
    if i0 < 0:
        return
    fin = min(len(dest), i0 + len(src))
    for i in range(i0, fin):
        v = dest[i] + int(src[i - i0] * vol)
        dest[i] = 32767 if v > 32767 else (-32768 if v < -32768 else v)


def _sfx(tipo):
    rnd = random.Random(7)
    def gen(dur, f):
        n = int(dur * SR)
        return array.array("h", (int(max(-1, min(1, f(i / SR, i / n))) * 30000) for i in range(n)))
    s, pi2 = math.sin, 2 * math.pi
    if tipo == "pop":
        return gen(0.12, lambda t, u: s(pi2 * (420 * t - 1100 * t * t)) * math.exp(-u * 5) * 0.9)
    if tipo == "ding":
        return gen(0.6, lambda t, u: (s(pi2 * 1318.5 * t) * 0.6 + s(pi2 * 1975.5 * t) * 0.3) * math.exp(-u * 6))
    if tipo == "err":
        return gen(0.3, lambda t, u: (1 if s(pi2 * 150 * t) > 0 else -1) * 0.28 * (1 if u < 0.42 or u > 0.55 else 0) * math.exp(-u * 1.5))
    if tipo == "tick":
        return gen(0.03, lambda t, u: s(pi2 * 2400 * t) * (1 - u) * 0.5)
    if tipo == "whoosh":
        est = [0.0]
        def w(t, u):
            est[0] += (rnd.uniform(-1, 1) - est[0]) * (0.04 + 0.25 * s(math.pi * u))
            return est[0] * s(math.pi * u) ** 2 * 1.6
        return gen(0.45, w)
    return gen(0.05, lambda t, u: 0)


def lista_sfx(G):
    """Mismas reglas que engine.js (appear, cam, cap, brand) y componentes.js (quitar). Tiempos nominales."""
    out, t0s = [], inicios(G)
    for b, T in zip(G["beats"], t0s):
        cap = b.get("cap")
        caps = [(T, cap)] if isinstance(cap, str) else [(T + c.get("en", 0), c["texto"]) for c in (cap or [])]
        for tc, tx in caps:
            for marca, tipo in (("!", "err"), ("*", "ding")):
                if marca in tx:
                    out.append((tc + 0.05 + len(tx.split(marca)[0].split()) * 0.11, tipo)); break
        for a in b.get("acciones", []):
            t = T + a.get("en", 0)
            if "aparece" in a:
                sf = a.get("sfx", "pop")
                if sf:
                    como, dur = a.get("como", "drop"), a.get("dur", 0.6)
                    refs = a["aparece"] if isinstance(a["aparece"], list) else [a["aparece"]]
                    for k in range(len(refs)):
                        out.append((t + k * a.get("escalon", 0.08) + (dur * 0.35 if como == "drop" else 0), sf))
            elif "cam" in a and a.get("dur", 1) > 0.6:
                out.append((t, "whoosh"))
            elif "marca" in a:
                out.append((t, "ding"))
            elif "quita_bits" in a:
                out += [(t + i * 0.08, "tick") for i in range(4)]
            elif "sfx" in a:
                out.append((t, a["sfx"]))
    return sorted(out)


# ───────────────────────────── voz ─────────────────────────────
def externo(vid):
    """Audio ya hecho (voz + música) que se usa tal cual: videos/<id>/audio_externo.(flac|wav|mp3|m4a|mp4|ogg)"""
    for ext in ("flac", "wav", "mp3", "m4a", "mp4", "ogg", "opus"):
        p = os.path.join(carpeta(vid), "audio_externo." + ext)
        if os.path.exists(p):
            return p
    return None


def voz(vid):
    if externo(vid):
        G = validar(vid, callar=True)
        G.pop("tiempos", None); guardar(vid, G)
        return print(f"✔ voz: se usa el audio externo ({os.path.basename(externo(vid))}); la animación sigue los tiempos del guion tal cual")
    G = validar(vid, callar=True); c = cfg(); d = carpeta(vid)
    vd = os.path.join(d, "voz"); os.makedirs(vd, exist_ok=True)
    nom, real, pista, sin_voz = inicios(G), [0.0], array.array("h"), []
    for b in G["beats"]:
        texto = b.get("voz", "").strip()
        wav = os.path.join(vd, b["id"] + ".wav")
        marca = os.path.join(vd, b["id"] + ".txt")
        if texto and c["tts"]:
            sello = hashlib.sha1((c["tts"] + "|" + texto).encode()).hexdigest()
            if not (os.path.exists(wav) and os.path.exists(marca) and open(marca).read() == sello):
                cmd = [x.replace("{salida}", wav).replace("{texto}", texto) for x in shlex.split(c["tts"])]
                print(f"  ▸ voz {b['id']}: {texto[:60]}")
                run(cmd, input=None if "{texto}" in c["tts"] else texto.encode(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                open(marca, "w").write(sello)
        if texto and os.path.exists(wav):      # generada o grabada a mano en voz/<beat>.wav
            pcm = leer_pcm(wav)
            dur = len(pcm) / SR + c["pausa"]
        else:
            pcm, dur = array.array("h"), b["dur"]
            if texto:
                sin_voz.append(b["id"])
        ini = int(real[-1] * SR)
        pista.extend([0] * max(0, ini - len(pista))); pista.extend(pcm)
        real.append(round(real[-1] + dur, 3))
    pista.extend([0] * max(0, int(real[-1] * SR) - len(pista)))
    escribir_wav(os.path.join(d, "voz.wav"), pista)
    G["tiempos"] = {"nom": [round(x, 3) for x in nom], "real": real}
    guardar(vid, G)
    if sin_voz:
        print(f"  aviso: sin voz en {len(sin_voz)} beat(s) ({', '.join(sin_voz[:6])}…). Configurá \"tts\" en kit.json o grabá videos/{vid}/voz/<beat>.wav")
    print(f"✔ voz: {real[-1]:.1f}s reales (nominal {nom[-1]:.1f}s) → voz.wav y tiempos en guion.json")


# ───────────────────────────── mezcla ─────────────────────────────
def escribir_video_json(vid, G):
    p = os.path.join(carpeta(vid), "video.json")
    V = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    dur = G["tiempos"]["real"][-1] if G.get("tiempos") else inicios(G)[-1]
    V.update({"orden": G.get("orden", V.get("orden", 99)), "titulo": G["titulo"], "duracion": round(dur, 2),
              "audio": "audio.flac", "salida": G.get("salida", f"pieza_por_pieza_{vid}.mp4")})
    V.setdefault("y", 560)
    if "tarjetas" in G:                      # tiempos de tarjetas: nominales en el guion → reales en video.json
        V["tarjetas"] = [{**t, "a": round(a_real(G, t["a"]), 2), "b": round(a_real(G, t["b"]), 2)} for t in G["tarjetas"]]
    V.setdefault("tarjetas", [])
    json.dump(V, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ep = os.path.join(carpeta(vid), "episodio.js")
    if not os.path.exists(ep):
        open(ep, "w", encoding="utf-8").write(open(os.path.join(RAIZ, "herramientas", "episodio_generico.js"), encoding="utf-8").read())
    return V


def mezcla(vid):
    G = validar(vid, callar=True); c = cfg(); d = carpeta(vid)
    V = escribir_video_json(vid, G)
    if externo(vid):
        out = os.path.join(d, "audio.flac")
        run(["ffmpeg", "-v", "error", "-y", "-i", externo(vid), "-vn", "-t", str(V["duracion"]), "-af", "apad", "-ac", "2", "-ar", str(SR), out])
        return print(f"✔ mezcla: audio.flac desde {os.path.basename(externo(vid))} (sin efectos ni música nuevos) y video.json actualizados")
    n = int(V["duracion"] * SR) + 1
    vz = os.path.join(d, "voz.wav")
    pista = leer_pcm(vz) if os.path.exists(vz) else array.array("h")
    pista = pista[:n]; pista.extend([0] * (n - len(pista)))
    cache, lista = {}, lista_sfx(G)
    for tn, tipo in lista:
        if tipo not in cache:
            cache[tipo] = _sfx(tipo)
        sumar(pista, cache[tipo], a_real(G, tn), c["vol_sfx"])
    tmp = os.path.join(d, "_mezcla.wav"); escribir_wav(tmp, pista)
    out = os.path.join(d, "audio.flac")
    mus = c["musica"] and os.path.join(RAIZ, c["musica"])
    for cand in ("musica.flac", "musica.mp3", "musica.wav"):
        if os.path.exists(os.path.join(d, cand)):
            mus = os.path.join(d, cand)
    if mus and os.path.exists(mus):
        fade = max(0, V["duracion"] - 1.5)
        run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-stream_loop", "-1", "-i", mus, "-filter_complex",
             f"[1:a]volume={c['vol_musica']},afade=t=out:st={fade}:d=1.5[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[o]",
             "-map", "[o]", "-ac", "2", "-ar", str(SR), out])
    else:
        run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-ac", "2", "-ar", str(SR), out])
    os.remove(tmp)
    print(f"✔ mezcla: audio.flac ({V['duracion']}s · {len(lista)} efectos{' · con música' if mus and os.path.exists(mus) else ''}) y video.json actualizados")


# ───────────────────────────── render / hoja / cortes ─────────────────────────────
def mp4(vid):
    V = json.load(open(os.path.join(carpeta(vid), "video.json"), encoding="utf-8"))
    return os.path.join(RAIZ, "salida", V["salida"])


def render(vid):
    G = validar(vid, callar=True)
    if not os.path.exists(os.path.join(carpeta(vid), "audio.flac")):
        mezcla(vid)
    else:
        escribir_video_json(vid, G)
    env = dict(os.environ)
    if cfg()["gpu"] and "GPU" not in env:
        env["GPU"] = "1"
    run(["bash", os.path.join(RAIZ, "renderizar.sh"), vid], env=env)
    if not os.path.exists(mp4(vid)):
        sys.exit("✘ el render no produjo el MP4. Probá GPU=0 python3 herramientas/director.py render " + vid)


def hoja(vid):
    G = leer(vid); src = mp4(vid)
    if not os.path.exists(src):
        sys.exit(f"✘ falta {src}: primero render")
    tmp = os.path.join(RAIZ, "salida", f"_{vid}_hoja"); os.makedirs(tmp, exist_ok=True)
    t0s = inicios(G); fs = []
    for i, b in enumerate(G["beats"]):
        t = a_real(G, t0s[i] + b["dur"] * 0.8)
        f = os.path.join(tmp, f"{i:03d}.jpg")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-vf", "scale=360:640", "-q:v", "3", f])
        fs.append((f, b["id"], t))
    cols = min(6, len(fs)); filas = math.ceil(len(fs) / cols)
    out = os.path.join(RAIZ, "salida", f"{vid}_hoja.jpg")
    try:
        from PIL import Image, ImageDraw
        H = Image.new("RGB", (cols * 360, filas * 640), "#0b0c14")
        for i, (f, bid, t) in enumerate(fs):
            im = Image.open(f); dr = ImageDraw.Draw(im)
            dr.rectangle([0, 0, 360, 30], fill="#000000"); dr.text((8, 8), f"{i + 1} · {bid} · {t:.1f}s", fill="#cdf23a")
            H.paste(im, ((i % cols) * 360, (i // cols) * 640))
        H.save(out, quality=85)
    except ImportError:
        run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(tmp, "%03d.jpg"), "-vf", f"tile={cols}x{filas}", "-frames:v", "1", out])
    for f, *_ in fs:
        os.remove(f)
    os.rmdir(tmp)
    print(f"✔ hoja de contactos: {out}  ({len(fs)} beats, en orden de lectura)")


def cortes(vid):
    G = leer(vid); src = mp4(vid)
    if not G.get("cortes"):
        return print("  (sin \"cortes\" en el guion)")
    if not os.path.exists(src):
        sys.exit(f"✘ falta {src}: primero render")
    t0s = inicios(G); idx = {b["id"]: i for i, b in enumerate(G["beats"])}
    for c in G["cortes"]:
        a, b = a_real(G, t0s[idx[c["desde"]]]), a_real(G, t0s[idx[c["hasta"]] + 1])
        out = os.path.join(RAIZ, "salida", f"{vid}_{c['nombre']}.mp4")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", src, "-t", f"{b - a:.3f}",
             "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
             "-af", f"afade=t=out:st={max(0, b - a - 0.25):.3f}:d=0.25", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out])
        print(f"✔ corte: {out}  ({b - a:.1f}s)")


# ───────────────────────────── versión realista (Blender) ─────────────────────────────
def _motor(vid, extra):
    env = dict(os.environ, EXTRA=extra)
    if cfg()["gpu"] and "GPU" not in env:
        env["GPU"] = "1"
    run(["bash", os.path.join(RAIZ, "renderizar.sh"), vid], env=env)


def horno(vid):
    """Exporta la animación cuadro a cuadro → salida/<id>.bake.json (sirve para cualquier episodio, con o sin guion.json)."""
    _motor(vid, "bake=1")
    if not os.path.exists(os.path.join(RAIZ, "salida", vid + ".bake.json")):
        sys.exit("✘ el horno no produjo el .bake.json")


def blender(vid):
    """Renderiza los cuadros con Blender. Opciones extra: BL="--cuadros 0,120 --escala 50" director.py blender <id>"""
    import shutil
    c = cfg(); bake = os.path.join(RAIZ, "salida", vid + ".bake.json")
    if not os.path.exists(bake):
        horno(vid)
    script = os.path.join(RAIZ, "blender", "render_blender.py")
    extra = shlex.split(c["blender_args"]) + shlex.split(os.environ.get("BL", ""))
    if shutil.which(c["blender"]) or os.path.exists(c["blender"]):
        run([c["blender"], "-b", "-P", script, "--", bake] + extra)
    else:
        print("  (no encontré el ejecutable de Blender; pruebo con el módulo bpy de Python)")
        run([sys.executable, script, bake] + extra)


def componer(vid):
    """Une los cuadros de Blender con textos, tarjetas y audio → salida/<nombre>_blender.mp4"""
    _motor(vid, "capa=blender")
    print("✔ versión realista:", mp4(vid).replace(".mp4", "_blender.mp4"))


def realista(vid):
    horno(vid); blender(vid); componer(vid)


def nuevo(vid):
    d = carpeta(vid)
    if os.path.exists(os.path.join(d, "guion.json")):
        sys.exit(f"✘ ya existe videos/{vid}/guion.json")
    os.makedirs(d, exist_ok=True)
    G = {"id": vid, "titulo": "Título del video", "orden": 99, "salida": f"pieza_por_pieza_{vid}.mp4",
         "camara": {"az": 40, "el": 30, "size": 12, "tx": 0, "ty": 2, "tz": 0},
         "piezas": [{"id": "compu", "tipo": "caja", "size": [4, 1, 3], "pos": [0, 0, 0], "color": "cream"}],
         "beats": [{"id": "b1", "dur": 2.5, "voz": "Tomas una compu.", "cap": "Tomas una *compu*",
                    "acciones": [{"en": 0.2, "aparece": "compu", "como": "drop"}]},
                   {"id": "fin", "dur": 3.0, "voz": "Esto es Pieza por Pieza. Una idea pequeña, algo extraordinario.",
                    "acciones": [{"en": 0.2, "marca": "PIEZA POR PIEZA", "sub": "Una idea pequeña, algo extraordinario"}]}]}
    guardar(vid, G); escribir_video_json(vid, G)
    print(f"✔ creado videos/{vid}/ — editá guion.json y corré: python3 herramientas/director.py todo {vid}")


def todo(vid):
    validar(vid); voz(vid); mezcla(vid); render(vid); hoja(vid); cortes(vid)
    print(f"\n✔ TODO LISTO: {mp4(vid)}\n  Para revisión, mandá solo: salida/{vid}_hoja.jpg + videos/{vid}/guion.json")


CMDS = {"nuevo": nuevo, "validar": validar, "voz": voz, "mezcla": mezcla, "render": render, "hoja": hoja, "cortes": cortes, "todo": todo,
        "horno": horno, "blender": blender, "componer": componer, "realista": realista}
if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in CMDS:
        sys.exit(__doc__)
    try:
        CMDS[sys.argv[1]](sys.argv[2])
    except subprocess.CalledProcessError as e:
        sys.exit(f"✘ falló: {' '.join(map(str, e.cmd))[:300]}")
