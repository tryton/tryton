#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
import tryton.common as common

_ = gettext.gettext

class ScreenContainer(object):

    def __init__(self):
        self.viewport = gtk.Viewport()
        self.viewport.set_shadow_type(gtk.SHADOW_NONE)
        self.vbox = gtk.VBox(spacing=3)
        self.vbox.pack_end(self.viewport)
        self.filter_vbox = None
        self.button = None

    def widget_get(self):
        return self.vbox

    def add_filter(self, widget, fnct, clear_fnct):
        tooltips = common.Tooltips()

        self.filter_vbox = gtk.VBox(spacing=0)
        self.filter_vbox.set_border_width(0)
        hbox = gtk.HBox(homogeneous=False, spacing=0)
        label = gtk.Label(_('Search'))
        label.set_alignment(0.0, 0.5)
        hbox.pack_start(label, expand=True, fill=True)

        but_find = gtk.Button()
        tooltips.set_tip(but_find, _('Find'))
        but_find.connect('clicked', fnct)
        img_find = gtk.Image()
        img_find.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_find.set_alignment(0.5, 0.5)
        but_find.add(img_find)
        but_find.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_find, expand=False, fill=False)

        but_clear = gtk.Button()
        tooltips.set_tip(but_clear, _('Clear'))
        but_clear.connect('clicked', clear_fnct)
        img_clear = gtk.Image()
        img_clear.set_from_stock('tryton-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_clear.set_alignment(0.5, 0.5)
        but_clear.add(img_clear)
        but_clear.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_clear, expand=False, fill=False)

        hbox.show_all()
        self.filter_vbox.pack_start(hbox, expand=True, fill=False)

        hseparator = gtk.HSeparator()
        hseparator.show()
        self.filter_vbox.pack_start(hseparator, expand=True, fill=False)
        self.filter_vbox.pack_start(widget, expand=True, fill=True)

        self.vbox.pack_start(self.filter_vbox, expand=False, fill=True)

        tooltips.enable()

    def show_filter(self):
        if self.filter_vbox:
            self.filter_vbox.show()

    def hide_filter(self):
        if self.filter_vbox:
            self.filter_vbox.hide()

    def set(self, widget):
        if self.viewport.get_child():
            self.viewport.remove(self.viewport.get_child())
        self.viewport.add(widget)
        self.viewport.show_all()

    def size_get(self):
        return self.viewport.get_child().size_request()
