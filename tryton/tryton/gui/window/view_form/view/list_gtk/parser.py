#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import os
import gobject
import tempfile
import gtk
import locale
import gettext
import webbrowser

from functools import wraps, partial

from editabletree import EditableTreeView, TreeView
from tryton.gui.window.view_form.view.interface import ParserInterface
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm
from tryton.gui.window.view_form.screen import Screen
import tryton.rpc as rpc
from tryton.common import COLORS, node_attributes, \
        file_selection, file_open
import tryton.common as common
from tryton.common.cellrendererbutton import CellRendererButton
from tryton.common.cellrendererdate import CellRendererDate
from tryton.common.cellrenderertext import CellRendererText, \
    CellRendererTextCompletion
from tryton.common.cellrenderertoggle import CellRendererToggle
from tryton.common.cellrenderercombo import CellRendererCombo
from tryton.common.cellrendererinteger import CellRendererInteger
from tryton.common.cellrendererfloat import CellRendererFloat
from tryton.common.cellrendererbinary import CellRendererBinary
from tryton.common.cellrendererclickablepixbuf import \
    CellRendererClickablePixbuf
from tryton.translate import date_format
from tryton.common import RPCExecute, RPCException
from tryton.common.completion import get_completion, update_completion
from tryton.common.selection import SelectionMixin

_ = gettext.gettext


def send_keys(renderer, editable, position, treeview):
    editable.connect('key_press_event', treeview.on_keypressed)
    editable.editing_done_id = editable.connect('editing_done',
            treeview.on_editing_done)
    if isinstance(editable, (gtk.ComboBoxEntry, gtk.ComboBox)):
        editable.connect('changed', treeview.on_editing_done)


def sort_model(column, treeview, screen):
    for col in treeview.get_columns():
        if col != column:
            col.arrow_show = False
            col.arrow.hide()
    screen.order = None
    if not column.arrow_show:
        column.arrow_show = True
        column.arrow.set(gtk.ARROW_DOWN, gtk.SHADOW_IN)
        column.arrow.show()
        screen.order = [(column.name, 'ASC')]
    else:
        if column.arrow.get_property('arrow-type') == gtk.ARROW_DOWN:
            column.arrow.set(gtk.ARROW_UP, gtk.SHADOW_IN)
            screen.order = [(column.name, 'DESC')]
        else:
            column.arrow_show = False
            column.arrow.hide()
    store = treeview.get_model()
    unsaved_records = [x for x in store.group if x.id < 0]
    search_string = screen.screen_container.get_text() or u''
    if screen.search_count == len(store) or unsaved_records or screen.parent:
        ids = screen.search_filter(search_string=search_string, only_ids=True)
        store.sort(ids)
    else:
        screen.search_filter(search_string=search_string)


def realized(func):
    "Decorator for treeview realized"
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if (hasattr(self.treeview, 'get_realized')
                and not self.treeview.get_realized()):
            return
        return func(self, *args, **kwargs)
    return wrapper


