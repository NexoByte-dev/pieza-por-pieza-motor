"""Renderizador realista: lee salida/<id>.bake.json (exportado por el estudio) y renderiza con Blender
la MISMA animación del motor, con materiales físicos, bordes biselados, sombras suaves y fondo transparente.
Los PNG se componen después en el estudio (textos, tarjetas y audio idénticos al render normal).

  blender -b -P blender/render_blender.py -- salida/<id>.bake.json [opciones]
  python3 blender/render_blender.py salida/<id>.bake.json [opciones]        (si tenés `pip install bpy`)

Opciones:
  --salida DIR       carpeta de los PNG (por defecto salida/blender/<id>/)
  --motor cycles|eevee   (por defecto cycles; usa la GPU si Blender la ve)
  --muestras N       muestras de Cycles (por defecto 64)
  --escala P         porcentaje de resolución, 100 = 1080x1920 (por defecto 100)
  --cuadros A        "todos" (defecto), una lista "0,120,300" o un rango "100-200"
  --paso N           renderiza 1 de cada N cuadros (pruebas rápidas)
  --bisel X          ancho del bisel de los bordes (por defecto 0.04; 0 lo apaga)
  --look estandar|agx    transformación de color (estandar respeta la paleta del canal)
  --guardar ARCHIVO.blend   además guarda la escena para abrirla en Blender
Si se corta, al volver a correrlo sigue donde quedó (salta los PNG que ya existen; --rehacer los pisa).
"""
import argparse, base64, json, math, os, sys, tempfile, time
import bpy, bmesh
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("bake"); ap.add_argument("--salida"); ap.add_argument("--motor", default="cycles", choices=["cycles", "eevee"])
ap.add_argument("--muestras", type=int, default=64); ap.add_argument("--escala", type=int, default=100)
ap.add_argument("--cuadros", default="todos"); ap.add_argument("--paso", type=int, default=1)
ap.add_argument("--bisel", type=float, default=0.04); ap.add_argument("--look", default="estandar", choices=["estandar", "agx"])
ap.add_argument("--guardar"); ap.add_argument("--rehacer", action="store_true")
A = ap.parse_args(argv)

B = json.load(open(A.bake, encoding="utf-8"))
OUT = A.salida or os.path.join(os.path.dirname(os.path.abspath(A.bake)), "blender", B["id"])
os.makedirs(OUT, exist_ok=True)
N = B["frames"]
if A.cuadros == "todos":
    CUADROS = list(range(0, N, A.paso))
elif "-" in A.cuadros:
    a, b = map(int, A.cuadros.split("-")); CUADROS = list(range(a, min(b, N - 1) + 1, A.paso))
else:
    CUADROS = [int(x) for x in A.cuadros.split(",") if int(x) < N]

# three.js (Y arriba) → Blender (Z arriba)
C = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
def mat(e):     # 16 números en orden de columnas (three.js)
    return Matrix(((e[0], e[4], e[8], e[12]), (e[1], e[5], e[9], e[13]), (e[2], e[6], e[10], e[14]), (e[3], e[7], e[11], e[15])))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ───────── motor de render ─────────
def poner(obj, attr, val):
    try: setattr(obj, attr, val); return True
    except Exception: return False

gpu = "CPU"
if A.motor == "cycles":
    sc.render.engine = "CYCLES"
    sc.cycles.samples = A.muestras
    poner(sc.cycles, "use_denoising", True)
    poner(sc.render, "use_persistent_data", True)
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences
        for tipo in ("OPTIX", "CUDA", "METAL", "HIP", "ONEAPI"):
            if not poner(pr, "compute_device_type", tipo):
                continue
            (getattr(pr, "refresh_devices", None) or pr.get_devices)()
            ds = [d for d in pr.devices if d.type == tipo]
            if ds:
                for d in pr.devices: d.use = d.type == tipo
                sc.cycles.device = "GPU"; gpu = f"{tipo}: {ds[0].name}"; break
    except Exception as e:
        print("  (sin GPU para Cycles:", e, ")")
else:
    if not poner(sc.render, "engine", "BLENDER_EEVEE_NEXT"):
        sc.render.engine = "BLENDER_EEVEE"
    gpu = "EEVEE"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = B["W"], B["H"], A.escala
sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.render.fps = B["fps"]
poner(sc.view_settings, "view_transform", "Standard" if A.look == "estandar" else "AgX")
poner(sc.view_settings, "look", "None")

# ───────── luz ─────────
w = bpy.data.worlds.new("mundo"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.72, 0.78, 1.0, 1); bg.inputs[1].default_value = 0.55
def luz(nombre, tipo, energia, direccion, color=(1, 1, 1), **kw):
    L = bpy.data.lights.new(nombre, tipo); L.energy = energia; L.color = color
    for k, v in kw.items(): poner(L, k, v)
    o = bpy.data.objects.new(nombre, L); sc.collection.objects.link(o)
    o.rotation_euler = Vector(direccion).to_track_quat("Z", "Y").to_euler()     # la luz apunta hacia -Z local
    return o
luz("sol", "SUN", 3.2, (-0.8, -0.6, 2.0), (1.0, 0.96, 0.9), angle=math.radians(7))
luz("relleno", "SUN", 0.9, (1.0, -0.9, 0.7), (0.75, 0.82, 1.0), angle=math.radians(40))

# ───────── texturas ─────────
tmpd = tempfile.mkdtemp()
IMGS = []
for i, url in enumerate(B["texs"]):
    p = os.path.join(tmpd, f"tex{i}.png")
    open(p, "wb").write(base64.b64decode(url.split(",", 1)[1]))
    im = bpy.data.images.load(p); im.pack(); IMGS.append(im)

# ───────── mallas ─────────
def estado_reposo(tr):
    """La matriz del estado más 'grande' del objeto: su escala se hornea en la malla para que el bisel no se deforme."""
    mejor, vol = None, -1
    for st in tr:
        if len(st) > 2:
            M = mat(st[2:18]); v = abs(M.to_3x3().determinant())
            if v > vol: mejor, vol = M, v
    return mejor

OBJ = []
for i, (m, tr) in enumerate(zip(B["meshes"], B["tracks"])):
    g = B["geoms"][m["geom"]]
    R = estado_reposo(tr)
    if R is None:
        OBJ.append(None); continue
    s0 = R.to_scale(); s0 = Vector([x if abs(x) > 1e-6 else 1.0 for x in s0])
    P = g["pos"]; vs = [(P[k] * s0.x, P[k + 1] * s0.y, P[k + 2] * s0.z) for k in range(0, len(P), 3)]
    idx = g["idx"] or list(range(len(vs)))
    fs = [tuple(idx[k:k + 3]) for k in range(0, len(idx), 3)]
    me = bpy.data.meshes.new(f"m{i}"); me.from_pydata(vs, [], fs)
    con_tex = m["tex"] >= 0
    if g["uv"] and con_tex:
        uv = me.uv_layers.new(name="uv")
        for lp in me.loops:
            uv.data[lp.index].uv = (g["uv"][lp.vertex_index * 2], g["uv"][lp.vertex_index * 2 + 1])
    plano = con_tex or len(vs) <= 4
    if not plano:                                  # suelda los vértices duplicados de three.js para poder biselar y suavizar
        bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
        for p in me.polygons: p.use_smooth = True
        try: me.set_sharp_from_angle(angle=math.radians(35))
        except Exception: pass
    me.update()
    o = bpy.data.objects.new(f"o{i}", me); sc.collection.objects.link(o)
    dmin = min(o.dimensions) if not plano else 0
    if not plano and A.bisel > 0 and dmin > 0.06:
        bv = o.modifiers.new("bisel", "BEVEL"); bv.width = min(A.bisel, dmin * 0.25); bv.segments = 3
        bv.limit_method = "ANGLE"; bv.angle_limit = math.radians(40); poner(bv, "harden_normals", True)

    # material: uno por objeto, porque color/opacidad/brillo se animan por objeto
    transl = any(len(st) > 2 and st[18] < 0.999 for st in tr)
    ma = bpy.data.materials.new(f"mat{i}"); ma.use_nodes = True
    nt = ma.node_tree; bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    em = bs.inputs.get("Emission Color") or bs.inputs.get("Emission")
    es = bs.inputs.get("Emission Strength")
    alfa = bs.inputs["Alpha"]; op = None
    if m["basico"]:                                # etiquetas, mosaicos y cúpulas: color propio, sin sombreado
        bs.inputs["Base Color"].default_value = (0, 0, 0, 1); bs.inputs["Roughness"].default_value = 1
        sp = bs.inputs.get("Specular IOR Level") or bs.inputs.get("Specular")
        if sp: sp.default_value = 0
        if es: es.default_value = 1.0
        if con_tex:
            tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = IMGS[m["tex"]]
            nt.links.new(tx.outputs["Color"], em)
            op = nt.nodes.new("ShaderNodeMath"); op.operation = "MULTIPLY"
            nt.links.new(tx.outputs["Alpha"], op.inputs[0]); nt.links.new(op.outputs[0], alfa)
        transl = True
        poner(o, "visible_shadow", False)
    else:
        bs.inputs["Roughness"].default_value = 0.42
        if es: es.default_value = 1.0
        c = bs.inputs.get("Coat Weight")
        if c: c.default_value = 0.15
    if transl:
        poner(ma, "surface_render_method", "BLENDED"); poner(ma, "blend_method", "BLEND")
        if not m["basico"]: bs.inputs["Roughness"].default_value = 0.12       # lo translúcido se ve como vidrio/acrílico
    me.materials.append(ma)
    OBJ.append({"o": o, "bs": bs, "em": em, "alfa": alfa, "op": op, "basico": m["basico"], "tex": con_tex,
                "inv": Matrix.Diagonal((1 / s0.x, 1 / s0.y, 1 / s0.z, 1)), "tr": tr, "k": 0})

