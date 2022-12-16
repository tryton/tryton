# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import GObject, Gtk

from tryton.common.selection import selection_shortcuts


class CellRendererCombo(Gtk.CellRendererCombo):

    def on_editing_started(self, editable, path):
        super().on_editing_started(editable, path)
        selection_shortcuts(editable)


GObject.type_register(CellRendererCombo)
