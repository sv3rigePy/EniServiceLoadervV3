import os

# ============================================================
# STA-BOOTSTRAP (nur für eingebettete Webseiten/WebView2 nötig)
# ============================================================
#
# Ein echter eingebetteter Browser (WebView2, für DeepL/Temp-Mail
# im Programm) braucht einen COM-Thread im "STA"-Modus. Der normale
# Python-Start-Thread läuft nicht in diesem Modus. Deshalb startet
# sich das Programm hier einmalig selbst in einem passenden
# .NET-Thread neu, bevor der eigentliche Code (weiter unten,
# unverändert) läuft. Schlägt das aus irgendeinem Grund fehl (z. B.
# .NET/pythonnet nicht verfügbar), läuft alles wie gewohnt im
# normalen Thread weiter - nur eingebettete Webseiten würden dann
# nicht funktionieren.

if __name__ == "__main__" and os.environ.get("_ENI_STA_AKTIV") != "1":
    try:
        import clr
        clr.AddReference("System.Threading")
        from System.Threading import ApartmentState, Thread, ThreadStart

        os.environ["_ENI_STA_AKTIV"] = "1"

        # Immer den vollständigen, absoluten Pfad verwenden - sonst
        # könnte der Programmordner (und damit z. B. gespeicherte
        # Einstellungen) je nachdem, wie das Programm gestartet
        # wurde (Doppelklick, Verknüpfung, Kommandozeile ...),
        # unterschiedlich aufgelöst werden.
        _eni_datei_pfad = os.path.abspath(__file__)

        with open(_eni_datei_pfad, "r", encoding="utf-8") as _eni_datei:
            _eni_quellcode = _eni_datei.read()

        _eni_kompiliert = compile(_eni_quellcode, _eni_datei_pfad, "exec")

        def _eni_im_sta_thread_starten():
            exec(
                _eni_kompiliert,
                {"__name__": "__main__", "__file__": _eni_datei_pfad}
            )

        _eni_sta_thread = Thread(ThreadStart(_eni_im_sta_thread_starten))
        _eni_sta_thread.ApartmentState = ApartmentState.STA
        _eni_sta_thread.Start()
        _eni_sta_thread.Join()

        raise SystemExit(0)

    except SystemExit:
        raise
    except Exception as _eni_sta_fehler:
        print(f"STA-Start nicht möglich, starte normal: {_eni_sta_fehler}")


import sys
import subprocess
import importlib.util
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog, colorchooser
from pathlib import Path
import urllib.request
import threading
import shutil
import os
import time
import socket
import json
import ctypes
import platform
import secrets
import string
from datetime import datetime

try:
    import winsound
except ImportError:
    winsound = None


# ============================================================
# AUTOMATISCHE PAKET-INSTALLATION
# ============================================================

def paket_installieren(paket, import_name):
    try:
        # Bereits geladene Module (z. B. "clr" nach dem STA-Bootstrap)
        # direkt als vorhanden zählen - find_spec() kann bei manchen
        # bereits importierten Modulen (eigene Import-Hooks wie bei
        # pythonnet) fälschlich eine Exception werfen.
        if import_name in sys.modules:
            return True

        if importlib.util.find_spec(import_name) is not None:
            return True

        print(f"Installiere {paket} ...")
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            paket
        ])

        return True

    except Exception as e:
        print(f"Fehler bei {paket}: {e}")
        return False


PIL_OK = paket_installieren("Pillow", "PIL")
CV2_OK = paket_installieren("opencv-python", "cv2")
UEBERSETZER_OK = paket_installieren("deep-translator", "deep_translator")
AUTOKLICKER_OK = paket_installieren("keyboard", "keyboard")
BROWSER_PAKET_OK = (
    paket_installieren("pythonnet", "clr")
    and paket_installieren("pywebview", "webview")
)


# ============================================================
# IMPORTS
# ============================================================

from PIL import Image, ImageTk, ImageFilter, ImageDraw, ImageFont

if CV2_OK:
    import cv2
else:
    cv2 = None

if UEBERSETZER_OK:
    from deep_translator import GoogleTranslator, DeeplTranslator
else:
    GoogleTranslator = None
    DeeplTranslator = None

if AUTOKLICKER_OK:
    import keyboard
else:
    keyboard = None

import webbrowser

WEBVIEW_OK = False
EingebetteterBrowser = None

if BROWSER_PAKET_OK:
    try:
        import clr as _eni_clr
        from webview.platforms.edgechromium import EdgeChrome as _EniEdgeChrome
        from webview.window import Window as _EniFensterModell

        _eni_clr.AddReference("System.Windows.Forms")
        from System.Windows.Forms import Control as _EniControl

        from uuid import uuid4 as _eni_uuid4

        _eni_browser_fenster = []

        class _EniEingebetteterBrowser(tk.Frame):
            # Echter eingebetteter Chromium-Browser (WebView2) als
            # normales Tkinter-Widget - Rechte an pywebview/tkwebview2
            # angelehnt, mit einer Korrektur für die aktuelle
            # pywebview-Version (Attributname hat sich geändert).
            def __init__(self, parent, breite, hoehe, url="", **kw):
                tk.Frame.__init__(self, parent, width=breite, height=hoehe, **kw)

                control = _EniControl()
                uid = (
                    "master" if not _eni_browser_fenster
                    else "child_" + _eni_uuid4().hex[:8]
                )

                fenster_modell = _EniFensterModell(
                    uid, str(id(self)), url=None, html=None, js_api=None,
                    width=breite, height=hoehe, x=None, y=None,
                    resizable=True, fullscreen=False, min_size=(200, 100),
                    hidden=False, frameless=False, easy_drag=True,
                    minimized=False, on_top=False, confirm_close=False,
                    background_color="#161618", transparent=False,
                    text_select=True, localization=None,
                    zoomable=True, draggable=True, vibrancy=False
                )

                self._fenster_modell = fenster_modell
                self._web_view = _EniEdgeChrome(control, fenster_modell, None)
                self._control = control
                self._web = self._web_view.webview
                _eni_browser_fenster.append(fenster_modell)

                self._chwnd = int(str(self._control.Handle))
                ctypes.windll.user32.SetParent(
                    self._chwnd, self.winfo_id()
                )
                ctypes.windll.user32.MoveWindow(
                    self._chwnd, 0, 0, breite, hoehe, True
                )

                self.bind("<Destroy>", lambda e: self._web.Dispose())
                self.bind("<Configure>", self._groesse_anpassen)

                if url:
                    self.url_laden(url)

            def _groesse_anpassen(self, event):
                ctypes.windll.user32.MoveWindow(
                    self._chwnd, 0, 0,
                    self.winfo_width(), self.winfo_height(), True
                )

            def url_laden(self, url):
                self._web_view.load_url(url)

        EingebetteterBrowser = _EniEingebetteterBrowser
        WEBVIEW_OK = True

    except Exception as _eni_webview_fehler:
        print(f"Eingebetteter Browser nicht verfügbar: {_eni_webview_fehler}")


# ============================================================
# KONFIGURATION
# ============================================================

APP_NAME = "ENI SERVICE"

BREITE = 1000
HOEHE = 720

ORDNER = Path(__file__).resolve().parent

BAT_DATEI = ORDNER / "eni_multitool_run.bat"
PY_DATEI = ORDNER / "eni_multitool.py"

BAT_URL = (
    "https://raw.githubusercontent.com/"
    "sv3rigePy/ENIMULTITOOL/refs/heads/main/"
    "eni_multitool_run.bat"
)

PY_URL = (
    "https://raw.githubusercontent.com/"
    "sv3rigePy/ENIMULTITOOL/refs/heads/main/"
    "eni_multitool.py"
)

HINTERGRUND_DATEI = ORDNER / "background.jpg"

HINTERGRUND_URL = (
    "https://raw.githubusercontent.com/"
    "sv3rigePy/ENIMULTITOOL/refs/heads/main/"
    "background.jpg"
)

VIDEO_INFO = ORDNER / "background_video.txt"

LOG_DATEI = ORDNER / "eni_service.log"

UEBERSETZER_KONFIG_DATEI = ORDNER / "eni_translator_config.json"

AUTOKLICKER_KONFIG_DATEI = ORDNER / "eni_autoclicker_config.json"

NOTIZEN_DATEI = ORDNER / "eni_notizen.json"
DESKTOP_ICONS_DATEI = ORDNER / "eni_desktop_icons.json"
EINSTELLUNGEN_DATEI = ORDNER / "eni_einstellungen.json"


# ============================================================
# SPRACHEN
# ============================================================

SPRACHE = "de"


TEXT = {
    "de": {
        "eni": "EniMultitool",
        "menu_open": "Terminal öffnen",
        "menu_close": "Terminal schließen",
        "settings": "Einstellungen",
        "folder": "Ordner öffnen",
        "log": "Log",
        "internet": "Internet testen",
        "temp": "Temporäre Dateien aufräumen",
        "background": "Hintergrund auswählen",
        "status_ready": "Bereit",
        "settings_title": "Einstellungen",
        "language": "Sprache",
        "transparency": "Transparenz",
        "choose_background": "Hintergrund auswählen",
        "choose_video": "Video auswählen",
        "reset_background": "Standard-Hintergrund",
        "settings_taskbar_color": "Taskleiste - Farbe für offene Programme",
        "settings_taskbar_color_choose": "Farbe wählen",
        "close": "Schließen",
        "back": "Zurück",
        "log_title": "Log",
        "internet_title": "Internet-Verbindung",
        "internet_yes": "Internet-Verbindung vorhanden.",
        "internet_no": "Keine Internet-Verbindung.",
        "temp_title": "Temporäre Dateien",
        "temp_confirm": (
            "Möchtest du die temporären Dateien wirklich aufräumen?\n\n"
            "Nur Dateien innerhalb des Windows-Temp-Ordners werden "
            "bearbeitet.\n"
            "Dateien, die gerade verwendet werden, werden übersprungen."
        ),
        "temp_done": (
            "Temp-Bereinigung abgeschlossen.\n\n"
            "Gelöscht: {deleted}\n"
            "Übersprungen: {skipped}\n"
            "Freigegeben: {size}"
        ),
        "download": "Download",
        "download_files": "Lade benötigte Dateien herunter...",
        "download_done": "Download abgeschlossen.",
        "download_error": "Download fehlgeschlagen.",
        "background_download": "Standard-Hintergrund wird heruntergeladen...",
        "folder_error": "Ordner konnte nicht geöffnet werden.",
        "video_error": "Video konnte nicht geladen werden.",
        "translate": "Übersetzer (Beta)",
        "translate_title": "Übersetzer (Beta)",
        "translate_source": "Von",
        "translate_target": "Nach",
        "translate_input": "Text",
        "translate_output": "Übersetzung",
        "translate_button": "Übersetzen",
        "translate_empty": "Bitte gib einen Text ein.",
        "translate_error": (
            "Übersetzung fehlgeschlagen. "
            "Prüfe deine Internetverbindung und versuche es erneut."
        ),
        "translate_missing_lib": (
            "Die Übersetzer-Bibliothek konnte nicht installiert werden."
        ),
        "translate_deepl_key": (
            "DeepL API-Key (optional, für zuverlässigere Übersetzungen "
            "– ohne Key wird die kostenlose Google-Übersetzung versucht)"
        ),
        "auto_detect": "Automatisch erkennen",
        "autoclicker": "Autoclicker",
        "autoclicker_title": "Autoclicker",
        "autoclicker_interval": "Intervall (Millisekunden)",
        "autoclicker_button_side": "Maustaste",
        "autoclicker_start": "Starten",
        "autoclicker_stop": "Stoppen",
        "autoclicker_status_running": "Läuft... ({klicks} Klicks)",
        "autoclicker_status_stopped": "Gestoppt",
        "autoclicker_hotkey_hinweis": (
            "Der Hotkey funktioniert auch, wenn ein anderes Fenster "
            "im Vordergrund ist (z. B. ein Spiel)."
        ),
        "autoclicker_missing_lib": (
            "Die Hotkey-Bibliothek konnte nicht installiert werden. "
            "Start/Stopp funktioniert nur über den Knopf in diesem Fenster."
        ),
        "autoclicker_invalid_interval": (
            "Bitte ein gültiges Intervall in Millisekunden eingeben "
            "(mindestens 10)."
        ),
        "autoclicker_hotkey": "Hotkey",
        "autoclicker_change_hotkey": "Ändern",
        "autoclicker_press_key": "Drücke eine Taste...",
        "commands": "Befehle",
        "commands_title": "Wichtige Befehle",
        "commands_copy": "Kopieren",
        "commands_copied": "Kopiert!",
        "password": "Passwort-Generator",
        "password_gen": "Passwort-Generator",
        "password_length": "Länge",
        "password_uppercase": "Großbuchstaben (A-Z)",
        "password_lowercase": "Kleinbuchstaben (a-z)",
        "password_digits": "Zahlen (0-9)",
        "password_symbols": "Sonderzeichen (!?%&...)",
        "password_generate": "Generieren",
        "password_copy": "Kopieren",
        "password_copied": "Kopiert!",
        "password_none_selected": (
            "Bitte mindestens eine Zeichenart auswählen."
        ),
        "sysinfo": "System-Info",
        "sysinfo_title": "System-Informationen",
        "sysinfo_os": "Betriebssystem",
        "sysinfo_computer": "Rechnername",
        "sysinfo_cpu": "CPU-Kerne",
        "sysinfo_ram": "Arbeitsspeicher",
        "sysinfo_disk": "Festplatte (C:)",
        "sysinfo_refresh": "Aktualisieren",
        "notes": "Notizen",
        "notes_title": "Notizen",
        "notes_new_page": "+ Neue Seite",
        "notes_rename": "Umbenennen",
        "notes_delete": "Löschen",
        "notes_delete_confirm": "Diese Seite wirklich löschen?",
        "notes_rename_prompt": "Neuer Seitenname:",
        "desktop_add": "Auf Desktop anzeigen",
        "desktop_remove": "Vom Desktop entfernen",
        "desktop_icon_rename": "Namen ändern",
        "desktop_icon_rename_prompt": "Neuer Name:",
        "desktop_icon_image": "Hintergrundbild wählen",
        "desktop_icon_image_reset": "Standardbild verwenden",
        "deepl_web": "DeepL",
        "deepl_web_title": "DeepL",
        "tempmail_web": "Temp-Mail",
        "tempmail_web_title": "Temp-Mail",
        "webview_missing": (
            "Eingebetteter Browser nicht verfügbar - Seite wird stattdessen "
            "im normalen Browser geöffnet."
        ),
        "clock": "Uhr",
        "clock_title": "Uhr",
        "clock_timer_heading": "TIMER",
        "clock_stopwatch_heading": "STOPPUHR",
        "clock_hours": "Stunden",
        "clock_minutes": "Minuten",
        "clock_seconds": "Sekunden",
        "clock_start": "Start",
        "clock_pause": "Pause",
        "clock_resume": "Fortsetzen",
        "clock_reset": "Zurücksetzen",
        "clock_status_running": "Läuft",
        "clock_status_paused": "Pausiert",
        "clock_status_stopped": "Gestoppt",
        "clock_timer_invalid": "Bitte eine gültige Zeit eingeben.",
        "clock_alarm_title": "Timer abgelaufen!",
        "clock_alarm_message": "Die eingestellte Zeit ist abgelaufen.",
        "clock_alarm_off": "Alarm ausschalten",
    },

    "en": {
        "eni": "EniMultitool",
        "menu_open": "Open terminal",
        "menu_close": "Close terminal",
        "settings": "Settings",
        "folder": "Open folder",
        "log": "Log",
        "internet": "Test internet",
        "temp": "Clean temporary files",
        "background": "Choose background",
        "status_ready": "Ready",
        "settings_title": "Settings",
        "language": "Language",
        "transparency": "Transparency",
        "choose_background": "Choose background",
        "choose_video": "Choose video",
        "reset_background": "Default background",
        "settings_taskbar_color": "Taskbar - color for open programs",
        "settings_taskbar_color_choose": "Choose color",
        "close": "Close",
        "back": "Back",
        "log_title": "Log",
        "internet_title": "Internet connection",
        "internet_yes": "Internet connection available.",
        "internet_no": "No internet connection.",
        "temp_title": "Temporary files",
        "temp_confirm": (
            "Do you really want to clean the temporary files?\n\n"
            "Only files inside the Windows Temp folder will be processed.\n"
            "Files currently in use will be skipped."
        ),
        "temp_done": (
            "Temp cleanup completed.\n\n"
            "Deleted: {deleted}\n"
            "Skipped: {skipped}\n"
            "Freed: {size}"
        ),
        "download": "Download",
        "download_files": "Downloading required files...",
        "download_done": "Download completed.",
        "download_error": "Download failed.",
        "background_download": "Downloading default background...",
        "folder_error": "Could not open folder.",
        "video_error": "Could not load video.",
        "translate": "Translator (Beta)",
        "translate_title": "Translator (Beta)",
        "translate_source": "From",
        "translate_target": "To",
        "translate_input": "Text",
        "translate_output": "Translation",
        "translate_button": "Translate",
        "translate_empty": "Please enter some text.",
        "translate_error": (
            "Translation failed. "
            "Check your internet connection and try again."
        ),
        "translate_missing_lib": (
            "The translator library could not be installed."
        ),
        "translate_deepl_key": (
            "DeepL API key (optional, for more reliable translations "
            "- without a key, free Google Translate is tried)"
        ),
        "auto_detect": "Auto-detect",
        "autoclicker": "Autoclicker",
        "autoclicker_title": "Autoclicker",
        "autoclicker_interval": "Interval (milliseconds)",
        "autoclicker_button_side": "Mouse button",
        "autoclicker_start": "Start",
        "autoclicker_stop": "Stop",
        "autoclicker_status_running": "Running... ({klicks} clicks)",
        "autoclicker_status_stopped": "Stopped",
        "autoclicker_hotkey_hinweis": (
            "The hotkey also works while another window is in the "
            "foreground (e.g. a game)."
        ),
        "autoclicker_missing_lib": (
            "The hotkey library could not be installed. "
            "Start/stop only works via the button in this window."
        ),
        "autoclicker_invalid_interval": (
            "Please enter a valid interval in milliseconds (at least 10)."
        ),
        "autoclicker_hotkey": "Hotkey",
        "autoclicker_change_hotkey": "Change",
        "autoclicker_press_key": "Press a key...",
        "commands": "Commands",
        "commands_title": "Important Commands",
        "commands_copy": "Copy",
        "commands_copied": "Copied!",
        "password": "Password Generator",
        "password_gen": "Password Generator",
        "password_length": "Length",
        "password_uppercase": "Uppercase (A-Z)",
        "password_lowercase": "Lowercase (a-z)",
        "password_digits": "Digits (0-9)",
        "password_symbols": "Symbols (!?%&...)",
        "password_generate": "Generate",
        "password_copy": "Copy",
        "password_copied": "Copied!",
        "password_none_selected": (
            "Please select at least one character type."
        ),
        "sysinfo": "System Info",
        "sysinfo_title": "System Information",
        "sysinfo_os": "Operating system",
        "sysinfo_computer": "Computer name",
        "sysinfo_cpu": "CPU cores",
        "sysinfo_ram": "Memory",
        "sysinfo_disk": "Disk (C:)",
        "sysinfo_refresh": "Refresh",
        "notes": "Notes",
        "notes_title": "Notes",
        "notes_new_page": "+ New page",
        "notes_rename": "Rename",
        "notes_delete": "Delete",
        "notes_delete_confirm": "Really delete this page?",
        "notes_rename_prompt": "New page name:",
        "desktop_add": "Show on desktop",
        "desktop_remove": "Remove from desktop",
        "desktop_icon_rename": "Rename",
        "desktop_icon_rename_prompt": "New name:",
        "desktop_icon_image": "Choose background image",
        "desktop_icon_image_reset": "Use default image",
        "deepl_web": "DeepL",
        "deepl_web_title": "DeepL",
        "tempmail_web": "Temp-Mail",
        "tempmail_web_title": "Temp-Mail",
        "webview_missing": (
            "Embedded browser not available - opening the page in your "
            "normal browser instead."
        ),
        "clock": "Clock",
        "clock_title": "Clock",
        "clock_timer_heading": "TIMER",
        "clock_stopwatch_heading": "STOPWATCH",
        "clock_hours": "Hours",
        "clock_minutes": "Minutes",
        "clock_seconds": "Seconds",
        "clock_start": "Start",
        "clock_pause": "Pause",
        "clock_resume": "Resume",
        "clock_reset": "Reset",
        "clock_status_running": "Running",
        "clock_status_paused": "Paused",
        "clock_status_stopped": "Stopped",
        "clock_timer_invalid": "Please enter a valid time.",
        "clock_alarm_title": "Timer finished!",
        "clock_alarm_message": "The time you set has run out.",
        "clock_alarm_off": "Turn off alarm",
    }
}


