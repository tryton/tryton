# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gettext
import os
from tryton.config import CONFIG, TRYTON_ICON, PIXMAPS_DIR
from tryton.common import get_toplevel_window

_ = gettext.gettext


class Tips(object):

    def __init__(self):
        self.tips = [
            _('''<b>Welcome to Tryton</b>


'''),
            _(u'''<b>Do you know Triton, one of the namesakes for our project?</b>

Triton (pronounced /ˈtraɪtən/ TRYE-tən, or as in Greek Τρίτων) is the
largest moon of the planet Neptune, discovered on October 10, 1846
by William Lassell. It is the only large moon in the Solar System
with a retrograde orbit, which is an orbit in the opposite direction
to its planet's rotation. At 2,700 km in diameter, it is the seventh-largest
moon in the Solar System. Triton comprises more than 99.5 percent of all
the mass known to orbit Neptune, including the planet's rings and twelve
other known moons. It is also more massive than all the Solar System's
159 known smaller moons combined.
'''),
            _('''<b>Export list records</b>

You can copy records from any list with Ctrl + C
and paste in any application with Ctrl + V
'''),
            _('''<b>Export graphs</b>

You can save any graphs in PNG file with right-click on it.
'''),
        ]

        parent = get_toplevel_window()
        self.win = gtk.Dialog(_('Tips'), parent,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        self.win.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.win.set_icon(TRYTON_ICON)
        self.win.set_default_size(500, 400)

        self.win.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.win.set_default_response(gtk.RESPONSE_CLOSE)
        vbox = gtk.VBox()
        img = gtk.Image()
        img.set_from_file(os.path.join(PIXMAPS_DIR, 'tryton.png'))
        vbox.pack_start(img, False, False)
        self.label = gtk.Label()
        self.label.set_alignment(0, 0)
        vbox.pack_start(self.label, True, True)
        separator = gtk.HSeparator()
        vbox.pack_start(separator, False, False)

        hbox = gtk.HBox()
        self.check = gtk.CheckButton(_('_Display a new tip next time'), True)
        self.check.set_active(True)
        hbox.pack_start(self.check)
        but_previous = gtk.Button()
        hbox_previous = gtk.HBox()
        img_previous = gtk.Image()
        img_previous.set_from_stock('tryton-go-previous', gtk.ICON_SIZE_BUTTON)
        hbox_previous.pack_start(img_previous)
        label_previous = gtk.Label(_('Previous'))
        hbox_previous.pack_start(label_previous)
        but_previous.add(hbox_previous)
        but_previous.set_relief(gtk.RELIEF_NONE)
        but_previous.connect('clicked', self.tip_previous)
        hbox.pack_start(but_previous)
        hbox_next = gtk.HBox()
        label_next = gtk.Label(_('Next'))
        hbox_next.pack_start(label_next)
        but_next = gtk.Button()
        img_next = gtk.Image()
        img_next.set_from_stock('tryton-go-next', gtk.ICON_SIZE_BUTTON)
        hbox_next.pack_start(img_next)
        but_next.add(hbox_next)
        but_next.set_relief(gtk.RELIEF_NONE)
        but_next.connect('clicked', self.tip_next)
        hbox.pack_start(but_next)
        vbox.pack_start(hbox, False, False)
        self.win.vbox.pack_start(vbox)
        self.win.show_all()

        try:
            self.number = int(CONFIG['tip.position'])
        except ValueError:
            self.number = 0

        self.tip_set()

        self.win.run()
        CONFIG['tip.autostart'] = self.check.get_active()
        CONFIG['tip.position'] = self.number + 1
        CONFIG.save()
        parent.present()
        self.win.destroy()

    def tip_set(self):
        tip = self.tips[self.number % len(self.tips)]
        self.label.set_text(tip)
        self.label.set_use_markup(True)

    def tip_next(self, widget):
        self.number += 1
        self.tip_set()

    def tip_previous(self, widget):
        self.number -= 1
        self.tip_set()
