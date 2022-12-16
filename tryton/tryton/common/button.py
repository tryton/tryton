# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gtk

from tryton.common import IconFactory

_ = gettext.gettext


class Button(Gtk.Button):

    def __init__(self, attrs=None):
        self.attrs = attrs or {}
        self.label = '_' + attrs.get('string', '').replace('_', '__')
        super(Button, self).__init__(label=self.label, stock=None,
            use_underline=True)
        self._set_icon(attrs.get('icon'))

    def _set_icon(self, stock):
        self.set_always_show_image(bool(stock))
        image = self.get_image()
        if not image and not stock:
            return
        if not stock:
            self.set_image(None)
            return
        self.set_image(IconFactory.get_image(stock, Gtk.IconSize.BUTTON))

    def state_set(self, record):
        if record:
            states = record.expr_eval(self.attrs.get('states', {}))
        else:
            states = {}
        if states.get('invisible', False):
            self.hide()
        else:
            self.show()
        self.set_sensitive(not states.get('readonly', False))
        self._set_icon(states.get('icon', self.attrs.get('icon')))

        if self.attrs.get('rule'):
            label = self.label
            tip = self.attrs.get('help', '')
            if record:
                clicks = record.get_button_clicks(self.attrs['name'])
                if clicks:
                    label += ' (%s)' % len(clicks)
                    if tip:
                        tip += '\n'
                    tip += _('By: ') + _(', ').join(iter(clicks.values()))
            self.set_label(label)
            self.set_tooltip_text(tip)

        if self.attrs.get('type', 'class') == 'class':
            parent = record.parent if record else None
            while parent:
                if parent.modified:
                    self.set_sensitive(False)
                    break
                parent = parent.parent
