import re
import subprocess
from gi.repository import Gtk, Adw
from src.lang import LANGUAGE, t
from src.app_prefs import LANGUAGE_CHOICES, get_language_preference, set_language_preference

# Gängige Tastaturlayouts: (xkb-Code, Anzeigename)
KEYBOARD_LAYOUTS = [
    ("ad",  "Andorran"),
    ("af",  "Afghan"),
    ("al",  "Albanian"),
    ("am",  "Armenian"),
    ("ara",  "Arabic"),
    ("at",  "Austrian (AT)"),
    ("au",  "Australian"),
    ("az",  "Azerbaijani"),
    ("ba",  "Bosnian"),
    ("bd",  "Bengali"),
    ("be",  "Belgian"),
    ("bg",  "Bulgarian"),
    ("br",  "Brazilian"),
    ("brai",  "Braille"),
    ("bt",  "Bhutanese"),
    ("bw",  "Botswanan"),
    ("by",  "Belarusian"),
    ("ca",  "Canadian"),
    ("cd",  "Congolese (DR)"),
    ("ch",  "Swiss"),
    ("cm",  "Cameroonian"),
    ("cn",  "Chinese"),
    ("cz",  "Czech"),
    ("de",  "German (DE)"),
    ("dk",  "Danish"),
    ("ee",  "Estonian"),
    ("epo",  "Esperanto"),
    ("es",  "Spanish"),
    ("et",  "Ethiopian"),
    ("eu",  "Basque"),
    ("fi",  "Finnish"),
    ("fo",  "Faroese"),
    ("fr",  "French"),
    ("gb",  "English (UK)"),
    ("ge",  "Georgian"),
    ("gh",  "Ghanaian"),
    ("gn",  "Guinean"),
    ("gr",  "Greek"),
    ("hr",  "Croatian"),
    ("hu",  "Hungarian"),
    ("ie",  "Irish"),
    ("il",  "Hebrew"),
    ("in",  "Indian"),
    ("iq",  "Iraqi"),
    ("ir",  "Persian"),
    ("is",  "Icelandic"),
    ("it",  "Italian"),
    ("jp",  "Japanese"),
    ("ke",  "Kenyan"),
    ("kg",  "Kyrgyz"),
    ("kh",  "Khmer"),
    ("kr",  "Korean"),
    ("kz",  "Kazakh"),
    ("la",  "Lao"),
    ("latam",  "Latin American"),
    ("lk",  "Sinhala"),
    ("lt",  "Lithuanian"),
    ("lv",  "Latvian"),
    ("ma",  "Moroccan"),
    ("mao",  "Maori"),
    ("md",  "Moldavian"),
    ("me",  "Montenegrin"),
    ("mk",  "Macedonian"),
    ("ml",  "Malian"),
    ("mm",  "Burmese"),
    ("mn",  "Mongolian"),
    ("mt",  "Maltese"),
    ("mv",  "Maldivian"),
    ("my",  "Malaysian"),
    ("ng",  "Nigerian"),
    ("nl",  "Dutch"),
    ("no",  "Norwegian"),
    ("np",  "Nepali"),
    ("ph",  "Filipino"),
    ("pk",  "Pakistani"),
    ("pl",  "Polish"),
    ("pt",  "Portuguese"),
    ("ro",  "Romanian"),
    ("rs",  "Serbian"),
    ("ru",  "Russian"),
    ("se",  "Swedish"),
    ("si",  "Slovenian"),
    ("sk",  "Slovak"),
    ("sn",  "Senegalese"),
    ("sy",  "Syrian"),
    ("tg",  "Togolese"),
    ("th",  "Thai"),
    ("tj",  "Tajik"),
    ("tm",  "Turkmen"),
    ("tr",  "Turkish"),
    ("tw",  "Taiwanese"),
    ("tz",  "Tanzanian"),
    ("ua",  "Ukrainian"),
    ("us",  "English (US)"),
    ("uz",  "Uzbek"),
    ("vn",  "Vietnamese"),
    ("za",  "South African"),
]

