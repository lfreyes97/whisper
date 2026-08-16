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

## App web (Streamlit)

Una tercera alternativa, en el navegador:

```bash
uv run streamlit run scripts/app_streamlit.py
```

Abre `http://localhost:8501`. Tiene las mismas opciones que la CLI en la barra lateral (modelo, dispositivo, idioma, formato, beam size, regenerar existentes) y dos formas de indicar la entrada:

- **Carpeta local**: escribes una ruta del propio equipo (default `~/Música`), igual que la CLI.
- **Subir archivos**: arrastras uno o más audios desde el navegador (útil si corres la app en otra máquina).

Al transcribir muestra barra de progreso total y del archivo en curso, una tabla con el resultado de cada audio, y un botón de descarga por archivo transcrito (además de guardarlo en la carpeta de salida, igual que la CLI/GUI). El modelo se cachea entre corridas (`st.cache_resource`) para no recargarlo en cada clic.

A diferencia de la GUI de escritorio, aquí no hay botón de cancelar a medio proceso — es una limitación del modelo de ejecución de Streamlit (el script corre de un tirón por cada interacción); para cortar una corrida larga, cierra la pestaña o detén el proceso (`Ctrl+C` en la terminal donde corre `streamlit run`).

## Estructura del proyecto

```
scripts/
  core.py           # lógica de transcripción compartida (CLI + GUI + app web)
  transcribir.py    # CLI de transcripción
  gui.py            # GUI de escritorio, GTK4 + libadwaita
  app_streamlit.py  # app web, Streamlit
  setup_cuda.sh     # symlinks de librerías CUDA para ctranslate2
notebooks/
  stt_example.ipynb  # notebook exploratorio paso a paso con faster-whisper
transcripciones/   # salida de las transcripciones
```
