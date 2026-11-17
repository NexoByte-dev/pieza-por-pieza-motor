#!/usr/bin/env bash
# Pieza por Pieza · arregla y vuelve a ensamblar el video realista (Blender) en la Asus.
#
#   bash arreglar_moe.sh                 # video "moe", busca el repo solo
#   bash arreglar_moe.sh moe /ruta/al/repo
#
# Qué hace (en este orden, y se detiene con un mensaje claro si algo falla):
#   1. encuentra el repo del motor y el archivo parche_gpu.zip
#   2. aplica el parche (unzip -o encima del repo) y apaga la GPU del navegador en kit.json
#   3. cierra servidores viejos que ocupan el puerto
#   4. comprueba que estén todos los cuadros de Blender (NO vuelve a renderizar)
#   5. ensambla con GPU=0, corrige el formato de color si hace falta
#   6. saca un cuadro de prueba y te dice dónde quedó todo
set -uo pipefail

ID=${1:-moe}
REPO=${2:-}
AQUI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
paso() { printf '\n\033[1;36m▸ %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
paro() { printf '\n\033[1;31m✘ %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(uname)" = Linux ] || printf '\033[33m⚠ Esto no es Linux (¿estás en la Mac?). Los cuadros de Blender de moe están en la Asus: corre este script allá.\033[0m\n'

# ── 1. repo y parche ─────────────────────────────────────────────
paso "Buscando el repo del motor"
es_repo() { [ -f "$1/engine.js" ] && [ -f "$1/servidor.py" ] && [ -f "$1/renderizar.sh" ]; }
if [ -z "$REPO" ]; then
  for c in "$PWD" "$AQUI"; do es_repo "$c" && REPO=$c && break; done
fi
if [ -z "$REPO" ]; then
  while IFS= read -r f; do
    d=$(dirname "$f"); case "$d" in *node_modules*) continue;; esac
    es_repo "$d" && REPO=$d && break
  done < <(find "$HOME/Downloads" -maxdepth 8 -name engine.js 2>/dev/null | sort)
fi
[ -n "$REPO" ] && es_repo "$REPO" || paro "No encontré el repo (la carpeta con engine.js y servidor.py). Pásala así: bash arreglar_moe.sh $ID /ruta/al/repo"
REPO=$(cd "$REPO" && pwd)
ok "repo: $REPO"

paso "Buscando parche_gpu.zip"
ZIP=""
for c in "$AQUI/parche_gpu.zip" "$HOME/Downloads/parche_gpu.zip" "$REPO/parche_gpu.zip" "$REPO/../../parche_gpu.zip" "$REPO/../parche_gpu.zip"; do
  [ -f "$c" ] && ZIP=$c && break
done
if [ -z "$ZIP" ]; then
  while IFS= read -r f; do ZIP=$f; break; done < <(find "$HOME/Downloads" -maxdepth 8 -name 'parche_gpu*.zip' 2>/dev/null | sort -r)
fi
[ -n "$ZIP" ] || paro "No encontré parche_gpu.zip. Descárgalo del chat y ponlo en ~/Downloads."
ok "parche: $ZIP"

command -v ffmpeg >/dev/null  || paro "Falta ffmpeg (sudo apt install ffmpeg)"
command -v python3 >/dev/null || paro "Falta python3"
command -v unzip >/dev/null   || paro "Falta unzip (sudo apt install unzip)"
cd "$REPO" || paro "No pude entrar a $REPO"

# ── 2. aplicar parche ────────────────────────────────────────────
paso "Aplicando el parche"
unzip -o -q "$ZIP" -d "$REPO" || paro "No pude descomprimir el parche"
grep -q "borra siempre" estudio.html || paro "El parche no quedó aplicado en estudio.html"
ok "estudio.html, herramientas/director.py, kit.ejemplo.json y MANUAL.md actualizados"
[ -f kit.json ] || cp kit.ejemplo.json kit.json
python3 - <<'PY'
import json
p = "kit.json"
c = json.load(open(p, encoding="utf-8"))
import sys
if sys.platform.startswith("linux"):
    c["gpu"] = False                     # en Linux ARM el Chromium con GPU pinta fondo negro y deja estelas
json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
ok "kit.json revisado (en Linux: gpu = false; en Mac se deja como está)"

# ── 3. servidores viejos ─────────────────────────────────────────
paso "Cerrando servidores viejos"
pkill -f servidor.py 2>/dev/null && ok "cerré un servidor que estaba abierto" || ok "no había ninguno"
sleep 1

# ── 4. cuadros de Blender ────────────────────────────────────────
paso "Comprobando los cuadros de Blender de «${ID}»"
[ -f "videos/$ID/video.json" ] || paro "No existe videos/$ID/video.json. ¿Es el id correcto? (usa: bash arreglar_moe.sh <id>)"
ESPERADOS=$(python3 -c "import json,math;print(math.ceil(json.load(open('videos/$ID/video.json'))['duracion']*30))")
HAY=$(find "salida/blender/$ID" -maxdepth 1 -name '*.png' 2>/dev/null | wc -l)
ok "$HAY cuadros de $ESPERADOS esperados"
if [ "$HAY" -lt "$ESPERADOS" ]; then
  paro "Faltan cuadros de Blender. Termínalos (retoma donde quedó) y vuelve a correr este script:
    python3 herramientas/director.py blender $ID"
fi

# ── 5. ensamblar ─────────────────────────────────────────────────
paso "Ensamblando (GPU=0, sin renderizar nada de nuevo)"
GPU=0 python3 herramientas/director.py componer "$ID" || paro "Falló el ensamblado. Pégame las últimas líneas de arriba."

SALIDA=$(python3 -c "import json;print(json.load(open('videos/$ID/video.json'))['salida'])")
MP4="salida/${SALIDA%.mp4}_blender.mp4"
[ -f "$MP4" ] || paro "No apareció $MP4"
ok "ensamblado: $MP4"

paso "Revisando el formato de color"
PIX=$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of csv=p=0 "$MP4")
FINAL="salida/${SALIDA%.mp4}_blender_final.mp4"
if [ "$PIX" = "yuvj420p" ]; then
  ok "estaba en rango completo (yuvj420p); lo convierto al estándar"
  ffmpeg -v error -hide_banner -y -i "$MP4" -vf "scale=in_range=full:out_range=tv,format=yuv420p" \
    -c:v libx264 -crf 17 -preset medium -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
    -c:a aac -b:a 256k -movflags +faststart "$FINAL" || paro "Falló la conversión de color"
else
  ok "ya estaba en formato estándar ($PIX)"
  cp -f "$MP4" "$FINAL"
fi

# ── 6. cuadro de prueba y resumen ────────────────────────────────
paso "Sacando un cuadro de prueba"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$FINAL")
T=$(python3 -c "print(min(11, float('$DUR')/2))")
PRUEBA="salida/${ID}_cuadro_prueba.png"
ffmpeg -v error -hide_banner -y -ss "$T" -i "$FINAL" -frames:v 1 "$PRUEBA" && ok "$PRUEBA (segundo $T)"

printf '\n\033[1;32m✔ LISTO\033[0m\n'
printf '  Video final : %s/%s  (%s)\n' "$REPO" "$FINAL" "$(du -h "$FINAL" | cut -f1)"
printf '  Cuadro prueba: %s/%s\n' "$REPO" "$PRUEBA"
printf '\n  Para llevarlo a la Mac:\n    wormhole send %s/%s\n' "$REPO" "$FINAL"
printf '  Revisa primero el cuadro de prueba: fondo azul oscuro y sin textos encimados.\n'