KEYBOARD_LAYOUTS_ES = {
    "Andorran": "Andorrano",
    "Afghan": "Afgano",
    "Albanian": "Albanés",
    "Armenian": "Armenio",
    "Arabic": "Árabe",
    "Austrian (AT)": "Austriaco (AT)",
    "Australian": "Australiano",
    "Azerbaijani": "Azerbaiyano",
    "Bosnian": "Bosnio",
    "Bengali": "Bengalí",
    "Belgian": "Belga",
    "Bulgarian": "Búlgaro",
    "Brazilian": "Brasileño",
    "Braille": "Braille",
    "Bhutanese": "Butanés",
    "Botswanan": "Botsuano",
    "Belarusian": "Bielorruso",
    "Canadian": "Canadiense",
    "Congolese (DR)": "Congoleño (RD)",
    "Swiss": "Suizo",
    "Cameroonian": "Camerunés",
    "Chinese": "Chino",
    "Czech": "Checo",
    "German (DE)": "Alemán (DE)",
    "Danish": "Danés",
    "Estonian": "Estonio",
    "Esperanto": "Esperanto",
    "Spanish": "Español",
    "Ethiopian": "Etíope",
    "Basque": "Vasco",
    "Finnish": "Finlandés",
    "Faroese": "Feroés",
    "French": "Francés",
    "English (UK)": "Inglés (UK)",
    "Georgian": "Georgiano",
    "Ghanaian": "Ghanés",
    "Guinean": "Guineano",
    "Greek": "Griego",
    "Croatian": "Croata",
    "Hungarian": "Húngaro",
    "Irish": "Irlandés",
    "Hebrew": "Hebreo",
    "Indian": "Indio",
    "Iraqi": "Iraquí",
    "Persian": "Persa",
    "Icelandic": "Islandés",
    "Italian": "Italiano",
    "Japanese": "Japonés",
    "Kenyan": "Keniano",
    "Kyrgyz": "Kirguís",
    "Khmer": "Jemer",
    "Korean": "Coreano",
    "Kazakh": "Kazajo",
    "Lao": "Laosiano",
    "Latin American": "Latinoamericano",
    "Sinhala": "Cingalés",
    "Lithuanian": "Lituano",
    "Latvian": "Letón",
    "Moroccan": "Marroquí",
    "Maori": "Maorí",
    "Moldavian": "Moldavo",
    "Montenegrin": "Montenegrino",
    "Macedonian": "Macedonio",
    "Malian": "Maliense",
    "Burmese": "Birmano",
    "Mongolian": "Mongol",
    "Maltese": "Maltés",
    "Maldivian": "Maldivo",
    "Malaysian": "Malasio",
    "Nigerian": "Nigeriano",
    "Dutch": "Neerlandés",
    "Norwegian": "Noruego",
    "Nepali": "Nepalí",
    "Filipino": "Filipino",
    "Pakistani": "Pakistaní",
    "Polish": "Polaco",
    "Portuguese": "Portugués",
    "Romanian": "Rumano",
    "Serbian": "Serbio",
    "Russian": "Ruso",
    "Swedish": "Sueco",
    "Slovenian": "Esloveno",
    "Slovak": "Eslovaco",
    "Senegalese": "Senegalés",
    "Syrian": "Sirio",
    "Togolese": "Togolés",
    "Thai": "Tailandés",
    "Tajik": "Tayiko",
    "Turkmen": "Turcomano",
    "Turkish": "Turco",
    "Taiwanese": "Taiwanés",
    "Tanzanian": "Tanzano",
    "Ukrainian": "Ucraniano",
    "English (US)": "Inglés (US)",
    "Uzbek": "Uzbeko",
    "Vietnamese": "Vietnamita",
    "South African": "Sudafricano",
}

