#!/usr/bin/env python3
"""App web (Streamlit) para transcribir audios con faster-whisper.

Uso: uv run streamlit run scripts/app_streamlit.py
"""

import tempfile
from pathlib import Path

import streamlit as st

from core import AUDIO_EXTS, FORMATO_EXT, MODELOS, cargar_modelo, listar_audios, transcribir_audio

IDIOMAS = [("Autodetectar", None), ("Español", "es"), ("Inglés", "en")]
FORMATOS = [("Texto con timestamps", "txt"), ("Texto plano", "plano"), ("Subtítulos (.srt)", "srt")]

st.set_page_config(page_title="Transcriptor", page_icon="🎙️", layout="centered")


@st.cache_resource(show_spinner=False)
def obtener_modelo(modelo: str, device: str):
    """Cachea el modelo cargado: no se vuelve a cargar entre reruns si no cambian los parámetros."""
    return cargar_modelo(modelo, device, on_fallback=lambda e: st.warning(f"CUDA no disponible ({e}); usando CPU."))


def guardar_subidos(archivos) -> Path:
    """Vuelca los archivos subidos a una carpeta temporal y devuelve su ruta."""
    if "carpeta_subidos" not in st.session_state:
        st.session_state.carpeta_subidos = tempfile.mkdtemp(prefix="whisper-stt-")
    carpeta = Path(st.session_state.carpeta_subidos)
    for archivo in archivos:
        (carpeta / archivo.name).write_bytes(archivo.getvalue())
    return carpeta


st.title("🎙️ Transcriptor")
st.caption("Transcribe audios con faster-whisper (mismo motor que la CLI y la GUI de escritorio).")

with st.sidebar:
    st.header("Opciones")
    modelo = st.selectbox("Modelo", MODELOS, index=MODELOS.index("small"))
    device = st.selectbox("Dispositivo", ["cuda", "cpu"])
    idioma_nombre = st.selectbox("Idioma", [n for n, _ in IDIOMAS])
    idioma = dict(IDIOMAS)[idioma_nombre]
    formato_nombre = st.selectbox("Formato", [n for n, _ in FORMATOS])
    formato = dict(FORMATOS)[formato_nombre]
    beam_size = st.slider("Beam size", 1, 10, 5)
    overwrite = st.checkbox("Regenerar existentes")
    salida_str = st.text_input("Carpeta de salida", str(Path.home() / "transcripciones"))

modo = st.radio("Entrada", ["Carpeta local", "Subir archivos"], horizontal=True)

audios: list[Path] = []
if modo == "Carpeta local":
    entrada_str = st.text_input("Ruta de la carpeta o archivo", str(Path.home() / "Música"))
    entrada = Path(entrada_str).expanduser()
    try:
        audios = listar_audios(entrada)
    except FileNotFoundError as e:
        st.error(str(e))
    if entrada.is_dir() and not audios:
        st.info("No se encontraron audios en esa carpeta.")
else:
    subidos = st.file_uploader(
        "Arrastra uno o más audios", type=[e.lstrip(".") for e in sorted(AUDIO_EXTS)], accept_multiple_files=True,
    )
    if subidos:
        carpeta = guardar_subidos(subidos)
        audios = listar_audios(carpeta)

if audios:
    st.write(f"**{len(audios)} audio(s)** detectado(s): " + ", ".join(a.name for a in audios))

if st.button("Transcribir", type="primary", disabled=not audios):
    salida = Path(salida_str).expanduser()
    salida.mkdir(parents=True, exist_ok=True)
    ext = FORMATO_EXT[formato]

    pendientes = [a for a in audios if overwrite or not (salida / f"{a.stem}{ext}").exists()]
    saltados = len(audios) - len(pendientes)
    if saltados:
        st.info(f"Saltando {saltados} audio(s) ya transcritos (marca 'Regenerar existentes' para forzar).")

    if not pendientes:
        st.success("Nada que hacer: todos los audios ya están transcritos.")
    else:
        with st.spinner(f"Cargando modelo '{modelo}' ({device})..."):
            model = obtener_modelo(modelo, device)

        barra_total = st.progress(0.0, text=f"0/{len(pendientes)}")
        barra_archivo = st.progress(0.0)
        estado = st.empty()
        resultados = []

        for i, audio in enumerate(pendientes, 1):
            estado.write(f"**[{i}/{len(pendientes)}]** {audio.name}")
            barra_archivo.progress(0.0)
            try:
                texto, info = transcribir_audio(
                    model, audio, beam_size=beam_size, idioma=idioma, formato=formato,
                    on_progress=lambda frac: barra_archivo.progress(frac),
                )
                destino = salida / f"{audio.stem}{ext}"
                destino.write_text(texto, encoding="utf-8")
                resultados.append({
                    "Audio": audio.name, "Duración (min)": round(info.duration / 60, 1),
                    "Idioma": info.language, "Estado": "✔ ok", "texto": texto, "destino": destino,
                })
            except Exception as e:
                resultados.append({
                    "Audio": audio.name, "Duración (min)": None, "Idioma": None,
                    "Estado": f"✘ error: {e}", "texto": None, "destino": None,
                })
            barra_total.progress(i / len(pendientes), text=f"{i}/{len(pendientes)}")

        estado.empty()
        barra_archivo.empty()

        ok = sum(1 for r in resultados if r["Estado"] == "✔ ok")
        fallidos = len(resultados) - ok
        if fallidos:
            st.warning(f"Listo con errores: {ok} ok, {fallidos} fallido(s).")
        else:
            st.success(f"Listo: {ok} audio(s) transcrito(s) en {salida}")

        st.dataframe(
            [{k: v for k, v in r.items() if k not in ("texto", "destino")} for r in resultados],
            hide_index=True, width="stretch",
        )

        for r in resultados:
            if r["texto"] is not None:
                st.download_button(
                    f"Descargar {r['destino'].name}", data=r["texto"],
                    file_name=r["destino"].name, mime="text/plain", key=f"dl-{r['destino'].name}",
                )
