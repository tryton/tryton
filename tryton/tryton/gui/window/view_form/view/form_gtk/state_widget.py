# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import functools

from gi.repository import Gtk

import tryton.common as common
from tryton.action import Action
from tryton.config import CONFIG
from tryton.pyson import PYSONDecoder


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


class Link(StateMixin, Gtk.Button):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_can_focus(False)
        if self.attrs.get('icon'):
            self.set_always_show_image(True)
            self.set_image(common.IconFactory.get_image(
                    self.attrs['icon'], Gtk.IconSize.LARGE_TOOLBAR))
            self.set_image_position(Gtk.PositionType.TOP)
        self._current = None

    @property
    def action_id(self):
        return int(self.attrs['id'])

    def state_set(self, record):
        super().state_set(record)
        if not self.get_visible():
            return
        if CONFIG['client.modepda']:
            self.hide()
            return
        if record:
            data = {
                'model': record.model_name,
                'id': record.id,
                'ids': [record.id],
                }
            context = record.get_context()
            pyson_ctx = {
                'active_model': record.model_name,
                'active_id': record.id,
                'active_ids': [record.id],
                }
            self._current = record.id
        else:
            data = {}
            context = {}
            pyson_ctx = {}
            self._current = None
        pyson_ctx['context'] = context
        try:
            self.disconnect_by_func(self.__class__.clicked)
        except TypeError:
            pass
        self.connect('clicked', self.__class__.clicked, [data, context])
        action = common.RPCExecute(
            'model', 'ir.action', 'get_action_value', self.action_id,
            context=context)
        self.set_label(action['rec_name'])

        decoder = PYSONDecoder(pyson_ctx)
        domain = decoder.decode(action['pyson_domain'])
        if action.get('pyson_search_value'):
            domain = [domain, decoder.decode(action['pyson_search_value'])]
        tab_domains = [(n, decoder.decode(d))
            for n, d, c in action['domains'] if c]
        if tab_domains:
            label = ('%s\n' % action['rec_name']) + '\n'.join(
                '%s (%%d)' % n for n, _ in tab_domains)
        else:
            label = '%s (%%d)' % action['rec_name']
        if record and self.action_id in record.links_counts:
            counter = record.links_counts[self.action_id]
            self._set_label_counter(label, counter)
        else:
            counter = [0] * (len(tab_domains) or 1)
            if record:
                record.links_counts[self.action_id] = counter
            if tab_domains:
                for i, (_, tab_domain) in enumerate(tab_domains):
                    common.RPCExecute(
                        'model', action['res_model'], 'search_count',
                        ['AND', domain, tab_domain], context=context,
                        callback=functools.partial(
                            self._set_count, idx=i, current=self._current,
                            counter=counter, label=label))
            else:
                common.RPCExecute(
                    'model', action['res_model'], 'search_count', domain,
                    context=context, callback=functools.partial(
                        self._set_count, current=self._current,
                        counter=counter, label=label))

    def _set_count(self, value, idx=0, current=None, counter=None, label=''):
        if current != self._current:
            return
        try:
            counter[idx] = value()
        except common.RPCException:
            pass
        self._set_label_counter(label, counter)

    def _set_label_counter(self, label, counter):
        self.set_label(label % tuple(counter))
        if self.attrs.get('empty') == 'hide':
            if any(counter):
                self.show()
            else:
                self.hide()

    def clicked(self, data):
        Action.execute(self.action_id, *data, keyword=True)