KEYBOARD_LAYOUTS_DE = {
    "Andorran": "Andorranisch",
    "Afghan": "Afghanisch",
    "Albanian": "Albanisch",
    "Armenian": "Armenisch",
    "Arabic": "Arabisch",
    "Austrian (AT)": "Österreichisch (AT)",
    "Australian": "Australisch",
    "Azerbaijani": "Aserbaidschanisch",
    "Bosnian": "Bosnisch",
    "Bengali": "Bengalisch",
    "Belgian": "Belgisch",
    "Bulgarian": "Bulgarisch",
    "Brazilian": "Brasilianisch",
    "Braille": "Braille",
    "Bhutanese": "Bhutanisch",
    "Botswanan": "Botswanisch",
    "Belarusian": "Weißrussisch",
    "Canadian": "Kanadisch",
    "Congolese (DR)": "Kongolesisch (DR)",
    "Swiss": "Schweizer",
    "Cameroonian": "Kamerunisch",
    "Chinese": "Chinesisch",
    "Czech": "Tschechisch",
    "German (DE)": "Deutsch (DE)",
    "Danish": "Dänisch",
    "Estonian": "Estnisch",
    "Esperanto": "Esperanto",
    "Spanish": "Spanisch",
    "Ethiopian": "Äthiopisch",
    "Basque": "Baskisch",
    "Finnish": "Finnisch",
    "Faroese": "Färöisch",
    "French": "Französisch",
    "English (UK)": "Englisch (UK)",
    "Georgian": "Georgisch",
    "Ghanaian": "Ghanaisch",
    "Guinean": "Guineisch",
    "Greek": "Griechisch",
    "Croatian": "Kroatisch",
    "Hungarian": "Ungarisch",
    "Irish": "Irisch",
    "Hebrew": "Hebräisch",
    "Indian": "Indisch",
    "Iraqi": "Irakisch",
    "Persian": "Persisch",
    "Icelandic": "Isländisch",
    "Italian": "Italienisch",
    "Japanese": "Japanisch",
    "Kenyan": "Kenianisch",
    "Kyrgyz": "Kirgisisch",
    "Khmer": "Khmerisch",
    "Korean": "Koreanisch",
    "Kazakh": "Kasachisch",
    "Lao": "Laotisch",
    "Latin American": "Lateinamerikanisch",
    "Sinhala": "Singhalesisch",
    "Lithuanian": "Litauisch",
    "Latvian": "Lettisch",
    "Moroccan": "Marokkanisch",
    "Maori": "Maori",
    "Moldavian": "Moldauisch",
    "Montenegrin": "Montenegrinisch",
    "Macedonian": "Mazedonisch",
    "Malian": "Malisch",
    "Burmese": "Myanmarisch",
    "Mongolian": "Mongolisch",
    "Maltese": "Maltesisch",
    "Maldivian": "Maledivisch",
    "Malaysian": "Malaysisch",
    "Nigerian": "Nigerianisch",
    "Dutch": "Niederländisch",
    "Norwegian": "Norwegisch",
    "Nepali": "Nepalesisch",
    "Filipino": "Philippinisch",
    "Pakistani": "Pakistanisch",
    "Polish": "Polnisch",
    "Portuguese": "Portugiesisch",
    "Romanian": "Rumänisch",
    "Serbian": "Serbisch",
    "Russian": "Russisch",
    "Swedish": "Schwedisch",
    "Slovenian": "Slowenisch",
    "Slovak": "Slowakisch",
    "Senegalese": "Senegalesisch",
    "Syrian": "Syrisch",
    "Togolese": "Togoisch",
    "Thai": "Thaiisch",
    "Tajik": "Tadschikisch",
    "Turkmen": "Turkmenisch",
    "Turkish": "Türkisch",
    "Taiwanese": "Taiwanisch",
    "Tanzanian": "Tansanisch",
    "Ukrainian": "Ukrainisch",
    "English (US)": "Englisch (US)",
    "Uzbek": "Usbekisch",
    "Vietnamese": "Vietnamesisch",
    "South African": "Südafrikanisch",
}