class ParserTree(ParserInterface):

    def __init__(self, parent=None, attrs=None, screen=None,
            children_field=None):
        super(ParserTree, self).__init__(parent, attrs, screen,
            children_field=children_field)
        self.treeview = None

    def parse(self, model_name, root_node, fields):
        dict_widget = {}
        state_widgets = []
        attrs = node_attributes(root_node)
        on_write = attrs.get('on_write', '')
        editable = attrs.get('editable', False)
        if editable:
            treeview = EditableTreeView(editable)
        else:
            treeview = TreeView()
            treeview.cells = {}
        treeview.sequence = attrs.get('sequence', False)
        treeview.colors = attrs.get('colors', '"black"')
        treeview.keyword_open = attrs.get('keyword_open', False)
        self.treeview = treeview
        treeview.set_property('rules-hint', True)
        if not self.title:
            self.title = attrs.get('string', 'Unknown')
        tooltips = common.Tooltips()
        expandable = False

        for node in root_node.childNodes:
            node_attrs = node_attributes(node)
            if node.localName == 'field':
                fname = str(node_attrs['name'])
                for boolean_fields in ('readonly', 'required', 'expand'):
                    if boolean_fields in node_attrs:
                        node_attrs[boolean_fields] = \
                            bool(int(node_attrs[boolean_fields]))
                if fname not in fields:
                    continue
                for attr_name in ('relation', 'domain', 'selection',
                        'relation_field', 'string', 'views', 'invisible',
                        'add_remove', 'sort', 'context', 'filename',
                        'selection_change_with'):
                    if attr_name in fields[fname].attrs and \
                            not attr_name in node_attrs:
                        node_attrs[attr_name] = fields[fname].attrs[attr_name]
                cell_type = node_attrs.get('widget',
                    fields[fname].attrs['type'])
                cell = CELLTYPES.get(cell_type)(fname, model_name,
                    treeview, node_attrs)
                treeview.cells[fname] = cell
                renderer = cell.renderer

                readonly = not (editable and not node_attrs.get('readonly',
                    fields[fname].attrs.get('readonly', False)))
                if isinstance(renderer, CellRendererToggle):
                    renderer.set_property('activatable', not readonly)
                elif isinstance(renderer,
                        (gtk.CellRendererProgress, CellRendererButton)):
                    pass
                else:
                    renderer.set_property('editable', not readonly)
                if (not readonly
                        and not isinstance(renderer, CellRendererBinary)):
                    renderer.connect_after('editing-started', send_keys,
                            treeview)

                col = gtk.TreeViewColumn(fields[fname].attrs['string'])

                prefixes = []
                suffixes = []
                if cell_type in ('url', 'email', 'callto', 'sip'):
                    prefixes.append(Affix(fname, self.treeview, node_attrs,
                            protocol=cell_type))
                if 'icon' in node_attrs:
                    prefixes.append(Affix(fname, self.treeview, node_attrs))
                for affix in node.childNodes:
                    affix_attrs = node_attributes(affix)
                    if affix.localName == 'prefix':
                        list_ = prefixes
                    else:
                        list_ = suffixes
                    list_.append(Affix(fname, self.treeview, affix_attrs))

                for prefix in prefixes:
                    col.pack_start(prefix.renderer, expand=False)
                    col.set_cell_data_func(prefix.renderer, prefix.setter)

                col.pack_start(renderer, expand=True)
                col.set_cell_data_func(renderer, cell.setter)
                col.name = fname

                for suffix in suffixes:
                    col.pack_start(suffix.renderer, expand=False)
                    col.set_cell_data_func(suffix.renderer, suffix.setter)

                hbox = gtk.HBox(False, 2)
                label = gtk.Label(fields[fname].attrs['string'])
                label.show()
                help = fields[fname].attrs['string']
                if fields[fname].attrs.get('help'):
                    help += '\n' + fields[fname].attrs['help']
                tooltips.set_tip(label, help)
                tooltips.enable()
                arrow = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_IN)
                col.arrow = arrow
                col.arrow_show = False
                hbox.pack_start(label, True, True, 0)
                hbox.pack_start(arrow, False, False, 0)
                hbox.show()
                col.set_widget(hbox)

                col._type = fields[fname].attrs['type']
                col.set_clickable(True)
                twidth = {
                    'integer': 60,
                    'biginteger': 60,
                    'float': 80,
                    'numeric': 80,
                    'float_time': 100,
                    'date': 110,
                    'datetime': 160,
                    'selection': 90,
                    'char': 100,
                    'one2many': 50,
                    'many2many': 50,
                    'boolean': 20,
                    'binary': 200,
                }
                width = self.screen.tree_column_width[model_name].get(fname)
                if not width:
                    if 'width' in node_attrs:
                        width = int(node_attrs['width'])
                    else:
                        width = twidth.get(fields[fname].attrs['type'], 100)
                col.width = width
                if width > 0:
                    col.set_fixed_width(width)
                col.set_min_width(1)
                expand = node_attrs.get('expand', False)
                col.set_expand(expand)
                expandable |= expand
                if (not treeview.sequence
                        and not self.children_field
                        and fields[fname].attrs.get('sortable', True)):
                    col.connect('clicked', sort_model, treeview, self.screen)
                col.set_resizable(True)
                col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
                col.set_visible(not node_attrs.get('tree_invisible',
                    fields[fname].attrs.get('tree_invisible', False)))
                if fname == self.screen.exclude_field:
                    col.set_visible(False)
                i = treeview.append_column(col)
                if 'sum' in node_attrs and fields[fname].attrs['type'] \
                        in ('integer', 'biginteger', 'float', 'numeric',
                            'float_time'):
                    label = gtk.Label(node_attrs['sum'] + _(': '))
                    label_sum = gtk.Label()
                    if isinstance(fields[fname].attrs.get('digits'),
                            basestring):
                        digits = 2
                    else:
                        digits = fields[fname].attrs.get('digits', (16, 2))[1]
                    dict_widget[i] = (fname, label, label_sum, digits)
            elif node.localName == 'button':
                #TODO add shortcut
                cell = Button(treeview, self.screen, node_attrs)
                state_widgets.append(cell)
                renderer = cell.renderer
                string = node_attrs.get('string', _('Unknown'))
                col = gtk.TreeViewColumn(string, renderer)
                col.name = None

                label = gtk.Label(string)
                label.show()
                help = string
                if node_attrs.get('help'):
                    help += '\n' + node_attrs['help']
                tooltips.set_tip(label, help)
                tooltips.enable()
                arrow = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_IN)
                col.arrow = arrow
                col.arrow_show = False
                col.set_widget(label)

                col._type = 'button'
                col.set_cell_data_func(renderer, cell.setter)
                if 'width' in node_attrs:
                    width = int(node_attrs['width'])
                else:
                    width = 80
                col.width = width
                if width > 0:
                    col.set_fixed_width(width)
                col.set_resizable(True)
                col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
                i = treeview.append_column(col)
        if not expandable:
            col = gtk.TreeViewColumn()
            col.name = None
            arrow = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_IN)
            col.arrow = arrow
            col.arrow_show = False
            col._type = 'fill'
            col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            treeview.append_column(col)
        treeview.set_fixed_height_mode(True)
        return treeview, dict_widget, state_widgets, on_write, [], None


