#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import gobject
from editabletree import EditableTreeView
from tryton.gui.window.view_form.view.interface import ParserInterface
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm
from tryton.gui.window.view_form.screen import Screen
from tryton.config import CONFIG
import tryton.rpc as rpc
from tryton.common import DT_FORMAT, DHM_FORMAT, COLORS, node_attributes, \
        TRYTON_ICON, HM_FORMAT
import tryton.common as common
from tryton.exceptions import TrytonError, TrytonServerError
from tryton.common.cellrendererbutton import CellRendererButton
from tryton.common.cellrendererdate import CellRendererDate
from tryton.common.cellrenderertext import CellRendererText
from tryton.common.cellrenderertoggle import CellRendererToggle
from tryton.common.cellrenderercombo import CellRendererCombo
from tryton.common.cellrendererinteger import CellRendererInteger
from tryton.common.cellrendererfloat import CellRendererFloat
from tryton.action import Action
from tryton.translate import date_format
from tryton.pyson import PYSONDecoder
import gtk
import locale
import datetime
import time
import gettext
import operator

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
    screen.sort = None
    if not column.arrow_show:
        column.arrow_show = True
        column.arrow.set(gtk.ARROW_DOWN, gtk.SHADOW_IN)
        column.arrow.show()
        screen.sort = [(column.name, 'ASC')]
    else:
        if column.arrow.get_property('arrow-type') == gtk.ARROW_DOWN:
            column.arrow.set(gtk.ARROW_UP, gtk.SHADOW_IN)
            screen.sort = [(column.name, 'DESC')]
        else:
            column.arrow_show = False
            column.arrow.hide()
    store = treeview.get_model()
    unsaved_records = [x for x in store.group if x.id < 0]
    search_string = screen.screen_container.get_text() or None
    if screen.search_count == len(store):
        ids = screen.search_filter(search_string=search_string, only_ids=True)
        store.sort(ids)
    else:
        screen.search_filter(search_string=search_string)
    for record in unsaved_records:
        store.group.append(record)

