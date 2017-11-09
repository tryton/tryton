# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gobject
import gtk
import pango
import sys
import json
import locale
import gettext
from functools import wraps
from collections import defaultdict

from tryton.config import CONFIG
from tryton.common.cellrendererbutton import CellRendererButton
from tryton.common.cellrenderertoggle import CellRendererToggle
from tryton.gui.window import Window
from tryton.common.popup_menu import populate
from tryton.common import RPCExecute, RPCException, node_attributes, Tooltips
from tryton.common import domain_inversion, simplify, unique_value
from tryton.pyson import PYSONDecoder
import tryton.common as common
from . import View
from .list_gtk.editabletree import EditableTreeView, TreeView
from .list_gtk.widget import (Affix, Char, Text, Int, Boolean, URL, Date,
    Time, Float, TimeDelta, Binary, M2O, O2O, O2M, M2M, Selection, Reference,
    ProgressBar, Button, Image)

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
        gobject.idle_add(wait)
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


class AdaptModelGroup(gtk.GenericTreeModel):

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
            if (record.parent and
                    record.group is not self.group):
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
        ids2pos = {}
        pos = 0
        new_order = []
        for record in self.group:
            ids2pos[record.id] = pos
            new_order.append(pos)
            pos += 1
        pos = 0
        for obj_id in ids:
            try:
                old_pos = ids2pos[obj_id]
                if old_pos != pos:
                    new_order[old_pos] = pos
                pos += 1
            except KeyError:
                continue
        self.group.sort(lambda x, y:
            cmp(new_order[ids2pos[x.id]], new_order[ids2pos[y.id]]))
        prev = None
        for record in self.group:
            if prev:
                prev.next[id(self.group)] = record
            prev = record
        if prev:
            prev.next[id(self.group)] = None
        path = gtk.TreePath()
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
            return gtk.TREE_MODEL_LIST_ONLY
        return 0

    def on_get_n_columns(self):
        # XXX
        return 1

    def on_get_column_type(self, index):
        # XXX
        return gobject.TYPE_PYOBJECT

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