class Affix(object):

    def __init__(self, field_name, treeview, attrs, protocol=None):
        super(Affix, self).__init__()
        self.field_name = attrs.get('name', field_name)
        self.attrs = attrs
        self.protocol = protocol
        self.icon = attrs.get('icon')
        if protocol:
            self.renderer = CellRendererClickablePixbuf()
            self.renderer.connect('clicked', self.clicked)
            if not self.icon:
                self.icon = 'tryton-web-browser'
        elif self.icon:
            self.renderer = gtk.CellRendererPixbuf()
        else:
            self.renderer = gtk.CellRendererText()
        self.treeview = treeview

    @realized
    def setter(self, column, cell, store, iter_):
        record = store.get_value(iter_, 0)
        field = record[self.field_name]
        field.state_set(record, states=('invisible',))
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible)
        if self.icon:
            if self.icon in record.group.fields:
                value = record[self.icon].get_client(record) or ''
            else:
                value = self.icon
            common.ICONFACTORY.register_icon(value)
            pixbuf = self.treeview.render_icon(stock_id=value,
                size=gtk.ICON_SIZE_BUTTON, detail=None)
            cell.set_property('pixbuf', pixbuf)
        else:
            text = self.attrs.get('string', '')
            if not text:
                text = field.get_client(record) or ''
            cell.set_property('text', text)

    def clicked(self, renderer, path):
        store = self.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        value = record[self.field_name].get(record)
        if value:
            if self.protocol == 'email':
                value = 'mailto:%s' % value
            elif self.protocol == 'callto':
                value = 'callto:%s' % value
            elif self.protocol == 'sip':
                value = 'sip:%s' % value
            webbrowser.open(value, new=2)


