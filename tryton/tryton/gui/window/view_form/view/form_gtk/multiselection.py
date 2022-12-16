# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import gtk
import gobject

from .interface import WidgetInterface
from tryton.common.selection import SelectionMixin

MOVEMENT_KEYS = {gtk.keysyms.Up, gtk.keysyms.Down, gtk.keysyms.space,
    gtk.keysyms.Left, gtk.keysyms.KP_Left,
    gtk.keysyms.Right, gtk.keysyms.KP_Right,
    gtk.keysyms.Home, gtk.keysyms.KP_Home,
    gtk.keysyms.End, gtk.keysyms.KP_End}


class MultiSelection(WidgetInterface, SelectionMixin):

    def __init__(self, field_name, model_name, attrs=None):
        super(MultiSelection, self).__init__(field_name, model_name,
            attrs=attrs)

        self.widget = viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_placement(gtk.CORNER_TOP_LEFT)
        viewport.add(scroll)

        self.model = gtk.ListStore(gobject.TYPE_INT, gobject.TYPE_STRING)
        self.tree = gtk.TreeView()
        self.tree.set_model(self.model)
        self.tree.set_search_column(1)
        self.tree.connect('focus-out-event', lambda *a: self._focus_out())
        self.tree.connect('button-press-event', self.__button_press)
        self.tree.connect('key_press_event', self.__key_press)
        selection = self.tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        selection.connect('changed', self.send_modified)
        scroll.add(self.tree)
        name_column = gtk.TreeViewColumn(attrs.get('string', ''))
        name_cell = gtk.CellRendererText()
        name_column.pack_start(name_cell)
        name_column.add_attribute(name_cell, 'text', 1)
        self.tree.append_column(name_column)

        self.nullable_widget = False
        self.init_selection()
        self.id2path = {}

    def _color_widget(self):
        return self.tree

    def grab_focus(self):
        self.tree.grab_focus()

    @property
    def modified(self):
        if self.record and self.field:
            group = set(r.id for r in self.field.get_client(self.record))
            value = set(self.get_value())
            return value != group
        return False

    def send_modified(self, *args):
        if self.record:
            self.record.signal('record-modified')

    def get_value(self):
        model, paths = self.tree.get_selection().get_selected_rows()
        return [model[path][0] for path in paths]

    def set_value(self, record, field):
        field.set_client(record, self.get_value())

    def display(self, record, field):
        self.update_selection(record, field)
        super(MultiSelection, self).display(record, field)
        self.model.clear()
        if field is None:
            return
        id2path = {}
        for idx, (value, name) in enumerate(self.selection):
            self.model.append((value, name))
            id2path[value] = idx
        selection = self.tree.get_selection()
        selection.unselect_all()
        group = field.get_client(record)
        for element in group:
            if (element not in group.record_removed
                    and element not in group.record_deleted
                    and element.id in id2path):
                selection.select_path(id2path[element.id])

    def __button_press(self, treeview, event):
        if event.button == 1:
            event.state |= gtk.gdk.CONTROL_MASK

    def __key_press(self, treeview, event):
        if event.keyval in MOVEMENT_KEYS:
            event.state |= gtk.gdk.CONTROL_MASK
