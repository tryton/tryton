# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject

from tryton.common.selection import selection_shortcuts


class CellRendererCombo(gtk.CellRendererCombo):

    def set_sensitive(self, value):
        self.set_property('sensitive', value)

    def do_activate(self, event, widget, path, background_area, cell_area,
            flags):
        if not self.props.visible:
            return
        return gtk.CellRendererCombo.do_activate(self, event, widget, path,
            background_area, cell_area, flags)

    def do_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        if not self.props.visible:
            return
        if not event:
            event = gtk.gdk.Event(gtk.keysyms.Tab)
        editable = gtk.CellRendererCombo.do_start_editing(self, event, widget,
            path, background_area, cell_area, flags)
        return selection_shortcuts(editable)

gobject.type_register(CellRendererCombo)
