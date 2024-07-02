# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
import webbrowser
from urllib.parse import urlencode, urljoin

from gi.repository import Gtk

import tryton.common as common
from tryton.common.common import selection
from tryton.common.underline import set_underline
from tryton.config import CONFIG
from tryton.rpc import CONNECTION

from .char import Char
from .widget import TranslateMixin, Widget

_ = gettext.gettext


class URL(Char):
    "url"

    def __init__(self, view, attrs):
        super(URL, self).__init__(view, attrs)

        self.tooltips = common.Tooltips()
        self.button = Gtk.Button()
        self.button.set_image(common.IconFactory.get_image(
                'tryton-public', Gtk.IconSize.SMALL_TOOLBAR))
        self.button.set_relief(Gtk.ReliefStyle.NONE)
        self.button.connect('clicked', self.button_clicked)
        self.widget.pack_start(
            self.button, expand=False, fill=False, padding=0)

    def display(self):
        super(URL, self).display()
        self.set_tooltips()
        if self.record and 'icon' in self.attrs:
            icon = self.attrs['icon']
            if icon in self.record.group.fields:
                value = self.record[icon].get_client(self.record)
                value = value if value else 'tryton-public'
            else:
                value = icon
            self.button.set_image(common.IconFactory.get_image(
                    value, Gtk.IconSize.SMALL_TOOLBAR))
        self.button.set_sensitive(bool(self.entry.get_text()))

    def set_tooltips(self):
        value = self.entry.get_text()
        if value:
            self.tooltips.enable()
            self.tooltips.set_tip(self.button, value)
        else:
            self.tooltips.set_tip(self.button, '')
            self.tooltips.disable()

    def button_clicked(self, widget):
        value = self.entry.get_text()
        if value:
            webbrowser.open(value, new=2)


class Email(URL):
    "email"

    def button_clicked(self, widget):
        value = self.entry.get_text()
        if value:
            webbrowser.open('mailto:%s' % value, new=2)

    def set_tooltips(self):
        value = self.entry.get_text()
        if value:
            self.tooltips.enable()
            self.tooltips.set_tip(self.button, 'mailto:%s' % value)
        else:
            self.tooltips.set_tip(self.button, '')
            self.tooltips.disable()


class CallTo(URL):
    "call to"

    def button_clicked(self, widget):
        value = self.entry.get_text()
        if value:
            webbrowser.open('callto:%s' % value, new=2)

    def set_tooltips(self):
        value = self.entry.get_text()
        if value:
            self.tooltips.enable()
            self.tooltips.set_tip(self.button, 'callto:%s' % value)
        else:
            self.tooltips.set_tip(self.button, '')
            self.tooltips.disable()


class SIP(URL):
    "sip"

    def button_clicked(self, widget):
        value = self.entry.get_text()
        if value:
            webbrowser.open('sip:%s' % value, new=2)

    def set_tooltips(self):
        value = self.entry.get_text()
        if value:
            self.tooltips.enable()
            self.tooltips.set_tip(self.button, 'sip:%s' % value)
        else:
            self.tooltips.set_tip(self.button, '')
            self.tooltips.disable()


class HTML(Widget, TranslateMixin):
    "HTML"

    def __init__(self, view, attrs):
        super().__init__(view, attrs)
        self.widget = Gtk.HBox()
        self.mnemonic_widget = self.button = Gtk.LinkButton()
        self.button.set_label(set_underline(attrs['string']))
        self.button.set_use_underline(True)
        self.button.set_alignment(0, 0.5)
        self.widget.pack_start(
            self.button, expand=False, fill=False, padding=0)

        if attrs.get('translate'):
            self.button.set_image(common.IconFactory.get_image(
                    'tryton-translate', Gtk.IconSize.SMALL_TOOLBAR))
            self.button.set_always_show_image(True)
            self.button.connect('clicked', self.translate)

    def uri(self, language=None):
        if not self.record or self.record.id < 0 or CONNECTION.url is None:
            uri = ''
        else:
            path = ['ir/html', self.model_name, str(self.record.id),
                self.field_name]
            params = {
                'language': language or CONFIG['client.lang'],
                'title': CONFIG['client.title'],
                }
            uri = urljoin(
                CONNECTION.url + '/', '/'.join(path) + '?' + urlencode(params))
        return uri

    def display(self):
        super().display()
        if self.attrs.get('translate'):
            self.button.set_uri(self.uri())

    def _readonly_set(self, value):
        super()._readonly_set(value)
        for button in self.widget.get_children():
            button.set_sensitive(not value)

    def translate_dialog(self, languages):
        languages = {l['name']: l['code'] for l in languages}
        result = selection(
            _('Choose a language'), languages, default=CONFIG['client.lang'])
        if result:
            webbrowser.open(self.uri(language=result[1]), new=2)