class ViewTree(View):

    def __init__(self, screen, xml, children_field):
        super(ViewTree, self).__init__(screen, xml)
        self.view_type = 'tree'
        self.widgets = defaultdict(list)
        self.state_widgets = []
        self.children_field = children_field
        self.sum_widgets = []
        self.sum_box = gtk.HBox()
        self.reload = False
        if self.attributes.get('editable'):
            self.treeview = EditableTreeView(self.attributes['editable'], self)
        else:
            self.treeview = TreeView(self)

        self.parse(xml)

        self.treeview.set_property('rules-hint', True)
        self.treeview.set_fixed_height_mode(
            all(c.get_sizing() == gtk.TREE_VIEW_COLUMN_FIXED
                for c in self.treeview.get_columns()))
        self.treeview.connect('button-press-event', self.__button_press)
        self.treeview.connect('key-press-event', self.on_keypress)
        self.treeview.connect_after('row-activated', self.__sig_switch)
        if self.children_field:
            self.treeview.connect('test-expand-row', self.test_expand_row)
            self.treeview.set_expander_column(self.treeview.get_column(0))
        self.treeview.set_rubber_banding(True)

        selection = self.treeview.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        selection.connect('changed', self.__select_changed)

        self.set_drag_and_drop()

        self.widget = gtk.VBox()
        scroll = gtk.ScrolledWindow()
        scroll.add(self.treeview)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_placement(gtk.CORNER_TOP_LEFT)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        viewport.add(scroll)
        self.widget.pack_start(viewport, expand=True, fill=True)

        self.sum_box.show()
        self.widget.pack_start(self.sum_box, expand=False, fill=False)

        self.display()

    def parse(self, xml):
        for node in xml.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            if node.tagName == 'field':
                self._parse_field(node)
            elif node.tagName == 'button':
                self._parse_button(node)

        self.add_last_column()

    def _parse_field(self, node):
        group = self.screen.group
        node_attrs = node_attributes(node)
        name = node_attrs['name']
        field = group.fields[name]
        for b_field in ('readonly', 'expand'):
            if b_field in node_attrs:
                node_attrs[b_field] = bool(int(node_attrs[b_field]))
        for i_field in ('width', 'height'):
            if i_field in node_attrs:
                node_attrs[i_field] = int(node_attrs[i_field])
        if 'widget' not in node_attrs:
            node_attrs['widget'] = field.attrs['type']

        for attr in ('relation', 'domain', 'selection',
                'relation_field', 'string', 'views', 'invisible',
                'add_remove', 'sort', 'context', 'size', 'filename',
                'autocomplete', 'translate', 'create', 'delete',
                'selection_change_with', 'schema_model'):
            if (attr in field.attrs
                    and attr not in node_attrs):
                node_attrs[attr] = field.attrs[attr]

        Widget = self.get_widget(node_attrs['widget'])
        widget = Widget(self, node_attrs)
        self.widgets[name].append(widget)

        column = gtk.TreeViewColumn(field.attrs['string'])
        column._type = 'field'
        column.name = name

        prefixes = []
        suffixes = []
        if node_attrs['widget'] in ('url', 'email', 'callto', 'sip'):
            prefixes.append(Affix(self, node_attrs,
                    protocol=node_attrs['widget']))
        if 'icon' in node_attrs:
            prefixes.append(Affix(self, node_attrs))
        for affix in node.childNodes:
            affix_attrs = node_attributes(affix)
            if 'name' not in affix_attrs:
                affix_attrs['name'] = name
            if affix.tagName == 'prefix':
                list_ = prefixes
            else:
                list_ = suffixes
            list_.append(Affix(self, affix_attrs))

        for prefix in prefixes:
            column.pack_start(prefix.renderer, expand=False)
            column.set_cell_data_func(prefix.renderer,
                prefix.setter)

        column.pack_start(widget.renderer, expand=True)
        column.set_cell_data_func(widget.renderer, widget.setter)

        for suffix in suffixes:
            column.pack_start(suffix.renderer, expand=False)
            column.set_cell_data_func(suffix.renderer,
                suffix.setter)

        self.set_column_widget(column, field, node_attrs)
        self.set_column_width(column, field, node_attrs)

        if (not self.attributes.get('sequence')
                and not self.children_field
                and field.attrs.get('sortable', True)):
            column.connect('clicked', self.sort_model)

        self.treeview.append_column(column)

        self.add_sum(node_attrs)

    def _parse_button(self, node):
        node_attrs = node_attributes(node)
        widget = Button(self, node_attrs)
        self.state_widgets.append(widget)

        column = gtk.TreeViewColumn(node_attrs.get('string', ''),
            widget.renderer)
        column._type = 'button'
        column.name = None
        column.set_cell_data_func(widget.renderer, widget.setter)

        self.set_column_widget(column, None, node_attrs, arrow=False)
        self.set_column_width(column, None, node_attrs)

        decoder = PYSONDecoder(self.screen.context)
        column.set_visible(
            not decoder.decode(node_attrs.get('tree_invisible', '0')))

        self.treeview.append_column(column)

    WIDGETS = {
        'char': Char,
        'many2one': M2O,
        'date': Date,
        'one2many': O2M,
        'many2many': M2M,
        'selection': Selection,
        'float': Float,
        'numeric': Float,
        'timedelta': TimeDelta,
        'integer': Int,
        'biginteger': Int,
        'time': Time,
        'boolean': Boolean,
        'text': Text,
        'url': URL,
        'email': URL,
        'callto': URL,
        'sip': URL,
        'progressbar': ProgressBar,
        'reference': Reference,
        'one2one': O2O,
        'binary': Binary,
        'image': Image,
        }

    @classmethod
    def get_widget(cls, name):
        return cls.WIDGETS[name]

    def set_column_widget(self, column, field, attributes, arrow=True):
        hbox = gtk.HBox(False, 2)
        label = gtk.Label(attributes['string'])
        if field and self.editable:
            required = field.attrs.get('required')
            readonly = field.attrs.get('readonly')
            if (required or not readonly) and hasattr(pango, 'AttrWeight'):
                # FIXME when Pango.attr_weight_new is introspectable
                attrlist = pango.AttrList()
                if required:
                    attrlist.insert(pango.AttrWeight(pango.WEIGHT_BOLD, 0, -1))
                if not readonly:
                    attrlist.change(pango.AttrStyle(pango.STYLE_ITALIC, 0, -1))
                label.set_attributes(attrlist)
        label.show()
        help = None
        if field and field.attrs.get('help'):
            help = field.attrs['help']
        elif attributes.get('help'):
            help = attributes['help']
        if help:
            tooltips = Tooltips()
            tooltips.set_tip(label, help)
            tooltips.enable()
        if arrow:
            arrow_widget = gtk.Arrow(gtk.ARROW_NONE, gtk.SHADOW_NONE)
            arrow_widget.show()
            column.arrow = arrow_widget
        hbox.pack_start(label, True, True, 0)
        if arrow:
            hbox.pack_start(arrow_widget, False, False, 0)
            column.set_clickable(True)
        hbox.show()
        column.set_widget(hbox)
        column.set_alignment(0.5)

    def set_column_width(self, column, field, attributes):
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

        width = self.screen.tree_column_width[self.screen.model_name].get(
            column.name)
        if not width:
            if 'width' in attributes:
                width = int(attributes['width'])
            elif field:
                width = default_width.get(field.attrs['type'], 100)
            else:
                width = 80
        column.width = width
        if width > 0:
            column.set_fixed_width(width)
        column.set_min_width(1)

        expand = attributes.get('expand', False)
        column.set_expand(expand)
        column.set_resizable(True)
        if not field or field.attrs['type'] != 'text':
            column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)

    def get_column_widget(self, column):
        'Return the widget of the column'
        idx = [c for c in self.treeview.get_columns()
            if c.name == column.name].index(column)
        return self.widgets[column.name][idx]

    def add_sum(self, attributes):
        if 'sum' not in attributes:
            return
        if gtk.widget_get_default_direction() == gtk.TEXT_DIR_RTL:
            text = _(':') + attributes['sum']
        else:
            text = attributes['sum'] + _(':')
        label, sum_ = gtk.Label(text), gtk.Label()

        hbox = gtk.HBox()
        hbox.pack_start(label, expand=True, fill=False, padding=2)
        hbox.pack_start(sum_, expand=True, fill=False, padding=2)
        hbox.show_all()
        self.sum_box.pack_start(hbox, expand=False, fill=False)

        self.sum_widgets.append((attributes['name'], sum_))

    def sort_model(self, column):
        for col in self.treeview.get_columns():
            if col != column and getattr(col, 'arrow', None):
                col.arrow.set(gtk.ARROW_NONE, gtk.SHADOW_NONE)
        self.screen.order = self.screen.default_order
        if column.arrow.props.arrow_type == gtk.ARROW_NONE:
            column.arrow.set(gtk.ARROW_DOWN, gtk.SHADOW_IN)
            self.screen.order = [(column.name, 'ASC')]
        else:
            if column.arrow.props.arrow_type == gtk.ARROW_DOWN:
                column.arrow.set(gtk.ARROW_UP, gtk.SHADOW_IN)
                self.screen.order = [(column.name, 'DESC')]
            else:
                column.arrow.set(gtk.ARROW_NONE, gtk.SHADOW_NONE)
        model = self.treeview.get_model()
        unsaved_records = [x for x in model.group if x.id < 0]
        search_string = self.screen.screen_container.get_text() or u''
        if (self.screen.search_count == len(model)
                or unsaved_records
                or self.screen.parent):
            ids = self.screen.search_filter(
                search_string=search_string, only_ids=True)
            model.sort(ids)
        else:
            self.screen.search_filter(search_string=search_string)

    def add_last_column(self):
        for column in self.treeview.get_columns():
            if column.get_expand():
                break
        else:
            column = gtk.TreeViewColumn()
            column._type = 'fill'
            column.name = None
            column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            self.treeview.append_column(column)

    def set_drag_and_drop(self):
        dnd = False
        if self.children_field:
            children = self.screen.group.fields.get(self.children_field)
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

        if not dnd:
            return

        self.treeview.enable_model_drag_dest(
            [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)],
            gtk.gdk.ACTION_MOVE)
        self.treeview.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK | gtk.gdk.BUTTON3_MASK,
            [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)],
            gtk.gdk.ACTION_MOVE)
        # XXX have to set manually because enable_model_drag_source
        # does not set the mask
        # https://bugzilla.gnome.org/show_bug.cgi?id=756177
        self.treeview.drag_source_set(
            gtk.gdk.BUTTON1_MASK | gtk.gdk.BUTTON3_MASK,
            [gtk.TargetEntry.new(
                    'MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)],
            gtk.gdk.ACTION_MOVE)

        self.treeview.connect("drag-data-get", self.drag_data_get)
        self.treeview.connect('drag-data-received',
            self.drag_data_received)
        self.treeview.connect('drag-drop', self.drag_drop)
        self.treeview.connect('drag-data-delete', self.drag_data_delete)

    @property
    def modified(self):
        return False

    @property
    def editable(self):
        return bool(getattr(self.treeview, 'editable', False))

    def get_fields(self):
        return [col.name for col in self.treeview.get_columns() if col.name]

    def get_buttons(self):
        return [b for b in self.state_widgets
            if isinstance(b.renderer, CellRendererButton)]

    def on_keypress(self, widget, event):
        control_mask = gtk.gdk.CONTROL_MASK
        if sys.platform == 'darwin':
            control_mask = gtk.gdk.MOD2_MASK
        if (event.keyval == gtk.keysyms.c
                and event.state & control_mask):
            self.on_copy()
            return False
        if (event.keyval == gtk.keysyms.v
                and event.state & control_mask):
            self.on_paste()
            return False

    def test_expand_row(self, widget, iter_, path):
        model = widget.get_model()
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
        for clipboard_type in (gtk.gdk.SELECTION_CLIPBOARD,
                gtk.gdk.SELECTION_PRIMARY):
            clipboard = self.treeview.get_clipboard(clipboard_type)
            targets = [
                ('STRING', 0, 0),
                ('TEXT', 0, 1),
                ('COMPOUND_TEXT', 0, 2),
                ('UTF8_STRING', 0, 3)
            ]
            selection = self.treeview.get_selection()
            # Set to clipboard directly if not too much selected rows
            # to speed up paste
            # Don't use set_with_data on mac see:
            # http://bugzilla.gnome.org/show_bug.cgi?id=508601
            if selection.count_selected_rows() < 100 \
                    or sys.platform == 'darwin':
                data = []
                selection.selected_foreach(self.copy_foreach, data)
                clipboard.set_text('\n'.join(data), -1)
            else:
                clipboard.set_with_data(targets, self.copy_get_func,
                        self.copy_clear_func, selection)

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

    def copy_get_func(self, clipboard, selectiondata, info, selection):
        data = []
        selection.selected_foreach(self.copy_foreach, data)
        clipboard.set_text('\n'.join(data), -1)
        del data
        return

    def copy_clear_func(self, clipboard, selection):
        del selection
        return

    def on_paste(self):
        if not self.editable:
            return

        def unquote(value):
            if value[:1] == '"' and value[-1:] == '"':
                return value[1:-1]
            return value
        data = []
        for clipboard_type in (gtk.gdk.SELECTION_CLIPBOARD,
                gtk.gdk.SELECTION_PRIMARY):
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
        if self.screen.current_record:
            record = self.screen.current_record
            group = record.group
            idx = group.index(record)
        else:
            group = self.screen.group
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
        self.screen.current_record = record
        self.screen.display(set_cursor=True)

    def drag_data_get(self, treeview, context, selection, target_id,
            etime):
        treeview.emit_stop_by_name('drag-data-get')

        def _func_sel_get(model, path, iter_, data):
            value = model.get_value(iter_, 0)
            data.append(json.dumps(
                    value.get_path(model.group), separators=(',', ':')))
        data = []
        treeselection = treeview.get_selection()
        treeselection.selected_foreach(_func_sel_get, data)
        if not data:
            return
        data = str(data[0])
        selection.set(selection.get_target(), 8, data)
        return True

    def drag_data_received(self, treeview, context, x, y, selection,
            info, etime):
        treeview.emit_stop_by_name('drag-data-received')
        if self.attributes.get('sequence'):
            field = self.screen.group.fields[self.attributes['sequence']]
            for record in self.screen.group:
                if field.get_state_attrs(
                        record).get('readonly', False):
                    return
        try:
            selection_data = selection.data
        except AttributeError:
            selection_data = selection.get_data()
        if not selection_data:
            return

        # Don't received if the treeview was editing because it breaks the
        # internal state of the cursor.
        cursor, column = treeview.get_cursor()
        if column:
            for renderer in column.get_cell_renderers():
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
            if position in (gtk.TREE_VIEW_DROP_BEFORE,
                    gtk.TREE_VIEW_DROP_AFTER):
                check_path = path[:-1]
            if not check_recursion(record_path, check_path):
                return
            if position == gtk.TREE_VIEW_DROP_BEFORE:
                model.move_before(record, path)
            elif position == gtk.TREE_VIEW_DROP_AFTER:
                model.move_after(record, path)
            elif self.children_field:
                model.move_into(record, path)
        else:
            model.move_after(record, (len(model) - 1,))
        if hasattr(gtk.gdk, 'drop_finish'):
            gtk.gdk.drop_finish(context, False, etime)
        else:
            context.drop_finish(False, etime)
        if self.attributes.get('sequence'):
            record.group.set_sequence(field=self.attributes['sequence'])
        return True

    def drag_drop(self, treeview, context, x, y, time):
        treeview.emit_stop_by_name('drag-drop')
        targets = treeview.drag_dest_get_target_list()
        target = treeview.drag_dest_find_target(context, targets)
        treeview.drag_get_data(context, target, time)
        return True

    def drag_data_delete(self, treeview, context):
        treeview.emit_stop_by_name('drag-data-delete')

    def __button_press(self, treeview, event):
        if event.button == 3:
            try:
                path, col, x, y = treeview.get_path_at_pos(
                    int(event.x), int(event.y))
            except TypeError:
                # Outside row
                return False
            menu = gtk.Menu()
            copy_item = gtk.ImageMenuItem('gtk-copy')
            copy_item.set_use_stock(True)
            copy_item.connect('activate', lambda x: self.on_copy())
            menu.append(copy_item)
            if self.editable:
                paste_item = gtk.ImageMenuItem('gtk-paste')
                paste_item.set_use_stock(True)
                paste_item.connect('activate', lambda x: self.on_paste())
                menu.append(paste_item)
            menu.show_all()
            menu.popup(None, None, None, event.button, event.time)

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
                menu.show_all()

            selection = treeview.get_selection()
            if selection.count_selected_rows() == 1:
                group = self.screen.group
                if selection.get_mode() == gtk.SELECTION_SINGLE:
                    model = selection.get_selected()[0]
                elif selection.get_mode() == gtk.SELECTION_MULTIPLE:
                    model = selection.get_selected_rows()[0]
                record = model.get_value(model.get_iter(path), 0)
                # Delay filling of popup as it can take time
                gobject.idle_add(pop, menu, group, record)
            return True  # Don't change the selection
        elif event.button == 2:
            event.button = 1
            event.state |= gtk.gdk.MOD1_MASK
            treeview.emit('button-press-event', event)
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

    def save_width_height(self):
        if not CONFIG['client.save_width_height']:
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

        if fields and any(fields.itervalues()):
            model_name = self.screen.model_name
            try:
                RPCExecute('model', 'ir.ui.view_tree_width', 'set_width',
                    model_name, fields)
            except RPCException:
                pass
            self.screen.tree_column_width[model_name].update(fields)

    def destroy(self):
        self.save_width_height()
        self.treeview.destroy()

    def __sig_switch(self, treeview, path, column):
        if column._type == 'button':
            return
        allow_similar = False
        event = gtk.get_current_event()
        if (event.state & gtk.gdk.MOD1_MASK
                or event.state & gtk.gdk.SHIFT_MASK):
            allow_similar = True
        with Window(allow_similar=allow_similar):
            if not self.screen.row_activate() and self.children_field:
                if treeview.row_expanded(path):
                    treeview.collapse_row(path)
                else:
                    treeview.expand_row(path, False)

    def __select_changed(self, tree_sel):
        previous_record = self.screen.current_record
        if previous_record and previous_record not in previous_record.group:
            previous_record = None

        if tree_sel.get_mode() == gtk.SELECTION_SINGLE:
            model, iter_ = tree_sel.get_selected()
            if model and iter_:
                record = model.get_value(iter_, 0)
                self.screen.current_record = record
            else:
                self.screen.current_record = None

        elif tree_sel.get_mode() == gtk.SELECTION_MULTIPLE:
            model, paths = tree_sel.get_selected_rows()
            if model and paths:
                iter_ = model.get_iter(paths[0])
                record = model.get_value(iter_, 0)
                self.screen.current_record = record
            else:
                self.screen.current_record = None

        if self.editable and previous_record:
            def go_previous():
                self.screen.current_record = previous_record
                self.set_cursor()
            if (not self.screen.parent
                    and previous_record != self.screen.current_record):

                def save():
                    if not previous_record.destroyed:
                        if not previous_record.save():
                            go_previous()

                if not previous_record.validate(self.get_fields()):
                    go_previous()
                    return True
                # Delay the save to let GTK process the current event
                gobject.idle_add(save)
            elif (previous_record != self.screen.current_record
                    and self.screen.pre_validate):

                def pre_validate():
                    if not previous_record.destroyed:
                        if not previous_record.pre_validate():
                            go_previous()
                # Delay the pre_validate to let GTK process the current event
                gobject.idle_add(pre_validate)
        self.update_sum()

    def set_value(self):
        if self.editable:
            self.treeview.set_value()

    def reset(self):
        pass

    def display(self):
        self.treeview.display_counter += 1
        current_record = self.screen.current_record
        if (self.reload
                or not self.treeview.get_model()
                or (self.screen.group !=
                    self.treeview.get_model().group)):
            model = AdaptModelGroup(self.screen.group,
                    self.children_field)
            self.treeview.set_model(model)
            # __select_changed resets current_record to None
            self.screen.current_record = current_record
            if current_record:
                selection = self.treeview.get_selection()
                path = current_record.get_index_path(model.group)
                selection.select_path(path)
        self.reload = False
        if not current_record:
            selection = self.treeview.get_selection()
            selection.unselect_all()
        self.treeview.queue_draw()
        if self.editable:
            self.set_state()
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
        record = self.screen.current_record
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
            field = self.screen.group.fields[name]
            for record in self.screen.group:
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
                    converter = self.screen.context.get(
                        field.attrs.get('converter'))
                    selected_sum = common.timedelta.format(
                        selected_sum, converter)
                    sum_ = common.timedelta.format(sum_, converter)
                elif digit:
                    selected_sum = locale.format(
                        '%.*f', (digit, selected_sum or 0), True)
                    sum_ = locale.format('%.*f', (digit, sum_ or 0), True)
                else:
                    selected_sum = locale.format(
                        '%s', selected_sum or 0, True)
                    sum_ = locale.format('%s', sum_ or 0, True)

                text = '%s / %s' % (selected_sum, sum_)
            else:
                text = '-'
            label.set_text(text)

    def set_cursor(self, new=False, reset_view=True):
        self.treeview.grab_focus()
        model = self.treeview.get_model()
        if self.screen.current_record and model:
            path = self.screen.current_record.get_index_path(model.group)
            if model.get_flags() & gtk.TREE_MODEL_LIST_ONLY:
                path = (path[0],)
            focus_column = self.treeview.next_column(path, editable=new)
            if path[:-1]:
                self.treeview.expand_to_path(gtk.TreePath(path[:-1]))
            self.treeview.scroll_to_cell(path, focus_column,
                use_align=False)
            current_path = self.treeview.get_cursor()[0]
            selected_path = \
                self.treeview.get_selection().get_selected_rows()[1]
            path = gtk.TreePath(path)
            if (current_path != path and path not in selected_path) or new:
                self.treeview.set_cursor(path, focus_column, new)

    @property
    def selected_records(self):
        def _func_sel_get(model, path, iter_, records):
            records.append(model.get_value(iter_, 0))
        records = []
        sel = self.treeview.get_selection()
        sel.selected_foreach(_func_sel_get, records)
        return records

    def unset_editable(self):
        self.treeview.editable = False
        for col in self.treeview.get_columns():
            for renderer in col.get_cell_renderers():
                if isinstance(renderer, CellRendererToggle):
                    renderer.set_property('activatable', False)
                elif isinstance(renderer,
                        (gtk.CellRendererProgress, CellRendererButton,
                            gtk.CellRendererPixbuf)):
                    pass
                else:
                    renderer.set_property('editable', False)

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
                selection.select_path(gtk.TreePath(path))
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
            iter_ = model.get_iter(gtk.TreePath(starting_path))
        else:
            iter_ = None
        for path_idx in range(model.iter_n_children(iter_)):
            path = starting_path + (path_idx,)
            expanded = self.treeview.row_expanded(gtk.TreePath(path))
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
                self.treeview.expand_to_path(gtk.TreePath(expand_path))