def _layout_label(label: str) -> str:
    if LANGUAGE == "es_MX":
        return KEYBOARD_LAYOUTS_ES.get(label, label)
    if LANGUAGE == "de":
        return KEYBOARD_LAYOUTS_DE.get(label, label)
    return label


def read_input_conf() -> dict:
    """Liest Tastatur/Input-Einstellungen (unterstützt Lua-Modus via hyprctl/hypr-user.lua und input.conf)."""
    import json
    from src.config import is_lua_mode, CAELESTIA_HYPR_USER, HYPR_INPUT_CONF

    result = {}

    # 1. Versuche aktuelle Optionen direkt von hyprctl abzufragen (zuverlässig in Lua und Conf)
    try:
        res_kb = subprocess.run(
            ["hyprctl", "getoption", "input:kb_layout", "-j"],
            capture_output=True, text=True, timeout=2
        )
        if res_kb.returncode == 0:
            data = json.loads(res_kb.stdout)
            str_val = data.get("str", "").strip()
            if str_val:
                result["kb_layout"] = str_val
    except Exception:
        pass

    try:
        res_num = subprocess.run(
            ["hyprctl", "getoption", "input:numlock_by_default", "-j"],
            capture_output=True, text=True, timeout=2
        )
        if res_num.returncode == 0:
            data = json.loads(res_num.stdout)
            result["numlock_by_default"] = "true" if data.get("int") == 1 else "false"
    except Exception:
        pass

    # 2. Falls aus hypr-user.lua überschrieben
    if is_lua_mode() and CAELESTIA_HYPR_USER.exists():
        try:
            content = CAELESTIA_HYPR_USER.read_text()
            kb_m = re.search(r'kb_layout\s*=\s*["\']([^"\']+)["\']', content)
            if kb_m:
                result["kb_layout"] = kb_m.group(1)
            num_m = re.search(r'numlock_by_default\s*=\s*(true|false)', content, re.IGNORECASE)
            if num_m:
                result["numlock_by_default"] = num_m.group(1).lower()
        except Exception as e:
            print(f"hypr-user.lua lesen: {e}")

    # 3. Fallback: input.conf
    if HYPR_INPUT_CONF.exists() and ("kb_layout" not in result or "numlock_by_default" not in result):
        try:
            content = HYPR_INPUT_CONF.read_text()
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "{" in line or "}" in line:
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() not in result:
                        result[k.strip()] = v.strip()
        except Exception as e:
            print(f"input.conf lesen fehler: {e}")

    return result


