# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import csv
import gettext

import gtk

import tryton.common as common
from tryton.common import RPCExecute, RPCException
from tryton.gui.window.win_csv import WinCSV

_ = gettext.gettext


class WinImport(WinCSV):
    "Window import"

    def __init__(self, name, model, context):
        self.name = name
        self.model = model
        self.context = context
        self.fields_data = {}
        self.fields = {}
        self.fields_invert = {}
        super(WinImport, self).__init__()
        self.dialog.set_title(_('CSV Import: %s') % name)

    def add_buttons(self, box):
        button_autodetect = gtk.Button(
            _('_Auto-Detect'), stock=None, use_underline=True)
        button_autodetect.set_alignment(0.0, 0.0)
        button_autodetect.set_image(common.IconFactory.get_image(
                'tryton-search', gtk.ICON_SIZE_BUTTON))
        button_autodetect.set_always_show_image(True)
        button_autodetect.connect_after('clicked', self.sig_autodetect)
        box.pack_start(button_autodetect, False, False, 0)

    def add_chooser(self, box):
        hbox_csv_import = gtk.HBox()
        box.pack_start(hbox_csv_import, False, True, 4)
        label_csv_import = gtk.Label(_("File to Import:"))
        hbox_csv_import.pack_start(label_csv_import, False, False, 0)
        self.import_csv_file = gtk.FileChooserButton(_("Open..."))
        label_csv_import.set_mnemonic_widget(self.import_csv_file)
        hbox_csv_import.pack_start(self.import_csv_file, True, True, 0)

    def add_csv_header_param(self, table):
        label_csv_skip = gtk.Label(_('Lines to Skip:'))
        label_csv_skip.set_alignment(1, 0.5)
        table.attach(label_csv_skip, 2, 3, 1, 2)

        self.csv_skip = gtk.SpinButton()
        self.csv_skip.configure(gtk.Adjustment(0, 0, 100, 1, 10), 1, 0)
        label_csv_skip.set_mnemonic_widget(self.csv_skip)
        table.attach(self.csv_skip, 3, 4, 1, 2)

    def model_populate(self, fields, parent_node=None, prefix_field='',
            prefix_name=''):
        fields_order = list(fields.keys())
        fields_order.sort(
            key=lambda x: fields[x].get('string', ''), reverse=True)
        for field in fields_order:
            if not fields[field].get('readonly', False):
                self.fields_data[prefix_field + field] = fields[field]
                name = fields[field]['string'] or field
                node = self.model1.insert(
                    parent_node, 0, [name, prefix_field + field])
                name = prefix_name + name
                # Only One2Many can be nested for import
                if fields[field]['type'] == 'one2many':
                    relation = fields[field].get('relation')
                else:
                    relation = None
                self.fields[prefix_field + field] = (name, relation)
                self.fields_invert[name] = prefix_field + field
                if relation:
                    self.model1.insert(node, 0, [None, ''])

    def _get_fields(self, model):
        try:
            return RPCExecute('model', model, 'fields_get', None,
                context=self.context)
        except RPCException:
            return ''

    def on_row_expanded(self, treeview, iter, path):
        child = self.model1.iter_children(iter)
        # autodetect could call for node without children
        if child is None:
            return
        if self.model1.get_value(child, 0) is None:
            prefix_field = self.model1.get_value(iter, 1)
            name, model = self.fields[prefix_field]
            self.model_populate(self._get_fields(model), iter, prefix_field +
                    '/', name + '/')
            self.model1.remove(child)

    def sig_autodetect(self, widget=None):
        fname = self.import_csv_file.get_filename()
        if not fname:
            common.message(_('You must select an import file first.'))
            return True

        encoding = self.get_encoding()
        self.csv_skip.set_value(1)
        try:
            data = csv.reader(
                open(fname, 'r', encoding=encoding, newline=''),
                quotechar=self.get_quotechar(),
                delimiter=self.get_delimiter())
        except IOError:
            common.warning(_('Error opening CSV file'), _('Error'))
            return True
        self.sig_unsel_all()
        word = ''
        for line in data:
            for word in line:
                if word not in self.fields_invert and word not in self.fields:
                    iter = self.model1.get_iter_first()
                    prefix = ''
                    for parent in word.split('/')[:-1]:
                        while iter:
                            if self.model1.get_value(iter, 0) == parent or \
                                    self.model1.get_value(iter, 1) == \
                                    (prefix + parent):
                                self.on_row_expanded(self.view1, iter,
                                        self.model1.get_path(iter))
                                iter = self.model1.iter_children(iter)
                                prefix = parent + '/'
                                break
                            else:
                                iter = self.model1.iter_next(iter)

                if word in self.fields_invert:
                    name = word
                    field = self.fields_invert[word]
                elif word in self.fields:
                    name = self.fields[word][0]
                    field = word
                else:
                    common.warning(_('Error processing the file at field %s.')
                        % word, _('Error'))
                    return True
                num = self.model2.append()
                self.model2.set(num, 0, name, 1, field)
            break
        return True

    def sig_sel(self, *args):
        sel = self.view1.get_selection()
        sel.selected_foreach(self._sig_sel_add)

    def _sig_sel_add(self, store, path, iter):
        num = self.model2.append()
        name = self.fields[store.get_value(iter, 1)][0]
        self.model2.set(num, 0, name, 1, store.get_value(iter, 1))

    def sig_unsel(self, *args):
        store, paths = self.view2.get_selection().get_selected_rows()
        # Convert first into TreeIter before removing from the store
        iters = [store.get_iter(p) for p in paths]
        for i in iters:
            store.remove(i)

    def sig_unsel_all(self, *args):
        self.model2.clear()

    def response(self, dialog, response):
        if response == gtk.RESPONSE_OK:
            fields = []
            iter = self.model2.get_iter_first()
            while iter:
                fields.append(self.model2.get_value(iter, 1))
                iter = self.model2.iter_next(iter)

            fname = self.import_csv_file.get_filename()
            if fname:
                self.import_csv(fname, fields)
        self.destroy()

    def import_csv(self, fname, fields):
        # TODO: make it works with references
        skip = self.csv_skip.get_value_as_int()
        encoding = self.get_encoding()
        reader = csv.reader(
            open(fname, 'r', encoding=encoding),
            quotechar=self.get_quotechar(),
            delimiter=self.get_delimiter())
        data = []
        for i, line in enumerate(reader):
            if i < skip or not line:
                continue
            data.append([x for x in line])
        try:
            count = RPCExecute(
                'model', self.model, 'import_data', fields, data,
                context=self.context)
        except RPCException:
            return
        if count == 1:
            common.message(_('%d record imported.') % count)
        else:
            common.message(_('%d records imported.') % count)
