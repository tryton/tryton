# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import gtk
import gobject

from .widget import Widget
from tryton.common.selection import SelectionMixin
from tryton.common.treeviewcontrol import TreeViewControl
from tryton.common.widget_style import set_widget_style


class MultiSelection(Widget, SelectionMixin):
    expand = True

    def __init__(self, view, attrs):
        super(MultiSelection, self).__init__(view, attrs)

        if int(attrs.get('yexpand', self.expand)):
            self.widget = gtk.ScrolledWindow()
            self.widget.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            self.widget.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        else:
            self.widget = gtk.VBox()
        self.widget.get_accessible().set_name(attrs.get('string', ''))

        self.model = gtk.ListStore(gobject.TYPE_INT, gobject.TYPE_STRING)
        self.tree = TreeViewControl()
        self.tree.set_model(self.model)
        self.tree.set_search_column(1)
        self.tree.connect('focus-out-event', lambda *a: self._focus_out())
        self.tree.set_headers_visible(False)
        selection = self.tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        selection.connect('changed', self.changed)
        self.widget.add(self.tree)
        name_column = gtk.TreeViewColumn()
        name_cell = gtk.CellRendererText()
        name_column.pack_start(name_cell)
        name_column.add_attribute(name_cell, 'text', 1)
        self.tree.append_column(name_column)

        self.nullable_widget = False
        self.init_selection()
        self.id2path = {}

    def _readonly_set(self, readonly):
        super(MultiSelection, self)._readonly_set(readonly)
        set_widget_style(self.tree, not readonly)
        selection = self.tree.get_selection()
        selection.set_select_function(lambda *a: not readonly)

    @property
    def modified(self):
        if self.record and self.field:
            group = set(r.id for r in self.field.get_client(self.record))
            value = set(self.get_value())
            return value != group
        return False

    def changed(self, selection):
        def focus_out():
            if self.widget.props.window:
                self._focus_out()
        # Must be deferred because it triggers a display of the form
        gobject.idle_add(focus_out)

    def get_value(self):
        model, paths = self.tree.get_selection().get_selected_rows()
        return [model[path][0] for path in paths]

    def set_value(self, record, field):
        field.set_client(record, self.get_value())

    def display(self, record, field):
        selection = self.tree.get_selection()
        selection.handler_block_by_func(self.changed)
        try:
            # Remove select_function to allow update,
            # it will be set back in the super call
            selection.set_select_function(lambda *a: True)
            self.update_selection(record, field)
            self.model.clear()
            if field is None:
                return
            id2path = {}
            for idx, (value, name) in enumerate(self.selection):
                self.model.append((value, name))
                id2path[value] = idx
            selection.unselect_all()
            group = field.get_client(record)
            for element in group:
                if (element not in group.record_removed
                        and element not in group.record_deleted
                        and element.id in id2path):
                    selection.select_path(id2path[element.id])
            super(MultiSelection, self).display(record, field)
        finally:
            selection.handler_unblock_by_func(self.changed)
