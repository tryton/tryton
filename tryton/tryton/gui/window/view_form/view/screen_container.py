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
        self.but_prev = None
        self.but_next = None
        self.alternate_viewport = gtk.Viewport()
        self.alternate_viewport.set_shadow_type(gtk.SHADOW_NONE)
        self.alternate_view = False

    def widget_get(self):
        return self.vbox

    def add_filter(self, widget, fnct, clear_fnct, prev_fnct, next_fnct):
        tooltips = common.Tooltips()

        self.filter_vbox = gtk.VBox(spacing=0)
        self.filter_vbox.set_border_width(0)
        hbox = gtk.HBox(homogeneous=False, spacing=0)
        label = gtk.Label(_('Search'))
        label.set_alignment(0.0, 0.5)
        hbox.pack_start(label, expand=True, fill=True)

        but_prev = gtk.Button()
        self.but_prev = but_prev
        tooltips.set_tip(but_prev, _('Previous'))
        but_prev.connect('clicked', prev_fnct)
        img_prev = gtk.Image()
        img_prev.set_from_stock('tryton-go-previous',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_prev.set_alignment(0.5, 0.5)
        but_prev.add(img_prev)
        but_prev.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_prev, expand=False, fill=False)

        but_next = gtk.Button()
        self.but_next = but_next
        tooltips.set_tip(but_next, _('Next'))
        but_next.connect('clicked', next_fnct)
        img_next = gtk.Image()
        img_next.set_from_stock('tryton-go-next',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_next.set_alignment(0.5, 0.5)
        but_next.add(img_next)
        but_next.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_next, expand=False, fill=False)

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

        self.but_next.set_sensitive(False)
        self.but_prev.set_sensitive(False)

        tooltips.enable()

    def show_filter(self):
        if self.filter_vbox:
            self.filter_vbox.show()

    def hide_filter(self):
        if self.filter_vbox:
            self.filter_vbox.hide()

    def set(self, widget):
        if self.alternate_view:
            if self.alternate_viewport.get_child():
                self.alternate_viewport.remove(
                        self.alternate_viewport.get_child())
            if widget == self.viewport.get_child():
                self.viewport.remove(self.viewport.get_child())
            self.alternate_viewport.add(widget)
            self.alternate_viewport.show_all()
            return
        if self.viewport.get_child():
            self.viewport.remove(self.viewport.get_child())
        self.viewport.add(widget)
        self.viewport.show_all()

    def size_get(self):
        return self.viewport.get_child().size_request()
