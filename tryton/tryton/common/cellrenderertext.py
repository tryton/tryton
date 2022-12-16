# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import Gtk, GObject


class CellRendererText(Gtk.CellRendererText):

    def __init__(self):
        super(CellRendererText, self).__init__()
        self.connect('editing-started', self.__class__.on_editing_started)

    def on_editing_started(self, editable, path):
        pass


class CellRendererTextCompletion(CellRendererText):

    def __init__(self, set_completion):
        super(CellRendererTextCompletion, self).__init__()
        self.set_completion = set_completion

    def on_editing_started(self, editable, path):
        super().on_editing_started(editable, path)
        self.set_completion(editable, path)


GObject.type_register(CellRendererText)
GObject.type_register(CellRendererTextCompletion)
