# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk

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


class Label(StateMixin, gtk.Label):

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
                or state_changes.get('readonly'))
        attrlist = common.get_label_attributes(readonly, required)
        self.set_attributes(attrlist)


class VBox(StateMixin, gtk.VBox):
    pass


class Image(StateMixin, gtk.Image):
    pass


class Frame(StateMixin, gtk.Frame):

    def __init__(self, label=None, attrs=None):
        if not label:  # label must be None to have no label widget
            label = None
        super(Frame, self).__init__(label=label, attrs=attrs)
        if not label:
            self.set_shadow_type(gtk.SHADOW_NONE)
        self.set_border_width(0)


class ScrolledWindow(StateMixin, gtk.ScrolledWindow):
    pass


class Notebook(StateMixin, gtk.Notebook):

    def state_set(self, record):
        super(Notebook, self).state_set(record)
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}))
        else:
            state_changes = {}
        if state_changes.get('readonly', self.attrs.get('readonly')):
            for widgets in self.widgets.itervalues():
                for widget in widgets:
                    widget._readonly_set(True)


class Alignment(gtk.Alignment):

    def __init__(self, widget, attrs):
        super(Alignment, self).__init__(
            float(attrs.get('xalign', 0.0)),
            float(attrs.get('yalign', 0.5)),
            float(attrs.get('xexpand', 1.0)),
            float(attrs.get('yexpand', 1.0)))
        self.add(widget)
        widget.connect('show', lambda *a: self.show())
        widget.connect('hide', lambda *a: self.hide())