class Char(object):

    def __init__(self, field_name, model_name, treeview, attrs=None,
            renderer=None):
        super(Char, self).__init__()
        self.field_name = field_name
        self.model_name = model_name
        self.attrs = attrs or {}
        if renderer is None:
            renderer = CellRendererText
        self.renderer = renderer()
        self.renderer.connect('editing-started', self.editing_started)
        self.treeview = treeview

    @realized
    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        text = self.get_textual_value(record)

        if isinstance(cell, CellRendererToggle):
            cell.set_active(bool(text))
        else:
            cell.set_sensitive(not (record.deleted or record.removed))
            if isinstance(cell,
                    (CellRendererText, CellRendererDate, CellRendererCombo)):
                cell.set_property('strikethrough', record.deleted)
            cell.set_property('text', text)
            fg_color = self.get_color(record)
            cell.set_property('foreground', fg_color)
            if fg_color == 'black':
                cell.set_property('foreground-set', False)
            else:
                cell.set_property('foreground-set', True)

        field = record[self.field_name]

        if self.attrs.get('type', field.attrs.get('type')) in \
                ('float', 'integer', 'biginteger', 'boolean',
                'numeric', 'float_time'):
            align = 1
        else:
            align = 0

        states = ('invisible',)
        if hasattr(self.treeview, 'editable') \
                and self.treeview.editable:
            states = ('readonly', 'required', 'invisible')

        field.state_set(record, states=states)
        invisible = field.get_state_attrs(record).get('invisible', False)
        cell.set_property('visible', not invisible)

        if hasattr(self.treeview, 'editable') \
                and self.treeview.editable:
            readonly = self.attrs.get('readonly',
                field.get_state_attrs(record).get('readonly', False))
            if invisible:
                readonly = True

            if not isinstance(cell, CellRendererToggle):
                bg_color = 'white'
                if not field.get_state_attrs(record).get('valid', True):
                    bg_color = COLORS.get('invalid', 'white')
                elif bool(int(
                            field.get_state_attrs(record).get('required', 0))):
                    bg_color = COLORS.get('required', 'white')
                cell.set_property('background', bg_color)
                if bg_color == 'white':
                    cell.set_property('background-set', False)
                else:
                    cell.set_property('background-set', True)
                    cell.set_property('foreground-set',
                        not (record.deleted or record.removed))

            if isinstance(cell, CellRendererToggle):
                cell.set_property('activatable', not readonly)
            elif isinstance(cell,
                    (gtk.CellRendererProgress, CellRendererButton)):
                pass
            else:
                cell.set_property('editable', not readonly)

        cell.set_property('xalign', align)

    def get_color(self, record):
        return record.expr_eval(self.treeview.colors)

    def open_remote(self, record, create, changed=False, text=None,
            callback=None):
        raise NotImplementedError

    def get_textual_value(self, record):
        if not record:
            return ''
        return record[self.field_name].get_client(record)

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        field.set_client(record, text)
        if callback:
            callback()

    def editing_started(self, cell, editable, path):
        return False

    def _get_record_field(self, path):
        store = self.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        field = record.group.fields[self.field_name]
        return record, field


class Int(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None,
            renderer=None):
        if renderer is None:
            renderer = CellRendererInteger
        super(Int, self).__init__(field_name, model_name, treeview,
            attrs=attrs, renderer=renderer)
        self.factor = float(attrs.get('factor', 1))

    def get_textual_value(self, record):
        if not record:
            return ''
        return record[self.field_name].get_client(record, factor=self.factor)

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        field.set_client(record, text, factor=self.factor)
        if callback:
            callback()


class Boolean(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None,
            renderer=None):
        if renderer is None:
            renderer = CellRendererToggle
        super(Boolean, self).__init__(field_name, model_name, treeview,
            attrs=attrs, renderer=renderer)
        self.renderer.connect('toggled', self._sig_toggled)

    def _sig_toggled(self, renderer, path):
        store = self.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        field = record[self.field_name]
        if not self.attrs.get('readonly',
                field.get_state_attrs(record).get('readonly', False)):
            value = record[self.field_name].get_client(record)
            record[self.field_name].set_client(record, int(not value))
            self.treeview.set_cursor(path)
        return True


