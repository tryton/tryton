# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import gettext
from gi.repository import Gtk, GdkPixbuf

from tryton.config import PIXMAPS_DIR, CONFIG
from tryton.common import get_toplevel_window
from tryton import __version__

COPYRIGHT = '''\
Copyright (C) 2004-2020 Tryton.
'''
AUTHORS = [
        'Bertrand Chenal <bertrand.chenal@b2ck.com>',
        'Cédric Krier <cedric.krier@b2ck.com>',
        'Franz Wiesinger',
        'Hartmut Goebel',
        'Korbinian Preisler <info@virtual-things.biz>',
        'Mathias Behrle <info@m9s.biz>',
        'Nicolas Évrard <nicolas.evrard@b2ck.com>',
        'Sednacom <contact@sednacom.fr>',
        'Udo Spallek <info@virtual-things.biz>',
        ]
_ = gettext.gettext


class About(object):

    def __init__(self):
        parent = get_toplevel_window()
        self.win = Gtk.AboutDialog()
        self.win.set_transient_for(parent)
        self.win.set_name(CONFIG['client.title'])
        self.win.set_version(__version__)
        self.win.set_comments(_("modularity, scalability and security"))
        self.win.set_copyright(COPYRIGHT)
        self.win.set_license_type(Gtk.License.GPL_3_0)
        self.win.set_website('http://www.tryton.org/')
        self.win.set_website_label("Tryton")
        self.win.set_authors(AUTHORS)
        self.win.set_translator_credits(_('translator-credits'))
        self.win.set_logo(GdkPixbuf.Pixbuf.new_from_file(
                os.path.join(PIXMAPS_DIR, 'tryton.svg')))
        self.win.run()
        parent.present()
        self.win.destroy()
