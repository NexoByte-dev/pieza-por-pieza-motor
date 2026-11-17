# Pieza por Pieza · motor de video

> **Flujo nuevo (kit de automatización): leer `MANUAL.md`.** Un video se escribe en `videos/<id>/guion.json` y se produce con `python3 herramientas/director.py todo <id>`. Lo de abajo sigue valiendo para los videos hechos a mano.

El **motor** casi no cambia. Cada video es **una carpeta** dentro de `videos/`.

```
pieza-por-pieza-motor/
├── engine.js, lib/, vendor/, node_modules/   ← el motor 3D (no se toca para un video nuevo)
├── estudio.html                              ← estudio en Chrome (vista previa + render)
├── renderizar.sh, servidor.py                ← render desde la terminal
├── abrir_estudio.command                     ← abre el estudio
└── videos/
    └── <id>/                                 ← un video = una carpeta
        ├── video.json                        ← título, duración, archivo de salida, tarjetas y sus tiempos
        ├── episodio.js                       ← la animación, los subtítulos de pantalla y la cámara
        ├── audio.flac                        ← la mezcla final (voz + música + efectos)
        └── tarjetas/                         ← imágenes que se superponen (capturas, gráficos, etiqueta de parte)
```

## Renderizar
```bash
./renderizar.sh lista        # videos disponibles
./renderizar.sh cuant3       # → salida/<nombre>.mp4
./renderizar.sh todos
GPU=1 ./renderizar.sh cuant3 # intenta usar la GPU
./abrir_estudio.command      # o con ventana, en Chrome
```

## Agregar un video nuevo
Claude agrega la carpeta `videos/<id>/` (en el repo o en un .tgz). El estudio la detecta solo: no hay que tocar ninguna lista.

### video.json
```json
{
 "orden": 6,
 "titulo": "Nombre que aparece en el estudio",
 "duracion": 90.0,
 "audio": "audio.flac",
 "salida": "pieza_por_pieza_nombre.mp4",
 "y": 560,
 "tarjetas": [
  { "img": "tarjetas/captura.png", "a": 40.6, "b": 43.2, "s": 1 },
  { "img": "tarjetas/badge.png", "a": 0, "b": 90, "s": 1, "x": 56, "y": 150 }
 ]
}
```
- `a` y `b`: segundo en que la tarjeta entra y sale (con fundido de 0.25 s).
- `s`: escala. `x`/`y`: posición (si no se ponen, va centrada a la altura `y` del video).

## Sincronizar entre computadoras
```bash
git pull      # antes de renderizar
```
