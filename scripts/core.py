"""Lógica de transcripción compartida entre la CLI y la GUI."""

from pathlib import Path

from faster_whisper import WhisperModel

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".opus"}
FORMATO_EXT = {"txt": ".txt", "plano": ".txt", "srt": ".srt"}
MODELOS = ["tiny", "base", "small", "medium", "large-v3"]


class TranscripcionCancelada(Exception):
    """Se lanza cuando se pide cancelar una transcripción en curso."""


def listar_audios(entrada: Path) -> list[Path]:
    if entrada.is_file():
        return [entrada]
    if not entrada.is_dir():
        raise FileNotFoundError(f"No existe la entrada: {entrada}")
    return sorted(p for p in entrada.iterdir() if p.suffix.lower() in AUDIO_EXTS)


def cargar_modelo(modelo: str, device: str, compute_type: str | None = None, on_fallback=None) -> WhisperModel:
    """Carga el modelo; si falla en cuda, reintenta en cpu (avisando vía on_fallback)."""
    compute_type = compute_type or ("float16" if device == "cuda" else "int8")
    try:
        return WhisperModel(modelo, device=device, compute_type=compute_type)
    except Exception as e:
        if device == "cuda":
            if on_fallback:
                on_fallback(e)
            return WhisperModel(modelo, device="cpu", compute_type="int8")
        raise


def fmt_srt_timestamp(segundos: float) -> str:
    h, resto = divmod(segundos, 3600)
    m, s = divmod(resto, 60)
    ms = round((s - int(s)) * 1000)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"


def render(segments, formato: str) -> str:
    if formato == "plano":
        return "\n".join(seg.text.strip() for seg in segments)
    if formato == "srt":
        bloques = [
            f"{i}\n{fmt_srt_timestamp(seg.start)} --> {fmt_srt_timestamp(seg.end)}\n{seg.text.strip()}\n"
            for i, seg in enumerate(segments, 1)
        ]
        return "\n".join(bloques)
    return "\n".join(f"[{seg.start:8.2f} -> {seg.end:8.2f}] {seg.text.strip()}" for seg in segments)


def transcribir_audio(model, audio: Path, *, beam_size=5, idioma=None, formato="txt",
                       on_progress=None, cancel_event=None):
    """Transcribe un solo audio y devuelve (texto_renderizado, info).

    on_progress(fraccion_0_a_1) se llama tras cada segmento procesado.
    cancel_event (threading.Event) se revisa entre segmentos; si está activo,
    lanza TranscripcionCancelada.
    """
    segments, info = model.transcribe(str(audio), beam_size=beam_size, vad_filter=True, language=idioma)
    duracion = info.duration
    segs = []
    for seg in segments:
        if cancel_event is not None and cancel_event.is_set():
            raise TranscripcionCancelada
        segs.append(seg)
        if on_progress and duracion:
            on_progress(min(1.0, seg.end / duracion))
    if on_progress:
        on_progress(1.0)
    return render(segs, formato), info
