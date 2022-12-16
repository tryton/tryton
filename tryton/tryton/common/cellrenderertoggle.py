# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject


class CellRendererToggle(gtk.CellRendererToggle):
    pass


gobject.type_register(CellRendererToggle)