def _write_input_conf_key(key: str, value: str):
    """Speichert input-Einstellungen in hypr-user.lua (Lua-Modus) oder input.conf."""
    from src.config import is_lua_mode, ensure_hypr_user_lua, CAELESTIA_HYPR_USER, HYPR_INPUT_CONF

    if is_lua_mode():
        ensure_hypr_user_lua()
        content = CAELESTIA_HYPR_USER.read_text() if CAELESTIA_HYPR_USER.exists() else ""
        # Suche nach einem vorhandenen hl.config({ input = { ... } }) Block
        block_pattern = r"hl\.config\s*\(\s*\{\s*input\s*=\s*\{([^}]*)\}\s*\}\s*\)"
        m = re.search(block_pattern, content)
        if m:
            inner = m.group(1)
            key_pattern = rf"({re.escape(key)}\s*=\s*)[^,\n]+"
            val_repr = f'"{value}"' if key == "kb_layout" else str(value).lower()
            if re.search(key_pattern, inner):
                new_inner = re.sub(key_pattern, rf"\g<1>{val_repr}", inner)
            else:
                # Ein bereits vorhandenes abschließendes Komma entfernen, sonst
                # entsteht ",," und Hyprland meldet "unexpected symbol near ','".
                stripped = inner.strip().rstrip(",")
                sep = ",\n        " if stripped else ""
                new_inner = f"{stripped}{sep}{key} = {val_repr}"
            new_content = content[:m.start(1)] + "\n        " + new_inner.strip() + "\n    " + content[m.end(1):]
        else:
            val_repr = f'"{value}"' if key == "kb_layout" else str(value).lower()
            new_block = (
                f"\n-- Input Configuration\n"
                f"hl.config({{\n"
                f"    input = {{\n"
                f"        {key} = {val_repr},\n"
                f"    }}\n"
                f"}})\n"
            )
            new_content = content + new_block
        from src.safe_io import atomic_write_text

        atomic_write_text(CAELESTIA_HYPR_USER, new_content)
        return

    if not HYPR_INPUT_CONF.exists():
        return
    try:
        content = HYPR_INPUT_CONF.read_text()
        pattern = rf"^(\s*{re.escape(key)}\s*=\s*).*"
        new_line = rf"\g<1>{value}"
        new_content, n = re.subn(pattern, new_line, content, flags=re.MULTILINE)
        if n == 0:
            new_content = re.sub(
                r"(input\s*\{[^}]*)",
                rf"\1    {key} = {value}\n",
                content,
                count=1,
                flags=re.DOTALL,
            )
        from src.safe_io import atomic_write_text

        atomic_write_text(HYPR_INPUT_CONF, new_content)
    except Exception as e:
        print(f"input.conf schreiben fehler: {e}")


