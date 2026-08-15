#!/usr/bin/env python3
"""Transcribe archivos de audio con faster-whisper."""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from core import FORMATO_EXT, cargar_modelo, listar_audios, transcribir_audio

console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, show_path=False, show_time=True, markup=True)],
)
log = logging.getLogger("transcribir")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe audios con faster-whisper.")
    parser.add_argument(
        "entrada", nargs="?", type=Path, default=Path.home() / "Música",
        help="Archivo de audio o carpeta con audios (default: ~/Música)",
    )
    parser.add_argument(
        "salida", nargs="?", type=Path, default=Path("transcripciones"),
        help="Carpeta de salida (default: ./transcripciones)",
    )
    parser.add_argument(
        "--modelo", default="small",
        help="Modelo de whisper: tiny, base, small, medium, large-v3... (default: small)",
    )
    parser.add_argument(
        "--device", default="cuda", choices=["cuda", "cpu"],
        help="Dispositivo de inferencia (default: cuda, con fallback automático a cpu si falla)",
    )
    parser.add_argument(
        "--compute-type", default=None,
        help="Tipo de cómputo (default: float16 en cuda, int8 en cpu)",
    )
    parser.add_argument(
        "--idioma", default=None,
        help="Forzar idioma (ej: es, en). Por defecto autodetecta.",
    )
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument(
        "--formato", choices=["txt", "srt", "plano"], default="txt",
        help="txt=con timestamps [mm:ss], srt=subtítulos, plano=solo el texto (default: txt)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Regenerar aunque ya exista la transcripción",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        audios = listar_audios(args.entrada)
    except FileNotFoundError as e:
        sys.exit(str(e))
    if not audios:
        sys.exit(f"No se encontraron audios en {args.entrada}")

    args.salida.mkdir(parents=True, exist_ok=True)
    ext = FORMATO_EXT[args.formato]

    pendientes = [a for a in audios if args.overwrite or not (args.salida / f"{a.stem}{ext}").exists()]
    saltados = len(audios) - len(pendientes)
    if saltados:
        log.info(f"Saltando {saltados} audio(s) ya transcritos (usa --overwrite para regenerar)")
    if not pendientes:
        log.info("Nada que hacer.")
        return

    with console.status(f"Cargando modelo '{args.modelo}' ({args.device})..."):
        model = cargar_modelo(
            args.modelo, args.device, args.compute_type,
            on_fallback=lambda e: log.warning(f"No se pudo usar CUDA ({e}). Reintentando en CPU..."),
        )
    log.info(f"Modelo '{args.modelo}' cargado | {len(pendientes)} audio(s) pendiente(s)")

    resultados = []  # (nombre, duracion_min | None, idioma | None, ok: bool)
    progress_cols = (
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    with Progress(*progress_cols, console=console) as progress:
        total_task = progress.add_task(f"Total ({len(pendientes)} audios)", total=len(pendientes))

        for audio in pendientes:
            archivo_task = progress.add_task(audio.name, total=100)
            try:
                texto, info = transcribir_audio(
                    model, audio, beam_size=args.beam_size, idioma=args.idioma, formato=args.formato,
                    on_progress=lambda frac: progress.update(archivo_task, completed=frac * 100),
                )
                destino = args.salida / f"{audio.stem}{ext}"
                destino.write_text(texto, encoding="utf-8")
                resultados.append((audio.name, info.duration / 60, info.language, True))
            except Exception as e:
                log.error(f"Error transcribiendo {audio.name}: {e}")
                resultados.append((audio.name, None, None, False))
            finally:
                progress.remove_task(archivo_task)
                progress.advance(total_task)

    tabla = Table(title="Resumen")
    tabla.add_column("Audio")
    tabla.add_column("Duración", justify="right")
    tabla.add_column("Idioma")
    tabla.add_column("Estado")
    for nombre, duracion_min, idioma, ok in resultados:
        estado = "[green]✔ ok[/green]" if ok else "[red]✘ error[/red]"
        tabla.add_row(nombre, f"{duracion_min:.1f} min" if duracion_min else "—", idioma or "—", estado)
    console.print(tabla)

    fallidos = sum(1 for r in resultados if not r[3])
    if fallidos:
        console.print(f"[red]{fallidos} audio(s) fallaron.[/red]")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrumpido por el usuario.")
