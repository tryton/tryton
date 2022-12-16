#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import gtk
import gettext

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
        self.filter_vbox = gtk.VBox(spacing=1)
        self.filter_vbox.set_border_width(1)
        label = gtk.Label(_('Search'))
        label.set_alignment(0.0, 0.5)
        label.show()
        self.filter_vbox.pack_start(label, expand=True, fill=False)
        hseparator = gtk.HSeparator()
        hseparator.show()
        self.filter_vbox.pack_start(hseparator, expand=True, fill=False)
        self.filter_vbox.pack_start(widget, expand=True, fill=True)
        hbuttonbox = gtk.HButtonBox()
        hbuttonbox.set_spacing(5)
        hbuttonbox.set_layout(gtk.BUTTONBOX_END)
        button_clear = gtk.Button()
        hbox_clear = gtk.HBox()
        img_clear = gtk.Image()
        img_clear.set_from_stock('tryton-clear', gtk.ICON_SIZE_BUTTON)
        hbox_clear.pack_start(img_clear)
        label_clear = gtk.Label(_('Clear'))
        hbox_clear.pack_start(label_clear)
        button_clear.add(hbox_clear)
        button_clear.connect('clicked', clear_fnct)
        hbuttonbox.pack_start(button_clear, expand=False, fill=False)
        self.button = gtk.Button()
        hbox_find = gtk.HBox()
        img_find = gtk.Image()
        img_find.set_from_stock('tryton-find', gtk.ICON_SIZE_BUTTON)
        hbox_find.pack_start(img_find)
        label_find = gtk.Label(_('Find'))
        hbox_find.pack_start(label_find)
        self.button.add(hbox_find)
        self.button.connect('clicked', fnct)
        self.button.set_property('can_default', True)
        hbuttonbox.pack_start(self.button, expand=False, fill=False)
        hbuttonbox.show_all()
        self.filter_vbox.pack_start(hbuttonbox, expand=False, fill=False)
        self.vbox.pack_start(self.filter_vbox, expand=False, fill=True)

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