class URL(Char):

    @realized
    def setter(self, column, cell, store, iter):
        super(URL, self).setter(column, cell, store, iter)
        record = store.get_value(iter, 0)
        field = record[self.field_name]
        field.state_set(record, states=('readonly',))
        readonly = field.get_state_attrs(record).get('readonly', False)
        cell.set_property('visible', not readonly)


class Date(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None,
            renderer=None):
        if renderer is None:
            renderer = partial(CellRendererDate, date_format())
        super(Date, self).__init__(field_name, model_name, treeview,
            attrs=attrs, renderer=renderer)
        self.renderer.connect('editing-started', self.editing_started)


class Datetime(Date):

    @realized
    def setter(self, column, cell, store, iter):
        super(Datetime, self).setter(column, cell, store, iter)
        record = store.get_value(iter, 0)
        field = record[self.field_name]
        time_format = field.time_format(record)
        self.renderer.format = date_format() + ' ' + time_format


class Time(Date):

    @realized
    def setter(self, column, cell, store, iter):
        super(Time, self).setter(column, cell, store, iter)
        record = store.get_value(iter, 0)
        field = record[self.field_name]
        time_format = field.time_format(record)
        self.renderer.format = time_format


class Float(Int):

    def __init__(self, field_name, model_name, treeview, attrs=None,
            renderer=None):
        if renderer is None:
            renderer = CellRendererFloat
        super(Float, self).__init__(field_name, model_name, treeview,
            attrs=attrs, renderer=renderer)

    @realized
    def setter(self, column, cell, store, iter):
        super(Float, self).setter(column, cell, store, iter)
        record = store.get_value(iter, 0)
        field = record[self.field_name]
        digits = field.digits(record, factor=self.factor)
        cell.digits = digits


class FloatTime(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None,
            renderer=None):
        super(FloatTime, self).__init__(field_name, model_name, treeview,
            attrs=attrs, renderer=renderer)
        self.conv = None
        if attrs and attrs.get('float_time'):
            self.conv = rpc.CONTEXT.get(attrs['float_time'])

    def get_textual_value(self, record):
        val = record[self.field_name].get(record)
        return common.float_time_to_text(val, self.conv)

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        digits = field.digits(record)
        field.set_client(record,
            common.text_to_float_time(text, self.conv, digits[1]))
        if callback:
            callback()


class Binary(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None,
            renderer=None):
        self.filename = attrs.get('filename')
        if renderer is None:
            renderer = partial(CellRendererBinary, bool(self.filename))
        super(Binary, self).__init__(field_name, model_name, treeview,
            attrs=attrs, renderer=renderer)
        self.renderer.connect('new', self.new_binary)
        self.renderer.connect('open', self.open_binary)
        self.renderer.connect('save', self.save_binary)
        self.renderer.connect('clear', self.clear_binary)

    def get_textual_value(self, record):
        pass

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()

    @realized
    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        size = record[self.field_name].get_size(record)
        cell.set_property('size', common.humanize(size) if size else '')

    def new_binary(self, renderer, path):
        filename = file_selection(_('Open...'))
        record, field = self._get_record_field(path)
        if filename:
            field.set_client(record, open(filename, 'rb').read())
            if self.filename:
                filename_field = record.group.fields[self.filename]
                filename_field.set_client(record, os.path.basename(filename))

    def open_binary(self, renderer, path):
        if not self.filename:
            return
        dtemp = tempfile.mkdtemp(prefix='tryton_')
        record, field = self._get_record_field(path)
        filename_field = record.group.fields.get(self.filename)
        filename = filename_field.get(record).replace(
            os.sep, '_').replace(os.altsep or os.sep, '_')
        if not filename:
            return
        file_path = os.path.join(dtemp, filename)
        with open(file_path, 'wb') as fp:
            fp.write(field.get_data(record))
        root, type_ = os.path.splitext(filename)
        if type_:
            type_ = type_[1:]
        file_open(file_path, type_)

    def save_binary(self, renderer, path):
        filename = ''
        record, field = self._get_record_field(path)
        if self.filename:
            filename_field = record.group.fields.get(self.filename)
            filename = filename_field.get(record)
        filename = file_selection(_('Save As...'), filename=filename,
            action=gtk.FILE_CHOOSER_ACTION_SAVE)
        if filename:
            with open(filename, 'wb') as fp:
                fp.write(field.get_data(record))

    def clear_binary(self, renderer, path):
        record, field = self._get_record_field(path)
        field.set_client(record, False)


