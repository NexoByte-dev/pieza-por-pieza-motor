#!/usr/bin/env bash
# Mac: doble clic (o ./abrir_estudio.command). Linux/GX10: ./abrir_estudio.command
cd "$(dirname "$0")"
PORT=${PORT:-8080}
python3 servidor.py "$PORT" salida &
SRV=$!; trap 'kill $SRV' EXIT
sleep 1
URL="http://localhost:$PORT/estudio.html"
if [ "$(uname)" = Darwin ]; then open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL"
else xdg-open "$URL" 2>/dev/null || echo "Abre en tu navegador: $URL"; fi
echo "Estudio abierto en $URL — deja esta ventana abierta mientras renderizas (Ctrl+C para cerrar)."
wait $SRV
