#!/usr/bin/env bash
# Renderiza desde la terminal, sin ventanas (usa Chrome/Chromium en modo headless; no necesita Playwright).
#   ./renderizar.sh cuant3          → salida/pieza_por_pieza_cuantizacion_parte3.mp4
#   ./renderizar.sh todos           → todos los videos de la carpeta videos/
#   ./renderizar.sh lista           → muestra los videos disponibles
#   GPU=1 ./renderizar.sh cuant3    → intenta usar la GPU (más rápido si funciona)
#   CHROME=/ruta/a/chrome ./renderizar.sh cuant3   → usa ese navegador
set -euo pipefail
cd "$(dirname "$0")"
ID=${1:-}
if [ -z "$ID" ] || [ "$ID" = lista ]; then
  python3 -c "import json,glob,os; vs=sorted(((json.load(open(f)),os.path.basename(os.path.dirname(f))) for f in glob.glob('videos/*/video.json')),key=lambda x:x[0].get('orden',999)); [print(f\"  {i:8} {v['titulo']}  ({v['duracion']} s)\") for v,i in vs]"
  [ -z "$ID" ] && echo "uso: ./renderizar.sh <id> | todos"; exit 0
fi
CH=${CHROME:-}
if [ -z "$CH" ]; then
  for c in chromium chromium-browser brave-browser google-chrome google-chrome-stable \
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" "/Applications/Chromium.app/Contents/MacOS/Chromium" \
           /snap/bin/chromium ~/.cache/ms-playwright/chromium-*/chrome-linux/chrome; do
    if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then CH=$c; break; fi
  done
fi
[ -n "$CH" ] || { echo "No encontré Chrome ni Chromium. Instalá uno (sudo apt install chromium) o usá CHROME=/ruta ./renderizar.sh $ID"; exit 1; }
PORT=${PORT:-8091}; OUT="$PWD/salida"; PERFIL=$(mktemp -d)
python3 servidor.py "$PORT" "$OUT" & SRV=$!
trap 'kill $SRV $NAV 2>/dev/null; sleep 0.5; rm -rf "$PERFIL" 2>/dev/null || true' EXIT
sleep 1
if [ "$ID" = todos ]; then Q="todos&auto=1"; else Q="p=$ID&auto=1"; fi
[ -n "${EXTRA:-}" ] && Q="$Q&$EXTRA"   # EXTRA=bake=1 (exporta para Blender) · EXTRA=capa=blender (compone los cuadros de Blender)
GL="--use-angle=swiftshader --enable-unsafe-swiftshader"
[ "${GPU:-0}" = 1 ] && GL="--use-angle=vulkan --enable-features=Vulkan --ignore-gpu-blocklist --enable-gpu"
[ "$(uname)" = Darwin ] && [ "${GPU:-0}" = 1 ] && GL="--use-angle=metal --ignore-gpu-blocklist"
SB=""; [ "$(id -u)" = 0 ] && SB="--no-sandbox"   # como root Chrome exige --no-sandbox
echo "▸ navegador: $CH"
"$CH" --headless=new --user-data-dir="$PERFIL" --no-first-run --no-default-browser-check --mute-audio \
  --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows \
  --autoplay-policy=no-user-gesture-required --window-size=1400,1000 $GL $SB \
  "http://127.0.0.1:$PORT/estudio.html?$Q" >/dev/null 2>&1 & NAV=$!
wait $SRV
echo "✔ listo: $OUT/"
