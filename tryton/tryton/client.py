# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import hashlib
import os
import sys
import traceback
from urllib.parse import urlparse

from gi.repository import Gdk, Gtk, Gio

from tryton import common
from tryton import gui
from tryton import translate
from tryton.config import CONFIG, get_config_dir
from tryton.gui.window.dblogin import DBLogin


def main():
    CSS = b"""
    .readonly entry, .readonly text {
        background-color: @insensitive_bg_color;
    }
    .required entry, entry.required, .required text, text.required {
        border-color: darker(@unfocused_borders);
    }
    .invalid entry, entry.invalid, .invalid text, text.invalid {
        border-color: @error_color;
    }
    label.required {
        font-weight: bold;
    }
    label.editable {
        font-style: italic;
    }
    .window-title, .wizard-title {
        font-size: large;
        font-weight: bold;
    }
    .window-title .status {
        font-size: medium;
        font-weight: normal;
    }
    """

    screen = Gdk.Screen.get_default()
    style_context = Gtk.StyleContext()
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    style_context.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    theme_path = os.path.join(get_config_dir(), 'theme.css')
    if os.path.exists(theme_path):
        provider = Gtk.CssProvider()
        provider.load_from_path(theme_path)
        style_context.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def excepthook(type_, value, traceback_):
        common.error(value, ''.join(traceback.format_tb(traceback_)))
    sys.excepthook = excepthook

    CONFIG.parse()
    if CONFIG.arguments:
        url = CONFIG.arguments[0]
        urlp = urlparse(url)
        if urlp.scheme == 'tryton':
            urlp = urlparse('http' + url[6:])
            database, _ = (urlp.path[1:].split('/', 1) + [None])[:2]
            CONFIG['login.host'] = urlp.netloc
            CONFIG['login.db'] = database
            CONFIG['login.expanded'] = True
        else:
            CONFIG.arguments = []
    translate.set_language_direction(CONFIG['client.language_direction'])
    translate.setlang(CONFIG['client.lang'])
    if CONFIG.arguments or DBLogin().run():
        server = '%(hostname)s:%(port)s/%(database)s' % {
            'hostname': common.get_hostname(CONFIG['login.host']),
            'port': common.get_port(CONFIG['login.host']),
            'database': CONFIG['login.db'],
            }
        server = hashlib.md5(server.encode('utf-8')).hexdigest()
        application_id = 'org.tryton._' + server
        app = gui.Main(
            application_id=application_id,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        app.run([sys.argv[0]] + CONFIG.arguments)


if __name__ == "__main__":
    main()