def t(key):
    return TEXT[SPRACHE][key]


# ============================================================
# LOG-SYSTEM
# ============================================================

LOG_ENTRIES = []


def log(text):
    zeit = datetime.now().strftime("%H:%M:%S")
    eintrag = f"[{zeit}] {text}"

    LOG_ENTRIES.append(eintrag)

    try:
        with open(LOG_DATEI, "a", encoding="utf-8") as f:
            f.write(eintrag + "\n")
    except Exception:
        pass

    print(eintrag)

    if "log_text" in globals():
        try:
            log_text.config(state="normal")
            log_text.insert("end", eintrag + "\n")
            log_text.see("end")
            log_text.config(state="disabled")
        except Exception:
            pass


# ============================================================
# HAUPTFENSTER
# ============================================================

fenster = tk.Tk()

fenster.title(APP_NAME)
fenster.geometry(f"{BREITE}x{HOEHE}")
fenster.resizable(False, False)
fenster.configure(bg="#0b0c0d")

try:
    fenster.iconname(APP_NAME)
except Exception:
    pass


# ============================================================
# EINHEITLICHES DESIGN (Farben + ttk-Theme)
# ============================================================
#
# ttk-Widgets (Combobox, Scrollbar, Progressbar, ...) ignorieren
# normale bg/fg-Optionen und sehen ohne das hier immer hell/nativ
# aus - das hat bisher hart mit dem dunklen Design gebrochen.

FARBE_HINTERGRUND = "#161618"
FARBE_TITELLEISTE = "#202124"
FARBE_OBERFLAECHE = "#202124"
FARBE_HOVER = "#2c2d31"
FARBE_RAND = "#333438"
FARBE_TEXT = "#eaeaea"
FARBE_TEXT_GEDAEMPFT = "#9a9aa0"
FARBE_AKZENT = "#3ef2a4"
FARBE_AKZENT_DUNKEL = "#1c8a5c"
FARBE_EINGABE = "#0f1011"

