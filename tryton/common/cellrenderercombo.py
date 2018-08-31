# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject

from tryton.common.selection import selection_shortcuts


class CellRendererCombo(gtk.CellRendererCombo):

    def do_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        editable = gtk.CellRendererCombo.do_start_editing(self, event, widget,
            path, background_area, cell_area, flags)
        return selection_shortcuts(editable)


gobject.type_register(CellRendererCombo)
