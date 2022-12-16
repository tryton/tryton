# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"""
%prog [options]
"""
import sys
try:
    import cdecimal
    # Use cdecimal globally
    if 'decimal' not in sys.modules:
        sys.modules['decimal'] = cdecimal
except ImportError:
    import decimal
    sys.modules['cdecimal'] = decimal
import os

if os.environ.get('GTK_VERSION', '2').startswith('3'):
    import pygtkcompat
    pygtkcompat.enable()
    pygtkcompat.enable_gtk(version='3.0')
    try:
        pygtkcompat.enable_goocanvas()
    except ValueError:
        pass

    from gi.repository import GdkPixbuf
    _unset = object()

    Gdk = sys.modules['gtk.gdk']
    # XXX this prevents isinstance test
    Gdk.PixbufLoader = GdkPixbuf.PixbufLoader.new

    Gtk = sys.modules['gtk']
    Gtk.widget_set_default_direction = Gtk.Widget.set_default_direction
    Gtk.accel_map_add_entry = Gtk.AccelMap.add_entry
    Gtk.accel_map_load = Gtk.AccelMap.load
    Gtk.accel_map_save = Gtk.AccelMap.save

    Gtk.PROGRESS_LEFT_TO_RIGHT = (Gtk.Orientation.HORIZONTAL, False)
    Gtk.PROGRESS_RIGHT_TO_LEFT = (Gtk.Orientation.HORIZONTAL, True)
    Gtk.PROGRESS_BOTTOM_TO_TOP = (Gtk.Orientation.VERTICAL, True)
    Gtk.PROGRESS_TOP_TO_BOTTOM = (Gtk.Orientation.VERTICAL, False)

    Gtk.CLIPBOARD_PRIMARY = Gdk.Atom.intern('PRIMARY', True)
    Gtk.CLIPBOARD_CLIPBOARD = Gdk.Atom.intern('CLIPBOARD', True)

    orig_tree_view_column_set_cell_data_func = (
        Gtk.TreeViewColumn.set_cell_data_func)

    def set_cell_data_func(self, cell, func, user_data=_unset):
        def callback(*args):
            if args[-1] == _unset:
                args = args[:-1]
            return func(*args)
        orig_tree_view_column_set_cell_data_func(
            self, cell, callback, user_data)
    Gtk.TreeViewColumn.set_cell_data_func = set_cell_data_func

    Gtk.TreeViewColumn.get_cell_renderers = Gtk.TreeViewColumn.get_cells

    orig_set_orientation = Gtk.ProgressBar.set_orientation

    def set_orientation(self, orientation):
        orientation, inverted = orientation
        orig_set_orientation(self, orientation)
        self.set_inverted(inverted)
    Gtk.ProgressBar.set_orientation = set_orientation

    orig_set_orientation = Gtk.CellRendererProgress.set_orientation

    def set_orientation(self, orientation):
        orientation, inverted = orientation
        orig_set_orientation(self, orientation)
        self.set_property('inverted', inverted)
    Gtk.CellRendererProgress.set_orientation = set_orientation

    orig_popup = Gtk.Menu.popup

    def popup(self, parent_menu_shell, parent_menu_item, func, button,
            activate_time, data=None):
        if func:
            def position_func(menu, x, y, user_data=None):
                return func(menu, user_data)
        else:
            position_func = None
        orig_popup(self, parent_menu_shell, parent_menu_item,
            position_func, data, button, activate_time)
    Gtk.Menu.popup = popup

    def get_active_text(self):
        active = self.get_active()
        if active < 0:
            return None
        else:
            model = self.get_model()
            index = self.get_property('entry-text-column')
            return model[active][index]
    Gtk.ComboBox.get_active_text = get_active_text

    Gtk.GenericCellRenderer.__gobject_init__ = Gtk.GenericCellRenderer.__init__

    from gi.repository import Pango
    Pango.SCALE_XX_SMALL = 1 / (1.2 * 1.2 * 1.2)
    Pango.SCALE_X_SMALL = 1 / (1.2 * 1.2)
    Pango.SCALE_SMALL = 1 / 1.2
    Pango.SCALE_MEDIUM = 1
    Pango.SCALE_LARGE = 1.2
    Pango.SCALE_X_LARGE = 1.2 * 1.2
    Pango.SCALE_XX_LARGE = 1.2 * 1.2 * 1.2
else:
    import pygtk
    pygtk.require('2.0')
import gtk

if not hasattr(gtk, 'TreePath'):
    gtk.TreePath = tuple
if not hasattr(gtk, 'TargetEntry'):
    gtk.TargetEntry = lambda *a: a
    gtk.TargetEntry.new = lambda *a: a
if not hasattr(gtk, 'CLIPBOARD_PRIMARY'):
    gtk.CLIPBOARD_PRIMARY = 'PRIMARY'
    gtk.CLIPBOARD_CLIPBOARD = 'CLIPBOARD'

import gobject
try:
    # Import earlier otherwise there is a segmentation fault on MSYS2
    import goocalendar
except ImportError:
    pass
gobject.threads_init()
from urlparse import urlparse
import threading

import tryton.common as common
from tryton.config import CONFIG, get_config_dir
from tryton import translate
from tryton import gui
from tryton.ipc import Client as IPCClient
import time
import signal

if not hasattr(gtk.gdk, 'lock'):
    class _Lock(object):
        __enter__ = gtk.gdk.threads_enter

        def __exit__(*ignored):
            gtk.gdk.threads_leave()

    gtk.gdk.lock = _Lock()

if sys.platform == 'win32':
    class Dialog(gtk.Dialog):

        def run(self):
            with gtk.gdk.lock:
                return super(Dialog, self).run()
    gtk.Dialog = Dialog


class TrytonClient(object):
    "Tryton client"

    def __init__(self):
        CONFIG.parse()
        if CONFIG.arguments:
            url, = CONFIG.arguments
            urlp = urlparse(url)
            if urlp.scheme == 'tryton':
                urlp = urlparse('http' + url[6:])
                hostname, port = (urlp.netloc.split(':', 1)
                        + [CONFIG.defaults['login.port']])[:2]
                database, _ = (urlp.path[1:].split('/', 1) + [None])[:2]
                if IPCClient(hostname, port, database).write(url):
                    sys.exit(0)
                CONFIG['login.server'] = hostname
                CONFIG['login.port'] = port
                CONFIG['login.db'] = database
                CONFIG['login.expanded'] = True
        translate.set_language_direction(CONFIG['client.language_direction'])
        translate.setlang(CONFIG['client.lang'])
        self.quit_client = (threading.Event()
            if sys.platform == 'win32' else None)
        common.ICONFACTORY.load_client_icons()

    def quit_mainloop(self):
        if sys.platform == 'win32':
            self.quit_client.set()
        else:
            if gtk.main_level() > 0:
                gtk.main_quit()

    def run(self):
        main = gui.Main(self)

        signal.signal(signal.SIGINT, lambda signum, frame: main.sig_quit())
        signal.signal(signal.SIGTERM, lambda signum, frame: main.sig_quit())
        if hasattr(signal, 'SIGQUIT'):
            signal.signal(signal.SIGQUIT,
                lambda signum, frame: main.sig_quit())

        def excepthook(*args):
            import common
            import traceback
            detail = ''.join(traceback.format_exception(*args))
            common.error(str(args[1]), detail)

        sys.excepthook = excepthook

        main.sig_login()

        if sys.platform == 'win32':
            # http://faq.pygtk.org/index.py?req=show&file=faq21.003.htp
            def sleeper():
                time.sleep(.001)
                return 1
            gobject.timeout_add(400, sleeper)

        try:
            if sys.platform == 'win32':
                while not self.quit_client.isSet():
                    with gtk.gdk.lock:
                            gtk.main_iteration()
            else:
                gtk.main()
        except KeyboardInterrupt:
            CONFIG.save()
            gtk.accel_map_save(os.path.join(get_config_dir(), 'accel.map'))

if __name__ == "__main__":
    CLIENT = TrytonClient()
    CLIENT.run()
