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
import pygtk
pygtk.require('2.0')
import gtk
import gobject
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

        if CONFIG['tip.autostart']:
            main.sig_tips()
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
                            gtk.main_iteration(True)
            else:
                gtk.main()
        except KeyboardInterrupt:
            CONFIG.save()
            gtk.accel_map_save(os.path.join(get_config_dir(), 'accel.map'))

if __name__ == "__main__":
    CLIENT = TrytonClient()
    CLIENT.run()