class M2O(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None,
            renderer=None):
        if renderer is None and int(attrs.get('completion', 1)):
            renderer = partial(CellRendererTextCompletion, self.set_completion)
        super(M2O, self).__init__(field_name, model_name, treeview,
            attrs=attrs, renderer=renderer)

    def value_from_text(self, record, text, callback=None):
        field = record.group.fields[self.field_name]
        if not text:
            field.set_client(record, (None, ''))
            if callback:
                callback()
            return

        relation = record[self.field_name].attrs['relation']
        domain = record[self.field_name].domain_get(record)
        context = record[self.field_name].context_get(record)
        dom = [('rec_name', 'ilike', '%' + text + '%'), domain]
        try:
            ids = RPCExecute('model', relation, 'search', dom, 0, None, None,
                context=context)
        except RPCException:
            field.set_client(record, (None, ''))
            if callback:
                callback()
            return
        if len(ids) != 1:
            self.search_remote(record, relation, ids, domain=domain,
                context=context, callback=callback)
            return
        field.set_client(record, ids[0])
        if callback:
            callback()

    def open_remote(self, record, create=True, changed=False, text=None,
            callback=None):
        field = record.group.fields[self.field_name]
        relation = field.attrs['relation']

        access = common.MODELACCESS[relation]
        if create and not access['create']:
            return
        elif not access['read']:
            return

        domain = field.domain_get(record)
        context = field.context_get(record)
        if create:
            obj_id = None
        elif not changed:
            obj_id = field.get(record)
        else:
            if text:
                dom = [('rec_name', 'ilike', '%' + text + '%'), domain]
            else:
                dom = domain
            try:
                ids = RPCExecute('model', relation, 'search', dom, 0, None,
                    None, context=context)
            except RPCException:
                field.set_client(record, False)
                if callback:
                    callback()
                return
            if len(ids) == 1:
                field.set_client(record, ids[0])
                if callback:
                    callback()
                return
            self.search_remote(record, relation, ids, domain=domain,
                context=context, callback=callback)
            return
        screen = Screen(relation, domain=domain, context=context,
            mode=['form'])

        def open_callback(result):
            if result:
                value = (screen.current_record.id,
                    screen.current_record.rec_name())
                field.set_client(record, value, force_change=True)
            if callback:
                callback()
        if obj_id:
            screen.load([obj_id])
            WinForm(screen, open_callback, save_current=True)
        else:
            WinForm(screen, open_callback, new=True, save_current=True)

    def search_remote(self, record, relation, ids=None, domain=None,
            context=None, callback=None):
        field = record.group.fields[self.field_name]

        def search_callback(found):
            value = None
            if found:
                value = found[0]
            field.set_client(record, value)
            if callback:
                callback()
        WinSearch(relation, search_callback, sel_multi=False, ids=ids,
            context=context, domain=domain)

    def set_completion(self, entry, path):
        if entry.get_completion():
            entry.set_completion(None)
        completion = get_completion()
        completion.connect('match-selected', self._completion_match_selected,
            path)
        completion.connect('action-activated',
            self._completion_action_activated, path)
        entry.set_completion(completion)
        entry.connect('key-press-event', self._key_press, path)
        entry.connect('changed', self._update_completion, path)

    def _key_press(self, entry, event, path):
        record, field = self._get_record_field(path)
        if (field.get(record) is not None
                and event.keyval in (gtk.keysyms.Delete,
                    gtk.keysyms.BackSpace)):
            entry.set_text('')
            field.set_client(record, None)
        return False

    def _completion_match_selected(self, completion, model, iter_, path):
        record, field = self._get_record_field(path)
        rec_name, record_id = model.get(iter_, 0, 1)
        field.set_client(record, (record_id, rec_name))

        completion.get_entry().set_text(rec_name)
        completion_model = completion.get_model()
        completion_model.clear()
        completion_model.search_text = rec_name
        return True

    def _update_completion(self, entry, path):
        record, field = self._get_record_field(path)
        if field.get(record) is not None:
            return
        model = field.attrs['relation']
        update_completion(entry, record, field, model)

    def _completion_action_activated(self, completion, index, path):
        record, field = self._get_record_field(path)
        entry = completion.get_entry()

        def callback():
            entry.set_text(field.get_client(record))
        if index == 0:
            self.open_remote(record, create=False, changed=True,
                text=entry.get_text(), callback=callback)
        elif index == 1:
            self.open_remote(record, create=True, callback=callback)


