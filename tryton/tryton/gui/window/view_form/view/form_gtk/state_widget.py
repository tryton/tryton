# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import Gtk

import tryton.common as common


class StateMixin(object):

    def __init__(self, *args, **kwargs):
        self.attrs = kwargs.pop('attrs')
        super(StateMixin, self).__init__(*args, **kwargs)

    def state_set(self, record):
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}))
        else:
            state_changes = {}
        if state_changes.get('invisible', self.attrs.get('invisible')):
            self.hide()
        else:
            self.show()


class Label(StateMixin, Gtk.Label):

    def state_set(self, record):
        super(Label, self).state_set(record)
        if 'name' in self.attrs and record:
            field = record.group.fields[self.attrs['name']]
        else:
            field = None
        if not self.attrs.get('string', True) and field:
            if record:
                text = field.get_client(record) or ''
            else:
                text = ''
            self.set_text(text)
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}))
        else:
            state_changes = {}
        required = ((field and field.attrs.get('required'))
                or state_changes.get('required'))
        readonly = ((field and field.attrs.get('readonly'))
                or state_changes.get('readonly', not bool(field)))
        common.apply_label_attributes(self, readonly, required)


class VBox(StateMixin, Gtk.VBox):
    pass


class Image(StateMixin, Gtk.Image):

    def state_set(self, record):
        super(Image, self).state_set(record)
        if not record:
            return
        name = self.attrs['name']
        if name in record.group.fields:
            field = record.group.fields[name]
            name = field.get(record)
        self.set_from_pixbuf(common.IconFactory.get_pixbuf(
                name, int(self.attrs.get('size', 48))))


class Frame(StateMixin, Gtk.Frame):

    def __init__(self, label=None, attrs=None):
        if not label:  # label must be None to have no label widget
            label = None
        super(Frame, self).__init__(label=label, attrs=attrs)
        if not label:
            self.set_shadow_type(Gtk.ShadowType.NONE)
        self.set_border_width(0)


class ScrolledWindow(StateMixin, Gtk.ScrolledWindow):

    def state_set(self, record):
        # Force to show first to ensure it is displayed in the Notebook
        self.show()
        super(ScrolledWindow, self).state_set(record)


class Notebook(StateMixin, Gtk.Notebook):

    def state_set(self, record):
        super(Notebook, self).state_set(record)
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}))
        else:
            state_changes = {}
        if state_changes.get('readonly', self.attrs.get('readonly')):
            for widgets in self.widgets.values():
                for widget in widgets:
                    widget._readonly_set(True)


class Expander(StateMixin, Gtk.Expander):

    def __init__(self, label=None, attrs=None):
        if not label:
            label = None
        super(Expander, self).__init__(label=label, attrs=attrs)
