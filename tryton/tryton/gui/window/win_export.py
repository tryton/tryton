# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import csv
import datetime
import gettext
import json
import locale
import os
import urllib.parse
from itertools import zip_longest
from numbers import Number

from gi.repository import Gdk, GObject, Gtk

import tryton.common as common
from tryton.common import IconFactory, RPCException, RPCExecute, tempfile
from tryton.common.underline import set_underline
from tryton.config import CONFIG
from tryton.gui.window.win_csv import WinCSV
from tryton.jsonrpc import JSONEncoder
from tryton.rpc import CONNECTION, clear_cache

from .infobar import InfoBar

_ = gettext.gettext
N_ = gettext.ngettext


class WinExport(WinCSV, InfoBar):
    "Window export"

    def __init__(self, name, screen):
        self.name = name
        self.screen = screen
        self.fields = {}
        super().__init__()
        self.dialog.set_title(_('CSV Export: %s') % name)
        self.dialog.vbox.pack_start(
            self.create_info_bar(), expand=False, fill=True, padding=0)
        # Trigger changed event to update ignore search limit
        active_index = self.selected_records.get_active()
        self.selected_records.set_active(-1)
        self.selected_records.set_active(active_index)

        self.dialog.add_button(
            set_underline(_("Close")), Gtk.ResponseType.CANCEL).set_image(
                IconFactory.get_image('tryton-close', Gtk.IconSize.BUTTON))
        self.dialog.add_button(
            set_underline(_("Open")), Gtk.ResponseType.OK).set_image(
                IconFactory.get_image('tryton-open', Gtk.IconSize.BUTTON))
        self.dialog.add_button(
            set_underline(_("Save As...")), Gtk.ResponseType.ACCEPT).set_image(
                IconFactory.get_image('tryton-save', Gtk.IconSize.BUTTON))
        self.dialog.set_default_response(Gtk.ResponseType.OK)

    @property
    def model(self):
        return self.screen.model_name

    @property
    def context(self):
        return self.screen.context

    @property
    def screen_is_tree(self):
        return bool(
            self.screen.current_view
            and self.screen.current_view.view_type == 'tree'
            and self.screen.current_view.children_field)

    @property
    def screen_has_selected(self):
        return bool(self.screen.selected_records)

    def add_buttons(self, box):
        button_save_export = Gtk.Button(
            label=_('_Save Export'), stock=None, use_underline=True)
        button_save_export.set_image(common.IconFactory.get_image(
                'tryton-save', Gtk.IconSize.BUTTON))
        button_save_export.set_always_show_image(True)
        button_save_export.connect_after('clicked', self.addreplace_predef)
        box.pack_start(
            button_save_export, expand=False, fill=False, padding=0)

        button_url = Gtk.MenuButton(
            label=_("_URL Export"), stock=None, use_underline=True)
        button_url.set_image(common.IconFactory.get_image(
                'tryton-public', Gtk.IconSize.BUTTON))
        button_url.set_always_show_image(True)
        box.pack_start(button_url, expand=False, fill=False, padding=0)
        menu_url = Gtk.Menu()
        menuitem_url = Gtk.MenuItem()
        menuitem_url.connect('activate', self.copy_url)
        menu_url.add(menuitem_url)
        menu_url.show_all()
        button_url.set_popup(menu_url)
        button_url.connect('button-press-event', self.set_url, menuitem_url)

        button_del_export = Gtk.Button(
            label=_('_Delete Export'), stock=None, use_underline=True)
        button_del_export.set_image(common.IconFactory.get_image(
                'tryton-delete', Gtk.IconSize.BUTTON))
        button_del_export.set_always_show_image(True)
        button_del_export.connect_after('clicked', self.remove_predef)
        box.pack_start(button_del_export, expand=False, fill=False, padding=0)

        frame_predef_exports = Gtk.Frame()
        frame_predef_exports.set_border_width(2)
        frame_predef_exports.set_shadow_type(Gtk.ShadowType.NONE)
        box.pack_start(frame_predef_exports, expand=True, fill=True, padding=0)
        viewport_exports = Gtk.Viewport()
        scrolledwindow_exports = Gtk.ScrolledWindow()
        scrolledwindow_exports.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        label_predef_exports = Gtk.Label(
            label=_("<b>Predefined exports</b>"), use_markup=True)
        frame_predef_exports.set_label_widget(label_predef_exports)
        viewport_exports.add(scrolledwindow_exports)
        frame_predef_exports.add(viewport_exports)

        self.pref_export = Gtk.TreeView()
        self.pref_export.append_column(
            Gtk.TreeViewColumn(_('Name'), Gtk.CellRendererText(), text=1))
        scrolledwindow_exports.add(self.pref_export)
        self.pref_export.connect("button-press-event", self.export_click)
        self.pref_export.connect("key-press-event", self.export_keypress)

        self.predef_model = Gtk.ListStore(
            GObject.TYPE_INT,
            GObject.TYPE_STRING,
            GObject.TYPE_PYOBJECT,
            GObject.TYPE_PYOBJECT)
        self.fill_predefwin()

    def add_chooser(self, box):
        hbox_csv_export = Gtk.HBox()
        box.pack_start(hbox_csv_export, expand=False, fill=True, padding=0)

        self.selected_records = Gtk.ComboBoxText()
        hbox_csv_export.pack_start(
            self.selected_records, expand=True, fill=True, padding=3)
        self.selected_records.append_text(_("Listed Records"))
        self.selected_records.append_text(_("Selected Records"))
        if not self.screen_is_tree and self.screen_has_selected:
            self.selected_records.set_active(1)
        else:
            self.selected_records.set_active(0)

        self.ignore_search_limit = Gtk.CheckButton(
            label=_("Ignore search limit"))
        hbox_csv_export.pack_start(
            self.ignore_search_limit, expand=False, fill=True, padding=3)

        self.selected_records.connect(
            'changed',
            lambda w: self.ignore_search_limit.set_visible(
                not w.get_active() and not self.screen_is_tree))

    def add_csv_header_param(self, box):
        self.add_field_names = Gtk.CheckButton(label=_("Add field names"))
        self.add_field_names.set_active(True)
        box.pack_start(
            self.add_field_names, expand=False, fill=True, padding=0)

    def model_populate(self, fields, parent_node=None, prefix_field='',
            prefix_name=''):

        def key(n_f):
            return n_f[1].get('string') or n_f[0]
        for name, field in sorted(list(fields.items()), key=key, reverse=True):

            string_ = field['string'] or name

            items = [(name, field, string_)]
            if field['type'] == 'selection':
                items.insert(0, ('%s.translated' % name, field,
                        _('%s (string)') % string_))
            elif field['type'] == 'reference':
                items.insert(0, ('%s.translated' % name, field,
                        _('%s (model name)') % string_))
                items.insert(0, ('%s/rec_name' % name, field,
                        _("%s/Record Name") % string_))

            for name, field, string_ in items:
                path = prefix_field + name
                node = self.model1.insert(parent_node, 0,
                    [string_, path])
                string_ = prefix_name + string_

                self.fields[path] = (string_, field.get('relation'))
                # Insert relation only to real field
                if '.' not in name:
                    if field.get('relation'):
                        self.model1.insert(node, 0, [None, ''])
                    elif field.get('translate', False):
                        for language in self.languages:
                            l_path = f"{path}:lang={language['code']}"
                            l_string = f"{string_} ({language['name']})"
                            self.model1.insert(
                                node, 0, [language['name'], l_path])
                            self.fields[l_path] = (l_string, None)

    def _get_fields(self, model):
        try:
            return RPCExecute('model', model, 'fields_get', None,
                context=self.context)
        except RPCException:
            return ''

    def on_row_expanded(self, treeview, iter, path):
        child = self.model1.iter_children(iter)
        if child and self.model1.get_value(child, 0) is None:
            prefix_field = self.model1.get_value(iter, 1)
            string_, relation = self.fields[prefix_field]
            self.model_populate(self._get_fields(relation), iter,
                prefix_field + '/', string_ + '/')
            self.model1.remove(child)

    def sig_sel(self, *args):
        sel = self.view1.get_selection()
        sel.selected_foreach(self._sig_sel_add)

    def _sig_sel_add(self, store, path, iter):
        name = store.get_value(iter, 1)
        self.sel_field(name)

    def sig_unsel(self, *args):
        store, paths = self.view2.get_selection().get_selected_rows()
        # Convert first into TreeIter before removing from the store
        iters = [store.get_iter(p) for p in paths]
        for i in iters:
            store.remove(i)

    def sig_unsel_all(self, *args):
        self.model2.clear()

    def fill_predefwin(self):
        try:
            exports = RPCExecute(
                'model', 'ir.export', 'get', self.model, [
                    'name', 'header', 'records', 'ignore_search_limit',
                    'export_fields.name'],
                context=self.context)
        except RPCException:
            return
        for export in exports:
            self.predef_model.append((
                    export['id'],
                    export['name'],
                    [f['name'] for f in export['export_fields.']],
                    export))
        self.pref_export.set_model(self.predef_model)

    def addreplace_predef(self, widget):
        iter = self.model2.get_iter_first()
        fields = []
        while iter:
            field_name = self.model2.get_value(iter, 1)
            fields.append(field_name)
            iter = self.model2.iter_next(iter)
        if not fields:
            return

        selection = self.pref_export.get_selection().get_selected()
        if selection is None:
            return
        model, iter_ = selection
        if iter_ is None:
            pref_id = None
            name = common.ask(_('What is the name of this export?'))
            if not name:
                return
        else:
            pref_id = model.get_value(iter_, 0)
            name = model.get_value(iter_, 1)
            override = common.sur(_("Override '%s' definition?") % name)
            if not override:
                return
        try:
            values = {
                'header': self.add_field_names.get_active(),
                'records': (
                    'selected' if self.selected_records.get_active()
                    else 'listed'),
                'ignore_search_limit': self.ignore_search_limit.get_active(),
                }
            if not pref_id:
                values.update({
                        'name': name,
                        'resource': self.model,
                        'export_fields': [{'name': x, } for x in fields],
                        })
                pref_id = RPCExecute(
                    'model', 'ir.export', 'set', values, context=self.context)
            else:
                RPCExecute(
                    'model', 'ir.export', 'update', pref_id, values, fields,
                    context=self.context)
        except RPCException:
            return
        clear_cache('model.%s.view_toolbar_get' % self.model)
        if iter_ is None:
            self.predef_model.append((pref_id, name, fields, values))
        else:
            model.set_value(iter_, 2, fields)
            model.set_value(iter_, 3, values)

    def remove_predef(self, widget):
        sel = self.pref_export.get_selection().get_selected()
        if sel is None:
            return None
        (model, i) = sel
        if not i:
            return None
        export_id = model.get_value(i, 0)
        try:
            RPCExecute(
                'model', 'ir.export', 'unset', export_id, context=self.context)
        except RPCException:
            return
        clear_cache('model.%s.view_toolbar_get' % self.model)
        for i in range(len(self.predef_model)):
            if self.predef_model[i][0] == export_id:
                del self.predef_model[i]
                break
        self.pref_export.set_model(self.predef_model)

    def sel_predef(self, path):
        self.model2.clear()
        _, _, fields, values = self.predef_model[path[0]]
        for name in fields:
            if name not in self.fields:
                iter = self.model1.get_iter_first()
                prefix = ''
                for parent in name.split('/')[:-1]:
                    while iter:
                        if self.model1.get_value(iter, 1) == \
                                (prefix + parent):
                            self.on_row_expanded(self.view1, iter,
                                    self.model1.get_path(iter))
                            iter = self.model1.iter_children(iter)
                            prefix += parent + '/'
                            break
                        else:
                            iter = self.model1.iter_next(iter)

            if name not in self.fields:
                continue
            self.sel_field(name)

        self.add_field_names.set_active(values.get('header'))
        self.selected_records.set_active(
            int(values.get('records') == 'selected'))
        self.ignore_search_limit.set_active(
            values.get('ignore_search_limit'))

    def sel_field(self, name):
        string_ = self.fields[name][0]
        self.model2.append((string_, name))

    def response(self, dialog, response):
        self.info_bar_clear()
        if response in {Gtk.ResponseType.OK, Gtk.ResponseType.ACCEPT}:
            fields = []
            iter = self.model2.get_iter_first()
            while iter:
                fields.append(self.model2.get_value(iter, 1))
                iter = self.model2.iter_next(iter)
            header = self.add_field_names.get_active()

            if self.selected_records.get_active():
                ids = [r.id for r in self.screen.selected_records]
                paths = self.screen.selected_paths
                try:
                    data = RPCExecute(
                        'model', self.model, 'export_data',
                        ids, fields, header,
                        context=self.context)
                except RPCException:
                    data = []
            elif self.screen_is_tree:
                ids = [r.id for r in self.screen.listed_records]
                paths = self.screen.listed_paths
                try:
                    data = RPCExecute(
                        'model', self.model, 'export_data',
                        ids, fields, header,
                        context=self.context)
                except RPCException:
                    data = []
            else:
                paths = None
                domain = self.screen.search_domain(
                    self.screen.screen_container.get_text())
                if self.ignore_search_limit.get_active():
                    offset, limit = 0, None
                else:
                    offset, limit = self.screen.offset, self.screen.limit
                try:
                    data = RPCExecute(
                        'model', self.model, 'export_data_domain',
                        domain, fields, offset, limit, self.screen.order,
                        header, context=self.context)
                except RPCException:
                    data = []

            if response == Gtk.ResponseType.ACCEPT:
                fname = common.file_selection(_('Save As...'),
                        action=Gtk.FileChooserAction.SAVE)
                if fname:
                    self.export_csv(fname, data, paths, header=header)
            else:
                fileno, fname = tempfile.mkstemp(
                    '.csv', common.slugify(self.name) + '_')
                if self.export_csv(fname, data, paths, header=header):
                    os.close(fileno)
                    common.file_open(fname, 'csv')
                else:
                    os.close(fileno)
        else:
            self.destroy()

    def export_csv(self, fname, data, paths, header=False):
        encoding = self.csv_enc.get_active_text() or 'utf_8_sig'
        locale_format = self.csv_locale.get_active()

        try:
            writer = csv.writer(
                open(fname, 'w', encoding=encoding, newline=''),
                quotechar=self.get_quotechar(),
                delimiter=self.get_delimiter())
            for row, path in zip_longest(data, paths or []):
                indent = len(path) - 1 if path else 0
                if row:
                    writer.writerow(self.format_row(
                            row, indent=indent, locale_format=locale_format))
            size = len(data)
            if header:
                size -= 1
            message = N_('%d record saved.', '%d records saved.', size) % size
            self.info_bar_add(message, Gtk.MessageType.INFO)
            return True
        except (IOError, UnicodeEncodeError, csv.Error) as exception:
            common.warning(str(exception), _('Export failed'))
            return False

    @classmethod
    def format_row(cls, line, indent=0, locale_format=True):
        row = []
        for i, val in enumerate(line):
            if locale_format:
                if isinstance(val, Number):
                    val = locale.str(val)
                elif isinstance(val, datetime.datetime):
                    val = common.timezoned_date(val)
                    val = val.strftime(common.date_format() + ' %X')
                elif isinstance(val, datetime.date):
                    val = val.strftime(common.date_format())
                elif isinstance(val, datetime.timedelta):
                    val = common.timedelta.format(
                        val, {'s': 1, 'm': 60, 'h': 60 * 60})
            elif isinstance(val, datetime.timedelta):
                val = val.total_seconds()
            elif isinstance(val, bool):
                val = int(val)
            if i == 0 and indent and isinstance(val, str):
                val = '  ' * indent + val
            if isinstance(val, bytes):
                val = base64.b64encode(val).decode('utf-8')
            row.append(val)
        return row

    def export_click(self, treeview, event):
        path_at_pos = treeview.get_path_at_pos(int(event.x), int(event.y))
        if not path_at_pos or event.button != 1:
            return
        path, col, x, y = path_at_pos
        selection = treeview.get_selection()
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.sel_predef(path)
            selection.select_path(path)
            return True
        elif selection.path_is_selected(path):
            selection.unselect_path(path)
            return True

    def export_keypress(self, treeview, event):
        if event.keyval not in [Gdk.KEY_Return, Gdk.KEY_space]:
            return
        model, selected = treeview.get_selection().get_selected()
        if not selected:
            return
        self.sel_predef(model.get_path(selected))

    def get_url(self):
        path = [CONFIG['login.db'], 'data', self.model]
        protocol = 'https' if CONNECTION.ssl else 'http'
        host = common.get_hostname(CONFIG['login.host'])
        port = common.get_port(CONFIG['login.host'])
        if protocol == 'https' and port == 445:
            netloc = host
        elif protocol == 'http' and port == 80:
            netloc = host
        else:
            netloc = '%s:%s' % (host, port)
        query_string = []
        if self.selected_records.get_active():
            domain = [r.id for r in self.screen.selected_records]
        else:
            domain = self.screen.search_domain(
                self.screen.screen_container.get_text())
            if (not self.ignore_search_limit.get_active()
                    and self.screen.limit is not None):
                query_string.append(('s', str(self.screen.limit)))
                query_string.append(
                    ('p', str(self.screen.offset // self.screen.limit)))
            if self.screen.order:
                for expr in self.screen.order:
                    query_string.append(('o', ','.join(filter(None, expr))))
        query_string.insert(0, ('d', json.dumps(
                    domain, cls=JSONEncoder, separators=(',', ':'))))
        if self.screen.local_context:
            query_string.append(('c', json.dumps(
                        self.screen.local_context,
                        cls=JSONEncoder, separators=(',', ':'))))

        iter_ = self.model2.get_iter_first()
        while iter_:
            query_string.append(('f', self.model2.get_value(iter_, 1)))
            iter_ = self.model2.iter_next(iter_)

        encoding = self.csv_enc.get_active_text()
        if encoding:
            query_string.append(('enc', encoding))

        query_string.append(('dl', self.get_delimiter()))
        query_string.append(('qc', self.get_quotechar()))
        if not self.add_field_names.get_active():
            query_string.append(('h', '0'))
        if self.csv_locale.get_active():
            query_string.append(('loc', '1'))

        query_string = urllib.parse.urlencode(query_string)
        return urllib.parse.urlunparse((
                protocol, netloc, '/'.join(path), '', query_string, ''))

    def set_url(self, button, event, menuitem):
        url = self.get_url()
        size = 80
        if len(url) > size:
            url = url[:size // 2] + '...' + url[-size // 2:]
        menuitem.set_label(url)

    def copy_url(self, menuitem):
        url = self.get_url()
        for selection in [
                Gdk.Atom.intern('PRIMARY', True),
                Gdk.Atom.intern('CLIPBOARD', True),
                ]:
            clipboard = Gtk.Clipboard.get(selection)
            clipboard.set_text(url, -1)
