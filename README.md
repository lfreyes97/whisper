# whisper-stt

Transcripción de audio a texto usando [faster-whisper](https://github.com/SYSTRAN/faster-whisper), acelerada por GPU (probado con RTX 3050).

## Requisitos

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- (opcional) GPU NVIDIA con CUDA para acelerar la transcripción — sin ella, el script funciona igual en CPU

## Instalación

```bash
uv sync
```

Esto instala `faster-whisper`, `rich` y las dependencias de CUDA (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`).

### GPU: symlinks de CUDA

`ctranslate2` (el backend de faster-whisper) busca las librerías CUDA en una ruta que no siempre coincide con la de los paquetes `nvidia-*` instalados por `uv`. Si al transcribir en `--device cuda` falla por no encontrar `libcublas`/`libcudnn`, corre una vez:

```bash
./scripts/setup_cuda.sh
```

Crea los symlinks necesarios dentro de `.venv`. Solo hace falta repetirlo si vuelves a correr `uv sync` desde cero.

## Uso

```bash
uv run scripts/transcribir.py [entrada] [salida] [opciones]
```

- `entrada`: archivo de audio o carpeta con audios (default: `~/Música`)
- `salida`: carpeta donde se guardan las transcripciones (default: `./transcripciones`)

Formatos de audio soportados: `.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.opus`.

### Opciones

| Opción | Default | Descripción |
|---|---|---|
| `--modelo` | `small` | Modelo de whisper: `tiny`, `base`, `small`, `medium`, `large-v3`... Con 4GB de VRAM, `small`/`base` van bien. |
| `--device` | `cuda` | `cuda` o `cpu`. Si `cuda` falla al cargar, reintenta automáticamente en `cpu`. |
| `--compute-type` | auto | Tipo de cómputo. Por defecto `float16` en `cuda`, `int8` en `cpu`. |
| `--idioma` | autodetecta | Forzar idioma (ej. `es`, `en`). |
| `--beam-size` | `5` | Calidad de la búsqueda: más alto = mejor y más lento. |
| `--formato` | `txt` | `txt` (con timestamps `[inicio -> fin]`), `plano` (solo texto) o `srt` (subtítulos). |
| `--overwrite` | `false` | Regenerar aunque ya exista la transcripción de un audio (por default se saltan). |

### Ejemplos

```bash
# Todo lo que haya en ~/Música, con el modelo y formato default
uv run scripts/transcribir.py

# Un archivo puntual, en español, como texto plano
uv run scripts/transcribir.py "~/Música/sermon.mp3" transcripciones --idioma es --formato plano

# Carpeta completa en CPU con subtítulos .srt
uv run scripts/transcribir.py ~/audios ./salida --device cpu --formato srt

# Re-transcribir todo aunque ya existan los .txt
uv run scripts/transcribir.py --overwrite
```

Al correrlo verás una barra de progreso total (audios procesados) y una por archivo (según el tiempo ya transcrito), y al terminar una tabla resumen con duración, idioma detectado y estado de cada audio. Si un archivo falla, se registra el error y continúa con el resto del batch; el script termina con código de salida `1` si hubo fallos.

Los audios ya transcritos (mismo nombre de salida) se saltan en corridas siguientes, así que el script es seguro de interrumpir (`Ctrl+C`) y reanudar.

## GUI de escritorio (GTK4 + libadwaita)

Si prefieres no usar la terminal, hay una interfaz gráfica con las mismas opciones que la CLI:

```bash
uv run scripts/gui.py
```

Requiere las librerías de sistema GTK4 y libadwaita (en la mayoría de distros GNOME ya vienen instaladas; en Arch: `gtk4` y `libadwaita`). `pygobject`/`pycairo` se compilan solos al hacer `uv sync` contra esas librerías del sistema.

Permite elegir carpeta o archivo de entrada, carpeta de salida, modelo, dispositivo, idioma, formato y beam size con controles gráficos; muestra una barra de progreso total y otra del archivo en curso, se puede cancelar a medio proceso, y al terminar deja una lista con el resultado (ok/error) de cada audio. Corre la transcripción en un hilo aparte para no congelar la ventana.

## Estructura del proyecto

```
scripts/
  core.py         # lógica de transcripción compartida (CLI + GUI)
  transcribir.py  # CLI de transcripción
  gui.py          # GUI GTK4 + libadwaita
  setup_cuda.sh   # symlinks de librerías CUDA para ctranslate2
notebooks/
  stt_example.ipynb  # notebook exploratorio paso a paso con faster-whisper
transcripciones/   # salida de las transcripciones
```