class ParserTree(ParserInterface):

    def __init__(self, parent=None, attrs=None, screen=None,
            children_field=None):
        super(ParserTree, self).__init__(parent, attrs, screen,
            children_field=children_field)
        self.treeview = None

    def parse(self, model_name, root_node, fields):
        dict_widget = {}
        button_list = []
        attrs = node_attributes(root_node)
        on_write = attrs.get('on_write', '')
        editable = attrs.get('editable', False)
        if editable:
            treeview = EditableTreeView(editable)
        else:
            treeview = gtk.TreeView()
            treeview.cells = {}
        treeview.sequence = attrs.get('sequence', False)
        treeview.colors = attrs.get('colors', '"black"')
        treeview.keyword_open = attrs.get('keyword_open', False)
        treeview.connect('focus', self.set_selection)
        self.treeview = treeview
        treeview.set_property('rules-hint', True)
        if not self.title:
            self.title = attrs.get('string', 'Unknown')
        tooltips = common.Tooltips()

        for node in root_node.childNodes:
            node_attrs = node_attributes(node)
            if node.localName == 'field':
                fname = str(node_attrs['name'])
                for boolean_fields in ('readonly', 'required'):
                    if boolean_fields in node_attrs:
                        node_attrs[boolean_fields] = \
                                bool(int(node_attrs[boolean_fields]))
                if fname not in fields:
                    continue
                for attr_name in ('relation', 'domain', 'selection',
                        'relation_field', 'string', 'views', 'invisible',
                        'add_remove', 'sort', 'context'):
                    if attr_name in fields[fname].attrs and \
                            not attr_name in node_attrs:
                        node_attrs[attr_name] = fields[fname].attrs[attr_name]
                cell = CELLTYPES.get(node_attrs.get('widget',
                    fields[fname].attrs['type']))(fname, model_name,
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
                if not readonly:
                    renderer.connect_after('editing-started', send_keys,
                            treeview)

                col = gtk.TreeViewColumn(fields[fname].attrs['string'])

                if 'icon' in node_attrs:
                    render_pixbuf = gtk.CellRendererPixbuf()
                    col.pack_start(render_pixbuf, expand=False)
                    icon = node_attrs['icon']
                    def setter(column, cell, store, iter):
                        record = store.get_value(iter, 0)
                        value = record[icon].get_client(record) or ''
                        common.ICONFACTORY.register_icon(value)
                        pixbuf = treeview.render_icon(stock_id=value,
                                size=gtk.ICON_SIZE_BUTTON, detail=None)
                        cell.set_property('pixbuf', pixbuf)
                    col.set_cell_data_func(render_pixbuf, setter)

                col.pack_start(renderer, expand=True)
                col.name = fname

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
                col.set_cell_data_func(renderer, cell.setter)
                col.set_clickable(True)
                twidth = {
                    'integer': 60,
                    'biginteger': 60,
                    'float': 80,
                    'numeric': 80,
                    'float_time': 100,
                    'date': 90,
                    'datetime': 140,
                    'selection': 90,
                    'char': 100,
                    'one2many': 50,
                    'many2many': 50,
                    'boolean': 20,
                }
                if 'width' in node_attrs:
                    width = int(node_attrs['width'])
                else:
                    width = twidth.get(fields[fname].attrs['type'], 100)
                col.width = width
                if width > 0:
                    col.set_fixed_width(width)
                col.set_min_width(1)
                #XXX doesn't work well when resize columns
                #col.set_expand(True)
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
                button_list.append(cell)
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
        if not bool(int(attrs.get('fill', '0'))):
            col = gtk.TreeViewColumn()
            col.name = None
            arrow = gtk.Arrow(gtk.ARROW_DOWN, gtk.SHADOW_IN)
            col.arrow = arrow
            col.arrow_show = False
            col._type = 'fill'
            col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            treeview.append_column(col)
        treeview.set_fixed_height_mode(True)
        return treeview, dict_widget, button_list, on_write, [], None

    def set_selection(self, treeview, direction):
        selection = treeview.get_selection()
        if len(treeview.get_model()):
            selection.select_path(0)
        return False


class Char(object):

    def __init__(self, field_name, model_name, treeview, attrs=None):
        super(Char, self).__init__()
        self.field_name = field_name
        self.model_name = model_name
        self.attrs = attrs or {}
        self.renderer = CellRendererText()
        self.treeview = treeview

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
            readonly = field.get_state_attrs(record).get('readonly', False)
            if invisible:
                readonly = True

            if not isinstance(cell, CellRendererToggle):
                bg_color = 'white'
                if not field.get_state_attrs(record).get('valid', True):
                    bg_color = COLORS.get('invalid', 'white')
                elif bool(int(field.get_state_attrs(record).get('required', 0))):
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
        return record.expr_eval(self.treeview.colors, check_load=False)

    def open_remote(self, record, create, changed=False, text=None,
            callback=None):
        raise NotImplementedError

    def get_textual_value(self, record):
        if not record:
            return ''
        return record[self.field_name].get_client(record) or ''

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        field.set_client(record, text)
        if callback:
            callback()

class Int(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None):
        super(Int, self).__init__(field_name, model_name, treeview,
            attrs=attrs)
        self.renderer = CellRendererInteger()

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        field.set_client(record, int(text))
        if callback:
            callback()

    def get_textual_value(self, record):
        return locale.format('%d',
                record[self.field_name].get_client(record) or 0, True)

class Boolean(Int):

    def __init__(self, field_name, model_name, treeview, attrs=None):
        super(Boolean, self).__init__(field_name, model_name, treeview,
            attrs=attrs)
        self.renderer = CellRendererToggle()
        self.renderer.connect('toggled', self._sig_toggled)

    def get_textual_value(self, record):
        return record[self.field_name].get_client(record)

    def _sig_toggled(self, renderer, path):
        store = self.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        field = record[self.field_name]
        if not field.get_state_attrs(record).get('readonly', False):
            value = record[self.field_name].get_client(record)
            record[self.field_name].set_client(record, int(not value))
            self.treeview.set_cursor(path)
        return True


class Date(Char):
    server_format = DT_FORMAT

    def __init__(self, field_name, model_name, treeview, attrs=None):
        super(Date, self).__init__(field_name, model_name, treeview,
            attrs=attrs)
        self.display_format = date_format()
        self.renderer = CellRendererDate(self.display_format)

    def get_textual_value(self, record):
        value = record[self.field_name].get_client(record)
        if not value:
            return ''
        date = datetime.date(*time.strptime(value, self.server_format)[:3])
        return common.datetime_strftime(date, self.display_format)

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        date = False
        try:
            date = datetime.date(*time.strptime(text, self.display_format)[:3])
            date = common.datetime_strftime(date, self.server_format)
        except ValueError:
            date = False
        field.set_client(record, date)
        if callback:
            callback()


class Datetime(Date):
    server_format = DHM_FORMAT

    def __init__(self, field_name, model_name, treeview, attrs=None):
        super(Datetime, self).__init__(field_name, model_name, treeview,
            attrs=attrs)
        self.display_format = date_format() + ' ' + HM_FORMAT
        self.renderer.format = self.display_format

    def get_textual_value(self, record):
        value = record[self.field_name].get_client(record)
        if not value:
            return ''
        date = datetime.datetime(*time.strptime(value,
            self.server_format)[:6])
        date = common.timezoned_date(date)
        return common.datetime_strftime(date, self.display_format)

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        date = False
        try:
            date = datetime.datetime(*time.strptime(text,
                self.display_format)[:6])
            date = common.untimezoned_date(date)
            date = common.datetime_strftime(date, self.server_format)
        except ValueError:
            date = False
        field.set_client(record, date)
        if callback:
            callback()


class Float(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None):
        super(Float, self).__init__(field_name, model_name, treeview,
            attrs=attrs)
        self.renderer = CellRendererFloat()

    def setter(self, column, cell, store, iter):
        super(Float, self).setter(column, cell, store, iter)
        record = store.get_value(iter, 0)
        field = record[self.field_name]
        digits = record.expr_eval(field.attrs.get('digits', (16, 2)))
        cell.digits = digits

    def get_textual_value(self, record):
        field = record[self.field_name]
        digit = record.expr_eval(field.attrs.get('digits', (16, 2)))[1]
        return locale.format('%.'+str(digit)+'f',
                record[self.field_name].get_client(record) or 0.0, True)

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        try:
            value = locale.atof(text)
        except ValueError:
            value = 0.0
        field.set_client(record, value)
        if callback:
            callback()


class FloatTime(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None):
        super(FloatTime, self).__init__(field_name, model_name, treeview,
            attrs=attrs)
        self.conv = None
        if attrs and attrs.get('float_time'):
            self.conv = rpc.CONTEXT.get(attrs['float_time'])

    def get_textual_value(self, record):
        val = record[self.field_name].get_client(record)
        return common.float_time_to_text(val, self.conv)

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        digits = record.expr_eval(field.attrs.get('digits', (16, 2)))
        field.set_client(record,
            round(common.text_to_float_time(text, self.conv), digits[1]))
        if callback:
            callback()

class M2O(Char):

    def value_from_text(self, record, text, callback=None):
        field = record.group.fields[self.field_name]
        if not text and not field.get_state_attrs(
                record)['required']:
            if callback:
                callback()
            return False

        relation = record[self.field_name].attrs['relation']
        domain = record[self.field_name].domain_get(record)
        context = record[self.field_name].context_get(record)
        if text:
            dom = [('rec_name', 'ilike', '%' + text + '%'),
                    domain]
        else:
            dom = domain
        args = ('model', relation, 'search', dom, 0, None, None,
                context)
        try:
            ids = rpc.execute(*args)
        except TrytonServerError, exception:
            ids = common.process_exception(exception, *args)
            if not ids:
                field.set_client(record, '???')
                if callback:
                    callback()
                return
        if len(ids) != 1:
            if callback:
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
            args = ('model', relation, 'search', dom, 0, None, None, context)
            try:
                ids = rpc.execute(*args)
            except TrytonServerError, exception:
                ids = common.process_exception(exception, *args)
                if not ids:
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
            if result and screen.save_current():
                value = (screen.current_record.id,
                    screen.current_record.rec_name())
                field.set_client(record, value)
            if callback:
                callback()
        if obj_id:
            screen.load([obj_id])
            WinForm(screen, open_callback)
        else:
            WinForm(screen, open_callback, new=True)

    def search_remote(self, record, relation, ids=None, domain=None,
            context=None, callback=None):
        field = record.group.fields[self.field_name]
        def search_callback(found):
            value = None
            if found:
                args = ('model', relation, 'read', found[0], ['rec_name'],
                        context)
                try:
                    res = rpc.execute(*args)
                except TrytonServerError, exception:
                    res = common.process_exception(exception, *args)
                if res:
                    value = (found[0], res['rec_name'])
            field.set_client(record, value)
            if callback:
                callback()
        WinSearch(relation, search_callback, sel_multi=False, ids=ids,
            context=context, domain=domain)


class O2O(M2O):
    pass


class UnsettableColumn(Exception):

    def __init__(self):
        Exception.__init__()


class O2M(Char):

    def setter(self, column, cell, store, iter):
        super(O2M, self).setter(column, cell, store, iter)
        cell.set_property('xalign', 0.5)

    def get_textual_value(self, record):
        return '( ' + str(len(record[self.field_name].\
                get_client(record))) + ' )'

    def value_from_text(self, record, text, callback=None):
        if callback:
            callback()

    def open_remote(self, record, create=True, changed=False, text=None,
            callback=None):
        group = record.value[self.field_name]
        field = record.group.fields[self.field_name]
        relation = field.attrs['relation']
        context = field.context_get(record)

        screen = Screen(relation, mode=['tree', 'form'],
            exclude_field=field.attrs.get('relation_field'))
        screen.group = group
        def open_callback(result):
            if callback:
                callback()
        WinForm(screen, open_callback, view_type='tree', context=context)


class M2M(Char):

    def setter(self, column, cell, store, iter):
        super(M2M, self).setter(column, cell, store, iter)
        cell.set_property('xalign', 0.5)

    def get_textual_value(self, record):
        return '( ' + str(len(record[self.field_name].\
                get_client(record))) + ' )'

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        if not text:
            field.set_client(record, [])
            if callback:
                callback()
            return
        if not (text[0] != '('):
            if callback:
                callback()
            return
        relation = field.attrs['relation']
        domain = field.domain_get(record)
        context = field.context_get(record)
        if text:
            dom = [('rec_name', 'ilike', '%' + text + '%'),
                    domain]
        else:
            dom = domain
        args = ('model', relation, 'search', dom, 0, CONFIG['client.limit'],
                None, context)
        try:
            ids = rpc.execute(*args)
        except TrytonServerError, exception:
            ids = common.process_exception(exception, *args)
            if ids is False:
                field.set_client(record, [])
                if callback:
                    callback()
                return
        if not callback:
            return
        def winsearch_callback(result):
            field.set_client(record, result or [])
            if callback:
                callback()
        WinSearch(relation, winsearch_callback, sel_multi=True, ids=ids,
            context=context, domain=domain)
        return

    def open_remote(self, record, create=True, changed=False, text=None,
            callback=None):
        field = record[self.field_name]
        relation = field.attrs['relation']
        context = field.context_get(record)
        domain = field.domain_get(record)
        if create:
            if text and len(text) and text[0] != '(':
                domain.append(('name', '=', text))
            args = ('model', relation, 'search', domain)
            try:
                ids = rpc.execute(*args)
            except TrytonServerError, exception:
                ids = common.process_exception(exception, *args)
                if ids is False:
                    field.set_client(record, False)
                    if callback:
                        callback()
            if ids and len(ids)==1:
                field.set_client(record, ids)
                if callback:
                    callback()
                return
        else:
            ids = [x.id for x in field.get_client(record)]
        def open_callback(result):
            if result:
                field.set_client(record, result)
            if callback:
                callback()
        WinSearch(relation, open_callback, sel_multi=True, ids=ids, context=context,
            domain=domain)


class Selection(Char):

    def __init__(self, *args):
        super(Selection, self).__init__(*args)
        self.renderer = CellRendererCombo()
        self.renderer.connect('editing-started', self.editing_started)
        self._last_domain = None
        self._domain_cache = {}
        selection = self.attrs.get('selection', [])[:]
        if not isinstance(selection, (list, tuple)):
            args = ('model', self.model_name, selection, rpc.CONTEXT)
            try:
                selection = rpc.execute(*args)
            except TrytonServerError, exception:
                selection = (common.process_exception(exception, args) or [])
        self.selection = selection[:]
        if self.attrs.get('sort', True):
            selection.sort(key=operator.itemgetter(1))
        self.renderer.set_property('model', self.get_model(selection))
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
        self.update_selection(record)
        value = record[self.field_name].get(record)
        if isinstance(value, (list, tuple)):
            value = value[0]
        return dict(self.selection).get(value, '')

    def value_from_text(self, record, text, callback=None):
        field = record[self.field_name]
        field.set_client(record, self._selection.get(text, False))
        if callback:
            callback()

    def editing_started(self, cell, editable, path):
        store = self.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)
        self.update_selection(record)
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

    def update_selection(self, record):
        if 'relation' not in self.attrs:
            return
        field = record[self.field_name]
        domain = field.domain_get(record)
        if str(domain) in self._domain_cache:
            self.selection = self._domain_cache[str(domain)]
            self._last_domain = domain
        if domain != self._last_domain:
            args = ('model', self.attrs['relation'], 'search_read', domain,
                0, None, None, ['rec_name'], rpc.CONTEXT)
            try:
                result = rpc.execute(*args)
            except TrytonServerError, exception:
                result = common.process_exception(exception, *args)

            if isinstance(result, list):
                selection = [(x['id'], x['rec_name']) for x in result]
                selection.append((False, ''))
                self._last_domain = domain
                self._domain_cache[str(domain)] = selection
            else:
                selection = []
                self._last_domain = None
        else:
            selection = self.selection
        self.selection = selection[:]