class GeneralPage(Gtk.Box):
    def __init__(self, main_window, **kwargs):
        super().__init__(**kwargs)
        self.main_window = main_window
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self.is_loading = False

        # ── EINGABE ──────────────────────────────────────────────────────
        input_group = Adw.PreferencesGroup(title=t("Input"))
        self.append(input_group)

        # Tastaturlayout-Dropdown
        layout_row = Adw.ActionRow(title=t("Keyboard Layout"))
        layout_row.set_subtitle(t("Live change in Hyprland"))

        self.layout_combo = Gtk.ComboBoxText()
        self.layout_combo.set_valign(Gtk.Align.CENTER)

        # Suchfunktion via Gtk.ComboBox hat keinen eingebauten Filter —
        # wir nutzen ein Entry-Completion-ähnliches Dropdown
        for code, label in KEYBOARD_LAYOUTS:
            self.layout_combo.append(code, f"{_layout_label(label)}  ({code})")

        layout_row.add_suffix(self.layout_combo)
        input_group.add(layout_row)

        # NumLock
        self.numlock_row = Adw.SwitchRow(
            title=t("NumLock on startup"),
            subtitle="numlock_by_default in input.conf"
        )
        input_group.add(self.numlock_row)

        # ── REGION & SPRACHE ─────────────────────────────────────────────
        system_group = Adw.PreferencesGroup(title=t("Region and Language"))
        self.append(system_group)

        self.app_lang_row = Adw.ActionRow(title=t("Caelestia-settings language"))
        self.app_lang_row.set_subtitle(t("Language of this application (restart required)"))
        self.app_lang_combo = Gtk.ComboBoxText()
        self.app_lang_combo.set_valign(Gtk.Align.CENTER)
        for code, label in LANGUAGE_CHOICES:
            self.app_lang_combo.append(code, t(label) if code == "auto" else label)
        self.app_lang_row.add_suffix(self.app_lang_combo)
        system_group.add(self.app_lang_row)

        self.ntp_row = Adw.SwitchRow(
            title=t("Automatic time synchronisation"),
            subtitle="timedatectl set-ntp",
        )
        self.ntp_row.connect("notify::active", self._on_ntp_changed)
        system_group.add(self.ntp_row)

        lang_row = Adw.ActionRow(title=t("System Language"))
        lang_row.set_subtitle(t("Requires password"))
        self.lang_combo = Gtk.ComboBoxText()
        locales: list[str] = []
        try:
            locales = subprocess.run(
                ["localectl", "list-locales"], capture_output=True, text=True, timeout=3
            ).stdout.splitlines()
            for locale_name in locales:
                if locale_name.strip():
                    self.lang_combo.append(locale_name.strip(), locale_name.strip())
        except Exception as e:
            print(f"Err locales: {e}")
        if not locales:
            self.lang_combo.append("de_DE.UTF-8", "Deutsch (Deutschland)")
            self.lang_combo.append("en_US.UTF-8", "English (US)")
            self.lang_combo.append("en_GB.UTF-8", "English (UK)")
        lang_row.add_suffix(self.lang_combo)
        system_group.add(lang_row)

        time_row = Adw.ActionRow(title=t("Timezone"))
        self.time_combo = Gtk.ComboBoxText()
        zones: list[str] = []
        try:
            zones = subprocess.run(
                ["timedatectl", "list-timezones"], capture_output=True, text=True, timeout=3
            ).stdout.splitlines()
            for zone in zones:
                if zone.strip():
                    self.time_combo.append(zone.strip(), zone.strip())
        except Exception as e:
            print(f"Err timezones: {e}")
        if not zones:
            self.time_combo.append("Europe/Berlin", "Berlin (CET/CEST)")
            self.time_combo.append("Europe/London", "London (GMT/BST)")
            self.time_combo.append("America/New_York", "New York (EST/EDT)")
            self.time_combo.append("UTC", "UTC")
        time_row.add_suffix(self.time_combo)
        system_group.add(time_row)

        # Laden & Signale
        self._load_all()
        self.layout_combo.connect("changed",        self._on_layout_changed)
        self.numlock_row.connect("notify::active",  self._on_numlock_changed)
        self.app_lang_combo.connect("changed",      self._on_app_language_changed)
        self.lang_combo.connect("changed",          self._on_language_changed)
        self.time_combo.connect("changed",          self._on_timezone_changed)

    def _on_app_language_changed(self, combo):
        if self.is_loading:
            return
        code = combo.get_active_id()
        if code:
            set_language_preference(code)
            self.main_window.add_toast(
                Adw.Toast.new(t("Restart Caelestia Settings to apply the new language."))
            )

    # ── Laden ─────────────────────────────────────────────────────────────

    def _load_all(self):
        self.is_loading = True

        self.app_lang_combo.set_active_id(get_language_preference())

        conf = read_input_conf()

        # Tastaturlayout
        layout = conf.get("kb_layout", "us").lower()
        if not self.layout_combo.set_active_id(layout):
            # Multiple layouts arrive as "latam,us": show friendly names but
            # keep the combined id so changing it round-trips correctly.
            labels_by_code = dict(KEYBOARD_LAYOUTS)
            parts = [part.strip() for part in layout.split(",") if part.strip()]
            if parts and all(part in labels_by_code for part in parts):
                names = ", ".join(_layout_label(labels_by_code[part]) for part in parts)
                self.layout_combo.append(layout, f"{names}  ({layout})")
            else:
                self.layout_combo.append(
                    layout, t("Unknown  ({code})").format(code=layout)
                )
            self.layout_combo.set_active_id(layout)

        # NumLock
        numlock_val = conf.get("numlock_by_default", "false").lower()
        self.numlock_row.set_active(numlock_val == "true")

        # Systemsprache
        try:
            res = subprocess.run(["localectl", "status"], capture_output=True, text=True)
            for line in res.stdout.splitlines():
                if "LANG=" in line:
                    lang = line.split("LANG=")[1].strip()
                    if not self.lang_combo.set_active_id(lang):
                        self.lang_combo.append(lang, f"{t('Current')}: {lang}")
                        self.lang_combo.set_active_id(lang)
        except Exception as e:
            print(f"Err Lang: {e}")

        # NTP
        try:
            res = subprocess.run(
                ["timedatectl", "show", "-p", "NTP", "--value"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            self.ntp_row.set_active(res.stdout.strip().lower() in ("yes", "true", "1"))
        except Exception as e:
            print(f"Err NTP: {e}")

        # Zeitzone
        try:
            res = subprocess.run(
                ["timedatectl", "show", "-p", "Timezone", "--value"],
                capture_output=True, text=True
            )
            tz = res.stdout.strip()
            if not self.time_combo.set_active_id(tz):
                self.time_combo.append(tz, f"{t('Current')}: {tz}")
                self.time_combo.set_active_id(tz)
        except Exception as e:
            print(f"Err Time: {e}")

        self.is_loading = False

    # ── Callbacks ─────────────────────────────────────────────────────────

    def show_toast(self, message):
        toast = Adw.Toast.new(message)
        if hasattr(self.main_window, "add_toast"):
            self.main_window.add_toast(toast)

    def _on_layout_changed(self, combo):
        if self.is_loading: return
        lang = combo.get_active_id()
        if not lang: return
        from src.config import is_lua_mode, hyprctl_eval
        try:
            if is_lua_mode():
                hyprctl_eval(f'hl.config({{ input = {{ kb_layout = "{lang}" }} }})')
            else:
                subprocess.run(["hyprctl", "keyword", "input:kb_layout", lang], check=True)
            _write_input_conf_key("kb_layout", lang)
            self.show_toast(t("Keyboard layout: {layout}").format(layout=lang.upper()))
        except Exception as e:
            self.show_toast(t("Error: {error}").format(error=e))

    def _on_numlock_changed(self, row, _):
        if self.is_loading: return
        val = "true" if row.get_active() else "false"
        from src.config import is_lua_mode, hyprctl_eval
        try:
            if is_lua_mode():
                hyprctl_eval(f'hl.config({{ input = {{ numlock_by_default = {val} }} }})')
            else:
                subprocess.run(["hyprctl", "keyword", "input:numlock_by_default", val], check=True)
            _write_input_conf_key("numlock_by_default", val)
            self.show_toast(t("NumLock: {value}").format(value=val))
        except Exception as e:
            self.show_toast(t("Error: {error}").format(error=e))

    def _on_language_changed(self, combo):
        if self.is_loading: return
        lang = combo.get_active_id()
        if not lang: return
        try:
            subprocess.run(["pkexec", "localectl", "set-locale", f"LANG={lang}"], check=True)
            self.show_toast(t("Language set successfully (reboot needed)."))
        except subprocess.CalledProcessError:
            self.show_toast(t("Language change cancelled."))
            self._load_all()
        except Exception as e:
            self.show_toast(t("Error: {error}").format(error=e))
            self._load_all()

    def _on_ntp_changed(self, row, _):
        if self.is_loading: return
        value = "true" if row.get_active() else "false"
        try:
            subprocess.run(["pkexec", "timedatectl", "set-ntp", value], check=True, timeout=20)
            self.show_toast(t("Automatic time synchronisation updated."))
        except subprocess.CalledProcessError:
            self.show_toast(t("Time synchronisation change cancelled."))
            self._load_all()
        except Exception as e:
            self.show_toast(t("Error: {error}").format(error=e))
            self._load_all()

    def _on_timezone_changed(self, combo):
        if self.is_loading: return
        tz = combo.get_active_id()
        if not tz: return
        try:
            subprocess.run(["pkexec", "timedatectl", "set-timezone", tz], check=True)
            self.show_toast(t("Timezone set successfully."))
        except subprocess.CalledProcessError:
            self.show_toast(t("Timezone change cancelled."))
            self._load_all()
        except Exception as e:
            self.show_toast(t("Error: {error}").format(error=e))
            self._load_all()