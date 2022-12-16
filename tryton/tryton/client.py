#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"""
%prog [options]
"""
import os
import sys

if os.name == 'nt':
    sys.path.insert(0, os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]),
                                    'GTK\\bin'))
    sys.path.insert(0, os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]),
                                    'GTK\\lib'))
    os.environ['PATH'] = os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]),
                                      'GTK\\bin') + ';' + os.environ['PATH']
    os.environ['PATH'] = os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]),
                                      'GTK\\lib') + ';' + os.environ['PATH']

import pygtk
pygtk.require('2.0')
import gtk
if os.name != 'nt':
    gtk.gdk.threads_init()
import logging

import version
import config
from config import CONFIG, CURRENT_DIR, PREFIX, PIXMAPS_DIR, TRYTON_ICON, get_home_dir
import translate
import gui
import traceback
import mx.DateTime
import time


class TrytonClient(object):
    "Tryton client"

    def __init__(self):
        logging.basicConfig()
        translate.setlang(CONFIG['client.lang'])

        for logger in CONFIG['logging.logger'].split(','):
            if logger:
                loglevel = {
                        'DEBUG': logging.DEBUG,
                        'INFO': logging.INFO,
                        'WARNING': logging.WARNING,
                        'ERROR': logging.ERROR,
                        'CRITICAL': logging.CRITICAL,
                        }
                log = logging.getLogger(logger)
                log.setLevel(loglevel[CONFIG['logging.level'].upper()])
        if CONFIG['logging.verbose']:
            logging.getLogger().setLevel(logging.INFO)
        else:
            logging.getLogger().setLevel(logging.ERROR)

        if not hasattr(mx.DateTime, 'strptime'):
            mx.DateTime.strptime = lambda x, y: mx.DateTime.mktime(
                    time.strptime(x, y))

        factory = gtk.IconFactory()
        factory.add_default()

        for fname in os.listdir(PIXMAPS_DIR):
            name = os.path.splitext(fname)[0]
            if not name.startswith('tryton-'):
                continue
            if not os.path.isfile(os.path.join(PIXMAPS_DIR, fname)):
                continue
            try:
                pixbuf = gtk.gdk.pixbuf_new_from_file(
                        os.path.join(PIXMAPS_DIR, fname))
            except:
                continue
            icon_set = gtk.IconSet(pixbuf)
            factory.add(name, icon_set)

    def run(self):
        main = gui.Main()

        def excepthook(exctyp, value, tb):
            import common

            if str(value) == 'NotLogged':
                return

            tb_s = reduce(lambda x, y: x+y,
                    traceback.format_exception(exctyp, value, tb))
            for path in sys.path:
                tb_s = tb_s.replace(path, '')
            common.error(str(value), main.window, tb_s)

        sys.excepthook = excepthook

        if CONFIG['tip.autostart']:
            main.sig_tips()
        main.sig_login()

        #XXX psyco breaks report printing
        #try:
        #    import psyco
        #    psyco.full()
        #except ImportError:
        #    pass

        try:
            gtk.main()
        except KeyboardInterrupt:
            CONFIG.save()
            if hasattr(gtk, 'accel_map_save'):
                gtk.accel_map_save(os.path.join(get_home_dir(), '.trytonsc'))

if __name__ == "__main__":
    CLIENT = TrytonClient()
    CLIENT.run()