class Reference(Char):

    def __init__(self, field_name, model_name, treeview, attrs=None):
        super(Reference, self).__init__(field_name, model_name, treeview,
            attrs=attrs)
        self._selection = {}
        selection = attrs.get('selection', [])
        if not isinstance(selection, (list, tuple)):
            try:
                selection = rpc.execute('model',
                        model_name, selection, rpc.CONTEXT)
            except TrytonServerError, exception:
                common.process_exception(exception)
                selection = []
        selection.sort(key=operator.itemgetter(1))
        for i, j in selection:
            self._selection[i] = str(j)

    def get_textual_value(self, record):
        value = record[self.field_name].get_client(record)
        if not value:
            model, (obj_id, name) = '', (-1, '')
        else:
            model, (obj_id, name) = value
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

    def setter(self, column, cell, store, iter):
        record = store.get_value(iter, 0)
        value = float(self.get_textual_value(record) or 0.0)
        cell.set_property('value', value)
        digit = record.expr_eval(self.attrs.get('digits', (16, 2)))[1]
        text = locale.format('%.' + str(digit) + 'f', value, True)
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

    def button_clicked(self, widget, path):
        if not path:
            return True
        store = self.treeview.get_model()
        record = store.get_value(store.get_iter(path), 0)

        state_changes = record.expr_eval(
            self.attrs.get('states', {}), check_load=False)
        if state_changes.get('invisible') \
                or state_changes.get('readonly'):
            return True

        self.screen.current_record = record
        obj_id = self.screen.save_current()
        if obj_id:
            if not self.attrs.get('confirm', False) or \
                    common.sur(self.attrs['confirm']):
                button_type = self.attrs.get('type', 'workflow')
                ctx = rpc.CONTEXT.copy()
                ctx.update(record.context_get())
                if button_type == 'workflow':
                    args = ('model', self.screen.model_name,
                            'workflow_trigger_validate', obj_id,
                            self.attrs['name'], ctx)
                    try:
                        rpc.execute(*args)
                    except TrytonServerError, exception:
                        common.process_exception(exception, *args)
                elif button_type == 'object':
                    args = ('model', self.screen.model_name,
                            self.attrs['name'], [obj_id], ctx)
                    try:
                        rpc.execute(*args)
                    except TrytonServerError, exception:
                        common.process_exception(exception, *args)
                elif button_type == 'action':
                    action_id = None
                    args = ('model', 'ir.action', 'get_action_id',
                            int(self.attrs['name']), ctx)
                    try:
                        action_id = rpc.execute(*args)
                    except TrytonServerError, exception:
                        action_id = common.process_exception(exception, *args)
                    if action_id:
                        Action.execute(action_id, {
                            'model': self.screen.model_name,
                            'id': obj_id,
                            'ids': [obj_id],
                            }, context=ctx)
                else:
                    raise TrytonError('Unallowed button type')
                self.screen.reload(written=True)
            else:
                self.screen.display()

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
    'boolean': Boolean,
    'text': Char,
    'url': Char,
    'email': Char,
    'callto': Char,
    'sip': Char,
    'progressbar': ProgressBar,
    'reference': Reference,
    'one2one': O2O,
}
