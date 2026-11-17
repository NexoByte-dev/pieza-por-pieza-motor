# MANUAL · Pieza por Pieza (documento de continuidad)

> Para cualquier modelo (Qwen local, Claude, ChatGPT) o persona que retome el trabajo:
> **leé este archivo y nada más**. No hace falta leer `engine.js` para hacer un video.

## 1. Qué es esto

Canal **Pieza por Pieza**: explica ideas complicadas en pasos cortos ("tomas X, agregas Y, ocurre un problema, agregamos Z"). Videos 3D verticales (1080×1920, 30 fps). Cierre fijo de todos los videos: *"Esto es Pieza por Pieza. Una idea pequeña, algo extraordinario."*

Reparto del trabajo:

| Quién | Qué hace |
|---|---|
| Scripts (`herramientas/director.py`) | Todo lo repetible: validar, voz, tiempos, efectos, render, hoja de contactos, Shorts, Blender |
| Modelo local | Escribe y corrige `guion.json`; corre los comandos; arregla errores del validador |
| Claude / ChatGPT | Solo dirección: idea → guion, y revisión de la hoja de contactos |

## 2. Un video = un archivo

```
videos/<id>/guion.json     ← LO ÚNICO que se escribe a mano (o lo escribe un modelo)
videos/<id>/episodio.js    ← genérico, se copia solo
videos/<id>/video.json     ← lo genera el director
videos/<id>/voz/<beat>.wav ← lo genera el TTS (o se graba a mano con ese nombre)
videos/<id>/audio.flac     ← lo genera el director (voz + efectos + música)
```

Flujo completo:

```bash
python3 herramientas/director.py nuevo mi_video     # crea la plantilla
# … editar videos/mi_video/guion.json …
python3 herramientas/director.py todo mi_video      # validar → voz → mezcla → render → hoja → cortes
```

Salidas en `salida/`: el MP4, `mi_video_hoja.jpg` (un cuadro por beat) y los Shorts.
**Para pedir revisión a Claude/ChatGPT se manda solo la hoja + el guion.json.** La respuesta debe ser cambios al guion.

Los videos viejos con `episodio.js` escrito a mano siguen funcionando igual (`./renderizar.sh <id>`).

## 3. Formato de guion.json

```json
{
  "id": "mi_video", "titulo": "…", "orden": 7, "salida": "pieza_por_pieza_mi_video.mp4",
  "camara": { "az": 40, "el": 30, "size": 12, "tx": 0, "ty": 2, "tz": 0 },
  "piezas": [ { "id": "compu", "tipo": "caja", "size": [4, 1, 3], "pos": [0, 0, 0], "color": "cream" } ],
  "beats":  [ { "id": "b1", "dur": 2.5, "voz": "Tomas una compu.", "cap": "Tomas una *compu*",
                "acciones": [ { "en": 0.2, "aparece": "compu", "como": "drop" } ] } ],
  "tarjetas": [ { "img": "tarjetas/captura.png", "a": 4.0, "b": 6.5, "s": 1 } ],
  "cortes":  [ { "nombre": "short_1", "desde": "b1", "hasta": "b3" } ]
}
```

**Espacio:** `x` derecha, `y` arriba, `z` hacia la cámara. `pos` es el centro de la **base** de la pieza. Una unidad ≈ un bloque chico. La escena típica ocupa de −5 a 5 en x.

**Cámara** (isométrica): `az` giro horizontal en grados, `el` elevación, `size` alto visible en unidades (más chico = más zoom), `tx,ty,tz` punto al que mira.

**Colores:** nombres de la paleta (`cream paper gray dark ink lime red blue sky pcb silicon alu`) o hex `#rrggbb`. Regla del canal: lima = idea clave / éxito, rojo = problema, sky = 16 bits, lima = 8 bits.

### Piezas (`tipo`)

| tipo | propiedades (además de `id`, `pos`, `padre`) |
|---|---|
| `caja` | `size:[ancho,alto,fondo]`, `color`, `opacity` |
| `cilindro` | `r`, `h`, `color`, `eje: "x"|"y"|"z"` |
| `esfera` | `r`, `color` |
| `etiqueta` | caja con texto al frente: `text`, `size`, `color`, `fg` |
| `texto` | texto plano: `text`, `w`, `h`, `face: "front"|"top"|"right"`, `fg`, `bg` |
| `cable` | `de:[x,y,z]`, `a:[x,y,z]`, `r`, `color` |
| `cupula` | barrera transparente: `r`, `color`, `opacity` |
| `grupo` | contenedor vacío; otras piezas lo usan como `padre` y se mueven con él |
| `memoria` | tanque RAM/VRAM con regla: `gb`, `nombre`, `ancho`, `u` (unidades por GB, 0.8), `placa` |
| `modelo` | bloque LLM con mosaico: `lado`, `nombre`, `color`, `seed` |
| `ficha` | token con texto: `text`, `color` |
| `bits` | fila de cubitos: `bits`, `color` |
| `bloques` | pila de bloques de 1 GB: `n`, `u`, `ancho`, `color`. Sus partes son `id.0`, `id.1`… y `id.*` son todas |