def einstellungen_laden():
    try:
        if EINSTELLUNGEN_DATEI.exists():
            with open(EINSTELLUNGEN_DATEI, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        try:
            log(f"Einstellungen konnten nicht geladen werden: {e}")
        except Exception:
            pass

    return {}


def einstellungen_speichern(daten):
    try:
        aktuell = einstellungen_laden()
        aktuell.update(daten)

        with open(EINSTELLUNGEN_DATEI, "w", encoding="utf-8") as f:
            json.dump(aktuell, f, ensure_ascii=False)

        try:
            log(f"Einstellungen gespeichert: {daten} -> {EINSTELLUNGEN_DATEI}")
        except Exception:
            pass

    except Exception as e:
        try:
            log(f"Einstellungen konnten nicht gespeichert werden: {e}")
        except Exception:
            pass


# In den Einstellungen änderbar: Farbe, mit der aktive (offene)
# Programme in der Taskleiste hervorgehoben werden. Wird dauerhaft
# gespeichert, damit sie nach einem Neustart erhalten bleibt.
TASKLEISTE_AKTIV_FARBE = einstellungen_laden().get(
    "taskleiste_farbe", FARBE_AKZENT
)

try:
    log(
        f"Einstellungen beim Start geladen aus {EINSTELLUNGEN_DATEI}: "
        f"Taskleisten-Farbe = {TASKLEISTE_AKTIV_FARBE}"
    )
except Exception:
    pass

# Gemeinsamer Rahmen-Stil für Entry/Text-Felder - macht sie als
# eigene Elemente erkennbar statt als schwarzes Loch, plus ein
# dezentes Aufleuchten in Akzentfarbe bei Fokus.
EINGABE_RAHMEN = {
    "highlightthickness": 1,
    "highlightbackground": FARBE_RAND,
    "highlightcolor": FARBE_AKZENT,
    "bd": 0,
    "relief": "flat",
}

ttk_stil = ttk.Style(fenster)

try:
    ttk_stil.theme_use("clam")
except Exception:
    pass

ttk_stil.configure(
    "TCombobox",
    fieldbackground=FARBE_EINGABE,
    background=FARBE_OBERFLAECHE,
    foreground=FARBE_TEXT,
    arrowcolor=FARBE_TEXT,
    bordercolor=FARBE_RAND,
    lightcolor=FARBE_EINGABE,
    darkcolor=FARBE_EINGABE,
    padding=4
)
ttk_stil.map(
    "TCombobox",
    fieldbackground=[("readonly", FARBE_EINGABE)],
    foreground=[("readonly", FARBE_TEXT)],
    selectbackground=[("readonly", FARBE_EINGABE)],
    selectforeground=[("readonly", FARBE_TEXT)]
)

fenster.option_add("*TCombobox*Listbox.background", FARBE_EINGABE)
fenster.option_add("*TCombobox*Listbox.foreground", FARBE_TEXT)
fenster.option_add(
    "*TCombobox*Listbox.selectBackground", FARBE_AKZENT_DUNKEL
)
fenster.option_add("*TCombobox*Listbox.selectForeground", FARBE_TEXT)

ttk_stil.configure(
    "TScrollbar",
    background=FARBE_OBERFLAECHE,
    troughcolor=FARBE_HINTERGRUND,
    arrowcolor=FARBE_TEXT,
    bordercolor=FARBE_HINTERGRUND
)
ttk_stil.map("TScrollbar", background=[("active", FARBE_HOVER)])

ttk_stil.configure(
    "TProgressbar",
    background=FARBE_AKZENT,
    troughcolor=FARBE_OBERFLAECHE,
    bordercolor=FARBE_HINTERGRUND,
    lightcolor=FARBE_AKZENT,
    darkcolor=FARBE_AKZENT
)


# ============================================================
# HINTERGRUND
# ============================================================

hintergrund_label = tk.Label(
    fenster,
    bd=0
)

hintergrund_label.place(
    x=0,
    y=0,
    width=BREITE,
    height=HOEHE
)

aktuelles_hintergrundbild = None
video_cap = None
video_aktiv = False

# Letztes Hintergrundbild (PIL, volle Fenstergröße) für den
# durchscheinenden Overlay-/Knopf-Hintergrund.
LETZTES_FRAME = None

# Wiederverwendetes PhotoImage für den Video-Hintergrund. Ein
# .paste() auf ein bestehendes Bild ist deutlich schneller als
# bei jedem Frame ein komplett neues Tk-Bild zu erzeugen.
VIDEO_PHOTO = None
VIDEO_ZAEHLER = 0


def hintergrund_bild_setzen(pfad):
    global aktuelles_hintergrundbild
    global LETZTES_FRAME

    try:
        bild = Image.open(pfad).convert("RGB")
        bild = bild.resize(
            (BREITE, HOEHE),
            Image.Resampling.LANCZOS
        )

        LETZTES_FRAME = bild

        aktuelles_hintergrundbild = ImageTk.PhotoImage(bild)

        hintergrund_label.config(
            image=aktuelles_hintergrundbild
        )

        panel_hintergrund_aktualisieren()

        log(f"Hintergrund gesetzt: {pfad}")

    except Exception as e:
        log(f"Fehler beim Hintergrund: {e}")


def video_stoppen():
    global video_cap
    global video_aktiv

    video_aktiv = False

    if video_cap is not None:
        try:
            video_cap.release()
        except Exception:
            pass

    video_cap = None


def video_starten(pfad):
    global video_cap
    global video_aktiv

    if cv2 is None:
        messagebox.showerror(
            "OpenCV",
            "OpenCV konnte nicht installiert werden."
        )
        return

    try:
        video_stoppen()

        video_cap = cv2.VideoCapture(str(pfad))

        if not video_cap.isOpened():
            raise Exception("Video konnte nicht geöffnet werden.")

        video_aktiv = True

        log(f"Video-Hintergrund gestartet: {pfad}")

        video_frame()

    except Exception as e:
        log(f"Video-Fehler: {e}")
        messagebox.showerror(
            "Video",
            t("video_error")
        )


def video_frame():
    global video_cap
    global video_aktiv
    global LETZTES_FRAME
    global VIDEO_PHOTO
    global VIDEO_ZAEHLER

    if not video_aktiv or video_cap is None:
        return

    try:
        ret, frame = video_cap.read()

        if not ret:
            video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            fenster.after(30, video_frame)
            return

        # Skalieren passiert mit OpenCV (schnelles C++) statt mit
        # PIL/LANCZOS - das war der Hauptgrund für das Ruckeln bei
        # Video-Hintergründen.
        frame = cv2.resize(
            frame,
            (BREITE, HOEHE),
            interpolation=cv2.INTER_LINEAR
        )

        frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        bild = Image.fromarray(frame)

        LETZTES_FRAME = bild

        if VIDEO_PHOTO is None:
            VIDEO_PHOTO = ImageTk.PhotoImage(bild)

            hintergrund_label.config(
                image=VIDEO_PHOTO
            )
        else:
            # Bestehendes Tk-Bild nur mit neuen Pixeln füllen,
            # statt jedes Mal ein neues Bild bei Tk zu registrieren.
            VIDEO_PHOTO.paste(bild)

        VIDEO_ZAEHLER += 1

        # Der Overlay-/Knopf-Hintergrund muss nicht bei jedem
        # einzelnen Video-Frame neu berechnet werden.
        if VIDEO_ZAEHLER % 3 == 0:
            panel_hintergrund_aktualisieren()

        fenster.after(30, video_frame)

    except Exception as e:
        log(f"Video-Frame-Fehler: {e}")


# ============================================================
# STANDARD-HINTERGRUND
# ============================================================

def standard_hintergrund_laden():

    if HINTERGRUND_DATEI.exists():
        hintergrund_bild_setzen(HINTERGRUND_DATEI)
        return

    log(t("background_download"))

    def download():
        try:
            urllib.request.urlretrieve(
                HINTERGRUND_URL,
                HINTERGRUND_DATEI
            )

            fenster.after(
                0,
                lambda: hintergrund_bild_setzen(
                    HINTERGRUND_DATEI
                )
            )

            log("Standard-Hintergrund heruntergeladen.")

        except Exception as e:
            log(f"Fehler beim Hintergrund-Download: {e}")

    threading.Thread(
        target=download,
        daemon=True
    ).start()


# ============================================================
# HINTERGRUND AUSWÄHLEN
# ============================================================

def hintergrund_auswaehlen():

    datei = filedialog.askopenfilename(
        title=t("background"),
        filetypes=[
            (
                "Bilder",
                "*.jpg *.jpeg *.png *.bmp *.webp"
            )
        ]
    )

    if not datei:
        return

    try:
        video_stoppen()

        shutil.copy2(
            datei,
            HINTERGRUND_DATEI
        )

        if VIDEO_INFO.exists():
            try:
                VIDEO_INFO.unlink()
            except Exception:
                pass

        hintergrund_bild_setzen(
            HINTERGRUND_DATEI
        )

        log(f"Neuer Bild-Hintergrund: {datei}")

    except Exception as e:
        log(f"Fehler beim Bild-Hintergrund: {e}")


def video_auswaehlen():

    datei = filedialog.askopenfilename(
        title=t("choose_video"),
        filetypes=[
            (
                "Videos",
                "*.mp4 *.avi *.mov *.mkv *.webm"
            )
        ]
    )

    if not datei:
        return

    try:
        video_stoppen()

        suffix = Path(datei).suffix

        video_datei = (
            ORDNER / f"background_video{suffix}"
        )

        shutil.copy2(
            datei,
            video_datei
        )

        with open(
            VIDEO_INFO,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(str(video_datei))

        if HINTERGRUND_DATEI.exists():
            try:
                HINTERGRUND_DATEI.unlink()
            except Exception:
                pass

        video_starten(video_datei)

        log(f"Neuer Video-Hintergrund: {datei}")

    except Exception as e:
        log(f"Fehler beim Video-Hintergrund: {e}")


def gespeicherten_hintergrund_laden():

    if VIDEO_INFO.exists():

        try:
            with open(
                VIDEO_INFO,
                "r",
                encoding="utf-8"
            ) as f:
                video_pfad = f.read().strip()

            if Path(video_pfad).exists():
                video_starten(video_pfad)
                return

        except Exception as e:
            log(f"Gespeichertes Video konnte nicht geladen werden: {e}")

    standard_hintergrund_laden()


# ============================================================
# ORDNER ÖFFNEN
# ============================================================

def ordner_oeffnen():

    try:
        os.startfile(str(ORDNER))
        log("Programmordner geöffnet.")

    except Exception as e:
        log(f"Ordner konnte nicht geöffnet werden: {e}")

        messagebox.showerror(
            "Fehler",
            t("folder_error")
        )


# ============================================================
# INTERNET TEST
# ============================================================

def internet_testen():

    log("Internet-Verbindung wird getestet...")

    def test():

        try:
            socket.create_connection(
                ("www.google.com", 443),
                timeout=5
            )

            fenster.after(
                0,
                internet_erfolgreich
            )

        except Exception:
            fenster.after(
                0,
                internet_fehlgeschlagen
            )

    threading.Thread(
        target=test,
        daemon=True
    ).start()


def internet_erfolgreich():

    log("Internet-Verbindung vorhanden.")

    messagebox.showinfo(
        t("internet_title"),
        t("internet_yes")
    )


def internet_fehlgeschlagen():

    log("Keine Internet-Verbindung.")

    messagebox.showwarning(
        t("internet_title"),
        t("internet_no")
    )


# ============================================================
# TEMP-BEREINIGUNG
# ============================================================

def groesse_formatieren(bytes_groesse):

    if bytes_groesse < 1024:
        return f"{bytes_groesse} B"

    if bytes_groesse < 1024 ** 2:
        return f"{bytes_groesse / 1024:.1f} KB"

    if bytes_groesse < 1024 ** 3:
        return f"{bytes_groesse / (1024 ** 2):.1f} MB"

    return f"{bytes_groesse / (1024 ** 3):.2f} GB"


def temp_aufräumen():

    bestaetigung = messagebox.askyesno(
        t("temp_title"),
        t("temp_confirm")
    )

    if not bestaetigung:
        log("Temp-Bereinigung abgebrochen.")
        return

    log("Temp-Bereinigung gestartet.")

    threading.Thread(
        target=temp_bereinigung_thread,
        daemon=True
    ).start()


def temp_bereinigung_thread():

    temp_ordner = Path(os.environ.get("TEMP", ""))

    geloescht = 0
    uebersprungen = 0
    freigegeben = 0

    if not temp_ordner.exists():
        fenster.after(
            0,
            lambda: temp_bereinigung_fertig(
                0,
                0,
                0
            )
        )
        return

    try:

        for eintrag in temp_ordner.iterdir():

            try:

                if eintrag.is_file():

                    try:
                        groesse = eintrag.stat().st_size
                    except Exception:
                        groesse = 0

                    eintrag.unlink()

                    geloescht += 1
                    freigegeben += groesse

                elif eintrag.is_dir():

                    groesse = 0

                    try:
                        for root, dirs, files in os.walk(
                            eintrag,
                            topdown=True
                        ):
                            for file in files:
                                try:
                                    groesse += (
                                        Path(root, file)
                                        .stat()
                                        .st_size
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    shutil.rmtree(eintrag)

                    geloescht += 1
                    freigegeben += groesse

            except Exception:
                uebersprungen += 1

    except Exception as e:
        log(f"Temp-Fehler: {e}")

    fenster.after(
        0,
        lambda: temp_bereinigung_fertig(
            geloescht,
            uebersprungen,
            freigegeben
        )
    )


def temp_bereinigung_fertig(
    geloescht,
    uebersprungen,
    freigegeben
):

    log(
        f"Temp-Bereinigung beendet: "
        f"{geloescht} gelöscht, "
        f"{uebersprungen} übersprungen, "
        f"{groesse_formatieren(freigegeben)} freigegeben."
    )

    messagebox.showinfo(
        t("temp_title"),
        t("temp_done").format(
            deleted=geloescht,
            skipped=uebersprungen,
            size=groesse_formatieren(freigegeben)
        )
    )


log_text = None


# ============================================================
# ENIMULTITOOL DOWNLOAD
# ============================================================

def datei_download(url, ziel):

    try:

        urllib.request.urlretrieve(
            url,
            ziel
        )

        return True

    except Exception as e:

        log(
            f"Download-Fehler bei {ziel.name}: {e}"
        )

        return False


def eni_multitool_starten():

    fehlende = []

    if not BAT_DATEI.exists():
        fehlende.append(
            ("eni_multitool_run.bat", BAT_URL, BAT_DATEI)
        )

    if not PY_DATEI.exists():
        fehlende.append(
            ("eni_multitool.py", PY_URL, PY_DATEI)
        )

    if fehlende:
        download_starten(fehlende)
        return

    log("EniMultitool-Dateien vorhanden.")
    ansicht_zeigen("eni_console")


# Das echte cmd-Fenster des EniMultitools wird als natives
# Windows-Fenster in das Panel eingebettet (SetParent), statt es
# als eigenes freischwebendes Fenster zu öffnen - genau wie beim
# eingebetteten Browser. Der Quellcode des Multitools selbst wird
# dabei nirgends gelesen oder angefasst.
ENI_MULTITOOL_PROZESS = None
ENI_KONSOLE_HWND = None

from ctypes import wintypes as _wintypes

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_GetWindowLong = getattr(_user32, "GetWindowLongPtrW", _user32.GetWindowLongW)
_SetWindowLong = getattr(_user32, "SetWindowLongPtrW", _user32.SetWindowLongW)

# HWND ist zeigergroß (auf 64-Bit-Windows 8 Byte) - ohne die
# korrekten Signaturen behandelt ctypes Rückgabe-/Parameterwerte
# sonst als 32-Bit int und Fensterkennungen können dabei
# stillschweigend abgeschnitten werden.
_GetWindowLong.restype = _wintypes.LPVOID
_GetWindowLong.argtypes = [_wintypes.HWND, ctypes.c_int]
_SetWindowLong.restype = _wintypes.LPVOID
_SetWindowLong.argtypes = [_wintypes.HWND, ctypes.c_int, _wintypes.LPVOID]

_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_APPWINDOW = 0x00040000


_user32.SetParent.restype = _wintypes.HWND
_user32.SetParent.argtypes = [_wintypes.HWND, _wintypes.HWND]

_user32.MoveWindow.restype = _wintypes.BOOL
_user32.MoveWindow.argtypes = [
    _wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, _wintypes.BOOL
]

_user32.SetWindowPos.restype = _wintypes.BOOL
_user32.SetWindowPos.argtypes = [
    _wintypes.HWND, _wintypes.HWND,
    ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int,
    ctypes.c_uint
]

_user32.IsWindowVisible.restype = _wintypes.BOOL
_user32.IsWindowVisible.argtypes = [_wintypes.HWND]

_user32.GetClassNameW.restype = ctypes.c_int
_user32.GetClassNameW.argtypes = [
    _wintypes.HWND, _wintypes.LPWSTR, ctypes.c_int
]

_user32.GetWindowThreadProcessId.restype = _wintypes.DWORD
_user32.GetWindowThreadProcessId.argtypes = [
    _wintypes.HWND, ctypes.POINTER(_wintypes.DWORD)
]

_user32.AttachThreadInput.restype = _wintypes.BOOL
_user32.AttachThreadInput.argtypes = [
    _wintypes.DWORD, _wintypes.DWORD, _wintypes.BOOL
]

_user32.SetForegroundWindow.restype = _wintypes.BOOL
_user32.SetForegroundWindow.argtypes = [_wintypes.HWND]

_user32.SetActiveWindow.restype = _wintypes.HWND
_user32.SetActiveWindow.argtypes = [_wintypes.HWND]

_user32.SetFocus.restype = _wintypes.HWND
_user32.SetFocus.argtypes = [_wintypes.HWND]

_user32.GetParent.restype = _wintypes.HWND
_user32.GetParent.argtypes = [_wintypes.HWND]

_kernel32.GetCurrentThreadId.restype = _wintypes.DWORD
_kernel32.GetCurrentThreadId.argtypes = []

_GWL_STYLE = -16
_GWL_EXSTYLE = -20
_GWLP_HWNDPARENT = -8
_WS_CAPTION = 0x00C00000
_WS_THICKFRAME = 0x00040000
_WS_POPUP = 0x80000000
_WS_CHILD = 0x40000000
_WS_SYSMENU = 0x00080000


def _eni_sichtbare_konsolenfenster():
    # Nicht über die Prozess-ID suchen: Auf aktuellem Windows läuft
    # cmd.exe standardmäßig in Windows Terminal, dessen Fenster
    # einem ANDEREN Prozess gehört als dem, den wir gestartet haben.
    # Stattdessen wird vor und nach dem Start verglichen, welches
    # Konsolen-/Terminalfenster neu dazugekommen ist.
    from ctypes import wintypes

    ergebnisse = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True

        klasse = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, klasse, 256)

        if klasse.value in (
            "ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"
        ):
            ergebnisse.append(hwnd)

        return True

    _user32.EnumWindows(_callback, 0)

    return set(ergebnisse)


def _eni_konsole_schliessen():
    """Schließt die EniMultitool-Konsole und ihren Prozess sauber."""
    global ENI_KONSOLE_HWND, ENI_MULTITOOL_PROZESS

    hwnd = ENI_KONSOLE_HWND
    ENI_KONSOLE_HWND = None

    # Erst das sichtbare Konsolenfenster schließen.
    if hwnd:
        try:
            _user32.ShowWindow(hwnd, 0)  # SW_HIDE
        except Exception:
            pass
        try:
            _user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        except Exception:
            pass

    # Danach den von uns gestarteten Prozess beenden.
    proc = ENI_MULTITOOL_PROZESS
    ENI_MULTITOOL_PROZESS = None

    if proc is not None:
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception as e:
            log(f"Fehler beim Schließen des EniMultitools: {e}")


def eni_konsole_fokussieren():
    """Fokus auf die echte Windows-Konsole setzen."""
    if ENI_KONSOLE_HWND is None:
        return

    try:
        hwnd = ENI_KONSOLE_HWND
        if not _user32.IsWindow(hwnd):
            return

        ziel_thread = _user32.GetWindowThreadProcessId(hwnd, None)
        eigener_thread = _kernel32.GetCurrentThreadId()
        verbunden = False

        if ziel_thread and ziel_thread != eigener_thread:
            verbunden = bool(
                _user32.AttachThreadInput(
                    eigener_thread, ziel_thread, True
                )
            )

        _user32.ShowWindow(hwnd, 5)  # SW_SHOW
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
        _user32.SetActiveWindow(hwnd)
        _user32.SetFocus(hwnd)

        if verbunden:
            _user32.AttachThreadInput(
                eigener_thread, ziel_thread, False
            )
    except Exception as e:
        log(f"Fehler beim Fokussieren der EniMultitool-Konsole: {e}")


def _eni_konsole_positionieren():
    """Hält die echte CMD exakt über dem ENI-Multitool-Bereich.

    Die CMD wird NICHT per SetParent() eingebettet, damit stdin und
    Tastatureingaben der echten Windows-Konsole erhalten bleiben.
    Stattdessen ist sie ein rahmenloses, eigenes Fenster mit ENI SERVICE
    als Owner. Bei jeder Bewegung/Größenänderung von ENI SERVICE wird sie
    neu auf die Position des Host-Frames gesetzt.
    """
    if ENI_KONSOLE_HWND is None:
        return

    try:
        hwnd = ENI_KONSOLE_HWND
        if not _user32.IsWindow(hwnd):
            return

        fenster.update_idletasks()
        eni_konsole_host.update_idletasks()

        x = int(eni_konsole_host.winfo_rootx())
        y = int(eni_konsole_host.winfo_rooty())
        breite = max(int(eni_konsole_host.winfo_width()), 10)
        hoehe = max(int(eni_konsole_host.winfo_height()), 10)

        # Rahmen, Titelzeile und Systemmenü entfernen. Dadurch kann der
        # Benutzer die CMD nicht mehr separat vom ENI SERVICE verschieben.
        stil = int(_GetWindowLong(hwnd, _GWL_STYLE))
        stil &= ~(
            _WS_CAPTION |
            _WS_THICKFRAME |
            _WS_SYSMENU |
            _WS_POPUP |
            _WS_CHILD
        )
        stil |= 0x10000000  # WS_VISIBLE
        _SetWindowLong(hwnd, _GWL_STYLE, stil)

        # ENI SERVICE wird als Owner gesetzt. Die CMD bleibt dadurch
        # an dieses Hauptfenster gebunden, ohne stdin zu verlieren.
        try:
            _SetWindowLong(
                hwnd,
                _GWLP_HWNDPARENT,
                _wintypes.LPVOID(fenster.winfo_id())
            )
        except Exception:
            pass

        # Keine eigene Taskleisten-Schaltfläche.
        try:
            ex = int(_GetWindowLong(hwnd, _GWL_EXSTYLE))
            ex = (ex | _WS_EX_TOOLWINDOW) & ~_WS_EX_APPWINDOW
            _SetWindowLong(hwnd, _GWL_EXSTYLE, ex)
        except Exception:
            pass

        # Immer exakt auf dem Host-Frame platzieren.
        # NOACTIVATE verhindert Fokusverlust beim Verschieben des ENI SERVICE.
        _user32.SetWindowPos(
            hwnd,
            0,
            x, y, breite, hoehe,
            0x0010 | 0x0004 | 0x0020  # NOACTIVATE | NOZORDER | FRAMECHANGED
        )
        _user32.ShowWindow(hwnd, 5)

    except Exception as e:
        log(f"Fehler beim Positionieren der EniMultitool-Konsole: {e}")


def _eni_konsole_verstecken():
    if ENI_KONSOLE_HWND is not None:
        try:
            _user32.ShowWindow(ENI_KONSOLE_HWND, 0)  # SW_HIDE
        except Exception:
            pass


def _eni_konsole_einbetten(hwnd):
    global ENI_KONSOLE_HWND

    ENI_KONSOLE_HWND = hwnd

    try:
        _eni_konsole_positionieren()

        def _groesse_anpassen(event=None):
            # Root-/Panel-Bewegungen werden über fenster <Configure>
            # ebenfalls abgefangen; dieser Handler deckt zusätzlich
            # Änderungen am eigentlichen Host-Frame ab.
            fenster.after_idle(_eni_konsole_positionieren)

        eni_konsole_host.bind("<Configure>", _groesse_anpassen)
        fenster.bind("<Configure>", _groesse_anpassen, add="+")

        eni_konsole_host.bind(
            "<Button-1>",
            lambda event: fenster.after(20, eni_konsole_fokussieren)
        )
        eni_konsole_host.bind(
            "<Enter>",
            lambda event: fenster.after(20, eni_konsole_fokussieren)
        )

        # Nach dem Start braucht conhost manchmal einen Moment, bis sein
        # Eingabefenster vollständig bereit ist.
        for delay in (100, 300, 600, 1000):
            fenster.after(delay, _eni_konsole_positionieren)
        fenster.after(500, eni_konsole_fokussieren)
        fenster.after(900, eni_konsole_fokussieren)

        log("Interaktive EniMultitool-Konsole an ENI SERVICE gebunden.")

    except Exception as e:
        log(f"Fehler beim Anzeigen der EniMultitool-Konsole: {e}")


def eni_multitool_prozess_starten():
    global ENI_MULTITOOL_PROZESS

    if (
        ENI_MULTITOOL_PROZESS is not None
        and ENI_MULTITOOL_PROZESS.poll() is None
    ):
        if ENI_KONSOLE_HWND is not None:
            _eni_konsole_positionieren()
            eni_konsole_fokussieren()
        return

    vorher = _eni_sichtbare_konsolenfenster()

    try:
        # Das EniMultitool wird unverändert als echte Windows-Konsole
        # gestartet. Die BAT-Datei wird nicht verändert oder gelesen.
        ENI_MULTITOOL_PROZESS = subprocess.Popen(
            [
                "conhost.exe",
                "cmd.exe",
                "/c",
                str(BAT_DATEI)
            ],
            cwd=str(ORDNER),
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        log("EniMultitool gestartet.")

    except Exception as e:
        log(f"Fehler beim Starten des EniMultitools: {e}")
        return

    def fenster_suchen(versuch=0):
        # Falls das Fenster bereits beendet wurde, nicht weiter danach suchen.
        if ENI_MULTITOOL_PROZESS is None:
            return

        neu = _eni_sichtbare_konsolenfenster() - vorher

        if neu:
            hwnd = neu.pop()
            _eni_konsole_einbetten(hwnd)

        elif versuch < 50:
            fenster.after(100, lambda: fenster_suchen(versuch + 1))
        else:
            log(
                "Konsolenfenster des EniMultitools konnte "
                "nicht gefunden werden."
            )

    fenster_suchen()


def download_starten(fehlende):

    download_label.config(text=t("download_files"))
    download_progress["maximum"] = len(fehlende)
    download_progress["value"] = 0

    ansicht_zeigen("download")

    def download_thread():

        erfolgreich = True

        for index, daten in enumerate(fehlende):

            name, url, ziel = daten

            log(f"Lade {name} herunter...")

            if not datei_download(
                url,
                ziel
            ):
                erfolgreich = False

            fenster.after(
                0,
                lambda wert=index + 1:
                    download_progress.config(
                        value=wert
                    )
            )

        fenster.after(
            0,
            lambda: download_fertig(
                erfolgreich
            )
        )

    threading.Thread(
        target=download_thread,
        daemon=True
    ).start()


def download_fertig(erfolgreich):

    ansicht_schliessen("download")

    if erfolgreich:

        log(t("download_done"))
        ansicht_zeigen("eni_console")

    else:

        log(t("download_error"))

        messagebox.showerror(
            t("download"),
            t("download_error")
        )


# ============================================================
# SPRACHE
# ============================================================

def sprache_aendern(neue_sprache):

    global SPRACHE

    SPRACHE = neue_sprache

    log(
        "Sprache geändert: "
        + ("Deutsch" if SPRACHE == "de" else "English")
    )

    hauptbuttons_aktualisieren()


# ============================================================
# EINSTELLUNGEN
# ============================================================

def transparenz_setzen(wert):

    try:
        wert = float(wert) / 100

        fenster.attributes(
            "-alpha",
            wert
        )

    except Exception:
        pass


# ============================================================
# ÜBERSETZER (eingebaut, öffnet keine Webseite)
# ============================================================

UEBERSETZUNG_SPRACHEN = [
    ("de", "Deutsch"),
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("nl", "Nederlands"),
    ("pl", "Polski"),
    ("pt", "Português"),
    ("ru", "Русский"),
    ("tr", "Türkçe"),
]


def uebersetzer_konfig_laden():
    try:
        if UEBERSETZER_KONFIG_DATEI.exists():
            with open(UEBERSETZER_KONFIG_DATEI, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass

    return {}


def uebersetzer_konfig_speichern(daten):
    try:
        with open(UEBERSETZER_KONFIG_DATEI, "w", encoding="utf-8") as f:
            json.dump(daten, f)
    except Exception:
        pass


def uebersetzer_ansicht_bauen(parent):

    fenster_uebersetzer = parent

    quelle_werte = [t("auto_detect")] + [
        name for _, name in UEBERSETZUNG_SPRACHEN
    ]
    ziel_werte = [name for _, name in UEBERSETZUNG_SPRACHEN]

    kopf_frame = tk.Frame(fenster_uebersetzer, bg="#161618")
    kopf_frame.pack(pady=(20, 5), padx=20, fill="x")

    tk.Label(
        kopf_frame,
        text=t("translate_source"),
        font=("Segoe UI", 10, "bold"),
        bg="#161618",
        fg="#cccccc"
    ).grid(row=0, column=0, sticky="w")

    tk.Label(
        kopf_frame,
        text=t("translate_target"),
        font=("Segoe UI", 10, "bold"),
        bg="#161618",
        fg="#cccccc"
    ).grid(row=0, column=2, sticky="w")

    quelle_box = ttk.Combobox(
        kopf_frame, values=quelle_werte, state="readonly", width=20
    )
    quelle_box.set(t("auto_detect"))
    quelle_box.grid(row=1, column=0, padx=(0, 10))

    ziel_box = ttk.Combobox(
        kopf_frame, values=ziel_werte, state="readonly", width=20
    )
    ziel_box.set("English" if SPRACHE == "de" else "Deutsch")

    def tauschen():
        aktuelle_quelle = quelle_box.get()
        aktuelles_ziel = ziel_box.get()

        if aktuelle_quelle in ziel_werte:
            ziel_box.set(aktuelle_quelle)
            quelle_box.set(aktuelles_ziel)

    tk.Button(
        kopf_frame,
        text="⇄",
        command=tauschen,
        font=("Segoe UI", 12, "bold"),
        bg="#202124",
        fg="white",
        activebackground="#2c2d31",
        activeforeground="white",
        bd=0,
        relief="flat",
        cursor="hand2",
        width=3
    ).grid(row=1, column=1, padx=5)

    ziel_box.grid(row=1, column=2, padx=(10, 0))

    tk.Label(
        fenster_uebersetzer,
        text=t("translate_deepl_key"),
        font=("Segoe UI", 9),
        bg="#161618",
        fg="#8a8a8f",
        anchor="w",
        wraplength=600,
        justify="left"
    ).pack(fill="x", padx=20, pady=(14, 2))

    deepl_key_var = tk.StringVar(
        value=uebersetzer_konfig_laden().get("deepl_api_key", "")
    )

    deepl_key_entry = tk.Entry(
        fenster_uebersetzer,
        textvariable=deepl_key_var,
        show="•",
        bg=FARBE_EINGABE,
        fg="white",
        insertbackground="white",
        font=("Segoe UI", 10),
        **EINGABE_RAHMEN
    )
    deepl_key_entry.pack(fill="x", padx=20, ipady=6)

    tk.Label(
        fenster_uebersetzer,
        text=t("translate_input"),
        font=("Segoe UI", 10, "bold"),
        bg="#161618",
        fg="#cccccc",
        anchor="w"
    ).pack(fill="x", padx=20, pady=(15, 2))

    eingabe_text = tk.Text(
        fenster_uebersetzer,
        height=5,
        wrap="word",
        bg=FARBE_EINGABE,
        fg="white",
        insertbackground="white",
        font=("Segoe UI", 11),
        padx=10,
        pady=8,
        **EINGABE_RAHMEN
    )
    eingabe_text.pack(fill="both", padx=20, pady=(0, 12))

    ausgabe_text = tk.Text(
        fenster_uebersetzer,
        height=5,
        wrap="word",
        bg=FARBE_EINGABE,
        fg=FARBE_AKZENT,
        insertbackground="white",
        font=("Segoe UI", 11),
        padx=10,
        pady=8,
        state="disabled",
        **EINGABE_RAHMEN
    )

    def ausgabe_setzen(text):
        ausgabe_text.config(state="normal")
        ausgabe_text.delete("1.0", "end")
        ausgabe_text.insert("1.0", text)
        ausgabe_text.config(state="disabled")

    def uebersetzen_klick():
        text = eingabe_text.get("1.0", "end").strip()

        if not text:
            messagebox.showwarning(
                t("translate"),
                t("translate_empty")
            )
            return

        quelle_name = quelle_box.get()
        ziel_name = ziel_box.get()

        quelle_code = "auto"

        for code, name in UEBERSETZUNG_SPRACHEN:
            if name == quelle_name:
                quelle_code = code
                break

        ziel_code = "en"

        for code, name in UEBERSETZUNG_SPRACHEN:
            if name == ziel_name:
                ziel_code = code
                break

        deepl_key = deepl_key_var.get().strip()

        uebersetzen_button.config(state="disabled", text="…")

        def fertig(ergebnis):
            ausgabe_setzen(ergebnis or "")
            uebersetzen_button.config(
                state="normal",
                text=t("translate_button")
            )

        def fehler(fehlertext):
            nachricht = t("translate_error")

            if fehlertext:
                nachricht += f"\n\n({fehlertext})"

            messagebox.showerror(
                t("translate"),
                nachricht
            )
            uebersetzen_button.config(
                state="normal",
                text=t("translate_button")
            )

        def arbeit():
            ergebnis = None
            letzter_fehler = None

            if deepl_key and DeeplTranslator is not None:
                try:
                    ergebnis = DeeplTranslator(
                        source=quelle_code,
                        target=ziel_code,
                        api_key=deepl_key
                    ).translate(text)

                    uebersetzer_konfig_speichern(
                        {"deepl_api_key": deepl_key}
                    )

                except Exception as e:
                    letzter_fehler = e
                    log(f"DeepL-Übersetzungs-Fehler: {e}")

            if ergebnis is None:
                try:
                    ergebnis = GoogleTranslator(
                        source=quelle_code,
                        target=ziel_code
                    ).translate(text)

                except Exception as e:
                    letzter_fehler = e
                    log(f"Google-Übersetzungs-Fehler: {e}")

            if ergebnis is None:
                fenster.after(
                    0,
                    lambda: fehler(letzter_fehler)
                )
                return

            log(f"Übersetzt: {quelle_code} -> {ziel_code}")

            fenster.after(0, lambda: fertig(ergebnis))

        threading.Thread(target=arbeit, daemon=True).start()

    uebersetzen_button = tk.Button(
        fenster_uebersetzer,
        text=t("translate_button"),
        command=uebersetzen_klick,
        pady=8,
        **PRIMARY_BUTTON_STYLE
    )
    uebersetzen_button.pack(fill="x", padx=20, pady=(0, 15))

    tk.Label(
        fenster_uebersetzer,
        text=t("translate_output"),
        font=("Segoe UI", 10, "bold"),
        bg="#161618",
        fg="#cccccc",
        anchor="w"
    ).pack(fill="x", padx=20, pady=(0, 2))

    ausgabe_text.pack(fill="both", padx=20, pady=(0, 20))


# ============================================================
# AUTOCLICKER (nur aktiv, solange ENI SERVICE läuft)
# ============================================================

MAUS_LINKS_DOWN = 0x0002
MAUS_LINKS_UP = 0x0004
MAUS_RECHTS_DOWN = 0x0008
MAUS_RECHTS_UP = 0x0010

AUTOCLICKER_AKTIV = False
AUTOCLICKER_STOP_EVENT = threading.Event()
AUTOCLICKER_KLICKS = 0


def maus_klick(rechts=False):
    if rechts:
        ctypes.windll.user32.mouse_event(MAUS_RECHTS_DOWN, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(MAUS_RECHTS_UP, 0, 0, 0, 0)
    else:
        ctypes.windll.user32.mouse_event(MAUS_LINKS_DOWN, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(MAUS_LINKS_UP, 0, 0, 0, 0)


def autoclicker_schleife(intervall, rechts):
    global AUTOCLICKER_KLICKS

    while not AUTOCLICKER_STOP_EVENT.is_set():
        maus_klick(rechts)
        AUTOCLICKER_KLICKS += 1
        time.sleep(intervall)


def autoclicker_konfig_laden():
    try:
        if AUTOKLICKER_KONFIG_DATEI.exists():
            with open(AUTOKLICKER_KONFIG_DATEI, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass

    return {}


def autoclicker_konfig_speichern(daten):
    try:
        with open(AUTOKLICKER_KONFIG_DATEI, "w", encoding="utf-8") as f:
            json.dump(daten, f)
    except Exception:
        pass


def autoclicker_ansicht_bauen(parent):

    fenster_auto = parent

    tk.Label(
        fenster_auto,
        text=t("autoclicker_interval"),
        font=("Segoe UI", 10, "bold"),
        bg="#161618",
        fg="#cccccc",
        anchor="w"
    ).pack(fill="x", padx=20, pady=(20, 2))

    intervall_var = tk.StringVar(value="100")

    tk.Entry(
        fenster_auto,
        textvariable=intervall_var,
        bg=FARBE_EINGABE,
        fg="white",
        insertbackground="white",
        font=("Segoe UI", 11),
        **EINGABE_RAHMEN
    ).pack(fill="x", padx=20, ipady=6)

    tk.Label(
        fenster_auto,
        text=t("autoclicker_button_side"),
        font=("Segoe UI", 10, "bold"),
        bg="#161618",
        fg="#cccccc",
        anchor="w"
    ).pack(fill="x", padx=20, pady=(16, 2))

    seite_werte = (
        ["Links", "Rechts"] if SPRACHE == "de" else ["Left", "Right"]
    )

    seite_box = ttk.Combobox(
        fenster_auto, values=seite_werte, state="readonly"
    )
    seite_box.set(seite_werte[0])
    seite_box.pack(fill="x", padx=20)

    status_label = tk.Label(
        fenster_auto,
        text=t("autoclicker_status_stopped"),
        font=("Segoe UI", 12, "bold"),
        bg="#161618",
        fg="#8a8a8f"
    )
    status_label.pack(pady=(24, 6))

    def status_aktualisieren():
        if AUTOCLICKER_AKTIV:
            status_label.config(
                text=t("autoclicker_status_running").format(
                    klicks=AUTOCLICKER_KLICKS
                ),
                fg=FARBE_AKZENT
            )
            start_stop_button.config(
                text=t("autoclicker_stop"),
                bg=GEFAHR_BUTTON_STYLE["bg"],
                fg=GEFAHR_BUTTON_STYLE["fg"],
                activebackground=GEFAHR_BUTTON_STYLE["activebackground"],
                activeforeground=GEFAHR_BUTTON_STYLE["activeforeground"]
            )

            fenster_auto.after(200, status_aktualisieren)
        else:
            status_label.config(
                text=t("autoclicker_status_stopped"),
                fg=FARBE_TEXT_GEDAEMPFT
            )
            start_stop_button.config(
                text=t("autoclicker_start"),
                bg=PRIMARY_BUTTON_STYLE["bg"],
                fg=PRIMARY_BUTTON_STYLE["fg"],
                activebackground=PRIMARY_BUTTON_STYLE["activebackground"],
                activeforeground=PRIMARY_BUTTON_STYLE["activeforeground"]
            )

    def starten():
        global AUTOCLICKER_AKTIV, AUTOCLICKER_KLICKS

        if AUTOCLICKER_AKTIV:
            return

        try:
            intervall_ms = int(intervall_var.get())

            if intervall_ms < 10:
                raise ValueError()

        except ValueError:
            messagebox.showerror(
                t("autoclicker"),
                t("autoclicker_invalid_interval")
            )
            return

        rechts = seite_box.get() == seite_werte[1]

        AUTOCLICKER_KLICKS = 0
        AUTOCLICKER_AKTIV = True
        AUTOCLICKER_STOP_EVENT.clear()

        threading.Thread(
            target=autoclicker_schleife,
            args=(intervall_ms / 1000, rechts),
            daemon=True
        ).start()

        log(
            f"Autoclicker gestartet ({intervall_ms} ms, "
            f"{'rechts' if rechts else 'links'})."
        )

        status_aktualisieren()

    def stoppen():
        global AUTOCLICKER_AKTIV

        if not AUTOCLICKER_AKTIV:
            return

        AUTOCLICKER_AKTIV = False
        AUTOCLICKER_STOP_EVENT.set()

        log(f"Autoclicker gestoppt ({AUTOCLICKER_KLICKS} Klicks).")

        status_aktualisieren()

    def umschalten():
        if AUTOCLICKER_AKTIV:
            stoppen()
        else:
            starten()

    start_stop_button = tk.Button(
        fenster_auto,
        text=t("autoclicker_start"),
        command=umschalten,
        pady=8,
        **PRIMARY_BUTTON_STYLE
    )
    start_stop_button.pack(fill="x", padx=20, pady=(10, 6))

    hotkey_registrierung = [None]
    hotkey_aktiv = keyboard is not None

    autoclicker_hotkey = autoclicker_konfig_laden().get("hotkey", "f6")

    def hotkey_callback():
        fenster.after(0, umschalten)

    def hotkey_registrieren(taste):
        if keyboard is None:
            return False

        try:
            hotkey_registrierung[0] = keyboard.add_hotkey(
                taste, hotkey_callback
            )
            return True

        except Exception as e:
            log(f"Autoclicker-Hotkey-Fehler: {e}")
            return False

    if hotkey_aktiv:
        hotkey_aktiv = hotkey_registrieren(autoclicker_hotkey)

    hotkey_zeile = tk.Frame(fenster_auto, bg="#161618")
    hotkey_zeile.pack(fill="x", padx=20, pady=(6, 0))

    hotkey_label = tk.Label(
        hotkey_zeile,
        text=f"{t('autoclicker_hotkey')}: {autoclicker_hotkey.upper()}",
        font=("Segoe UI", 10, "bold"),
        bg="#161618",
        fg="#cccccc"
    )
    hotkey_label.pack(side="left")

    def taste_erfasst(taste):
        nonlocal autoclicker_hotkey

        hotkey_aendern_button.config(state="normal")

        if not taste:
            hotkey_label.config(
                text=f"{t('autoclicker_hotkey')}: {autoclicker_hotkey.upper()}"
            )
            return

        if hotkey_registrierung[0] is not None:
            try:
                keyboard.remove_hotkey(hotkey_registrierung[0])
            except Exception:
                pass

        autoclicker_hotkey = taste
        hotkey_registrieren(autoclicker_hotkey)

        hotkey_label.config(
            text=f"{t('autoclicker_hotkey')}: {autoclicker_hotkey.upper()}"
        )

        autoclicker_konfig_speichern({"hotkey": autoclicker_hotkey})

        log(f"Autoclicker-Hotkey geändert: {autoclicker_hotkey}")

    def hotkey_aufnehmen():
        if keyboard is None:
            return

        hotkey_aendern_button.config(state="disabled")
        hotkey_label.config(text=t("autoclicker_press_key"))

        def warten():
            try:
                taste = keyboard.read_key()
            except Exception as e:
                log(f"Hotkey-Erfassung fehlgeschlagen: {e}")
                taste = None

            fenster.after(0, lambda: taste_erfasst(taste))

        threading.Thread(target=warten, daemon=True).start()

    hotkey_aendern_button = tk.Button(
        hotkey_zeile,
        text=t("autoclicker_change_hotkey"),
        command=hotkey_aufnehmen,
        font=("Segoe UI", 9, "bold"),
        bg="#202124",
        fg="white",
        activebackground="#2c2d31",
        activeforeground="white",
        bd=0,
        relief="flat",
        cursor="hand2",
        padx=12
    )

    if keyboard is None:
        hotkey_aendern_button.config(state="disabled")

    hotkey_aendern_button.pack(side="right")

    tk.Label(
        fenster_auto,
        text=(
            t("autoclicker_hotkey_hinweis") if hotkey_aktiv
            else t("autoclicker_missing_lib")
        ),
        font=("Segoe UI", 9),
        bg="#161618",
        fg="#8a8a8f",
        wraplength=380,
        justify="left"
    ).pack(fill="x", padx=20, pady=(6, 10))

    status_aktualisieren()


# ============================================================
# UHR (TIMER & STOPPUHR)
# ============================================================
#
# Beide laufen über eine feste End-/Startzeit (time.monotonic()),
# nicht über simples Hochzählen bei jedem Tick - so bleiben sie auch
# bei kurzen Rucklern im GUI-Thread exakt und laufen unabhängig davon
# weiter, ob das Panel gerade sichtbar ist (fenster.after läuft immer).

UHR_ALARM_FENSTER = {"aktuell": None}


def uhr_alarm_anzeigen():
    vorhandenes = UHR_ALARM_FENSTER["aktuell"]

    if vorhandenes is not None:
        try:
            vorhandenes.destroy()
        except Exception:
            pass

    popup = tk.Toplevel(fenster)
    popup.title(t("clock_alarm_title"))
    popup.configure(bg="#7a1f1f")
    popup.attributes("-topmost", True)
    popup.resizable(False, False)

    breite, hoehe = 420, 240
    fenster.update_idletasks()
    x = fenster.winfo_x() + (fenster.winfo_width() - breite) // 2
    y = fenster.winfo_y() + (fenster.winfo_height() - hoehe) // 2
    popup.geometry(f"{breite}x{hoehe}+{max(0, x)}+{max(0, y)}")

    UHR_ALARM_FENSTER["aktuell"] = popup

    def ausschalten():
        UHR_ALARM_FENSTER["aktuell"] = None

        try:
            popup.destroy()
        except Exception:
            pass

        log("Timer-Alarm ausgeschaltet.")

    # Auch das normale Schließkreuz löst dasselbe kontrollierte
    # Ausschalten aus - es gibt so immer nur einen sauberen Ausgang.
    popup.protocol("WM_DELETE_WINDOW", ausschalten)

    tk.Label(
        popup, text="⏰", font=("Segoe UI", 42), bg="#7a1f1f", fg="white"
    ).pack(pady=(22, 4))

    tk.Label(
        popup, text=t("clock_alarm_title"),
        font=("Segoe UI", 15, "bold"), bg="#7a1f1f", fg="white"
    ).pack()

    tk.Label(
        popup, text=t("clock_alarm_message"),
        font=("Segoe UI", 10), bg="#7a1f1f", fg="#f0d0d0"
    ).pack(pady=(4, 18))

    tk.Button(
        popup, text=t("clock_alarm_off"), command=ausschalten,
        font=("Segoe UI", 11, "bold"), bg="white", fg="#7a1f1f",
        activebackground="#f0f0f0", activeforeground="#7a1f1f",
        bd=0, relief="flat", cursor="hand2", padx=20, pady=8
    ).pack()

    popup.lift()
    popup.focus_force()

    log("Timer-Alarm ausgelöst.")


def _uhr_sekundaerer_knopf(parent, text):
    return tk.Button(
        parent, text=text, width=10, pady=6,
        font=("Segoe UI", 11, "bold"),
        bg="#2c2d31", fg="white",
        activebackground="#3a3b40", activeforeground="white",
        bd=0, relief="flat", cursor="hand2", highlightthickness=0,
        disabledforeground="#5a5a5e"
    )


def uhr_ansicht_bauen(parent):
    spalten = tk.Frame(parent, bg="#161618")
    spalten.pack(fill="both", expand=True, padx=10, pady=10)

    timer_spalte = tk.Frame(spalten, bg="#161618")
    timer_spalte.pack(side="left", fill="both", expand=True, padx=(10, 5))

    tk.Frame(spalten, bg=FARBE_RAND, width=1).pack(
        side="left", fill="y", pady=10
    )

    stoppuhr_spalte = tk.Frame(spalten, bg="#161618")
    stoppuhr_spalte.pack(side="left", fill="both", expand=True, padx=(5, 10))

    # ---------------- TIMER ----------------

    tk.Label(
        timer_spalte, text=t("clock_timer_heading"),
        font=("Segoe UI", 12, "bold"), bg="#161618", fg=FARBE_AKZENT
    ).pack(pady=(6, 14))

    eingabe_zeile = tk.Frame(timer_spalte, bg="#161618")
    eingabe_zeile.pack(pady=(0, 14))

    timer_h_var = tk.StringVar(value="0")
    timer_m_var = tk.StringVar(value="5")
    timer_s_var = tk.StringVar(value="0")

    def _eingabe_feld(eltern, variable, beschriftung):
        spalte = tk.Frame(eltern, bg="#161618")
        spalte.pack(side="left", padx=6)

        tk.Label(
            spalte, text=beschriftung, font=("Segoe UI", 8, "bold"),
            bg="#161618", fg="#9a9aa0"
        ).pack()

        eingabe = tk.Entry(
            spalte, textvariable=variable, width=4,
            font=("Consolas", 16, "bold"), justify="center",
            bg=FARBE_EINGABE, fg="white", insertbackground="white",
            **EINGABE_RAHMEN
        )
        eingabe.pack(ipady=4)
        return eingabe

    timer_h_eingabe = _eingabe_feld(eingabe_zeile, timer_h_var, t("clock_hours"))
    timer_m_eingabe = _eingabe_feld(eingabe_zeile, timer_m_var, t("clock_minutes"))
    timer_s_eingabe = _eingabe_feld(eingabe_zeile, timer_s_var, t("clock_seconds"))

    timer_anzeige = tk.Label(
        timer_spalte, text="00:00:00",
        font=("Consolas", 40, "bold"), bg="#161618", fg="white"
    )
    timer_anzeige.pack(pady=(4, 4))

    timer_status = tk.Label(
        timer_spalte, text=t("clock_status_stopped"),
        font=("Segoe UI", 10, "bold"), bg="#161618", fg="#8a8a8f"
    )
    timer_status.pack(pady=(0, 16))

    timer_knopf_zeile = tk.Frame(timer_spalte, bg="#161618")
    timer_knopf_zeile.pack()

    timer_start_knopf = tk.Button(
        timer_knopf_zeile, text=t("clock_start"), width=10,
        pady=6, **PRIMARY_BUTTON_STYLE
    )
    timer_start_knopf.pack(side="left", padx=4)

    timer_pause_knopf = _uhr_sekundaerer_knopf(timer_knopf_zeile, t("clock_pause"))
    timer_pause_knopf.pack(side="left", padx=4)

    timer_reset_knopf = _uhr_sekundaerer_knopf(timer_knopf_zeile, t("clock_reset"))
    timer_reset_knopf.pack(side="left", padx=4)

    timer_zustand = {
        "aktiv": False, "pausiert": False,
        "endzeit": 0.0, "rest": 0.0, "tick_id": None,
    }

    def timer_sekunden_formatieren(gesamt):
        gesamt = max(0, int(round(gesamt)))
        std, rest = divmod(gesamt, 3600)
        minu, sek = divmod(rest, 60)
        return f"{std:02d}:{minu:02d}:{sek:02d}"

    def timer_buttons_aktualisieren():
        if timer_zustand["aktiv"]:
            timer_start_knopf.config(state="disabled", text=t("clock_start"))
            timer_pause_knopf.config(state="normal")
            timer_reset_knopf.config(state="normal")
            timer_h_eingabe.config(state="disabled")
            timer_m_eingabe.config(state="disabled")
            timer_s_eingabe.config(state="disabled")
            timer_status.config(text=t("clock_status_running"), fg=FARBE_AKZENT)
        elif timer_zustand["pausiert"]:
            timer_start_knopf.config(state="normal", text=t("clock_resume"))
            timer_pause_knopf.config(state="disabled")
            timer_reset_knopf.config(state="normal")
            timer_status.config(text=t("clock_status_paused"), fg="#e0a030")
        else:
            timer_start_knopf.config(state="normal", text=t("clock_start"))
            timer_pause_knopf.config(state="disabled")
            timer_reset_knopf.config(state="normal")
            timer_h_eingabe.config(state="normal")
            timer_m_eingabe.config(state="normal")
            timer_s_eingabe.config(state="normal")
            timer_status.config(text=t("clock_status_stopped"), fg="#8a8a8f")

    def timer_tick():
        if not timer_zustand["aktiv"]:
            return

        rest = timer_zustand["endzeit"] - time.monotonic()

        if rest <= 0:
            timer_anzeige.config(text="00:00:00")
            timer_zustand["aktiv"] = False
            timer_zustand["pausiert"] = False
            timer_zustand["rest"] = 0.0
            timer_zustand["tick_id"] = None
            timer_buttons_aktualisieren()
            log("Timer abgelaufen.")
            uhr_alarm_anzeigen()
            return

        timer_anzeige.config(text=timer_sekunden_formatieren(rest))
        timer_zustand["tick_id"] = timer_spalte.after(200, timer_tick)

    def timer_starten():
        if timer_zustand["aktiv"]:
            return

        if timer_zustand["pausiert"] and timer_zustand["rest"] > 0:
            gesamt = timer_zustand["rest"]
        else:
            try:
                std = int(timer_h_var.get() or 0)
                minu = int(timer_m_var.get() or 0)
                sek = int(timer_s_var.get() or 0)

                if std < 0 or minu < 0 or sek < 0:
                    raise ValueError()

                gesamt = std * 3600 + minu * 60 + sek

                if gesamt <= 0:
                    raise ValueError()

            except ValueError:
                messagebox.showerror(t("clock_title"), t("clock_timer_invalid"))
                return

        timer_zustand["endzeit"] = time.monotonic() + gesamt
        timer_zustand["aktiv"] = True
        timer_zustand["pausiert"] = False

        timer_buttons_aktualisieren()
        log(f"Timer gestartet ({timer_sekunden_formatieren(gesamt)}).")
        timer_tick()

    def timer_pausieren():
        if not timer_zustand["aktiv"]:
            return

        if timer_zustand["tick_id"] is not None:
            try:
                timer_spalte.after_cancel(timer_zustand["tick_id"])
            except Exception:
                pass
            timer_zustand["tick_id"] = None

        timer_zustand["rest"] = max(
            0.0, timer_zustand["endzeit"] - time.monotonic()
        )
        timer_zustand["aktiv"] = False
        timer_zustand["pausiert"] = True

        timer_buttons_aktualisieren()
        log("Timer pausiert.")

    def timer_zuruecksetzen():
        if timer_zustand["tick_id"] is not None:
            try:
                timer_spalte.after_cancel(timer_zustand["tick_id"])
            except Exception:
                pass
            timer_zustand["tick_id"] = None

        timer_zustand["aktiv"] = False
        timer_zustand["pausiert"] = False
        timer_zustand["rest"] = 0.0

        timer_anzeige.config(text="00:00:00")
        timer_buttons_aktualisieren()
        log("Timer zurückgesetzt.")

    timer_start_knopf.config(command=timer_starten)
    timer_pause_knopf.config(command=timer_pausieren)
    timer_reset_knopf.config(command=timer_zuruecksetzen)

    timer_buttons_aktualisieren()

    # ---------------- STOPPUHR ----------------

    tk.Label(
        stoppuhr_spalte, text=t("clock_stopwatch_heading"),
        font=("Segoe UI", 12, "bold"), bg="#161618", fg=FARBE_AKZENT
    ).pack(pady=(6, 14))

    stoppuhr_anzeige = tk.Label(
        stoppuhr_spalte, text="00:00:00:00",
        font=("Consolas", 36, "bold"), bg="#161618", fg="white"
    )
    stoppuhr_anzeige.pack(pady=(46, 4))

    stoppuhr_status = tk.Label(
        stoppuhr_spalte, text=t("clock_status_stopped"),
        font=("Segoe UI", 10, "bold"), bg="#161618", fg="#8a8a8f"
    )
    stoppuhr_status.pack(pady=(0, 16))

    stoppuhr_knopf_zeile = tk.Frame(stoppuhr_spalte, bg="#161618")
    stoppuhr_knopf_zeile.pack()

    stoppuhr_start_knopf = tk.Button(
        stoppuhr_knopf_zeile, text=t("clock_start"), width=10,
        pady=6, **PRIMARY_BUTTON_STYLE
    )
    stoppuhr_start_knopf.pack(side="left", padx=4)

    stoppuhr_pause_knopf = _uhr_sekundaerer_knopf(
        stoppuhr_knopf_zeile, t("clock_pause")
    )
    stoppuhr_pause_knopf.pack(side="left", padx=4)

    stoppuhr_reset_knopf = _uhr_sekundaerer_knopf(
        stoppuhr_knopf_zeile, t("clock_reset")
    )
    stoppuhr_reset_knopf.pack(side="left", padx=4)

    stoppuhr_zustand = {
        "aktiv": False, "start_zeit": 0.0,
        "verstrichen": 0.0, "tick_id": None,
    }

    def stoppuhr_formatieren(gesamt):
        hundertstel_gesamt = max(0, int(gesamt * 100))
        std, rest = divmod(hundertstel_gesamt, 360000)
        minu, rest = divmod(rest, 6000)
        sek, hundertstel = divmod(rest, 100)
        return f"{std:02d}:{minu:02d}:{sek:02d}:{hundertstel:02d}"

    def stoppuhr_buttons_aktualisieren():
        angehalten_mit_rest = (
            not stoppuhr_zustand["aktiv"] and stoppuhr_zustand["verstrichen"] > 0
        )

        if stoppuhr_zustand["aktiv"]:
            stoppuhr_start_knopf.config(state="disabled", text=t("clock_start"))
            stoppuhr_pause_knopf.config(state="normal")
            stoppuhr_status.config(text=t("clock_status_running"), fg=FARBE_AKZENT)
        elif angehalten_mit_rest:
            stoppuhr_start_knopf.config(state="normal", text=t("clock_resume"))
            stoppuhr_pause_knopf.config(state="disabled")
            stoppuhr_status.config(text=t("clock_status_paused"), fg="#e0a030")
        else:
            stoppuhr_start_knopf.config(state="normal", text=t("clock_start"))
            stoppuhr_pause_knopf.config(state="disabled")
            stoppuhr_status.config(text=t("clock_status_stopped"), fg="#8a8a8f")

    def stoppuhr_tick():
        if not stoppuhr_zustand["aktiv"]:
            return

        verstrichen = (
            stoppuhr_zustand["verstrichen"]
            + (time.monotonic() - stoppuhr_zustand["start_zeit"])
        )
        stoppuhr_anzeige.config(text=stoppuhr_formatieren(verstrichen))
        stoppuhr_zustand["tick_id"] = stoppuhr_spalte.after(30, stoppuhr_tick)

    def stoppuhr_starten():
        if stoppuhr_zustand["aktiv"]:
            return

        stoppuhr_zustand["start_zeit"] = time.monotonic()
        stoppuhr_zustand["aktiv"] = True

        stoppuhr_buttons_aktualisieren()
        log("Stoppuhr gestartet.")
        stoppuhr_tick()

    def stoppuhr_pausieren():
        if not stoppuhr_zustand["aktiv"]:
            return

        if stoppuhr_zustand["tick_id"] is not None:
            try:
                stoppuhr_spalte.after_cancel(stoppuhr_zustand["tick_id"])
            except Exception:
                pass
            stoppuhr_zustand["tick_id"] = None

        stoppuhr_zustand["verstrichen"] += (
            time.monotonic() - stoppuhr_zustand["start_zeit"]
        )
        stoppuhr_zustand["aktiv"] = False

        stoppuhr_buttons_aktualisieren()
        log("Stoppuhr pausiert.")

    def stoppuhr_zuruecksetzen():
        if stoppuhr_zustand["tick_id"] is not None:
            try:
                stoppuhr_spalte.after_cancel(stoppuhr_zustand["tick_id"])
            except Exception:
                pass
            stoppuhr_zustand["tick_id"] = None

        stoppuhr_zustand["aktiv"] = False
        stoppuhr_zustand["verstrichen"] = 0.0

        stoppuhr_anzeige.config(text="00:00:00:00")
        stoppuhr_buttons_aktualisieren()
        log("Stoppuhr zurückgesetzt.")

    stoppuhr_start_knopf.config(command=stoppuhr_starten)
    stoppuhr_pause_knopf.config(command=stoppuhr_pausieren)
    stoppuhr_reset_knopf.config(command=stoppuhr_zuruecksetzen)

    stoppuhr_buttons_aktualisieren()


# ============================================================
# OVERLAY-MENÜ (vollflächiges, halbtransparentes Menü)
# ============================================================
#
# Es ist nur ein kleiner, klarer Schalter (ein Zeichen) sichtbar.
# Klickt man ihn, legt sich ein sauberes, dunkelgraues, leicht
# durchscheinendes Fenster über die komplette Oberfläche – der
# Hintergrund (Bild/Video) bleibt schwach sichtbar. Darin liegen
# alle Funktions-Buttons; reichen sie nicht mehr auf eine Seite,
# kann man mit dem Mausrad scrollen.

MENU_REIHENFOLGE = [
    "eni", "settings", "translate", "autoclicker",
    "commands", "password", "sysinfo", "notes", "clock",
    "deepl_web", "tempmail_web",
    "folder", "log", "internet", "temp",
]

MENU_BEFEHLE = {
    "eni": eni_multitool_starten,
    "settings": lambda: ansicht_zeigen("settings"),
    "translate": lambda: ansicht_zeigen("translate"),
    "autoclicker": lambda: ansicht_zeigen("autoclicker"),
    "commands": lambda: ansicht_zeigen("commands"),
    "password": lambda: ansicht_zeigen("password"),
    "sysinfo": lambda: ansicht_zeigen("sysinfo"),
    "notes": lambda: ansicht_zeigen("notes"),
    "clock": lambda: ansicht_zeigen("clock"),
    "deepl_web": lambda: ansicht_zeigen("deepl_web"),
    "tempmail_web": lambda: ansicht_zeigen("tempmail_web"),
    "folder": ordner_oeffnen,
    "log": lambda: ansicht_zeigen("log"),
    "internet": internet_testen,
    "temp": temp_aufräumen,
}

BUTTON_BG = "#1b1c1f"

TOGGLE_X = 24
TOGGLE_Y = 24
TOGGLE_GROESSE = 48

OVERLAY_SPALTEN = 2
OVERLAY_PADDING_SEITE = 80
OVERLAY_PADDING_OBEN = 110
OVERLAY_PADDING_UNTEN = 40
OVERLAY_KNOPF_HOEHE = 90
OVERLAY_ABSTAND = 26

OVERLAY_SPALTENBREITE = (
    BREITE
    - OVERLAY_PADDING_SEITE * 2
    - OVERLAY_ABSTAND * (OVERLAY_SPALTEN - 1)
) // OVERLAY_SPALTEN

OVERLAY_ZEILEN_HOEHE = OVERLAY_KNOPF_HOEHE + OVERLAY_ABSTAND

OVERLAY_ZEILEN_ANZAHL = -(-len(MENU_REIHENFOLGE) // OVERLAY_SPALTEN)

OVERLAY_INHALT_HOEHE = (
    OVERLAY_PADDING_OBEN
    + OVERLAY_ZEILEN_ANZAHL * OVERLAY_ZEILEN_HOEHE
    + OVERLAY_PADDING_UNTEN
)

OVERLAY_OFFEN = False
OVERLAY_ANIMIERT = False
SCROLL_OFFSET = 0


def graustufen_bild(x, y, breite, hoehe, alpha=0.72):
    breite = max(1, int(breite))
    hoehe = max(1, int(hoehe))

    basis = None

    if LETZTES_FRAME is not None:
        try:
            x2 = min(x + breite, BREITE)
            y2 = min(y + hoehe, HOEHE)

            basis = LETZTES_FRAME.crop((x, y, x2, y2))

            if basis.size != (breite, hoehe):
                # BILINEAR statt LANCZOS: für den kleinen,
                # laufend aktualisierten Glas-Effekt reicht das
                # locker und ist spürbar schneller.
                basis = basis.resize(
                    (breite, hoehe),
                    Image.Resampling.BILINEAR
                )

            basis = basis.convert("L").convert("RGB")

        except Exception:
            basis = None

    if basis is None:
        basis = Image.new("RGB", (breite, hoehe), (26, 26, 28))

    dunkel = Image.new("RGB", basis.size, (14, 14, 16))
    gemischt = Image.blend(basis, dunkel, alpha)

    return gemischt


def overlay_layout():
    for index, schluessel in enumerate(MENU_REIHENFOLGE):
        zeile = index // OVERLAY_SPALTEN
        spalte = index % OVERLAY_SPALTEN

        x = OVERLAY_PADDING_SEITE + spalte * (OVERLAY_SPALTENBREITE + OVERLAY_ABSTAND)
        y = OVERLAY_PADDING_OBEN + zeile * OVERLAY_ZEILEN_HOEHE + SCROLL_OFFSET

        menu_buttons[schluessel].place(
            x=x, y=y,
            width=OVERLAY_SPALTENBREITE, height=OVERLAY_KNOPF_HOEHE
        )


def mausrad_scrollen(event):
    global SCROLL_OFFSET

    if not OVERLAY_OFFEN or OVERLAY_ANIMIERT:
        return

    max_scroll = max(0, OVERLAY_INHALT_HOEHE - HOEHE)

    if max_scroll <= 0:
        return

    schritt = int(event.delta / 120 * 40)
    SCROLL_OFFSET = min(0, max(-max_scroll, SCROLL_OFFSET + schritt))

    overlay_layout()


overlay_frame = tk.Frame(
    fenster,
    bg="#161618",
    bd=0,
    highlightthickness=0
)

overlay_hintergrund_label = tk.Label(overlay_frame, bd=0)
overlay_hintergrund_label.place(x=0, y=0, relwidth=1, relheight=1)
overlay_hintergrund_label.bind("<MouseWheel>", mausrad_scrollen)
overlay_frame.bind("<MouseWheel>", mausrad_scrollen)

MENU_BUTTON_STYLE = {
    "font": ("Segoe UI", 12, "bold"),
    "bg": FARBE_OBERFLAECHE,
    "fg": FARBE_TEXT,
    "activebackground": FARBE_HOVER,
    "activeforeground": FARBE_AKZENT,
    "bd": 0,
    "relief": "flat",
    "cursor": "hand2",
    "highlightthickness": 1,
    "highlightbackground": FARBE_RAND,
    "highlightcolor": FARBE_AKZENT,
    "anchor": "w",
    "padx": 22,
}

PRIMARY_BUTTON_STYLE = {
    "font": ("Segoe UI", 11, "bold"),
    "bg": FARBE_AKZENT,
    "fg": "#0b0c0d",
    "activebackground": "#63f5bf",
    "activeforeground": "#0b0c0d",
    "bd": 0,
    "relief": "flat",
    "cursor": "hand2",
    "highlightthickness": 0,
}

GEFAHR_BUTTON_STYLE = {
    "font": ("Segoe UI", 11, "bold"),
    "bg": "#e74c3c",
    "fg": "white",
    "activebackground": "#ff6b5b",
    "activeforeground": "white",
    "bd": 0,
    "relief": "flat",
    "cursor": "hand2",
    "highlightthickness": 0,
}


# ============================================================
# ANSICHTEN (alles bleibt in diesem einen Fenster - Settings,
# Log, Übersetzer, Autoclicker und Download sind keine eigenen
# Fenster mehr, sondern frei verschiebbare Panels innerhalb des
# Overlays, wie kleine Fenster auf einem eigenen Mini-Desktop)
# ============================================================

ANSICHT_BREITE = 820
ANSICHT_HOEHE = 620
ANSICHT_MIN_BREITE = 420
ANSICHT_MIN_HOEHE = 320

TASKLEISTE_HOEHE = 42

# Das Menü-Raster ist immer sichtbar, sobald das Overlay offen ist.
# Beliebig viele Ansichten (Log, Befehle, ...) können gleichzeitig als
# frei verschiebbare Panels darüber liegen - wie mehrere geöffnete
# Fenster auf einem eigenen Mini-Desktop.
ansicht_frames = {}
ansicht_positionen = {}
ansicht_groessen = {}
ansicht_titel = {}
ANSICHT_ON_SHOW = {}

offene_ansichten = set()
minimierte_ansichten = []

# Merkt sich alle geöffneten (noch nicht per ✕ geschlossenen)
# Ansichten in der Reihenfolge, in der sie geöffnet wurden - egal
# ob gerade sichtbar oder minimiert. Genau diese Liste zeigt die
# Taskleiste an, wie bei einer echten Taskleiste.
laufende_reihenfolge = []

# Verhindert überlappende Minimieren/Wiederherstellen-Animationen,
# wenn schnell mehrfach auf denselben Taskleisten-Eintrag geklickt
# wird.
ansicht_animiert = set()


def ansicht_registrieren(name, frame, titel, on_show=None):
    ansicht_frames[name] = frame
    ansicht_titel[name] = titel

    ansicht_positionen[name] = [
        (BREITE - ANSICHT_BREITE) // 2,
        (HOEHE - ANSICHT_HOEHE) // 2,
    ]
    ansicht_groessen[name] = [ANSICHT_BREITE, ANSICHT_HOEHE]

    if on_show is not None:
        ANSICHT_ON_SHOW[name] = on_show


def _panel_slide_animieren(name, start_x, start_y, end_x, end_y,
                            dauer=140, schritte=6, fertig_fn=None):
    # Bewegt das Panel nur (x/y), Breite/Höhe bleiben die ganze Zeit
    # unverändert. Eine Größenänderung würde bei jedem Schritt ein
    # komplettes Neu-Layout aller Inhalte (Buttons, Textfelder, ...)
    # auslösen - das war der Grund für die spürbaren Ruckler. Reines
    # Verschieben ist dagegen günstig und bleibt flüssig.
    frame = ansicht_frames[name]

    def schritt(eased):
        x = start_x + (end_x - start_x) * eased
        y = start_y + (end_y - start_y) * eased
        frame.place(x=int(x), y=int(y))

    animiere(schritte, dauer, schritt, fertig_fn)


def ansicht_zeigen(name):
    # Die native EniMultitool-CMD soll nur sichtbar sein, wenn das
    # EniMultitool-Fenster aktiv ist. Sonst könnte sie über andere ENI-
    # Ansichten liegen. Der Prozess selbst bleibt dabei geöffnet.
    if name != "eni_console" and ENI_KONSOLE_HWND is not None:
        _eni_konsole_verstecken()

    # Ansichten sind eigenständige Desktop-Fenster - sie öffnen sich
    # direkt auf dem Desktop, unabhängig davon, ob das Overlay-Menü
    # gerade offen ist oder nicht.
    if name in ansicht_animiert:
        return

    war_minimiert = name in minimierte_ansichten
    war_schon_sichtbar = name in offene_ansichten

    if war_minimiert:
        minimierte_ansichten.remove(name)

    if name not in laufende_reihenfolge:
        laufende_reihenfolge.append(name)

    x, y = ansicht_positionen[name]
    breite, hoehe = ansicht_groessen[name]
    frame = ansicht_frames[name]

    if war_minimiert or not war_schon_sichtbar:
        # Von leicht unterhalb der Zielposition nach oben einfahren -
        # bei minimierten Fenstern etwas weiter, wie aus der
        # Taskleiste heraus.
        start_y = y + (140 if war_minimiert else 36)

        frame.place(x=x, y=start_y, width=breite, height=hoehe)
        frame.lift()

        ansicht_animiert.add(name)

        def _animation_fertig():
            ansicht_animiert.discard(name)

        _panel_slide_animieren(
            name, x, start_y, x, y, fertig_fn=_animation_fertig
        )
    else:
        frame.place(x=x, y=y, width=breite, height=hoehe)
        frame.lift()

    panel_titelleiste_glas_aktualisieren(name)

    if laufende_reihenfolge:
        taskleiste.lift()

    toggle_knopf.lift()

    offene_ansichten.add(name)

    # Läuft schon, seit es geöffnet wurde - bleibt so lange in der
    # Taskleiste sichtbar, bis es per ✕ geschlossen wird (nicht nur,
    # solange es minimiert ist).
    taskleiste_aktualisieren()

    on_show = ANSICHT_ON_SHOW.get(name)

    if on_show:
        on_show()


def ansicht_schliessen(name):
    if name == "eni_console":
        _eni_konsole_schliessen()

    if name in offene_ansichten:
        x, y = ansicht_positionen[name]

        def fertig():
            ansicht_frames[name].place_forget()

        _panel_slide_animieren(
            name, x, y, x, y + 36, dauer=110, schritte=5,
            fertig_fn=fertig
        )
    else:
        ansicht_frames[name].place_forget()

    offene_ansichten.discard(name)

    if name in minimierte_ansichten:
        minimierte_ansichten.remove(name)

    if name in laufende_reihenfolge:
        laufende_reihenfolge.remove(name)

    taskleiste_aktualisieren()


def ansicht_minimieren(name):
    if name == "eni_console":
        _eni_konsole_verstecken()

    if name not in offene_ansichten or name in ansicht_animiert:
        return

    x, y = ansicht_positionen[name]

    ansicht_animiert.add(name)

    def fertig():
        ansicht_animiert.discard(name)
        ansicht_frames[name].place_forget()
        offene_ansichten.discard(name)

        if name not in minimierte_ansichten:
            minimierte_ansichten.append(name)

        taskleiste_aktualisieren()

    _panel_slide_animieren(
        name, x, y, x, y + 140, fertig_fn=fertig
    )


taskleiste = tk.Frame(fenster, bg="#0e0f11")

taskleiste_hg = tk.Label(taskleiste, bd=0)
taskleiste_hg.place(x=0, y=0, relwidth=1, relheight=1)

TASKLEISTE_PHOTO = None
taskleiste_chips = []


def taskleiste_glas_aktualisieren():
    global TASKLEISTE_PHOTO

    try:
        bild = graustufen_bild(
            0, HOEHE - TASKLEISTE_HOEHE, BREITE, TASKLEISTE_HOEHE,
            alpha=0.58
        )

        if TASKLEISTE_PHOTO is None:
            TASKLEISTE_PHOTO = ImageTk.PhotoImage(bild)
            taskleiste_hg.config(image=TASKLEISTE_PHOTO)
        else:
            TASKLEISTE_PHOTO.paste(bild)

    except Exception:
        pass


def taskleiste_klick(name):
    # Wie bei einer echten Taskleiste: Klick auf ein aktives
    # (sichtbares) Fenster minimiert es, Klick auf ein minimiertes
    # holt es zurück.
    if name in offene_ansichten:
        ansicht_minimieren(name)
    else:
        ansicht_zeigen(name)


def taskleiste_aktualisieren():
    for widget in taskleiste_chips:
        widget.destroy()

    taskleiste_chips.clear()

    if not laufende_reihenfolge:
        taskleiste.place_forget()
        return

    for name in laufende_reihenfolge:
        aktiv = name not in minimierte_ansichten
        farbe_bg = FARBE_HOVER if aktiv else "#1e1f22"
        farbe_fg = TASKLEISTE_AKTIV_FARBE if aktiv else "white"

        chip = tk.Button(
            taskleiste,
            text=ansicht_titel.get(name, name),
            command=lambda n=name: taskleiste_klick(n),
            font=("Segoe UI", 9, "bold"),
            bg=farbe_bg,
            fg=farbe_fg,
            activebackground="#2c2d31",
            activeforeground=TASKLEISTE_AKTIV_FARBE,
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=8
        )
        chip.pack(side="left", padx=(10, 0), pady=6)
        taskleiste_chips.append(chip)

    taskleiste.place(
        x=0, y=HOEHE - TASKLEISTE_HOEHE,
        width=BREITE, height=TASKLEISTE_HOEHE
    )
    taskleiste.lift()
    taskleiste_glas_aktualisieren()


TITEL_HOEHE = 38


def panel_titelleiste_glas_aktualisieren(name):
    frame = ansicht_frames.get(name)

    if frame is None or not hasattr(frame, "titelleiste_hg"):
        return

    try:
        x, y = ansicht_positionen[name]
        breite = ansicht_groessen[name][0]

        bild = graustufen_bild(x, y, breite, TITEL_HOEHE, alpha=0.58)

        foto = getattr(frame, "titelleiste_foto", None)

        if foto is None or foto.width() != breite:
            foto = ImageTk.PhotoImage(bild)
            frame.titelleiste_foto = foto
            frame.titelleiste_hg.config(image=foto)
        else:
            foto.paste(bild)

    except Exception:
        pass


def ansicht_bauen(name, titel):
    # Ansichten hängen direkt am Hauptfenster (nicht am Overlay) -
    # dadurch funktionieren sie wie eigenständige Desktop-Fenster und
    # bleiben nutzbar, auch wenn das Overlay-Menü geschlossen ist.
    frame = tk.Frame(
        fenster, bg="#161618",
        highlightthickness=1, highlightbackground="#333438"
    )

    titelleiste = tk.Frame(
        frame, bg="#202124", cursor="fleur", height=TITEL_HOEHE
    )
    titelleiste.pack(fill="x", side="top")
    titelleiste.pack_propagate(False)

    # Leicht durchscheinender Hintergrund für die Titelleiste (wie
    # beim Overlay, nur schwächer) - liegt hinter Titel/Knöpfen.
    titelleiste_hg = tk.Label(titelleiste, bd=0, cursor="fleur")
    titelleiste_hg.place(x=0, y=0, relwidth=1, relheight=1)
    frame.titelleiste_hg = titelleiste_hg

    titel_label = tk.Label(
        titelleiste, text=titel,
        font=("Segoe UI", 11, "bold"),
        bg="#202124", fg="white"
    )
    titel_label.pack(side="left", padx=12, pady=9)

    schliessen_knopf = tk.Button(
        titelleiste,
        text="✕",
        command=lambda: ansicht_schliessen(name),
        font=("Segoe UI", 10, "bold"),
        bg="#202124",
        fg="white",
        activebackground="#c0392b",
        activeforeground="white",
        bd=0,
        relief="flat",
        cursor="hand2",
        padx=12
    )
    schliessen_knopf.pack(side="right", fill="y")

    minimieren_knopf = tk.Button(
        titelleiste,
        text="_",
        command=lambda: ansicht_minimieren(name),
        font=("Segoe UI", 10, "bold"),
        bg="#202124",
        fg="white",
        activebackground="#2c2d31",
        activeforeground="white",
        bd=0,
        relief="flat",
        cursor="hand2",
        padx=12
    )
    minimieren_knopf.pack(side="right", fill="y")

    inhalt = tk.Frame(frame, bg="#161618")
    inhalt.pack(fill="both", expand=True)

    # Titelleiste per Drag & Drop innerhalb des Overlays verschieben.
    ziehen_start = {"x": 0, "y": 0}

    def ziehen_beginnen(event):
        ziehen_start["x"] = event.x
        ziehen_start["y"] = event.y

    def ziehen_bewegen(event):
        alte_x, alte_y = ansicht_positionen[name]
        breite, hoehe = ansicht_groessen[name]

        neue_x = alte_x + (event.x - ziehen_start["x"])
        neue_y = alte_y + (event.y - ziehen_start["y"])

        neue_x = max(0, min(neue_x, BREITE - breite))
        neue_y = max(0, min(neue_y, HOEHE - hoehe))

        ansicht_positionen[name] = [neue_x, neue_y]
        frame.place(x=neue_x, y=neue_y)

    def ziehen_fertig(event):
        panel_titelleiste_glas_aktualisieren(name)

    for _titel_widget in (titelleiste, titelleiste_hg, titel_label):
        _titel_widget.bind("<ButtonPress-1>", ziehen_beginnen)
        _titel_widget.bind("<B1-Motion>", ziehen_bewegen)
        _titel_widget.bind("<ButtonRelease-1>", ziehen_fertig)

    # Größe ändern: an den Seiten (links/rechts/unten) oder am Griff
    # unten rechts ziehen, um das Panel schmaler/breiter bzw.
    # kleiner/größer zu machen.
    def resize_binden(widget, links=False, rechts=False, unten=False):
        start = {"x": 0, "y": 0}

        def beginnen(event):
            start["x"] = event.x
            start["y"] = event.y

        def bewegen(event):
            x, y = ansicht_positionen[name]
            breite, hoehe = ansicht_groessen[name]

            dx = event.x - start["x"]
            dy = event.y - start["y"]

            neue_x = x
            neue_breite = breite
            neue_hoehe = hoehe

            if rechts:
                neue_breite = breite + dx
            if unten:
                neue_hoehe = hoehe + dy
            if links:
                neue_breite = breite - dx
                neue_x = x + dx

            if neue_breite < ANSICHT_MIN_BREITE:
                if links:
                    neue_x = x + breite - ANSICHT_MIN_BREITE
                neue_breite = ANSICHT_MIN_BREITE

            if neue_hoehe < ANSICHT_MIN_HOEHE:
                neue_hoehe = ANSICHT_MIN_HOEHE

            if neue_x < 0:
                neue_breite += neue_x
                neue_x = 0

            if neue_x + neue_breite > BREITE:
                if links:
                    neue_x = BREITE - neue_breite
                else:
                    neue_breite = BREITE - neue_x

            if y + neue_hoehe > HOEHE:
                neue_hoehe = HOEHE - y

            ansicht_positionen[name] = [neue_x, y]
            ansicht_groessen[name] = [neue_breite, neue_hoehe]

            frame.place(x=neue_x, y=y, width=neue_breite, height=neue_hoehe)

        def fertig(event):
            panel_titelleiste_glas_aktualisieren(name)

        widget.bind("<ButtonPress-1>", beginnen)
        widget.bind("<B1-Motion>", bewegen)
        widget.bind("<ButtonRelease-1>", fertig)

    kante_rechts = tk.Frame(frame, bg="#161618", cursor="sb_h_double_arrow")
    kante_rechts.place(relx=1.0, y=0, anchor="ne", width=5, relheight=1.0)

    kante_links = tk.Frame(frame, bg="#161618", cursor="sb_h_double_arrow")
    kante_links.place(x=0, y=0, width=5, relheight=1.0)

    kante_unten = tk.Frame(frame, bg="#161618", cursor="sb_v_double_arrow")
    kante_unten.place(x=0, rely=1.0, anchor="sw", relwidth=1.0, height=5)

    griff = tk.Label(
        frame, text="⋰", bg="#202124", fg="#8a8a8f", cursor="size_nw_se"
    )
    griff.place(relx=1.0, rely=1.0, anchor="se", width=16, height=16)

    resize_binden(kante_rechts, rechts=True)
    resize_binden(kante_links, links=True)
    resize_binden(kante_unten, unten=True)
    resize_binden(griff, rechts=True, unten=True)

    ansicht_registrieren(name, frame, titel)
    panel_titelleiste_glas_aktualisieren(name)

    return inhalt


# --- Einstellungen ---------------------------------------------

einstellungen_ansicht = ansicht_bauen("settings", t("settings_title"))

tk.Label(
    einstellungen_ansicht,
    text=t("language"),
    font=("Segoe UI", 12, "bold"),
    bg="#161618",
    fg="white"
).pack(pady=(10, 5))

sprach_frame = tk.Frame(einstellungen_ansicht, bg="#161618")
sprach_frame.pack(pady=5)

tk.Button(
    sprach_frame,
    text="Deutsch",
    width=15,
    command=lambda: sprache_aendern("de"),
    **MENU_BUTTON_STYLE
).pack(side="left", padx=5)

tk.Button(
    sprach_frame,
    text="English",
    width=15,
    command=lambda: sprache_aendern("en"),
    **MENU_BUTTON_STYLE
).pack(side="left", padx=5)

tk.Label(
    einstellungen_ansicht,
    text=t("transparency"),
    font=("Segoe UI", 12, "bold"),
    bg="#161618",
    fg="white"
).pack(pady=(25, 5))

transparenz_schieber = tk.Scale(
    einstellungen_ansicht,
    from_=30,
    to=100,
    orient="horizontal",
    length=350,
    command=transparenz_setzen,
    bg="#161618",
    fg="white",
    troughcolor="#202124",
    highlightthickness=0,
    bd=0
)
transparenz_schieber.set(100)
transparenz_schieber.pack()

tk.Label(
    einstellungen_ansicht,
    text=t("background"),
    font=("Segoe UI", 12, "bold"),
    bg="#161618",
    fg="white"
).pack(pady=(25, 10))

tk.Button(
    einstellungen_ansicht,
    text=t("choose_background"),
    width=30,
    command=hintergrund_auswaehlen,
    **MENU_BUTTON_STYLE
).pack(pady=5)

tk.Button(
    einstellungen_ansicht,
    text=t("choose_video"),
    width=30,
    command=video_auswaehlen,
    **MENU_BUTTON_STYLE
).pack(pady=5)

tk.Button(
    einstellungen_ansicht,
    text=t("reset_background"),
    width=30,
    command=standard_hintergrund_laden,
    **MENU_BUTTON_STYLE
).pack(pady=5)

tk.Label(
    einstellungen_ansicht,
    text=t("settings_taskbar_color"),
    font=("Segoe UI", 12, "bold"),
    bg="#161618",
    fg="white"
).pack(pady=(25, 10))

taskleiste_farbe_zeile = tk.Frame(einstellungen_ansicht, bg="#161618")
taskleiste_farbe_zeile.pack(pady=(0, 10))

taskleiste_farbe_vorschau = tk.Label(
    taskleiste_farbe_zeile,
    text="  ",
    bg=TASKLEISTE_AKTIV_FARBE,
    width=4,
    highlightthickness=1,
    highlightbackground=FARBE_RAND
)
taskleiste_farbe_vorschau.pack(side="left", padx=(0, 10))


def taskleiste_farbe_waehlen():
    global TASKLEISTE_AKTIV_FARBE

    ergebnis = colorchooser.askcolor(
        color=TASKLEISTE_AKTIV_FARBE,
        title=t("settings_taskbar_color"),
        parent=fenster
    )

    if ergebnis and ergebnis[1]:
        TASKLEISTE_AKTIV_FARBE = ergebnis[1]
        taskleiste_farbe_vorschau.config(bg=TASKLEISTE_AKTIV_FARBE)
        taskleiste_aktualisieren()
        einstellungen_speichern({"taskleiste_farbe": TASKLEISTE_AKTIV_FARBE})


tk.Button(
    taskleiste_farbe_zeile,
    text=t("settings_taskbar_color_choose"),
    command=taskleiste_farbe_waehlen,
    **MENU_BUTTON_STYLE
).pack(side="left")


# --- Log ---------------------------------------------------------

log_ansicht = ansicht_bauen("log", t("log_title"))

log_text = tk.Text(
    log_ansicht,
    bg=FARBE_EINGABE,
    fg="white",
    insertbackground="white",
    font=("Consolas", 10),
    padx=10,
    pady=10,
    **EINGABE_RAHMEN
)
log_text.pack(fill="both", expand=True, padx=20, pady=(15, 20))

for _eintrag in LOG_ENTRIES:
    log_text.insert("end", _eintrag + "\n")

log_text.config(state="disabled")
log_text.see("end")


# --- EniMultitool (echtes cmd-Fenster eingebettet im Programm) -------

eni_konsole_ansicht = ansicht_bauen("eni_console", t("eni"))

# Reines Wirts-Frame, in das das echte cmd-Fenster per SetParent
# eingebettet wird (siehe eni_multitool_prozess_starten).
eni_konsole_host = tk.Frame(eni_konsole_ansicht, bg="black")
eni_konsole_host.pack(fill="both", expand=True, padx=20, pady=(15, 20))

ANSICHT_ON_SHOW["eni_console"] = eni_multitool_prozess_starten


# --- Übersetzer ----------------------------------------------------

uebersetzer_ansicht = ansicht_bauen("translate", t("translate_title"))
uebersetzer_ansicht_bauen(uebersetzer_ansicht)


# --- Autoclicker -----------------------------------------------------

autoclicker_ansicht = ansicht_bauen("autoclicker", t("autoclicker_title"))
autoclicker_ansicht_bauen(autoclicker_ansicht)


# --- Uhr (Timer & Stoppuhr) -------------------------------------------

uhr_ansicht = ansicht_bauen("clock", t("clock_title"))
uhr_ansicht_bauen(uhr_ansicht)


# --- Download --------------------------------------------------------

download_ansicht = ansicht_bauen("download", t("download"))

download_label = tk.Label(
    download_ansicht,
    text=t("download_files"),
    font=("Segoe UI", 12),
    bg="#161618",
    fg="white"
)
download_label.pack(pady=(120, 20))

download_progress = ttk.Progressbar(
    download_ansicht,
    length=400,
    mode="determinate"
)
download_progress.pack()


# --- Wichtige Befehle --------------------------------------------------

BEFEHLE_DE = [
    ("System & Windows", "tasklist", "Listet alle laufenden Prozesse auf."),
    (
        "System & Windows", "taskkill /IM name.exe /F",
        "Beendet einen Prozess zwangsweise über seinen Namen."
    ),
    (
        "System & Windows", "sfc /scannow",
        "Prüft und repariert beschädigte Windows-Systemdateien."
    ),
    (
        "System & Windows", "chkdsk C: /f",
        "Prüft und repariert Fehler auf der Festplatte C:."
    ),
    (
        "System & Windows", "systeminfo",
        "Zeigt detaillierte Infos zu System, Hardware und Betriebssystem."
    ),
    (
        "System & Windows", "ren alte_datei.endung dein_script.py",
        "Benennt eine Datei um - z. B. um eine falsche/versteckte "
        "Dateiendung zu korrigieren."
    ),
    (
        "System & Windows", "del /f /q dateiname",
        "Löscht eine Datei zwangsweise. Vorsicht, das geht nicht in den "
        "Papierkorb!"
    ),
    (
        "Netzwerk", "ipconfig /all",
        "Zeigt alle Netzwerkeinstellungen an (IP, Gateway, DNS)."
    ),
    (
        "Netzwerk", "ipconfig /flushdns",
        "Leert den DNS-Cache - hilft bei Verbindungsproblemen."
    ),
    (
        "Netzwerk", "netstat -ano",
        "Zeigt aktive Netzwerkverbindungen inkl. Prozess-ID."
    ),
    (
        "Netzwerk", "ping 8.8.8.8 -t",
        "Testet dauerhaft die Verbindung zu einem Server (Strg+C zum Stoppen)."
    ),
    (
        "Python & Coding", "python --version",
        "Zeigt die aktuell installierte Python-Version an."
    ),
    (
        "Python & Coding", "where python",
        "Zeigt den Pfad der aktiven Python-Installation an."
    ),
    (
        "Python & Coding", "pip install pyinstaller",
        "Installiert PyInstaller, um .py-Dateien in .exe umzuwandeln."
    ),
    (
        "Python & Coding", "python -m PyInstaller --onefile dein_script.py",
        "Baut aus einer .py-Datei eine einzelne .exe (mit Konsolenfenster "
        "für Debug-Ausgaben)."
    ),
    (
        "Python & Coding",
        "python -m PyInstaller --onefile --noconsole dein_script.py",
        "Baut aus einer .py-Datei eine einzelne .exe ohne Konsolenfenster "
        "- ideal für fertige Programme."
    ),
    (
        "Python & Coding", "pip install -r requirements.txt",
        "Installiert alle Pakete, die in requirements.txt gelistet sind."
    ),
    (
        "Python & Coding", "pip freeze > requirements.txt",
        "Schreibt alle installierten Pakete in eine requirements.txt."
    ),
    (
        "Python & Coding", "python -m venv venv",
        "Erstellt eine virtuelle Python-Umgebung im Ordner 'venv'."
    ),
    (
        "Python & Coding", r"venv\Scripts\activate",
        "Aktiviert die virtuelle Umgebung (Windows)."
    ),
    (
        "Git", "git clone <url>",
        "Lädt ein Repository (z. B. von GitHub) in einen neuen Ordner."
    ),
    (
        "Git", "git status",
        "Zeigt geänderte und neue Dateien im aktuellen Repository an."
    ),
    (
        "Git", 'git add . && git commit -m "..."',
        "Fügt alle Änderungen hinzu und erstellt einen Commit."
    ),
    (
        "Git", "git push",
        "Lädt lokale Commits zum verknüpften Remote-Repository hoch."
    ),
]

BEFEHLE_EN = [
    ("System & Windows", "tasklist", "Lists all running processes."),
    (
        "System & Windows", "taskkill /IM name.exe /F",
        "Force-kills a process by its name."
    ),
    (
        "System & Windows", "sfc /scannow",
        "Checks and repairs corrupted Windows system files."
    ),
    (
        "System & Windows", "chkdsk C: /f",
        "Checks and repairs errors on drive C:."
    ),
    (
        "System & Windows", "systeminfo",
        "Shows detailed info about system, hardware and OS."
    ),
    (
        "System & Windows", "ren old_file.ext your_script.py",
        "Renames a file - e.g. to fix a wrong/hidden file extension."
    ),
    (
        "System & Windows", "del /f /q filename",
        "Force-deletes a file. Careful, this skips the Recycle Bin!"
    ),
    (
        "Network", "ipconfig /all",
        "Shows all network settings (IP, gateway, DNS)."
    ),
    (
        "Network", "ipconfig /flushdns",
        "Clears the DNS cache - helps with connection issues."
    ),
    (
        "Network", "netstat -ano",
        "Shows active network connections including process ID."
    ),
    (
        "Network", "ping 8.8.8.8 -t",
        "Continuously tests the connection to a server (Ctrl+C to stop)."
    ),
    (
        "Python & Coding", "python --version",
        "Shows the currently installed Python version."
    ),
    (
        "Python & Coding", "where python",
        "Shows the path of the active Python installation."
    ),
    (
        "Python & Coding", "pip install pyinstaller",
        "Installs PyInstaller, used to turn .py files into .exe."
    ),
    (
        "Python & Coding", "python -m PyInstaller --onefile your_script.py",
        "Builds a single .exe with a console window (useful for debug "
        "output)."
    ),
    (
        "Python & Coding",
        "python -m PyInstaller --onefile --noconsole your_script.py",
        "Builds a single .exe with no console window - ideal for "
        "finished programs."
    ),
    (
        "Python & Coding", "pip install -r requirements.txt",
        "Installs every package listed in requirements.txt."
    ),
    (
        "Python & Coding", "pip freeze > requirements.txt",
        "Writes all installed packages into a requirements.txt."
    ),
    (
        "Python & Coding", "python -m venv venv",
        "Creates a virtual Python environment in a 'venv' folder."
    ),
    (
        "Python & Coding", r"venv\Scripts\activate",
        "Activates the virtual environment (Windows)."
    ),
    (
        "Git", "git clone <url>",
        "Downloads a repository (e.g. from GitHub) into a new folder."
    ),
    (
        "Git", "git status",
        "Shows changed and new files in the current repository."
    ),
    (
        "Git", 'git add . && git commit -m "..."',
        "Stages all changes and creates a commit."
    ),
    (
        "Git", "git push",
        "Uploads local commits to the linked remote repository."
    ),
]


def befehle_liste():
    return BEFEHLE_DE if SPRACHE == "de" else BEFEHLE_EN


befehle_ansicht = ansicht_bauen("commands", t("commands_title"))

befehle_canvas = tk.Canvas(
    befehle_ansicht, bg="#161618", highlightthickness=0, bd=0
)
befehle_scrollbar = tk.Scrollbar(
    befehle_ansicht, orient="vertical", command=befehle_canvas.yview
)
befehle_innen = tk.Frame(befehle_canvas, bg="#161618")

befehle_innen.bind(
    "<Configure>",
    lambda e: befehle_canvas.configure(
        scrollregion=befehle_canvas.bbox("all")
    )
)

befehle_canvas.create_window((0, 0), window=befehle_innen, anchor="nw")
befehle_canvas.configure(yscrollcommand=befehle_scrollbar.set)

befehle_canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=15)
befehle_scrollbar.pack(side="right", fill="y", padx=(0, 15), pady=15)


def _befehle_mausrad(event):
    befehle_canvas.yview_scroll(int(-event.delta / 120), "units")


befehle_canvas.bind("<MouseWheel>", _befehle_mausrad)
befehle_innen.bind("<MouseWheel>", _befehle_mausrad)

_letzte_kategorie = None

for _kategorie, _befehl, _beschreibung in befehle_liste():

    if _kategorie != _letzte_kategorie:
        tk.Label(
            befehle_innen,
            text=_kategorie,
            font=("Segoe UI", 11, "bold"),
            bg="#161618",
            fg="#9dffce",
            anchor="w"
        ).pack(
            fill="x", padx=(2, 15),
            pady=(16 if _letzte_kategorie is not None else 4, 4)
        )
        _letzte_kategorie = _kategorie

    _zeile = tk.Frame(befehle_innen, bg="#1b1c1f")
    _zeile.pack(fill="x", padx=(0, 15), pady=6)
    _zeile.bind("<MouseWheel>", _befehle_mausrad)

    _kopf = tk.Frame(_zeile, bg="#1b1c1f")
    _kopf.pack(fill="x")
    _kopf.bind("<MouseWheel>", _befehle_mausrad)

    _eingabe = tk.Entry(
        _kopf,
        font=("Consolas", 11),
        bg=FARBE_EINGABE,
        fg=FARBE_AKZENT,
        insertbackground=FARBE_AKZENT,
        **EINGABE_RAHMEN
    )
    _eingabe.insert(0, _befehl)
    _eingabe.config(state="readonly", readonlybackground=FARBE_EINGABE)
    _eingabe.pack(
        side="left", fill="x", expand=True, ipady=6, padx=(10, 6), pady=8
    )

    _kopier_knopf = tk.Button(
        _kopf,
        text=t("commands_copy"),
        font=("Segoe UI", 9, "bold"),
        bg="#202124",
        fg="white",
        activebackground="#2c2d31",
        activeforeground="white",
        bd=0,
        relief="flat",
        cursor="hand2",
        padx=10
    )

    def _kopieren_klick(cmd=_befehl, knopf=_kopier_knopf):
        fenster.clipboard_clear()
        fenster.clipboard_append(cmd)

        urspruenglicher_text = t("commands_copy")
        knopf.config(text=t("commands_copied"))
        fenster.after(900, lambda: knopf.config(text=urspruenglicher_text))

    _kopier_knopf.config(command=_kopieren_klick)
    _kopier_knopf.pack(side="right", padx=(0, 10))

    tk.Label(
        _zeile,
        text=_beschreibung,
        font=("Segoe UI", 9),
        bg="#1b1c1f",
        fg="#a0a0a5",
        anchor="w",
        justify="left",
        wraplength=680
    ).pack(fill="x", padx=10, pady=(0, 8))


# --- Passwort-Generator ------------------------------------------------

def passwort_generieren(
    laenge, gross, klein, zahlen, sonder
):
    zeichenarten = []

    if gross:
        zeichenarten.append(string.ascii_uppercase)
    if klein:
        zeichenarten.append(string.ascii_lowercase)
    if zahlen:
        zeichenarten.append(string.digits)
    if sonder:
        zeichenarten.append("!?%&()=+-_#*.,;:")

    if not zeichenarten:
        return None

    # Mindestens ein Zeichen aus jeder gewählten Kategorie garantieren,
    # der Rest wird aus dem gesamten Pool aufgefüllt und gemischt.
    pool = "".join(zeichenarten)

    pflicht = [secrets.choice(art) for art in zeichenarten]
    rest = [
        secrets.choice(pool)
        for _ in range(max(0, laenge - len(pflicht)))
    ]

    passwort = pflicht + rest
    for i in range(len(passwort) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        passwort[i], passwort[j] = passwort[j], passwort[i]

    return "".join(passwort[:laenge])


passwort_ansicht = ansicht_bauen("password", t("password_gen"))

tk.Label(
    passwort_ansicht,
    text=t("password_length"),
    font=("Segoe UI", 10, "bold"),
    bg="#161618",
    fg="#cccccc",
    anchor="w"
).pack(fill="x", padx=20, pady=(20, 2))

passwort_laenge_var = tk.IntVar(value=16)

tk.Scale(
    passwort_ansicht,
    from_=6,
    to=64,
    orient="horizontal",
    variable=passwort_laenge_var,
    bg="#161618",
    fg="white",
    troughcolor="#202124",
    highlightthickness=0,
    bd=0
).pack(fill="x", padx=20)

passwort_gross_var = tk.BooleanVar(value=True)
passwort_klein_var = tk.BooleanVar(value=True)
passwort_zahlen_var = tk.BooleanVar(value=True)
passwort_sonder_var = tk.BooleanVar(value=False)

CHECKBOX_STYLE = {
    "bg": "#161618",
    "fg": "white",
    "selectcolor": "#0f1011",
    "activebackground": "#161618",
    "activeforeground": "white",
    "font": ("Segoe UI", 10),
    "anchor": "w"
}

for _text, _var in (
    (t("password_uppercase"), passwort_gross_var),
    (t("password_lowercase"), passwort_klein_var),
    (t("password_digits"), passwort_zahlen_var),
    (t("password_symbols"), passwort_sonder_var),
):
    tk.Checkbutton(
        passwort_ansicht, text=_text, variable=_var, **CHECKBOX_STYLE
    ).pack(fill="x", padx=20, pady=2)

passwort_ausgabe_var = tk.StringVar(value="")

passwort_ausgabe_entry = tk.Entry(
    passwort_ansicht,
    textvariable=passwort_ausgabe_var,
    font=("Consolas", 14),
    bg=FARBE_EINGABE,
    fg=FARBE_AKZENT,
    insertbackground=FARBE_AKZENT,
    justify="center",
    state="readonly",
    readonlybackground=FARBE_EINGABE,
    **EINGABE_RAHMEN
)
passwort_ausgabe_entry.pack(fill="x", padx=20, pady=(20, 12), ipady=10)

passwort_knopf_zeile = tk.Frame(passwort_ansicht, bg="#161618")
passwort_knopf_zeile.pack(fill="x", padx=20)


def passwort_generieren_klick():
    ergebnis = passwort_generieren(
        passwort_laenge_var.get(),
        passwort_gross_var.get(),
        passwort_klein_var.get(),
        passwort_zahlen_var.get(),
        passwort_sonder_var.get()
    )

    if ergebnis is None:
        messagebox.showwarning(
            t("password_gen"), t("password_none_selected")
        )
        return

    passwort_ausgabe_var.set(ergebnis)


def passwort_kopieren_klick():
    if not passwort_ausgabe_var.get():
        return

    fenster.clipboard_clear()
    fenster.clipboard_append(passwort_ausgabe_var.get())

    urspruenglicher_text = t("password_copy")
    passwort_kopier_knopf.config(text=t("password_copied"))
    fenster.after(
        900, lambda: passwort_kopier_knopf.config(text=urspruenglicher_text)
    )


tk.Button(
    passwort_knopf_zeile,
    text=t("password_generate"),
    command=passwort_generieren_klick,
    pady=8,
    **PRIMARY_BUTTON_STYLE
).pack(side="left", fill="x", expand=True, padx=(0, 6))

passwort_kopier_knopf = tk.Button(
    passwort_knopf_zeile,
    text=t("password_copy"),
    command=passwort_kopieren_klick,
    font=("Segoe UI", 11, "bold"),
    bg=FARBE_OBERFLAECHE,
    fg=FARBE_TEXT,
    activebackground=FARBE_HOVER,
    activeforeground=FARBE_AKZENT,
    bd=0,
    relief="flat",
    cursor="hand2",
    pady=8
)
passwort_kopier_knopf.pack(side="left", fill="x", expand=True, padx=(6, 0))


# --- System-Info -----------------------------------------------------

class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def system_info_sammeln():
    daten = {}

    try:
        daten["os"] = (
            f"{platform.system()} {platform.release()} "
            f"({platform.version()})"
        )
    except Exception:
        daten["os"] = "-"

    daten["computer"] = platform.node() or "-"
    daten["cpu"] = str(os.cpu_count() or "-")

    try:
        gesamt, _, frei = shutil.disk_usage(str(ORDNER.anchor or "C:\\"))
        daten["disk"] = (
            f"{frei / (1024 ** 3):.1f} GB frei von "
            f"{gesamt / (1024 ** 3):.1f} GB"
        )
    except Exception:
        daten["disk"] = "-"

    try:
        status = _MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))

        gesamt_gb = status.ullTotalPhys / (1024 ** 3)
        frei_gb = status.ullAvailPhys / (1024 ** 3)

        daten["ram"] = (
            f"{gesamt_gb - frei_gb:.1f} GB genutzt von "
            f"{gesamt_gb:.1f} GB ({status.dwMemoryLoad}%)"
        )
    except Exception:
        daten["ram"] = "-"

    return daten


sysinfo_ansicht = ansicht_bauen("sysinfo", t("sysinfo_title"))

sysinfo_zeilen = {}

for _feld, _titel in (
    ("os", t("sysinfo_os")),
    ("computer", t("sysinfo_computer")),
    ("cpu", t("sysinfo_cpu")),
    ("ram", t("sysinfo_ram")),
    ("disk", t("sysinfo_disk")),
):
    _zeile = tk.Frame(sysinfo_ansicht, bg="#161618")
    _zeile.pack(fill="x", padx=20, pady=8)

    tk.Label(
        _zeile,
        text=_titel,
        font=("Segoe UI", 10, "bold"),
        bg="#161618",
        fg="#8a8a8f",
        width=18,
        anchor="w"
    ).pack(side="left")

    _wert_label = tk.Label(
        _zeile,
        text="-",
        font=("Segoe UI", 10),
        bg="#161618",
        fg="white",
        anchor="w"
    )
    _wert_label.pack(side="left", fill="x", expand=True)

    sysinfo_zeilen[_feld] = _wert_label


def sysinfo_aktualisieren():
    daten = system_info_sammeln()

    for feld, label in sysinfo_zeilen.items():
        label.config(text=daten.get(feld, "-"))


ANSICHT_ON_SHOW["sysinfo"] = sysinfo_aktualisieren
sysinfo_aktualisieren()


tk.Button(
    sysinfo_ansicht,
    text=t("sysinfo_refresh"),
    command=sysinfo_aktualisieren,
    pady=8,
    **PRIMARY_BUTTON_STYLE
).pack(fill="x", padx=20, pady=(20, 0))


# --- Notizen (mehrseitig, dauerhaft gespeichert) ------------------------

def notizen_laden():
    try:
        if NOTIZEN_DATEI.exists():
            with open(NOTIZEN_DATEI, "r", encoding="utf-8") as f:
                daten = json.load(f)

                if daten.get("seiten"):
                    return daten

    except Exception:
        pass

    return {"seiten": [{"titel": "Notiz 1", "text": ""}], "aktiv": 0}


def notizen_speichern():
    try:
        with open(NOTIZEN_DATEI, "w", encoding="utf-8") as f:
            json.dump(notizen_daten, f, ensure_ascii=False)
    except Exception:
        pass


notizen_daten = notizen_laden()

if notizen_daten.get("aktiv", 0) >= len(notizen_daten["seiten"]):
    notizen_daten["aktiv"] = 0


notizen_ansicht = ansicht_bauen("notes", t("notes_title"))

notizen_hauptbereich = tk.Frame(notizen_ansicht, bg=FARBE_HINTERGRUND)
notizen_hauptbereich.pack(fill="both", expand=True, padx=20, pady=(15, 20))

notizen_seitenleiste = tk.Frame(
    notizen_hauptbereich, bg=FARBE_OBERFLAECHE, width=180,
    highlightthickness=1, highlightbackground=FARBE_RAND
)
notizen_seitenleiste.pack(side="left", fill="y")
notizen_seitenleiste.pack_propagate(False)

notizen_liste_frame = tk.Frame(notizen_seitenleiste, bg=FARBE_OBERFLAECHE)
notizen_liste_frame.pack(fill="both", expand=True, padx=6, pady=6)

notizen_editor = tk.Text(
    notizen_hauptbereich,
    wrap="word",
    bg=FARBE_EINGABE,
    fg="white",
    insertbackground="white",
    font=("Segoe UI", 11),
    padx=14,
    pady=12,
    **EINGABE_RAHMEN
)
notizen_editor.pack(side="left", fill="both", expand=True, padx=(10, 0))


def notizen_text_sichern():
    aktiv = notizen_daten["aktiv"]

    if 0 <= aktiv < len(notizen_daten["seiten"]):
        notizen_daten["seiten"][aktiv]["text"] = notizen_editor.get(
            "1.0", "end-1c"
        )


def notizen_umbenennen(index):
    neuer_titel = simpledialog.askstring(
        t("notes_title"),
        t("notes_rename_prompt"),
        initialvalue=notizen_daten["seiten"][index]["titel"],
        parent=fenster
    )

    if neuer_titel:
        notizen_daten["seiten"][index]["titel"] = neuer_titel
        notizen_seitenliste_aktualisieren()
        notizen_speichern()


def notizen_loeschen(index):
    if len(notizen_daten["seiten"]) <= 1:
        return

    if not messagebox.askyesno(
        t("notes_title"), t("notes_delete_confirm")
    ):
        return

    del notizen_daten["seiten"][index]

    if notizen_daten["aktiv"] >= len(notizen_daten["seiten"]):
        notizen_daten["aktiv"] = len(notizen_daten["seiten"]) - 1

    notizen_seite_anzeigen(notizen_daten["aktiv"])


def notizen_kontextmenu(event, index):
    menu = tk.Menu(
        fenster, tearoff=0,
        bg=FARBE_OBERFLAECHE, fg=FARBE_TEXT,
        activebackground=FARBE_HOVER, activeforeground=FARBE_AKZENT,
        bd=0
    )

    menu.add_command(
        label=t("notes_rename"),
        command=lambda: notizen_umbenennen(index)
    )

    if len(notizen_daten["seiten"]) > 1:
        menu.add_command(
            label=t("notes_delete"),
            command=lambda: notizen_loeschen(index)
        )

    menu.tk_popup(event.x_root, event.y_root)


def notizen_seitenliste_aktualisieren():
    for widget in notizen_liste_frame.winfo_children():
        widget.destroy()

    for index, seite in enumerate(notizen_daten["seiten"]):
        aktiv = index == notizen_daten["aktiv"]
        farbe_bg = FARBE_HOVER if aktiv else FARBE_OBERFLAECHE
        farbe_fg = FARBE_AKZENT if aktiv else FARBE_TEXT

        zeile = tk.Frame(notizen_liste_frame, bg=farbe_bg)
        zeile.pack(fill="x", pady=1)

        # Dezenter Akzentstreifen links markiert die aktive Seite.
        tk.Frame(
            zeile, bg=FARBE_AKZENT if aktiv else farbe_bg, width=3
        ).pack(side="left", fill="y")

        knopf = tk.Button(
            zeile,
            text=seite["titel"],
            anchor="w",
            command=lambda i=index: notizen_seite_anzeigen(i),
            font=("Segoe UI", 9, "bold"),
            bg=farbe_bg,
            fg=farbe_fg,
            activebackground=FARBE_HOVER,
            activeforeground=FARBE_AKZENT,
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=7
        )
        knopf.pack(side="left", fill="x", expand=True)
        knopf.bind(
            "<Button-3>",
            lambda event, i=index: notizen_kontextmenu(event, i)
        )


def notizen_seite_anzeigen(index):
    notizen_text_sichern()

    notizen_daten["aktiv"] = index

    notizen_editor.delete("1.0", "end")
    notizen_editor.insert("1.0", notizen_daten["seiten"][index]["text"])

    notizen_seitenliste_aktualisieren()
    notizen_speichern()


def notizen_neue_seite():
    notizen_text_sichern()

    nummer = len(notizen_daten["seiten"]) + 1
    notizen_daten["seiten"].append({"titel": f"Notiz {nummer}", "text": ""})

    notizen_seite_anzeigen(len(notizen_daten["seiten"]) - 1)


tk.Button(
    notizen_seitenleiste,
    text=t("notes_new_page"),
    command=notizen_neue_seite,
    pady=7,
    **PRIMARY_BUTTON_STYLE
).pack(side="bottom", fill="x", padx=6, pady=6)

notizen_autosave_id = [None]


def notizen_geaendert(event=None):
    if notizen_autosave_id[0] is not None:
        fenster.after_cancel(notizen_autosave_id[0])

    def jetzt_speichern():
        notizen_text_sichern()
        notizen_speichern()
        notizen_autosave_id[0] = None

    notizen_autosave_id[0] = fenster.after(800, jetzt_speichern)


notizen_editor.bind("<KeyRelease>", notizen_geaendert)

notizen_editor.insert(
    "1.0", notizen_daten["seiten"][notizen_daten["aktiv"]]["text"]
)
notizen_seitenliste_aktualisieren()


# ============================================================
# DESKTOP-SYMBOLE (frei platzierbare Verknüpfungen auf dem
# Hintergrund, wie bei einem echten Desktop - per Rechtsklick auf
# einen Menü-Eintrag oder ein Symbol hinzufügen/entfernen)
# ============================================================

DESKTOP_SYMBOL_BREITE = 78
DESKTOP_SYMBOL_HOEHE = 92

desktop_icons = {}
desktop_icon_widgets = {}


def desktop_icons_datei_laden():
    try:
        if DESKTOP_ICONS_DATEI.exists():
            with open(DESKTOP_ICONS_DATEI, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass

    return {}


def desktop_icons_speichern():
    try:
        with open(DESKTOP_ICONS_DATEI, "w", encoding="utf-8") as f:
            json.dump(desktop_icons, f, ensure_ascii=False)
    except Exception:
        pass


def naechste_symbol_position():
    index = len(desktop_icons)
    spalte = index // 6
    zeile = index % 6

    # y startet unterhalb des ☰-Schalters oben links, damit sich
    # Symbole nicht mit ihm überlappen.
    return (
        24 + spalte * (DESKTOP_SYMBOL_BREITE + 20),
        100 + zeile * (DESKTOP_SYMBOL_HOEHE + 16)
    )


def desktop_symbol_titel(name):
    return desktop_icons[name].get("titel") or t(name)


_SCHRIFT_CACHE = {}


def _schrift_laden(groesse, fett=True):
    schluessel = (groesse, fett)

    if schluessel not in _SCHRIFT_CACHE:
        try:
            _SCHRIFT_CACHE[schluessel] = ImageFont.truetype(
                "segoeuib.ttf" if fett else "segoeui.ttf", groesse
            )
        except Exception:
            _SCHRIFT_CACHE[schluessel] = ImageFont.load_default()

    return _SCHRIFT_CACHE[schluessel]


def _text_kuerzen(zeichner, text, schrift, max_breite):
    if zeichner.textlength(text, font=schrift) <= max_breite:
        return text

    gekuerzt = text

    while len(gekuerzt) > 1:
        gekuerzt = gekuerzt[:-1]

        if zeichner.textlength(gekuerzt + "…", font=schrift) <= max_breite:
            return gekuerzt + "…"

    return text[:1]


def desktop_symbol_bild_erzeugen(name):
    info = desktop_icons[name]
    x, y = info["x"], info["y"]
    breite, hoehe = DESKTOP_SYMBOL_BREITE, DESKTOP_SYMBOL_HOEHE

    # Hintergrund direkt aus dem aktuellen Bild-/Video-Frame
    # ausschneiden und nur leicht abdunkeln - dadurch wirkt das
    # Symbol durchscheinend statt wie ein fester Kasten.
    hintergrund = None

    if LETZTES_FRAME is not None:
        try:
            x2 = min(x + breite, BREITE)
            y2 = min(y + hoehe, HOEHE)

            hintergrund = LETZTES_FRAME.crop((x, y, x2, y2))

            if hintergrund.size != (breite, hoehe):
                hintergrund = hintergrund.resize(
                    (breite, hoehe), Image.Resampling.BILINEAR
                )

            hintergrund = hintergrund.convert("RGBA")

        except Exception:
            hintergrund = None

    if hintergrund is None:
        hintergrund = Image.new("RGBA", (breite, hoehe), (22, 22, 24, 255))

    dunkel = Image.new("RGBA", (breite, hoehe), (8, 8, 10, 90))
    ergebnis = Image.alpha_composite(hintergrund, dunkel)

    bild_datei = info.get("bild")
    icon_gezeichnet = False

    if bild_datei:
        pfad = ORDNER / bild_datei

        if pfad.exists():
            try:
                icon_bild = Image.open(pfad).convert("RGBA")
                icon_bild.thumbnail((48, 48), Image.Resampling.LANCZOS)

                ix = (breite - icon_bild.width) // 2
                iy = 6 + (48 - icon_bild.height) // 2

                ergebnis.alpha_composite(icon_bild, (ix, iy))
                icon_gezeichnet = True

            except Exception as e:
                log(f"Icon-Bild-Fehler: {e}")

        if not icon_gezeichnet:
            info["bild"] = None

    zeichner = ImageDraw.Draw(ergebnis)

    if not icon_gezeichnet:
        kuerzel = desktop_symbol_titel(name)[:2].upper()
        schrift_gross = _schrift_laden(20)

        box = zeichner.textbbox((0, 0), kuerzel, font=schrift_gross)
        tw = box[2] - box[0]

        zeichner.text(
            ((breite - tw) / 2 - box[0], 14 - box[1]),
            kuerzel, font=schrift_gross, fill=(62, 242, 164, 255)
        )

    schrift_klein = _schrift_laden(12)
    zeile = _text_kuerzen(
        zeichner, desktop_symbol_titel(name), schrift_klein, breite - 6
    )

    box = zeichner.textbbox((0, 0), zeile, font=schrift_klein)
    tw = box[2] - box[0]
    tx = (breite - tw) / 2 - box[0]
    ty = 60

    # Leichter Schatten, damit der Text auf jedem Hintergrund
    # lesbar bleibt, statt eines festen Kastens.
    zeichner.text((tx + 1, ty + 1), zeile, font=schrift_klein, fill=(0, 0, 0, 210))
    zeichner.text((tx, ty), zeile, font=schrift_klein, fill=(255, 255, 255, 255))

    return ergebnis.convert("RGB")


def desktop_symbol_inhalt_aktualisieren(name):
    container = desktop_icon_widgets.get(name)

    if container is None:
        return

    try:
        bild = desktop_symbol_bild_erzeugen(name)

        # Bestehendes Tk-Bild wiederverwenden statt jedes Mal neu zu
        # erzeugen - gleiche Optimierung wie beim Video-Hintergrund.
        foto = getattr(container, "bild_photo", None)

        if foto is None:
            foto = ImageTk.PhotoImage(bild)
            container.bild_photo = foto
            container.bild_label.config(image=foto)
        else:
            foto.paste(bild)

    except Exception as e:
        log(f"Icon-Darstellungs-Fehler: {e}")


def desktop_symbol_umbenennen(name):
    neuer_titel = simpledialog.askstring(
        t("desktop_icon_rename"),
        t("desktop_icon_rename_prompt"),
        initialvalue=desktop_symbol_titel(name),
        parent=fenster
    )

    if neuer_titel:
        desktop_icons[name]["titel"] = neuer_titel
        desktop_symbol_inhalt_aktualisieren(name)
        desktop_icons_speichern()


def desktop_symbol_bild_waehlen(name):
    datei = filedialog.askopenfilename(
        title=t("desktop_icon_image"),
        filetypes=[
            ("Bilder", "*.jpg *.jpeg *.png *.bmp *.webp")
        ]
    )

    if not datei:
        return

    try:
        ziel = ORDNER / f"eni_icon_{name}.png"

        # RGBA erhalten (falls das Bild Transparenz hat), damit das
        # Symbol nicht als harter Kasten, sondern durchscheinend
        # dargestellt wird.
        bild = Image.open(datei)
        if bild.mode != "RGBA":
            bild = bild.convert("RGBA")
        bild.save(ziel)

        desktop_icons[name]["bild"] = ziel.name

        desktop_symbol_inhalt_aktualisieren(name)
        desktop_icons_speichern()

    except Exception as e:
        log(f"Icon-Bild-Fehler: {e}")
        messagebox.showerror(t("desktop_icon_image"), str(e))


def desktop_symbol_bild_zuruecksetzen(name):
    desktop_icons[name]["bild"] = None

    desktop_symbol_inhalt_aktualisieren(name)
    desktop_icons_speichern()


def desktop_kontextmenu(event, name):
    menu = tk.Menu(
        fenster, tearoff=0,
        bg=FARBE_OBERFLAECHE, fg=FARBE_TEXT,
        activebackground=FARBE_HOVER, activeforeground=FARBE_AKZENT,
        bd=0
    )

    if name in desktop_icons:
        menu.add_command(
            label=t("desktop_icon_rename"),
            command=lambda: desktop_symbol_umbenennen(name)
        )
        menu.add_command(
            label=t("desktop_icon_image"),
            command=lambda: desktop_symbol_bild_waehlen(name)
        )

        if desktop_icons[name].get("bild"):
            menu.add_command(
                label=t("desktop_icon_image_reset"),
                command=lambda: desktop_symbol_bild_zuruecksetzen(name)
            )

        menu.add_separator()
        menu.add_command(
            label=t("desktop_remove"),
            command=lambda: desktop_symbol_entfernen(name)
        )
    else:
        menu.add_command(
            label=t("desktop_add"),
            command=lambda: desktop_symbol_erstellen(name)
        )

    menu.tk_popup(event.x_root, event.y_root)


def desktop_symbol_erstellen(name, x=None, y=None, titel=None, bild=None):
    if name in desktop_icon_widgets:
        return

    if x is None or y is None:
        x, y = naechste_symbol_position()

    desktop_icons[name] = {"x": x, "y": y, "titel": titel, "bild": bild}

    container = tk.Frame(fenster, bd=0, highlightthickness=0, cursor="hand2")
    container.place(
        x=x, y=y,
        width=DESKTOP_SYMBOL_BREITE, height=DESKTOP_SYMBOL_HOEHE
    )

    bild_label = tk.Label(container, bd=0, highlightthickness=0)
    bild_label.place(x=0, y=0, relwidth=1, relheight=1)

    container.bild_label = bild_label

    desktop_icon_widgets[name] = container

    desktop_symbol_inhalt_aktualisieren(name)

    ziehen = {"x": 0, "y": 0, "bewegt": False}

    def maus_runter(event):
        ziehen["x"] = event.x
        ziehen["y"] = event.y
        ziehen["bewegt"] = False

    def maus_bewegen(event):
        alte_x = desktop_icons[name]["x"]
        alte_y = desktop_icons[name]["y"]

        neue_x = alte_x + (event.x - ziehen["x"])
        neue_y = alte_y + (event.y - ziehen["y"])

        neue_x = max(0, min(neue_x, BREITE - DESKTOP_SYMBOL_BREITE))
        neue_y = max(0, min(neue_y, HOEHE - DESKTOP_SYMBOL_HOEHE))

        if abs(event.x - ziehen["x"]) > 3 or abs(event.y - ziehen["y"]) > 3:
            ziehen["bewegt"] = True

        desktop_icons[name]["x"] = neue_x
        desktop_icons[name]["y"] = neue_y
        container.place(x=neue_x, y=neue_y)

    def maus_los(event):
        if ziehen["bewegt"]:
            desktop_symbol_inhalt_aktualisieren(name)
            desktop_icons_speichern()
        else:
            befehl = MENU_BEFEHLE.get(name)
            if befehl:
                befehl()

    for widget in (container, bild_label):
        widget.bind("<ButtonPress-1>", maus_runter)
        widget.bind("<B1-Motion>", maus_bewegen)
        widget.bind("<ButtonRelease-1>", maus_los)
        widget.bind(
            "<Button-3>", lambda event, n=name: desktop_kontextmenu(event, n)
        )

    desktop_icons_speichern()


def desktop_symbol_entfernen(name):
    widget = desktop_icon_widgets.pop(name, None)

    if widget is not None:
        widget.destroy()

    desktop_icons.pop(name, None)
    desktop_icons_speichern()


for _name, _info in desktop_icons_datei_laden().items():
    if _name in MENU_BEFEHLE and isinstance(_info, dict):
        try:
            desktop_symbol_erstellen(
                _name,
                _info.get("x"),
                _info.get("y"),
                _info.get("titel"),
                _info.get("bild")
            )
        except Exception:
            pass


def desktop_symbole_periodisch_aktualisieren():
    # Läuft bewusst NICHT im Video-Frame-Takt (das war die Ursache
    # für Ruckler bei Video-Hintergründen), sondern deutlich
    # seltener - reicht locker, damit Symbole/Glas-Effekte nicht
    # sichtbar veralten, ohne die CPU zu belasten. Bei
    # Standbild-Hintergrund gibt es ohnehin nichts, das sich ändern
    # könnte (Panels/Taskleiste aktualisieren sich dann schon beim
    # Öffnen/Verschieben).
    if video_aktiv:
        if not OVERLAY_OFFEN:
            for _symbol_name in list(desktop_icon_widgets.keys()):
                try:
                    desktop_symbol_inhalt_aktualisieren(_symbol_name)
                except Exception:
                    pass

        for _ansicht_name in list(offene_ansichten):
            panel_titelleiste_glas_aktualisieren(_ansicht_name)

        if minimierte_ansichten:
            taskleiste_glas_aktualisieren()

    fenster.after(2000, desktop_symbole_periodisch_aktualisieren)


# --- Eingebettete Webseiten (DeepL / Temp-Mail) -------------------------
#
# Öffnen sich als ganz normales Panel im Programm, mit echtem Browser
# (WebView2) drin - nicht als separates Browserfenster. Der Browser
# wird erst beim ersten Öffnen erzeugt, damit der Programmstart nicht
# durch zwei Chromium-Instanzen verzögert wird. Ist WebView2 aus
# irgendeinem Grund nicht verfügbar, öffnet sich die Seite ersatzweise
# im normalen Browser.

WEB_PANELS = [
    ("deepl_web", "deepl_web_title", "https://www.deepl.com/de/translator"),
    ("tempmail_web", "tempmail_web_title", "https://10minutemail.one/de"),
]

web_panel_inhalte = {}
web_panel_geladen = {}


def _web_panel_bauen(name, titel_schluessel, url):
    inhalt = ansicht_bauen(name, t(titel_schluessel))
    web_panel_inhalte[name] = inhalt
    web_panel_geladen[name] = False

    def bei_anzeigen(n=name, u=url):
        if web_panel_geladen.get(n):
            return

        web_panel_geladen[n] = True

        if not WEBVIEW_OK:
            hinweis = tk.Label(
                web_panel_inhalte[n],
                text=t("webview_missing"),
                font=("Segoe UI", 10),
                bg="#161618",
                fg="#8a8a8f",
                wraplength=700,
                justify="left"
            )
            hinweis.pack(fill="x", padx=20, pady=20)
            webbrowser.open(u)
            return

        try:
            browser = EingebetteterBrowser(
                web_panel_inhalte[n],
                ANSICHT_BREITE, ANSICHT_HOEHE - TITEL_HOEHE,
                url=u
            )
            browser.pack(fill="both", expand=True)

        except Exception as e:
            log(f"Eingebetteter-Browser-Fehler ({n}): {e}")

            hinweis = tk.Label(
                web_panel_inhalte[n],
                text=t("webview_missing"),
                font=("Segoe UI", 10),
                bg="#161618",
                fg="#8a8a8f",
                wraplength=700,
                justify="left"
            )
            hinweis.pack(fill="x", padx=20, pady=20)
            webbrowser.open(u)

    ANSICHT_ON_SHOW[name] = bei_anzeigen


for _web_name, _web_titel_schluessel, _web_url in WEB_PANELS:
    _web_panel_bauen(_web_name, _web_titel_schluessel, _web_url)


menu_buttons = {}

for _schluessel in MENU_REIHENFOLGE:

    def _hover_ein(event, k=_schluessel):
        menu_buttons[k].config(bg=FARBE_HOVER, fg=FARBE_AKZENT)

    def _hover_aus(event, k=_schluessel):
        menu_buttons[k].config(bg=FARBE_OBERFLAECHE, fg=FARBE_TEXT)

    _knopf = tk.Button(
        overlay_frame,
        text=t(_schluessel),
        command=MENU_BEFEHLE[_schluessel],
        **MENU_BUTTON_STYLE
    )

    _knopf.bind("<Enter>", _hover_ein)
    _knopf.bind("<Leave>", _hover_aus)
    _knopf.bind("<MouseWheel>", mausrad_scrollen)
    _knopf.bind(
        "<Button-3>", lambda event, k=_schluessel: desktop_kontextmenu(event, k)
    )

    menu_buttons[_schluessel] = _knopf

buttons = menu_buttons  # Rückwärtskompatibler Name


def hauptbuttons_aktualisieren():

    for schluessel in MENU_REIHENFOLGE:
        menu_buttons[schluessel].config(
            text=t(schluessel)
        )

    toggle_knopf.config(text="✕" if OVERLAY_OFFEN else "☰")


TOGGLE_PHOTO = None
OVERLAY_PHOTO = None


def panel_hintergrund_aktualisieren():
    global TOGGLE_PHOTO, OVERLAY_PHOTO

    try:
        toggle_bild = graustufen_bild(
            TOGGLE_X, TOGGLE_Y, TOGGLE_GROESSE, TOGGLE_GROESSE,
            alpha=0.45
        )

        if TOGGLE_PHOTO is None:
            TOGGLE_PHOTO = ImageTk.PhotoImage(toggle_bild)
            toggle_knopf.config(image=TOGGLE_PHOTO)
        else:
            # .paste() aktualisiert nur die Pixel des bestehenden
            # Bildes, statt laufend neue Tk-Bilder zu erzeugen.
            TOGGLE_PHOTO.paste(toggle_bild)

    except Exception:
        pass

    if OVERLAY_OFFEN and not OVERLAY_ANIMIERT:
        try:
            bild = graustufen_bild(0, 0, BREITE, HOEHE)

            if OVERLAY_PHOTO is None:
                OVERLAY_PHOTO = ImageTk.PhotoImage(bild)
                overlay_hintergrund_label.config(image=OVERLAY_PHOTO)
            else:
                OVERLAY_PHOTO.paste(bild)

        except Exception:
            pass



def animiere(schritte, dauer_gesamt, schritt_fn, fertig_fn=None):
    schritt_dauer = max(1, int(dauer_gesamt / schritte))

    def lauf(i):
        fortschritt = i / schritte
        eased = 1 - (1 - fortschritt) ** 3

        schritt_fn(eased)

        if i < schritte:
            fenster.after(schritt_dauer, lambda: lauf(i + 1))
        elif fertig_fn:
            fertig_fn()

    lauf(0)


def overlay_backdrop_schritt(eased, schliessen=False):
    fortschritt = (1 - eased) if schliessen else eased
    aktuelle_hoehe = max(1, int(HOEHE * fortschritt))

    bild = ImageTk.PhotoImage(
        graustufen_bild(0, 0, BREITE, aktuelle_hoehe)
    )

    overlay_hintergrund_label.config(image=bild)
    overlay_hintergrund_label.image = bild

    overlay_frame.place(
        x=0, y=0,
        width=BREITE, height=aktuelle_hoehe
    )


def menu_knoepfe_einblenden():
    for index, schluessel in enumerate(MENU_REIHENFOLGE):
        zeile = index // OVERLAY_SPALTEN
        spalte = index % OVERLAY_SPALTEN

        ziel_x = OVERLAY_PADDING_SEITE + spalte * (OVERLAY_SPALTENBREITE + OVERLAY_ABSTAND)
        ziel_y = OVERLAY_PADDING_OBEN + zeile * OVERLAY_ZEILEN_HOEHE + SCROLL_OFFSET
        start_y = ziel_y + 34

        knopf = menu_buttons[schluessel]

        knopf.place(
            x=ziel_x,
            y=start_y,
            width=OVERLAY_SPALTENBREITE,
            height=OVERLAY_KNOPF_HOEHE
        )

        def gleiten(k=schluessel, x=ziel_x, y0=start_y, y1=ziel_y):
            def schritt(eased):
                y = int(y0 + (y1 - y0) * eased)
                menu_buttons[k].place(x=x, y=y)

            animiere(10, 200, schritt)

        fenster.after(index * 45, gleiten)


def menu_knoepfe_ausblenden():
    for schluessel in MENU_REIHENFOLGE:
        menu_buttons[schluessel].place_forget()


def menu_oeffnen():
    global OVERLAY_OFFEN, OVERLAY_ANIMIERT

    if OVERLAY_ANIMIERT:
        return

    OVERLAY_OFFEN = True
    OVERLAY_ANIMIERT = True

    hauptbuttons_aktualisieren()

    overlay_frame.lift()

    # Bereits offene Desktop-Fenster bleiben während der ganzen
    # Öffnen-Animation über dem Overlay sichtbar, statt kurz zu
    # verschwinden und erst am Ende wieder aufzutauchen.
    for name in offene_ansichten:
        ansicht_frames[name].lift()

    taskleiste.lift()
    toggle_knopf.lift()

    def fertig():
        global OVERLAY_ANIMIERT, OVERLAY_PHOTO
        OVERLAY_ANIMIERT = False

        bild = graustufen_bild(0, 0, BREITE, HOEHE)
        OVERLAY_PHOTO = ImageTk.PhotoImage(bild)
        overlay_hintergrund_label.config(image=OVERLAY_PHOTO)

        menu_knoepfe_einblenden()

        # Ansichten sind eigene Desktop-Fenster und bleiben unabhängig
        # vom Overlay sichtbar - nur die Stapelreihenfolge muss neu
        # gesetzt werden, damit sie weiterhin über dem Overlay liegen.
        for name in offene_ansichten:
            ansicht_frames[name].lift()

        taskleiste.lift()
        toggle_knopf.lift()

    animiere(16, 260, overlay_backdrop_schritt, fertig)


def menu_schliessen():
    global OVERLAY_OFFEN, OVERLAY_ANIMIERT

    if OVERLAY_ANIMIERT:
        return

    OVERLAY_ANIMIERT = True
    OVERLAY_OFFEN = False

    hauptbuttons_aktualisieren()

    menu_knoepfe_ausblenden()

    # Offene/minimierte Ansichten und die Taskleiste sind eigene
    # Desktop-Fenster - nur das Overlay-Menü selbst wird ausgeblendet.

    def schritt(eased):
        overlay_backdrop_schritt(eased, schliessen=True)

    def fertig():
        global OVERLAY_ANIMIERT
        OVERLAY_ANIMIERT = False
        overlay_frame.place_forget()

    animiere(14, 200, schritt, fertig)


def menu_umschalten():
    if OVERLAY_OFFEN:
        menu_schliessen()
    else:
        menu_oeffnen()


toggle_knopf = tk.Button(
    fenster,
    text="☰",
    command=menu_umschalten,
    font=("Segoe UI", 16, "bold"),
    bg=BUTTON_BG,
    fg="white",
    activebackground="#2c2d31",
    activeforeground="white",
    bd=0,
    relief="flat",
    compound="center",
    cursor="hand2",
    highlightthickness=0
)

toggle_knopf.place(
    x=TOGGLE_X, y=TOGGLE_Y,
    width=TOGGLE_GROESSE, height=TOGGLE_GROESSE
)

toggle_knopf.lift()


# ============================================================
# FENSTER VERSTECKEN/ZEIGEN (rechte Umschalttaste)
# ============================================================

def fenster_sichtbarkeit_umschalten():
    def tun():
        try:
            if fenster.state() == "iconic":
                fenster.deiconify()
                fenster.lift()
            else:
                fenster.iconify()
        except Exception:
            pass

    fenster.after(0, tun)


if keyboard is not None:
    try:
        keyboard.add_hotkey(
            "right shift",
            fenster_sichtbarkeit_umschalten
        )
    except Exception as e:
        log(f"Fenster-Hotkey-Fehler: {e}")


# ============================================================
# START
# ============================================================

def programm_beenden():
    try:
        _eni_konsole_schliessen()
    except Exception:
        pass

    try:
        notizen_text_sichern()
        notizen_speichern()
    except Exception:
        pass

    fenster.destroy()


fenster.protocol("WM_DELETE_WINDOW", programm_beenden)

hauptbuttons_aktualisieren()

log("ENI SERVICE gestartet.")

gespeicherten_hintergrund_laden()

desktop_symbole_periodisch_aktualisieren()

fenster.mainloop()