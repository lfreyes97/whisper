#!/usr/bin/env python3
"""GUI de escritorio (GTK4 + libadwaita) para transcribir audios con faster-whisper."""

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from core import (  # noqa: E402
    AUDIO_EXTS,
    FORMATO_EXT,
    MODELOS,
    TranscripcionCancelada,
    cargar_modelo,
    listar_audios,
    transcribir_audio,
)

APP_ID = "org.iglesiaraah.whisperstt"

IDIOMAS = [("Autodetectar", None), ("Español", "es"), ("Inglés", "en")]
FORMATOS = [("Texto con timestamps", "txt"), ("Texto plano", "plano"), ("Subtítulos (.srt)", "srt")]
DEVICES = ["cuda", "cpu"]


class VentanaPrincipal(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="Transcriptor", default_width=640, default_height=760)

        self.entrada: Path = Path.home() / "Música"
        self.salida: Path = Path.home() / "transcripciones"
        self.cancelado = threading.Event()
        self.hilo: threading.Thread | None = None

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar_view = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar_view)
        toolbar_view.add_top_bar(Adw.HeaderBar())

        scroller = Gtk.ScrolledWindow(vexpand=True)
        toolbar_view.set_content(scroller)

        contenido = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=18,
            margin_top=18, margin_bottom=18, margin_start=18, margin_end=18,
        )
        scroller.set_child(contenido)

        self._construir_grupo_archivos(contenido)
        self._construir_grupo_opciones(contenido)
        self._construir_botones_accion(contenido)
        self._construir_grupo_progreso(contenido)
        self._construir_grupo_resultados(contenido)

    # -- construcción de la UI ------------------------------------------------

    def _construir_grupo_archivos(self, contenido: Gtk.Box) -> None:
        grupo = Adw.PreferencesGroup(title="Archivos")
        contenido.append(grupo)

        self.fila_entrada = Adw.ActionRow(title="Entrada", subtitle=str(self.entrada))
        cont_btns = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        btn_carpeta = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="Elegir carpeta")
        btn_carpeta.connect("clicked", self.on_elegir_carpeta)
        btn_archivo = Gtk.Button(icon_name="audio-x-generic-symbolic", tooltip_text="Elegir un audio")
        btn_archivo.connect("clicked", self.on_elegir_archivo)
        cont_btns.append(btn_carpeta)
        cont_btns.append(btn_archivo)
        self.fila_entrada.add_suffix(cont_btns)
        grupo.add(self.fila_entrada)

        self.fila_salida = Adw.ActionRow(title="Salida", subtitle=str(self.salida))
        btn_salida = Gtk.Button(icon_name="folder-open-symbolic", tooltip_text="Elegir carpeta de salida",
                                 valign=Gtk.Align.CENTER)
        btn_salida.connect("clicked", self.on_elegir_salida)
        self.fila_salida.add_suffix(btn_salida)
        grupo.add(self.fila_salida)

    def _construir_grupo_opciones(self, contenido: Gtk.Box) -> None:
        grupo = Adw.PreferencesGroup(title="Opciones")
        contenido.append(grupo)

        self.combo_modelo = Gtk.DropDown.new_from_strings(MODELOS)
        self.combo_modelo.set_selected(MODELOS.index("small"))
        fila = Adw.ActionRow(title="Modelo")
        fila.add_suffix(self.combo_modelo)
        grupo.add(fila)

        self.combo_device = Gtk.DropDown.new_from_strings(DEVICES)
        fila = Adw.ActionRow(title="Dispositivo")
        fila.add_suffix(self.combo_device)
        grupo.add(fila)

        self.combo_idioma = Gtk.DropDown.new_from_strings([n for n, _ in IDIOMAS])
        fila = Adw.ActionRow(title="Idioma")
        fila.add_suffix(self.combo_idioma)
        grupo.add(fila)

        self.combo_formato = Gtk.DropDown.new_from_strings([n for n, _ in FORMATOS])
        fila = Adw.ActionRow(title="Formato")
        fila.add_suffix(self.combo_formato)
        grupo.add(fila)

        self.spin_beam = Gtk.SpinButton.new_with_range(1, 10, 1)
        self.spin_beam.set_value(5)
        self.spin_beam.set_valign(Gtk.Align.CENTER)
        fila = Adw.ActionRow(title="Beam size", subtitle="Más alto = mejor calidad, más lento")
        fila.add_suffix(self.spin_beam)
        grupo.add(fila)

        self.switch_overwrite = Gtk.Switch(valign=Gtk.Align.CENTER)
        fila = Adw.ActionRow(title="Regenerar existentes",
                              subtitle="Volver a transcribir aunque ya exista la salida")
        fila.add_suffix(self.switch_overwrite)
        fila.set_activatable_widget(self.switch_overwrite)
        grupo.add(fila)

    def _construir_botones_accion(self, contenido: Gtk.Box) -> None:
        cont = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        contenido.append(cont)

        self.btn_iniciar = Gtk.Button(label="Transcribir", css_classes=["suggested-action", "pill"])
        self.btn_iniciar.connect("clicked", self.on_iniciar)
        cont.append(self.btn_iniciar)

        self.btn_cancelar = Gtk.Button(label="Cancelar", css_classes=["destructive-action", "pill"],
                                        sensitive=False)
        self.btn_cancelar.connect("clicked", self.on_cancelar)
        cont.append(self.btn_cancelar)

    def _construir_grupo_progreso(self, contenido: Gtk.Box) -> None:
        self.grupo_progreso = Adw.PreferencesGroup(title="Progreso", visible=False)
        contenido.append(self.grupo_progreso)

        self.label_estado = Gtk.Label(label="", halign=Gtk.Align.START, css_classes=["dim-label"],
                                       margin_bottom=6)
        self.grupo_progreso.add(self.label_estado)

        caja_barras = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.barra_total = Gtk.ProgressBar(show_text=True, text="Total")
        self.barra_archivo = Gtk.ProgressBar(show_text=True, text="Archivo actual")
        caja_barras.append(self.barra_total)
        caja_barras.append(self.barra_archivo)
        self.grupo_progreso.add(caja_barras)

    def _construir_grupo_resultados(self, contenido: Gtk.Box) -> None:
        self.grupo_resultados = Adw.PreferencesGroup(title="Resultados", visible=False)
        contenido.append(self.grupo_resultados)
        self.lista_resultados = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        self.grupo_resultados.add(self.lista_resultados)

    # -- selección de archivos -------------------------------------------------

    def on_elegir_carpeta(self, _btn: Gtk.Button) -> None:
        dialogo = Gtk.FileDialog(title="Elegir carpeta de audios")
        dialogo.select_folder(self, None, self._al_elegir_carpeta_entrada)

    def _al_elegir_carpeta_entrada(self, dialogo: Gtk.FileDialog, resultado: Gio.AsyncResult) -> None:
        try:
            carpeta = dialogo.select_folder_finish(resultado)
        except GLib.Error:
            return
        self.entrada = Path(carpeta.get_path())
        self.fila_entrada.set_subtitle(str(self.entrada))

    def on_elegir_archivo(self, _btn: Gtk.Button) -> None:
        filtro = Gtk.FileFilter(name="Audio")
        for ext in sorted(AUDIO_EXTS):
            filtro.add_suffix(ext.lstrip("."))
        filtros = Gio.ListStore.new(Gtk.FileFilter)
        filtros.append(filtro)
        dialogo = Gtk.FileDialog(title="Elegir archivo de audio", filters=filtros)
        dialogo.open(self, None, self._al_elegir_archivo_entrada)

    def _al_elegir_archivo_entrada(self, dialogo: Gtk.FileDialog, resultado: Gio.AsyncResult) -> None:
        try:
            archivo = dialogo.open_finish(resultado)
        except GLib.Error:
            return
        self.entrada = Path(archivo.get_path())
        self.fila_entrada.set_subtitle(str(self.entrada))

    def on_elegir_salida(self, _btn: Gtk.Button) -> None:
        dialogo = Gtk.FileDialog(title="Elegir carpeta de salida")
        dialogo.select_folder(self, None, self._al_elegir_salida)

    def _al_elegir_salida(self, dialogo: Gtk.FileDialog, resultado: Gio.AsyncResult) -> None:
        try:
            carpeta = dialogo.select_folder_finish(resultado)
        except GLib.Error:
            return
        self.salida = Path(carpeta.get_path())
        self.fila_salida.set_subtitle(str(self.salida))

    # -- transcripción -----------------------------------------------------

    def on_iniciar(self, _btn: Gtk.Button) -> None:
        try:
            audios = listar_audios(self.entrada)
        except FileNotFoundError as e:
            self._mostrar_toast(str(e))
            return
        if not audios:
            self._mostrar_toast(f"No se encontraron audios en {self.entrada}")
            return

        self.salida.mkdir(parents=True, exist_ok=True)
        formato = FORMATOS[self.combo_formato.get_selected()][1]
        ext = FORMATO_EXT[formato]

        overwrite = self.switch_overwrite.get_active()
        pendientes = [a for a in audios if overwrite or not (self.salida / f"{a.stem}{ext}").exists()]
        if not pendientes:
            self._mostrar_toast("Todos los audios ya están transcritos (activa 'Regenerar existentes').")
            return

        modelo = MODELOS[self.combo_modelo.get_selected()]
        device = DEVICES[self.combo_device.get_selected()]
        idioma = IDIOMAS[self.combo_idioma.get_selected()][1]
        beam_size = int(self.spin_beam.get_value())

        self._preparar_ui_para_ejecucion(len(pendientes))
        self.cancelado.clear()
        self.hilo = threading.Thread(
            target=self._ejecutar_transcripcion,
            args=(pendientes, modelo, device, idioma, formato, beam_size),
            daemon=True,
        )
        self.hilo.start()

    def on_cancelar(self, _btn: Gtk.Button) -> None:
        self.cancelado.set()
        self.btn_cancelar.set_sensitive(False)
        self.label_estado.set_label("Cancelando...")

    def _preparar_ui_para_ejecucion(self, total: int) -> None:
        self.btn_iniciar.set_sensitive(False)
        self.btn_cancelar.set_sensitive(True)
        self.grupo_progreso.set_visible(True)
        self.barra_total.set_fraction(0.0)
        self.barra_archivo.set_fraction(0.0)
        self.label_estado.set_label(f"0/{total}")
        self.grupo_resultados.set_visible(False)
        hijo = self.lista_resultados.get_first_child()
        while hijo is not None:
            siguiente = hijo.get_next_sibling()
            self.lista_resultados.remove(hijo)
            hijo = siguiente

    def _ejecutar_transcripcion(self, pendientes, modelo, device, idioma, formato, beam_size) -> None:
        """Corre en un hilo aparte; toda comunicación con la UI va por GLib.idle_add."""
        GLib.idle_add(self.label_estado.set_label, f"Cargando modelo '{modelo}' ({device})...")
        try:
            model = cargar_modelo(
                modelo, device,
                on_fallback=lambda e: GLib.idle_add(
                    self._mostrar_toast, f"CUDA no disponible ({e}); usando CPU."),
            )
        except Exception as e:
            GLib.idle_add(self._finalizar, [], False, f"No se pudo cargar el modelo: {e}")
            return

        total = len(pendientes)
        ext = FORMATO_EXT[formato]
        resultados = []

        for i, audio in enumerate(pendientes, 1):
            if self.cancelado.is_set():
                break
            GLib.idle_add(self.label_estado.set_label, f"[{i}/{total}] {audio.name}")
            GLib.idle_add(self.barra_archivo.set_fraction, 0.0)

            def progreso_cb(frac: float) -> None:
                GLib.idle_add(self.barra_archivo.set_fraction, frac)

            try:
                texto, info = transcribir_audio(
                    model, audio, beam_size=beam_size, idioma=idioma, formato=formato,
                    on_progress=progreso_cb, cancel_event=self.cancelado,
                )
                destino = self.salida / f"{audio.stem}{ext}"
                destino.write_text(texto, encoding="utf-8")
                resultados.append((audio.name, info.duration / 60, info.language, True))
            except TranscripcionCancelada:
                break
            except Exception as e:
                resultados.append((audio.name, None, None, False, str(e)))

            GLib.idle_add(self.barra_total.set_fraction, i / total)

        GLib.idle_add(self._finalizar, resultados, self.cancelado.is_set(), None)

    def _finalizar(self, resultados: list, fue_cancelado: bool, error: str | None) -> None:
        self.btn_iniciar.set_sensitive(True)
        self.btn_cancelar.set_sensitive(False)
        self.grupo_progreso.set_visible(False)

        if error:
            self._mostrar_toast(error)
            return

        for fila in resultados:
            nombre, duracion_min, idioma, ok = fila[0], fila[1], fila[2], fila[3]
            self._agregar_fila_resultado(nombre, duracion_min, idioma, ok)
        self.grupo_resultados.set_visible(bool(resultados))

        ok_n = sum(1 for r in resultados if r[3])
        fallidos = len(resultados) - ok_n
        if fue_cancelado:
            self._mostrar_toast(f"Cancelado. {ok_n} transcrito(s) antes de parar.")
        elif fallidos:
            self._mostrar_toast(f"Listo con errores: {ok_n} ok, {fallidos} fallido(s).")
        else:
            self._mostrar_toast(f"Listo: {ok_n} audio(s) transcrito(s).")

    def _agregar_fila_resultado(self, nombre: str, duracion_min: float | None, idioma: str | None,
                                 ok: bool) -> None:
        subtitulo = f"{duracion_min:.1f} min · {idioma}" if ok else "Error al transcribir"
        fila = Adw.ActionRow(title=nombre, subtitle=subtitulo)
        icono = Gtk.Image.new_from_icon_name(
            "emblem-ok-symbolic" if ok else "dialog-error-symbolic"
        )
        icono.set_css_classes(["success"] if ok else ["error"])
        fila.add_prefix(icono)
        self.lista_resultados.append(fila)

    def _mostrar_toast(self, mensaje: str) -> None:
        self.toast_overlay.add_toast(Adw.Toast(title=mensaje, timeout=4))


class Aplicacion(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)

    def do_activate(self) -> None:
        ventana = self.props.active_window
        if not ventana:
            ventana = VentanaPrincipal(self)
        ventana.present()


def main() -> int:
    return Aplicacion().run(None)


if __name__ == "__main__":
    raise SystemExit(main())