class O2O(M2O):
    pass


class UnsettableColumn(Exception):

    def __init__(self):
        Exception.__init__()


class O2M(Char):

    @realized
    def setter(self, column, cell, store, iter):
        super(O2M, self).setter(column, cell, store, iter)
        cell.set_property('xalign', 0.5)

    def get_textual_value(self, record):
        return '( ' + str(len(record[self.field_name]
                .get_eval(record))) + ' )'

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()

    def open_remote(self, record, create=True, changed=False, text=None,
            callback=None):
        group = record.value[self.field_name]
        field = record.group.fields[self.field_name]
        relation = field.attrs['relation']
        context = field.context_get(record)

        access = common.MODELACCESS[relation]
        if not access['read']:
            return

        screen = Screen(relation, mode=['tree', 'form'],
            exclude_field=field.attrs.get('relation_field'))
        screen.pre_validate = bool(int(self.attrs.get('pre_validate', 0)))
        screen.group = group

        def open_callback(result):
            if callback:
                callback()
        WinForm(screen, open_callback, view_type='tree', context=context)


class M2M(O2M):

    def open_remote(self, record, create=True, changed=False, text=None,
            callback=None):
        group = record.value[self.field_name]
        field = record.group.fields[self.field_name]
        relation = field.attrs['relation']
        context = field.context_get(record)
        domain = field.domain_get(record)

        screen = Screen(relation, mode=['tree', 'form'],
            exclude_field=field.attrs.get('relation_field'))
        screen.group = group

        def open_callback(result):
            if callback:
                callback()
        WinForm(screen, open_callback, view_type='tree', domain=domain,
            context=context)


class Selection(Char, SelectionMixin):

    def __init__(self, *args):
        super(Selection, self).__init__(*args)
        self.renderer = CellRendererCombo()
        self.renderer.connect('editing-started', self.editing_started)
        self.init_selection()
        self.renderer.set_property('model', self.get_model(self.selection))
        self.renderer.set_property('text-column', 0)

    def get_model(self, selection):
        model = gtk.ListStore(gobject.TYPE_STRING)
        self._selection = {}
        lst = []
        for (value, name) in selection:
            name = str(name)
            lst.append(name)
            self._selection[name] = value
            i = model.append()
            model.set(i, 0, name)
        return model

    def get_textual_value(self, record):
        field = record[self.field_name]
        self.update_selection(record, field)
        value = record[self.field_name].get(record)
        text = dict(self.selection).get(value, '')
        if value and not text:
            text = self.get_inactive_selection(value)
        return text

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        field.set_client(record, self._selection.get(text, False))
        if callback:
            callback()

    def editing_started(self, cell, editable, path):
        super(Selection, self).editing_started(cell, editable, path)
        store = self.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        field = record[self.field_name]
        self.update_selection(record, field)
        model = self.get_model(self.selection)
        editable.set_model(model)
        # GTK 2.24 and above use a ComboBox instead of a ComboBoxEntry
        if hasattr(editable, 'set_text_column'):
            editable.set_text_column(0)
        completion = gtk.EntryCompletion()
        #Only available in PyGTK 2.6 and above.
        if hasattr(completion, 'set_inline_selection'):
            completion.set_inline_selection(True)
        completion.set_model(model)
        editable.get_child().set_completion(completion)
        completion.set_text_column(0)
        return False