`padre`: id de otra pieza definida antes; la posición pasa a ser relativa a ella.

### Beats

Un beat = una frase. `dur` es la duración **nominal** en segundos; al generar la voz, cada beat se estira o encoge para durar lo que dura su frase (la animación sigue sincronizada sola).

- `voz`: lo que dice el narrador (frase completa, natural).
- `cap`: lo que se lee en pantalla. Máximo ~6 palabras. `*así*` resalta en lima (idea clave, suena un "ding"); `!así!` en rojo (problema, suena un error).
- `acciones`: lista. Cada una tiene `en` (segundos desde el inicio del beat, por defecto 0) y **una** de estas claves:

| acción | ejemplo | notas |
|---|---|---|
| `aparece` | `{"en":0.2,"aparece":"compu","como":"drop"}` | `como`: `drop` (cae y rebota), `pop`, `grow`, `fade`. `dur`. `"sfx":null` la silencia. Acepta lista de ids. **Cada pieza aparece una sola vez**; las que nunca "aparecen" están visibles desde el segundo 0 |
| `mueve` | `{"mueve":"compu","a":{"px":2,"py":1},"dur":0.8,"ease":"inOut"}` | pistas: `px py pz` posición, `sx sy sz` escala, `ry` giro (radianes), `op` opacidad. Valores absolutos |
| `oculta` | `{"oculta":"compu","dur":0.3}` | |
| `cam` | `{"cam":{"size":9,"az":30,"tx":1},"dur":1.2}` | solo las claves que cambian |
| `nota` | `{"nota":"aclaración chica","dur":2.5}` | texto pequeño bajo el caption |
| `flujo` | `{"flujo":{"de":"a","a":"b","count":16,"color":"blue","arc":1},"dur":3}` | partículas en arco; `de`/`a`: id de pieza, `[x,y,z]` o lista de puntos; `forma:"cube"` |
| `brillo` | `{"brillo":"llm","dur":1.5}` | solo tipo `modelo`: se ilumina ("está pensando") |
| `quita_bits` | `{"quita_bits":"num","desde":8,"hasta":16}` | solo tipo `bits` |
| `texto` | `{"texto":"cartel","valor":"nuevo texto"}` | cambia el texto de una etiqueta/texto/ficha |
| `color` | `{"color":"compu","valor":"lime"}` | cambia el color en ese instante |
| `marca` | `{"marca":"PIEZA POR PIEZA","sub":"Una idea pequeña, algo extraordinario"}` | tarjeta final |
| `sfx` | `{"sfx":"ding"}` | `pop ding whoosh err tick` |

`ease`: `linear out inOut back bounce`.

`tarjetas` (opcional): imágenes superpuestas; `a`/`b` en segundos **nominales** (el director los convierte). `cortes` (opcional): Shorts, de un beat a otro, incluidos.

### Reglas de estilo (lo que hace que el video funcione)

1. **Una idea por beat.** Frase corta en `voz`, 3–6 palabras en `cap`.
2. **Siempre pasa algo:** cada beat tiene al menos una acción visible en su primer medio segundo.
3. **Solo se agregan piezas:** lo anterior queda en pantalla; no se cambia de escena de golpe.
4. **Gancho en el primer beat** (un problema o una promesa), **problema en rojo** antes del minuto, **solución en lima**.
5. **La cámara se mueve con motivo:** zoom a lo nuevo, vuelta atrás para ver el conjunto.
6. Último beat: la frase de cierre + acción `marca`.
7. El guion suena seguro y convincente; sin frases que le quiten valor a lo que se enseña.

## 4. Comandos

```bash
python3 herramientas/director.py validar <id>   # errores con nombre de beat y de pieza; no renderiza
python3 herramientas/director.py voz <id>       # TTS por beat (con caché) → tiempos reales
python3 herramientas/director.py mezcla <id>    # voz + efectos (+ música) → audio.flac, video.json
python3 herramientas/director.py render <id>    # MP4
python3 herramientas/director.py hoja <id>      # salida/<id>_hoja.jpg
python3 herramientas/director.py cortes <id>    # Shorts
python3 herramientas/director.py todo <id>
```

