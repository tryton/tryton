#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import operator
import gtk
import gobject
import gettext
import math
from many2one import Many2One
from tryton.common import RPCExecute, RPCException

_ = gettext.gettext


class Reference(Many2One):

    def __init__(self, field_name, model_name, attrs=None):
        super(Reference, self).__init__(field_name, model_name, attrs=attrs)

        self.widget_combo = gtk.ComboBoxEntry()
        child = self.widget_combo.get_child()
        child.set_editable(False)
        child.connect('changed', self.sig_changed_combo)
        self.widget.pack_start(self.widget_combo, expand=False, fill=True)

        self.widget.pack_start(gtk.Label('-'), expand=False, fill=False)

        self._selection = {}
        self._selection2 = {}
        selection = attrs.get('selection', [])
        if not isinstance(selection, (list, tuple)):
            try:
                selection = RPCExecute('model', self.model_name, selection)
            except RPCException:
                selection = []
        selection.sort(key=operator.itemgetter(1))
        if selection:
            pop = sorted((len(x) for x in selection), reverse=True)
            average = sum(pop) / len(pop)
            deviation = int(math.sqrt(sum((x - average) ** 2 for x in pop) /
                    len(pop)))
            width = max(next((x for x in pop if x < (deviation * 4)), 10), 10)
        else:
            width = 10
        child.set_width_chars(width)

        self.set_popdown(selection)

        self.widget.set_focus_chain([self.widget_combo, self.wid_text])

    def grab_focus(self):
        return self.widget_combo.grab_focus()

    def get_model(self):
        child = self.widget_combo.get_child()
        res = child.get_text()
        return self._selection.get(res, False)

    def set_popdown(self, selection):
        model = gtk.ListStore(gobject.TYPE_STRING)
        for (i, j) in selection:
            name = str(j)
            model.append((name,))
            self._selection[name] = i
            self._selection2[i] = name
        self.widget_combo.set_model(model)
        self.widget_combo.set_text_column(0)

    def _readonly_set(self, value):
        super(Reference, self)._readonly_set(value)
        self.widget_combo.set_sensitive(not value)
        if not value:
            self.widget.set_focus_chain([self.widget_combo, self.wid_text])

    @property
    def modified(self):
        if self.record and self.field:
            try:
                model, name = self.field.get_client(self.record)
            except (ValueError, TypeError):
                model, name = '', ''
            return (model != self.get_model()
                or name != self.wid_text.get_text())
        return False

    def has_target(self, value):
        if value is None:
            return False
        model, value = value.split(',')
        if not value:
            value = None
        else:
            try:
                value = int(value)
            except ValueError:
                value = None
        result = model == self.get_model() and value >= 0
        return result

    def value_from_id(self, id_, str_=None):
        if str_ is None:
            str_ = ''
        return self.get_model(), (id_, str_)

    @staticmethod
    def id_from_value(value):
        _, value = value.split(',')
        return int(value)

    def sig_changed_combo(self, *args):
        if not self.changed:
            return
        self.wid_text.set_text('')
        self.wid_text.set_position(0)
        self.field.set_client(self.record, (self.get_model(), (-1, '')))

    def set_value(self, record, field):
        if not self.get_model():
            value = self.wid_text.get_text()
            if not value:
                field.set_client(record, None)
            else:
                return field.set_client(record, ('', value))
        return super(Reference, self).set_value(record, field)

    def set_text(self, value):
        if value:
            model, value = value
        else:
            model, value = None, None
        super(Reference, self).set_text(value)
        child = self.widget_combo.get_child()
        if model:
            child.set_text(self._selection2[model])
            child.set_position(len(self._selection2[model]))
        else:
            child.set_text('')
            child.set_position(0)