class Reference(Char, SelectionMixin):

    def __init__(self, field_name, model_name, treeview, attrs=None,
            renderer=None):
        super(Reference, self).__init__(field_name, model_name, treeview,
            attrs=attrs, renderer=renderer)
        self.init_selection()
        self._selection = dict(self.selection)

    def get_textual_value(self, record):
        value = record[self.field_name].get_client(record)
        if not value:
            model, name = '', ''
        else:
            model, name = value
        if model:
            return self._selection.get(model, model) + ',' + name
        else:
            return name

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()


class ProgressBar(object):
    orientations = {
        'left_to_right': gtk.PROGRESS_LEFT_TO_RIGHT,
        'right_to_left': gtk.PROGRESS_RIGHT_TO_LEFT,
        'bottom_to_top': gtk.PROGRESS_BOTTOM_TO_TOP,
        'top_to_bottom': gtk.PROGRESS_TOP_TO_BOTTOM,
    }

    def __init__(self, field_name, model_name, treeview, attrs=None):
        super(ProgressBar, self).__init__()
        self.field_name = field_name
        self.model_name = model_name
        self.attrs = attrs or {}
        self.renderer = gtk.CellRendererProgress()
        orientation = self.orientations.get(self.attrs.get('orientation',
            'left_to_right'), gtk.PROGRESS_LEFT_TO_RIGHT)
        self.renderer.set_property('orientation', orientation)
        self.treeview = treeview

    @realized
    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        field = record[self.field_name]
        value = float(self.get_textual_value(record) or 0.0)
        cell.set_property('value', value)
        digit = field.digits(record)[1]
        text = locale.format('%.*f', (digit, value), True)
        cell.set_property('text', text + '%')

    def open_remote(self, record, create, changed=False, text=None,
            callback=None):
        raise NotImplementedError

    def get_textual_value(self, record):
        return record[self.field_name].get_client(record) or ''

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        field.set_client(record, float(text))
        if callback:
            callback()


class Button(object):

    def __init__(self, treeview, screen, attrs=None):
        super(Button, self).__init__()
        self.attrs = attrs or {}
        self.renderer = CellRendererButton(attrs.get('string', _('Unknown')))
        self.treeview = treeview
        self.screen = screen

        self.renderer.connect('clicked', self.button_clicked)

    @realized
    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        states = record.expr_eval(self.attrs.get('states', {}))
        invisible = states.get('invisible', False)
        cell.set_property('visible', not invisible)
        readonly = states.get('readonly', False)
        cell.set_property('sensitive', not readonly)
        parent = record.parent if record else None
        while parent:
            if parent.modified:
                cell.set_property('sensitive', False)
                break
            parent = parent.parent
        # TODO icon

    def button_clicked(self, widget, path):
        if not path:
            return True
        store = self.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)

        state_changes = record.expr_eval(
            self.attrs.get('states', {}))
        if state_changes.get('invisible') \
                or state_changes.get('readonly'):
            return True
        self.screen.button(self.attrs)

CELLTYPES = {
    'char': Char,
    'many2one': M2O,
    'date': Date,
    'one2many': O2M,
    'many2many': M2M,
    'selection': Selection,
    'float': Float,
    'numeric': Float,
    'float_time': FloatTime,
    'integer': Int,
    'biginteger': Int,
    'datetime': Datetime,
    'time': Time,
    'boolean': Boolean,
    'text': Char,
    'url': URL,
    'email': URL,
    'callto': URL,
    'sip': URL,
    'progressbar': ProgressBar,
    'reference': Reference,
    'one2one': O2O,
    'binary': Binary,
}