Configuración en `kit.json` (raíz; copiá `kit.ejemplo.json`):

- `tts`: comando de tu TTS. `{salida}` = wav de destino. El texto entra por stdin, o por `{texto}` si lo ponés en el comando.
  Ej. Piper: `"piper --model voces/es_MX.onnx --output_file {salida}"`.
  Sin TTS: grabá `videos/<id>/voz/<beat>.wav` a mano y el resto funciona igual. Si cambia el texto de un beat, solo se regenera ese beat.
- `pausa`: silencio tras cada frase. `vol_sfx`, `vol_musica`, `musica` (ruta), o dejá `videos/<id>/musica.mp3`.
- `gpu`: usa `GPU=1` al renderizar. Por defecto solo en Mac. **En Linux/GX10 déjalo en `false`**: con GPU el Chromium pinta fondo negro y deja estelas de cuadros anteriores. Para forzarlo una vez: `GPU=1 python3 herramientas/director.py render <id>`.

## 5. Versión realista con Blender

No reemplaza al motor: **re-renderiza la misma animación** con materiales físicos, bordes biselados y sombras suaves. Funciona con cualquier episodio, incluso los viejos.

```bash
python3 herramientas/director.py horno <id>     # exporta la animación → salida/<id>.bake.json
BL="--cuadros 60,300 --escala 50" python3 herramientas/director.py blender <id>   # prueba de 2 cuadros
python3 herramientas/director.py blender <id>   # todos los cuadros → salida/blender/<id>/00000.png…
python3 herramientas/director.py componer <id>  # + textos, tarjetas y audio → salida/…_blender.mp4
python3 herramientas/director.py realista <id>  # los tres pasos
```

- Probado con Blender 5.3; escrito para funcionar desde 4.2. Ruta en `kit.json`: `"blender": "/ruta/a/blender"`. Alternativa: `pip install bpy`.
- Si se corta, se retoma solo (salta los PNG ya hechos). `--rehacer` los pisa.
- Opciones (`blender/render_blender.py --help`): `--motor eevee` (mucho más rápido, sin sombra en el piso), `--muestras`, `--bisel`, `--look agx`, `--guardar escena.blend` (para abrirla y retocar luces a mano).
- Límites conocidos: no dibuja los contornos de tinta ni las líneas de regla del tanque; los textos que cambian con la acción `texto` quedan con su valor inicial.
- Para cambiar el look (luces, materiales) se edita solo `blender/render_blender.py`, secciones "luz" y "material".

## 6. Cómo trabajar con un modelo (para gastar pocos tokens)

- Guion nuevo: pegarle `prompts/guion.md` + la idea. Devuelve solo el JSON.
- Si `validar` da errores: pegarle `prompts/corregir.md` + los errores + el guion.
- Revisión visual: `prompts/revisar.md` + la hoja de contactos + el guion.
- Nunca pedirle que reescriba el motor para un video. Si falta una pieza nueva (por ejemplo un teléfono), se agrega **una función** en `lib/componentes.js` y **una línea** en `CREAR` de `lib/guion.js`, y se anota en la tabla de piezas de este manual.

## 7. Mapa del repo

| Archivo | Para qué | ¿Se toca? |
|---|---|---|
| `engine.js` | motor 3D determinista | casi nunca |
| `lib/componentes.js` | piezas con identidad del canal | para agregar piezas |
| `lib/guion.js` | intérprete de guion.json | para agregar acciones/tipos |
| `herramientas/director.py` | pipeline | para agregar etapas |
| `blender/render_blender.py` | look realista | para ajustar luces/materiales |
| `estudio.html`, `renderizar.sh`, `servidor.py` | render en Chrome | no |
| `videos/demo_kit/` | ejemplo que usa casi todo | copiar ideas |

## Tipos y acciones extra (videos de archivos, ej. `nexora_s1`)
- Piezas: `carpeta` (text,w,d), `archivo` (s,text), `candado` (k), `compu` (k,text), `foto` (w,d,color o img de /recursos_dibujos/). Cualquier pieza acepta `ry` (giro).
- Acciones: `cuenta` (etiqueta, de, a, sufijo, dur) y `parpadea` (piezas, valor, hz, dur).
- Audio ya hecho: pon `videos/<id>/audio_externo.(flac|wav|mp3|mp4)`; `voz` y `mezcla` lo usan tal cual (sin TTS ni SFX).
- Fotos reales: copia las imágenes a `recursos_dibujos/` y usa `"img": "montana_01.jpg"` en las piezas `foto`.
