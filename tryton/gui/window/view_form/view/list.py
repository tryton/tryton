# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import json
import locale
import gettext
from functools import wraps

from gi.repository import Gdk, GLib, GObject, Gtk
from pygtkcompat.generictreemodel import GenericTreeModel

from tryton.config import CONFIG
from tryton.common.cellrendererbutton import CellRendererButton
from tryton.gui.window import Window
from tryton.common.popup_menu import populate
from tryton.common import RPCExecute, RPCException, node_attributes, Tooltips
from tryton.common import domain_inversion, simplify, unique_value
from tryton.pyson import PYSONDecoder
import tryton.common as common
from . import View, XMLViewParser
from .list_gtk.editabletree import EditableTreeView, TreeView
from .list_gtk.widget import (Affix, Char, Text, Int, Boolean, URL, Date,
    Time, Float, TimeDelta, Binary, M2O, O2O, O2M, M2M, Selection,
    MultiSelection, Reference, Dict, ProgressBar, Button, Image)

_ = gettext.gettext


def delay(func):
    """Decorator for ViewTree method to delay execution when idle and if
    display counter did not change"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        def wait():
            if not self.treeview.props.window:
                return
            if self.treeview.display_counter == display_counter:
                func(self, *args, **kwargs)
        display_counter = self.treeview.display_counter
        GLib.idle_add(wait)
    return wrapper


def path_convert_id2pos(model, id_path):
    "This function will transform a path of id into a path of position"
    group = model.group
    id_path = id_path[:]
    indexes = []
    while id_path:
        current_id = id_path.pop(0)
        try:
            record = group.get(current_id)
            indexes.append(group.index(record))
            group = record.children_group(model.children_field)
        except (KeyError, AttributeError, ValueError):
            return None
    return tuple(indexes)


class AdaptModelGroup(GenericTreeModel):

    def __init__(self, group, children_field=None):
        super(AdaptModelGroup, self).__init__()
        self.group = group
        self.set_property('leak_references', False)
        self.children_field = children_field
        self.__removed = None  # XXX dirty hack to allow update of has_child

    def added(self, group, record):
        if (group is self.group
                and (record.group is self.group
                    or record.group.child_name == self.children_field)):
            path = record.get_index_path(self.group)
            iter_ = self.get_iter(path)
            self.row_inserted(path, iter_)
            if record.children_group(self.children_field):
                self.row_has_child_toggled(path, iter_)
            if (record.parent
                    and record.group is not self.group):
                path = record.parent.get_index_path(self.group)
                iter_ = self.get_iter(path)
                self.row_has_child_toggled(path, iter_)

    def removed(self, group, record):
        if (group is self.group
                and (record.group is self.group
                    or record.group.child_name == self.children_field)):
            path = record.get_index_path(self.group)
            self.row_deleted(path)

    def append(self, model):
        self.group.add(model)

    def prepend(self, model):
        self.group.add(model, 0)

    def remove(self, iter_):
        record = self.get_value(iter_, 0)
        record.group.remove(record)
        self.invalidate_iters()

    def __move(self, record, path, offset=0):
        iter_ = self.get_iter(path)
        record_pos = self.get_value(iter_, 0)
        group = record_pos.group
        pos = group.index(record_pos) + offset
        if group is not record.group:
            prev_group = record.group
            record.group.remove(record, remove=True, force_remove=True)
            # Don't remove record from previous group
            # as the new parent will change the parent
            # This prevents concurrency conflict
            record.group.record_removed.remove(record)
            group.add(record)
            if not record.parent_name:
                record.modified_fields.setdefault(prev_group.parent_name)
                record.value[prev_group.parent_name] = None
            else:
                record.modified_fields.setdefault(record.parent_name)
        group.move(record, pos)

    def move_before(self, record, path):
        self.__move(record, path)

    def move_after(self, record, path):
        self.__move(record, path, 1)

    def move_into(self, record, path):
        iter_ = self.get_iter(path)
        parent = self.get_value(iter_, 0)
        group = parent.children_group(self.children_field)
        if group is not record.group:
            record.group.remove(record, remove=True, force_remove=True)
            # Don't remove record from previous group
            # as the new parent will change the parent
            # This prevents concurrency conflict
            if record in record.group.record_removed:
                record.group.record_removed.remove(record)
            group.add(record)
            record.modified_fields.setdefault(record.parent_name or 'id')
        group.move(record, 0)

    def sort(self, ids):
        old_idx = {record.id: i for i, record in enumerate(self.group)}
        new_idx = {id_: i for i, id_ in enumerate(ids)}
        size = len(self.group)
        self.group.sort(key=lambda r: new_idx.get(r.id, size))
        new_order = []
        prev = None
        for record in self.group:
            new_order.append(old_idx.get(record.id))
            if prev:
                prev.next[id(self.group)] = record
            prev = record
        if prev:
            prev.next[id(self.group)] = None
        path = Gtk.TreePath()
        # XXX pygobject does not allow to create empty TreePath,
        # it is always a path of 0
        # see: https://bugzilla.gnome.org/show_bug.cgi?id=770665
        if hasattr(path, 'get_depth'):
            while path.get_depth():
                path.up()
        self.rows_reordered(path, None, new_order)

    def __len__(self):
        return len(self.group)

    def on_get_flags(self):
        if not self.children_field:
            return Gtk.TreeModelFlags.LIST_ONLY
        return 0

    def on_get_n_columns(self):
        # XXX
        return 1

    def on_get_column_type(self, index):
        # XXX
        return GObject.TYPE_PYOBJECT

    def on_get_path(self, record):
        return record.get_index_path(self.group)

    def on_get_iter(self, path):
        group = self.group
        record = None
        for i in path:
            if group is None or i >= len(group):
                return None
            record = group[i]
            if not self.children_field:
                break
            group = record.children_group(self.children_field)
        return record

    def on_get_value(self, record, column):
        return record

    def on_iter_next(self, record):
        if record is None:
            return None
        return record.next.get(id(record.group))

    def on_iter_has_child(self, record):
        if record is None or not self.children_field:
            return False
        children = record.children_group(self.children_field)
        if children is None:
            return False
        length = len(children)
        if self.__removed and self.__removed in children:
            length -= 1
        return bool(length)

    def on_iter_children(self, record):
        if record is None:
            if self.group:
                return self.group[0]
            else:
                return None
        if self.children_field:
            children = record.children_group(self.children_field)
            if children:
                return children[0]
        return None

    def on_iter_n_children(self, record):
        if record is None:
            return len(self.group)
        if not self.children_field:
            return 0
        return len(record.children_group(self.children_field))

    def on_iter_nth_child(self, record, nth):
        if record is None:
            if nth < len(self.group):
                return self.group[nth]
            return None
        if not self.children_field:
            return None
        if nth < len(record.children_group(self.children_field)):
            return record.children_group(self.children_field)[nth]
        return None

    def on_iter_parent(self, record):
        if record is None:
            return None
        return record.parent


class TreeXMLViewParser(XMLViewParser):

    WIDGETS = {
        'biginteger': Int,
        'binary': Binary,
        'boolean': Boolean,
        'callto': URL,
        'char': Char,
        'date': Date,
        'dict': Dict,
        'email': URL,
        'float': Float,
        'image': Image,
        'integer': Int,
        'many2many': M2M,
        'many2one': M2O,
        'numeric': Float,
        'one2many': O2M,
        'one2one': O2O,
        'progressbar': ProgressBar,
        'reference': Reference,
        'selection': Selection,
        'multiselection': MultiSelection,
        'sip': URL,
        'text': Text,
        'time': Time,
        'timedelta': TimeDelta,
        'url': URL,
        }

    def _parse_tree(self, node, attributes):
        for child in node.childNodes:
            self.parse(child)

    def _parse_field(self, node, attributes):
        name = attributes['name']
        widget = self.WIDGETS[attributes['widget']](self.view, attributes)
        self.view.widgets[name].append(widget)

        column = Gtk.TreeViewColumn(attributes['string'])
        column._type = 'field'
        column.name = name

        prefixes = []
        suffixes = list(widget.suffixes)
        if attributes['widget'] in ['url', 'email', 'callto', 'sip']:
            prefixes.append(
                Affix(self.view, attributes, protocol=attributes['widget']))
        if 'icon' in attributes:
            prefixes.append(Affix(self.view, attributes))

        for affix in node.childNodes:
            affix_attrs = node_attributes(affix)
            if 'name' not in affix_attrs:
                affix_attrs['name'] = attributes['name']
            if affix.tagName == 'prefix':
                list_ = prefixes
            else:
                list_ = suffixes
            list_.append(Affix(self.view, affix_attrs))
        prefixes.extend(widget.prefixes)

        for prefix in prefixes:
            column.pack_start(prefix.renderer, expand=prefix.expand)
            column.set_cell_data_func(prefix.renderer, prefix.setter)
        column.pack_start(widget.renderer, expand=True)
        column.set_cell_data_func(widget.renderer, widget.setter)
        for suffix in suffixes:
            column.pack_start(suffix.renderer, expand=suffix.expand)
            column.set_cell_data_func(suffix.renderer, suffix.setter)

        self._set_column_widget(column, attributes, align=widget.align)
        self._set_column_width(column, attributes)

        if (not self.view.attributes.get('sequence')
                and not self.view.children_field
                and self.field_attrs[name].get('sortable', True)):
            column.connect('clicked', self.view.sort_model)

        self.view.treeview.append_column(column)

        if 'sum' in attributes:
            text = attributes['sum'] + _(':')
            label, sum_ = Gtk.Label(label=text), Gtk.Label()

            hbox = Gtk.HBox()
            hbox.pack_start(label, expand=True, fill=False, padding=2)
            hbox.pack_start(sum_, expand=True, fill=False, padding=2)
            hbox.show_all()
            self.view.sum_box.pack_start(
                hbox, expand=False, fill=False, padding=0)

            self.view.sum_widgets.append((attributes['name'], sum_))

    def _parse_button(self, node, attributes):
        button = Button(self.view, attributes)
        self.view.state_widgets.append(button)

        column = Gtk.TreeViewColumn(
            attributes.get('string', ''), button.renderer)
        column._type = 'button'
        column.name = None
        column.set_cell_data_func(button.renderer, button.setter)

        self._set_column_widget(column, attributes, arrow=False)
        self._set_column_width(column, attributes)

        decoder = PYSONDecoder(self.view.screen.context)
        column.set_visible(
            not decoder.decode(attributes.get('tree_invisible', '0')))

        self.view.treeview.append_column(column)

    def _set_column_widget(self, column, attributes, arrow=True, align=0.5):
        hbox = Gtk.HBox(homogeneous=False, spacing=2)
        label = Gtk.Label(label=attributes['string'])
        field = self.field_attrs.get(attributes['name'], {})
        if field and self.view.editable:
            required = field.get('required')
            readonly = field.get('readonly')
            common.apply_label_attributes(label, readonly, required)
        label.show()
        help = attributes.get('help')
        if help:
            tooltips = Tooltips()
            tooltips.set_tip(label, help)
            tooltips.enable()
        if arrow:
            arrow_widget = Gtk.Image()
            arrow_widget.show()
            column.arrow = arrow_widget
        hbox.pack_start(label, expand=True, fill=True, padding=0)
        if arrow:
            hbox.pack_start(arrow_widget, expand=False, fill=False, padding=0)
            column.set_clickable(True)
        hbox.show()
        column.set_widget(hbox)
        column.set_alignment(align)

    def _set_column_width(self, column, attributes):
        default_width = {
            'integer': 60,
            'biginteger': 60,
            'float': 80,
            'numeric': 80,
            'timedelta': 100,
            'date': 100,
            'datetime': 100,
            'time': 100,
            'selection': 90,
            'char': 100,
            'one2many': 50,
            'many2many': 50,
            'boolean': 20,
            'binary': 200,
            }

        screen = self.view.screen
        width = screen.tree_column_width[screen.model_name].get(column.name)
        field_attrs = self.field_attrs.get(attributes['name'], {})
        if not width:
            if 'width' in attributes:
                width = int(attributes['width'])
            elif field_attrs:
                width = default_width.get(field_attrs['type'], 100)
                if attributes.get('symbol'):
                    width += 20
            else:
                width = 80
        column.width = width
        if width > 0:
            column.set_fixed_width(width)
        column.set_min_width(1)

        expand = bool(attributes.get('expand', False))
        column.set_expand(expand)
        column.set_resizable(True)
        if attributes.get('widget') != 'text':
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)


class ViewTree(View):
    view_type = 'tree'
    xml_parser = TreeXMLViewParser
    draggable = False

    def __init__(self, view_id, screen, xml, children_field):
        self.children_field = children_field
        self.sum_widgets = []
        self.sum_box = Gtk.HBox()
        self.treeview = None
        self._editable = bool(int(xml.getAttribute('editable') or 0))
        if self._editable:
            self.treeview = EditableTreeView(self)
            grid_lines = Gtk.TreeViewGridLines.BOTH
        else:
            self.treeview = TreeView(self)
            grid_lines = Gtk.TreeViewGridLines.VERTICAL

        super().__init__(view_id, screen, xml)
        self.set_drag_and_drop()

        self.mnemonic_widget = self.treeview

        # Add last column if necessary
        for column in self.treeview.get_columns():
            if column.get_expand():
                break
        else:
            column = Gtk.TreeViewColumn()
            column._type = 'fill'
            column.name = None
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            self.treeview.append_column(column)

        self.treeview.set_property('enable-grid-lines', grid_lines)
        self.treeview.set_fixed_height_mode(
            all(c.get_sizing() == Gtk.TreeViewColumnSizing.FIXED
                for c in self.treeview.get_columns()))
        self.treeview.connect('button-press-event', self.__button_press)
        self.treeview.connect('key-press-event', self.on_keypress)
        self.treeview.connect_after('row-activated', self.__sig_switch)
        if self.children_field:
            child_col = 1 if self.draggable else 0
            self.treeview.connect('test-expand-row', self.test_expand_row)
            self.treeview.set_expander_column(
                self.treeview.get_column(child_col))
        self.treeview.set_rubber_banding(True)

        selection = self.treeview.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect('changed', self.__select_changed)

        self.widget = Gtk.VBox()
        self.scroll = scroll = Gtk.ScrolledWindow()
        scroll.add(self.treeview)
        scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_placement(Gtk.CornerType.TOP_LEFT)
        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        viewport.add(scroll)
        self.widget.pack_start(viewport, expand=True, fill=True, padding=0)

        self.sum_box.show()
        self.widget.pack_start(
            self.sum_box, expand=False, fill=False, padding=0)

        self.display()

    def get_column_widget(self, column):
        'Return the widget of the column'
        idx = [c for c in self.treeview.get_columns()
            if c.name == column.name].index(column)
        return self.widgets[column.name][idx]

    def sort_model(self, column):
        up = common.IconFactory.get_pixbuf('tryton-arrow-up')
        down = common.IconFactory.get_pixbuf('tryton-arrow-down')
        for col in self.treeview.get_columns():
            if col != column and getattr(col, 'arrow', None):
                col.arrow.clear()
        self.screen.order = self.screen.default_order
        if not column.arrow.props.pixbuf:
            column.arrow.set_from_pixbuf(down)
            self.screen.order = [(column.name, 'ASC')]
        else:
            if column.arrow.props.pixbuf == down:
                column.arrow.set_from_pixbuf(up)
                self.screen.order = [(column.name, 'DESC')]
            else:
                column.arrow.clear()
        model = self.treeview.get_model()
        unsaved_records = [x for x in model.group if x.id < 0]
        search_string = self.screen.screen_container.get_text() or ''
        if (self.screen.search_count == len(model)
                or unsaved_records
                or self.screen.parent):
            ids = self.screen.search_filter(
                search_string=search_string, only_ids=True)
            model.sort(ids)
        else:
            self.screen.search_filter(search_string=search_string)

    def update_arrow(self):
        order = self.screen.order
        if order and len(order) == 1:
            (name, direction), = order
            if direction:
                direction = direction.split(None, 1)[0]
                direction = {
                    'ASC': common.IconFactory.get_pixbuf('tryton-arrow-down'),
                    'DESC': common.IconFactory.get_pixbuf('tryton-arrow-up'),
                    }[direction]
        else:
            name, direction = None, None

        for col in self.treeview.get_columns():
            arrow = getattr(col, 'arrow', None)
            if arrow:
                if col.name != name:
                    arrow.clear()
                else:
                    if direction:
                        arrow.set_from_pixbuf(direction)
                    else:
                        arrow.clear()

    def set_drag_and_drop(self):
        dnd = False
        if self.children_field:
            children = self.group.fields.get(self.children_field)
            if children:
                parent_name = children.attrs.get('relation_field')
                dnd = parent_name in self.widgets
        elif self.attributes.get('sequence'):
            dnd = True
        # Disable DnD on mac until it is fully supported
        if sys.platform == 'darwin':
            dnd = False
        if self.screen.readonly:
            dnd = False

        self.draggable = dnd
        if not dnd:
            return

        self.treeview.enable_model_drag_dest(
            [('MY_TREE_MODEL_ROW', Gtk.TargetFlags.SAME_WIDGET, 0)],
            Gdk.DragAction.MOVE)
        self.treeview.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK | Gdk.ModifierType.BUTTON3_MASK,
            [('MY_TREE_MODEL_ROW', Gtk.TargetFlags.SAME_WIDGET, 0)],
            Gdk.DragAction.MOVE)
        # XXX have to set manually because enable_model_drag_source
        # does not set the mask
        # https://bugzilla.gnome.org/show_bug.cgi?id=756177
        self.treeview.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK | Gdk.ModifierType.BUTTON3_MASK,
            [Gtk.TargetEntry.new(
                    'MY_TREE_MODEL_ROW', Gtk.TargetFlags.SAME_WIDGET, 0)],
            Gdk.DragAction.MOVE)

        self.treeview.connect("drag-data-get", self.drag_data_get)
        self.treeview.connect('drag-data-received',
            self.drag_data_received)
        self.treeview.connect('drag-drop', self.drag_drop)
        self.treeview.connect('drag-data-delete', self.drag_data_delete)

        drag_column = Gtk.TreeViewColumn()
        drag_column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        drag_column._type = 'drag'
        drag_column.name = None
        cell_pixbuf = Gtk.CellRendererPixbuf()
        cell_pixbuf.props.pixbuf = common.IconFactory.get_pixbuf('tryton-drag')
        drag_column.pack_start(cell_pixbuf, expand=False)
        self.treeview.insert_column(drag_column, 0)

    @property
    def modified(self):
        return False

    @property
    def editable(self):
        return self._editable and not self.screen.readonly

    def get_fields(self):
        return [col.name for col in self.treeview.get_columns() if col.name]

    def get_buttons(self):
        return [b for b in self.state_widgets
            if isinstance(b.renderer, CellRendererButton)]

    def on_keypress(self, widget, event):
        control_mask = Gdk.ModifierType.CONTROL_MASK
        if sys.platform == 'darwin':
            control_mask = Gdk.ModifierType.MOD2_MASK
        if (event.keyval == Gdk.KEY_c
                and event.state & control_mask):
            self.on_copy()
            return False
        if (event.keyval == Gdk.KEY_v
                and event.state & control_mask):
            self.on_paste()
            return False

    def test_expand_row(self, widget, iter_, path):
        model = widget.get_model()
        if model.iter_n_children(iter_) > CONFIG['client.limit']:
            self.record = model.get_value(iter_, 0)
            self.screen.switch_view('form')
            return True
        iter_ = model.iter_children(iter_)
        if not iter_:
            return False
        fields = [col.name for col in self.treeview.get_columns()
                if col.name]
        while iter_:
            record = model.get_value(iter_, 0)
            if not record.get_loaded(fields):
                for field in fields:
                    record[field]
                    if record.exception:
                        return True
            iter_ = model.iter_next(iter_)
        return False

    def on_copy(self):
        for clipboard_type in [
                Gdk.SELECTION_CLIPBOARD, Gdk.SELECTION_PRIMARY]:
            clipboard = self.treeview.get_clipboard(clipboard_type)
            selection = self.treeview.get_selection()
            data = []
            selection.selected_foreach(self.copy_foreach, data)
            clipboard.set_text('\n'.join(data), -1)

    def copy_foreach(self, treemodel, path, iter, data):
        record = treemodel.get_value(iter, 0)
        values = []
        for col in self.treeview.get_columns():
            if not col.get_visible() or not col.name:
                continue
            widget = self.get_column_widget(col)
            values.append('"'
                + str(widget.get_textual_value(record)).replace('"', '""')
                + '"')
        data.append('\t'.join(values))
        return

    def on_paste(self):
        if not self.editable:
            return

        def unquote(value):
            if value[:1] == '"' and value[-1:] == '"':
                return value[1:-1]
            return value
        data = []
        for clipboard_type in [
                Gdk.SELECTION_CLIPBOARD, Gdk.SELECTION_PRIMARY]:
            clipboard = self.treeview.get_clipboard(clipboard_type)
            text = clipboard.wait_for_text()
            if not text:
                continue
            data = [[unquote(v) for v in l.split('\t')]
                for l in text.splitlines()]
            break
        col = self.treeview.get_cursor()[1]
        columns = [c for c in self.treeview.get_columns()
            if c.get_visible() and c.name]
        if col in columns:
            idx = columns.index(col)
            columns = columns[idx:]
        if self.record:
            record = self.record
            group = record.group
            idx = group.index(record)
        else:
            group = self.group
            idx = len(group)
        default = None
        for line in data:
            if idx >= len(group):
                record = group.new(default=False)
                if default is None:
                    default = record.default_get()
                record.set_default(default)
                group.add(record)
            record = group[idx]
            for col, value in zip(columns, line):
                widget = self.get_column_widget(col)
                if widget.get_textual_value(record) != value:
                    widget.value_from_text(record, value)
                    if value and not widget.get_textual_value(record):
                        # Stop setting value if a value is correctly set
                        idx = len(group)
                        break
            if not record.validate():
                break
            idx += 1
        self.record = record
        self.screen.display(set_cursor=True)

    def drag_data_get(self, treeview, context, selection, target_id,
            etime):
        treeview.stop_emission_by_name('drag-data-get')

        def _func_sel_get(model, path, iter_, data):
            value = model.get_value(iter_, 0)
            data.append(json.dumps(
                    value.get_path(model.group), separators=(',', ':')))
        data = []
        treeselection = treeview.get_selection()
        treeselection.selected_foreach(_func_sel_get, data)
        if not data:
            return
        selection.set(selection.get_target(), 8, data[0].encode('utf-8'))
        return True

    def drag_data_received(self, treeview, context, x, y, selection,
            info, etime):
        treeview.stop_emission_by_name('drag-data-received')
        if self.attributes.get('sequence'):
            field = self.group.fields[self.attributes['sequence']]
            for record in self.group:
                if field.get_state_attrs(
                        record).get('readonly', False):
                    return
        try:
            selection_data = selection.data
        except AttributeError:
            selection_data = selection.get_data()
        if not selection_data:
            return
        selection_data = selection_data.decode('utf-8')

        # Don't received if the treeview was editing because it breaks the
        # internal state of the cursor.
        cursor, column = treeview.get_cursor()
        if column:
            for renderer in column.get_cells():
                if renderer.props.editing:
                    return

        model = treeview.get_model()
        try:
            data = json.loads(selection_data)
        except ValueError:
            return
        record = model.group.get_by_path(data)
        record_path = record.get_index_path(model.group)
        drop_info = treeview.get_dest_row_at_pos(x, y)

        def check_recursion(from_, to):
            if not from_ or not to:
                return True
            if from_ == to:
                return False
            length = min(len(from_), len(to))
            if len(from_) < len(to) and from_[:length] == to[:length]:
                return False
            return True
        if drop_info:
            path, position = drop_info
            check_path = tuple(path)
            if position in [
                    Gtk.TreeViewDropPosition.BEFORE,
                    Gtk.TreeViewDropPosition.AFTER]:
                check_path = path[:-1]
            if not check_recursion(record_path, check_path):
                return
            if position == Gtk.TreeViewDropPosition.BEFORE:
                model.move_before(record, path)
            elif position == Gtk.TreeViewDropPosition.AFTER:
                model.move_after(record, path)
            elif self.children_field:
                model.move_into(record, path)
        else:
            model.move_after(record, (len(model) - 1,))
        Gdk.drop_finish(context, False, etime)
        selection = self.treeview.get_selection()
        selection.unselect_all()
        selection.select_path(record.get_index_path(model.group))
        if self.attributes.get('sequence'):
            record.group.set_sequence(field=self.attributes['sequence'])
        return True

    def drag_drop(self, treeview, context, x, y, time):
        treeview.stop_emission_by_name('drag-drop')
        targets = treeview.drag_dest_get_target_list()
        target = treeview.drag_dest_find_target(context, targets)
        treeview.drag_get_data(context, target, time)
        return True

    def drag_data_delete(self, treeview, context):
        treeview.stop_emission_by_name('drag-data-delete')

    def __button_press(self, treeview, event):
        if event.button == 3:
            try:
                path, col, x, y = treeview.get_path_at_pos(
                    int(event.x), int(event.y))
            except TypeError:
                # Outside row
                return False
            menu = Gtk.Menu()
            copy_item = Gtk.MenuItem(label=_('Copy'))
            copy_item.connect('activate', lambda x: self.on_copy())
            menu.append(copy_item)
            if self.editable:
                paste_item = Gtk.MenuItem(label=_('Paste'))
                paste_item.connect('activate', lambda x: self.on_paste())
                menu.append(paste_item)

            def pop(menu, group, record):
                # Don't activate actions if parent is modified
                parent = record.parent if record else None
                while parent:
                    if parent.modified:
                        break
                    parent = parent.parent
                else:
                    populate(menu, group.model_name, record)
                for col in self.treeview.get_columns():
                    if not col.get_visible() or not col.name:
                        continue
                    field = group.fields[col.name]
                    model = None
                    if field.attrs['type'] == 'many2one':
                        model = field.attrs['relation']
                        record_id = field.get(record)
                    elif field.attrs['type'] == 'reference':
                        value = field.get(record)
                        if value:
                            model, record_id = value.split(',')
                            record_id = int(record_id)
                    if not model:
                        continue
                    label = field.attrs['string']
                    context = field.get_context(record)
                    populate(
                        menu, model, record_id, title=label, field=field,
                        context=context)

            selection = treeview.get_selection()
            if selection.count_selected_rows() == 1:
                group = self.group
                if selection.get_mode() == Gtk.SelectionMode.SINGLE:
                    model = selection.get_selected()[0]
                elif selection.get_mode() == Gtk.SelectionMode.MULTIPLE:
                    model = selection.get_selected_rows()[0]
                record = model.get_value(model.get_iter(path), 0)
                pop(menu, group, record)
            menu.show_all()
            if hasattr(menu, 'popup_at_pointer'):
                menu.popup_at_pointer(event)
            else:
                menu.popup(None, None, None, event.button, event.time)
            return True  # Don't change the selection
        elif event.button == 2:
            with Window(allow_similar=True):
                self.screen.row_activate()
            return True
        return False

    def group_list_changed(self, group, signal):
        model = self.treeview.get_model()
        if model is not None:
            if signal[0] == 'record-added':
                model.added(group, signal[1])
            elif signal[0] == 'record-removed':
                model.removed(group, signal[1])
        self.display()

    def __str__(self):
        return 'ViewList (%d)' % id(self)

    def __getitem__(self, name):
        return None

    def save_width(self):
        if not CONFIG['client.save_tree_width']:
            return
        fields = {}
        last_col = None
        for col in self.treeview.get_columns():
            if col.get_visible():
                last_col = col
            if not hasattr(col, 'name') or not hasattr(col, 'width'):
                continue
            if (col.get_width() != col.width and col.get_visible()
                    and not col.get_expand()):
                fields[col.name] = col.get_width()
        # Don't set width for last visible columns
        # as it depends of the screen size
        if last_col and last_col.name in fields:
            del fields[last_col.name]

        if fields and any(fields.values()):
            model_name = self.screen.model_name
            try:
                RPCExecute('model', 'ir.ui.view_tree_width', 'set_width',
                    model_name, fields)
            except RPCException:
                pass
            self.screen.tree_column_width[model_name].update(fields)

    def destroy(self):
        self.save_width()
        self.treeview.destroy()

    def __sig_switch(self, treeview, path, column):
        if column._type == 'button':
            return
        allow_similar = False
        event = Gtk.get_current_event()
        if (event.state & Gdk.ModifierType.MOD1_MASK
                or event.state & Gdk.ModifierType.SHIFT_MASK):
            allow_similar = True
        with Window(allow_similar=allow_similar):
            if not self.screen.row_activate() and self.children_field:
                if treeview.row_expanded(path):
                    treeview.collapse_row(path)
                else:
                    treeview.expand_row(path, False)

    def __select_changed(self, tree_sel):
        previous_record = self.record
        if previous_record and previous_record not in previous_record.group:
            previous_record = None

        if tree_sel.get_mode() == Gtk.SelectionMode.SINGLE:
            model, iter_ = tree_sel.get_selected()
            if model and iter_:
                record = model.get_value(iter_, 0)
                self.record = record
            else:
                self.record = None

        elif tree_sel.get_mode() == Gtk.SelectionMode.MULTIPLE:
            model, paths = tree_sel.get_selected_rows()
            if model and paths:
                iter_ = model.get_iter(paths[0])
                record = model.get_value(iter_, 0)
                self.record = record
            else:
                self.record = None

        if self.editable and previous_record:
            def go_previous():
                self.record = previous_record
                self.set_cursor()
            if not self.screen.parent and previous_record != self.record:

                def save():
                    if not previous_record.destroyed:
                        if not previous_record.save():
                            go_previous()

                if not previous_record.validate(self.get_fields()):
                    go_previous()
                    return True
                # Delay the save to let GTK process the current event
                GLib.idle_add(save)
            elif previous_record != self.record and self.screen.pre_validate:

                def pre_validate():
                    if not previous_record.destroyed:
                        if not previous_record.pre_validate():
                            go_previous()
                # Delay the pre_validate to let GTK process the current event
                GLib.idle_add(pre_validate)
        self.update_sum()

    def set_value(self):
        if self.editable:
            self.treeview.set_value()

    def reset(self):
        pass

    def display(self, force=False):
        self.treeview.display_counter += 1
        current_record = self.record
        if (force
                or not self.treeview.get_model()
                or self.group != self.treeview.get_model().group):
            model = AdaptModelGroup(self.group, self.children_field)
            self.treeview.set_model(model)
            # __select_changed resets current_record to None
            self.record = current_record
            if current_record:
                selection = self.treeview.get_selection()
                path = current_record.get_index_path(model.group)
                selection.select_path(path)
        if not current_record:
            selection = self.treeview.get_selection()
            selection.unselect_all()
        self.treeview.queue_draw()
        if self.editable:
            self.set_state()
        self.update_arrow()
        self.update_sum()

        # Set column visibility depending on attributes and domain
        domain = []
        if self.screen.domain:
            domain.append(self.screen.domain)
        tab_domain = self.screen.screen_container.get_tab_domain()
        if tab_domain:
            domain.append(tab_domain)
        domain = simplify(domain)
        decoder = PYSONDecoder(self.screen.context)
        for column in self.treeview.get_columns():
            name = column.name
            if not name:
                continue
            widget = self.get_column_widget(column)
            widget.set_editable()
            if decoder.decode(widget.attrs.get('tree_invisible', '0')):
                column.set_visible(False)
            elif name == self.screen.exclude_field:
                column.set_visible(False)
            else:
                inv_domain = domain_inversion(domain, name)
                if not isinstance(inv_domain, bool):
                    inv_domain = simplify(inv_domain)
                unique, _, _ = unique_value(inv_domain)
                column.set_visible(not unique or bool(self.children_field))

    def set_state(self):
        record = self.record
        if record:
            for field in record.group.fields:
                field = record.group.fields.get(field, None)
                if field:
                    field.state_set(record)

    @delay
    def update_sum(self):
        selected_records = self.selected_records
        for name, label in self.sum_widgets:
            sum_ = None
            selected_sum = None
            loaded = True
            digit = 0
            field = self.group.fields[name]
            for record in self.group:
                if not record.get_loaded([name]) and record.id >= 0:
                    loaded = False
                    break
                value = field.get(record)
                if value is not None:
                    if sum_ is None:
                        sum_ = value
                    else:
                        sum_ += value
                    if record in selected_records or not selected_records:
                        if selected_sum is None:
                            selected_sum = value
                        else:
                            selected_sum += value
                    if hasattr(field, 'digits'):
                        fdigits = field.digits(record)
                        if fdigits and digit is not None:
                            digit = max(fdigits[1], digit)
                        else:
                            digit = None

            if loaded:
                if field.attrs['type'] == 'timedelta':
                    converter = field.converter(self.group)
                    selected_sum = common.timedelta.format(
                        selected_sum, converter)
                    sum_ = common.timedelta.format(sum_, converter)
                elif digit is not None:
                    selected_sum = locale.localize(
                        '{0:.{1}f}'.format(selected_sum or 0, digit), True)
                    sum_ = locale.localize(
                        '{0:.{1}f}'.format(sum_ or 0, digit), True)
                else:
                    selected_sum = locale.localize(
                        '{}'.format(selected_sum or 0), True)
                    sum_ = locale.localize('{}'.format(sum_ or 0), True)

                text = '%s / %s' % (selected_sum, sum_)
            else:
                text = '-'
            label.set_text(text)

    def set_cursor(self, new=False, reset_view=True):
        self.treeview.grab_focus()
        model = self.treeview.get_model()
        if self.record and model:
            path = self.record.get_index_path(model.group)
            if model.get_flags() & Gtk.TreeModelFlags.LIST_ONLY:
                path = (path[0],)
            focus_column, focus_cell = self.treeview.next_column(
                path, editable=new)
            if path[:-1]:
                self.treeview.expand_to_path(Gtk.TreePath(path[:-1]))
            self.treeview.scroll_to_cell(path, focus_column,
                use_align=False)
            current_path = self.treeview.get_cursor()[0]
            selected_path = \
                self.treeview.get_selection().get_selected_rows()[1]
            path = Gtk.TreePath(path)
            if (current_path != path and path not in selected_path) or new:
                self.treeview.set_cursor(path, focus_column, start_editing=new)

    @property
    def selected_records(self):
        def _func_sel_get(model, path, iter_, records):
            records.append(model.get_value(iter_, 0))
        records = []
        sel = self.treeview.get_selection()
        sel.selected_foreach(_func_sel_get, records)
        return records

    def get_selected_paths(self):
        selection = self.treeview.get_selection()
        model, rows = selection.get_selected_rows()
        id_paths = []
        for row in rows:
            path = ()
            id_path = []
            for node in row:
                path += (node,)
                iter_ = model.get_iter(path)
                id_path.append(model.get_value(iter_, 0).id)
            id_paths.append(id_path)
        return id_paths

    def select_nodes(self, nodes):
        selection = self.treeview.get_selection()
        if not nodes:
            return
        selection.unselect_all()
        scroll = False
        model = self.treeview.get_model()
        for node in nodes:
            path = path_convert_id2pos(model, node)
            if path:
                selection.select_path(Gtk.TreePath(path))
                if not scroll:
                    self.treeview.scroll_to_cell(path)
                    scroll = True

    def get_expanded_paths(self, starting_path=None, starting_id_path=None):
        # Use id instead of position
        # because the position may change between load
        if not starting_path:
            starting_path = tuple()
        if not starting_id_path:
            starting_id_path = []
        id_paths = []
        model = self.treeview.get_model()
        if starting_path:
            iter_ = model.get_iter(Gtk.TreePath(starting_path))
        else:
            iter_ = None
        for path_idx in range(model.iter_n_children(iter_)):
            path = starting_path + (path_idx,)
            expanded = self.treeview.row_expanded(Gtk.TreePath(path))
            if expanded:
                iter_ = model.get_iter(path)
                expanded_record = model.get_value(iter_, 0)
                id_path = starting_id_path + [expanded_record.id]
                id_paths.append(id_path)
                child_id_paths = self.get_expanded_paths(path, id_path)
                id_paths += child_id_paths
        return id_paths

    def expand_nodes(self, nodes):
        model = self.treeview.get_model()
        for node in nodes:
            expand_path = path_convert_id2pos(model, node)
            if expand_path:
                self.treeview.expand_to_path(Gtk.TreePath(expand_path))
