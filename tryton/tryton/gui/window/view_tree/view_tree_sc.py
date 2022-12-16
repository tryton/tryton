#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import tryton.rpc as rpc
import gobject
import gtk
import gettext
from tryton.gui import Main
import tryton.common as common

_ = gettext.gettext


class ViewTreeSC(object):

    def __init__(self, tree, model, window):
        self.model = model
        self.tree = tree
        self.window = window
        self.tree.get_selection().set_mode('single')
        column = gtk.TreeViewColumn (_('ID'), gtk.CellRendererText(), text=0)
        self.tree.append_column(column)
        column.set_visible(False)
        cell = gtk.CellRendererText()

        column = gtk.TreeViewColumn (_('Description'), cell, text=1)
        self.tree.append_column(column)
        self.tree.connect('key_press_event', self.on_keypress)

    def on_keypress(self, widget, event):
        if event.keyval in (gtk.keysyms.Down, gtk.keysyms.Up):
            path, column = self.tree.get_cursor()
            if not path:
                return False
            store = self.tree.get_model()
            if event.keyval == gtk.keysyms.Down:
                if path[0] ==  len(store) - 1:
                    return True
            elif event.keyval == gtk.keysyms.Up:
                if path[0] == 0:
                    return True

    def update(self):
        store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING,
                gobject.TYPE_STRING)
        user =  rpc._USER
        args = ('model', 'ir.ui.view_sc', 'get_sc', user, self.model,
                rpc.CONTEXT)
        try:
            view_sc = rpc.execute(*args)
        except Exception, exception:
            view_sc = common.process_exception(exception, self.window, *args)
            if not view_sc:
                return
        for shortcut in view_sc:
            num = store.append()
            store.set(num, 0, shortcut['res_id'], 1, shortcut['name'],
                    2, shortcut['id'])
        self.tree.set_model(store)
        if self.model == 'ir.ui.menu':
            Main.get_main().shortcut_set(shortcuts=view_sc)

    def value_get(self, col):
        sel = self.tree.get_selection().get_selected()
        if sel is None:
            return None
        (model, i) = sel
        if not i:
            return None
        return model.get_value(i, col)

    def sel_id_get(self):
        res = self.value_get(0)
        if res is not None:
            return int(res)
        return None