# piso que solo recibe sombras (Cycles)
if A.motor == "cycles":
    bpy.ops.mesh.primitive_plane_add(size=4000, location=(0, 0, 0))
    piso = bpy.context.active_object; piso.name = "piso"; poner(piso, "is_shadow_catcher", True)

camd = bpy.data.cameras.new("cam"); camd.type = "ORTHO"; camd.clip_start = 0.1; camd.clip_end = 5000
cam = bpy.data.objects.new("cam", camd); sc.collection.objects.link(cam); sc.camera = cam
ck = 0

def aplicar(f):
    """Deja la escena en el estado del cuadro f (los tracks solo guardan los cambios)."""
    global ck
    for d in OBJ:
        if d is None: continue
        tr = d["tr"]
        while d["k"] < len(tr) and tr[d["k"]][0] <= f:
            st = tr[d["k"]]; d["k"] += 1
            vis = len(st) > 2
            d["o"].hide_render = not vis; d["o"].hide_viewport = not vis
            if not vis: continue
            d["o"].matrix_world = C @ mat(st[2:18]) @ d["inv"]
            opa, col, emi = st[18], st[19:22], st[22:25]
            if d["basico"]:
                if d["tex"]: d["op"].inputs[1].default_value = opa
                else:
                    d["em"].default_value = (*col, 1); d["alfa"].default_value = opa
            else:
                d["bs"].inputs["Base Color"].default_value = (*col, 1)
                d["em"].default_value = (*emi, 1); d["alfa"].default_value = opa
    while ck < len(B["cam"]) and B["cam"][ck][0] <= f:
        st = B["cam"][ck]; ck += 1
        cam.matrix_world = C @ mat(st[1:17])
        alto = st[17] * 2                          # alto visible en unidades del motor
        camd.ortho_scale = max(alto, alto * B["W"] / B["H"])

print(f"▸ {B['id']}: {len(CUADROS)} cuadros de {N} · {A.motor} ({gpu}) · {sum(1 for d in OBJ if d)} mallas → {OUT}")
t0 = time.time(); hechos = 0
pend = set(CUADROS)
for f in range(0, max(CUADROS) + 1):
    aplicar(f)
    if f not in pend: continue
    dest = os.path.join(OUT, f"{f:05d}.png")
    if os.path.exists(dest) and not A.rehacer: continue
    sc.frame_set(f)
    sc.render.filepath = dest
    bpy.ops.render.render(write_still=True)
    hechos += 1
    if hechos % 10 == 1:
        s = time.time() - t0
        print(f"  {hechos}/{len(CUADROS)} · {s:.0f}s · {s / hechos:.2f}s por cuadro", flush=True)
if A.guardar:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(A.guardar))
print(f"✔ Blender: {hechos} cuadros nuevos en {time.time() - t0:.0f}s → {OUT}")
