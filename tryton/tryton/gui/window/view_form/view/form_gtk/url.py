# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
from .char import Char
import webbrowser
import tryton.common as common
from tryton.config import CONFIG


class URL(Char):
    "url"

    def __init__(self, view, attrs):
        super(URL, self).__init__(view, attrs)

        self.tooltips = common.Tooltips()
        self.button = gtk.Button()
        self.button.set_image(common.IconFactory.get_image(
                'tryton-public', gtk.ICON_SIZE_SMALL_TOOLBAR))
        self.button.set_relief(gtk.RELIEF_NONE)
        self.button.connect('clicked', self.button_clicked)
        self.button.set_alignment(0.5, 0.5)
        self.widget.pack_start(self.button, expand=False, fill=False)
        self.widget.set_focus_chain([self.entry])

    def display(self, record, field):
        super(URL, self).display(record, field)
        self.set_tooltips()
        if record and 'icon' in self.attrs:
            icon = self.attrs['icon']
            if icon in record.group.fields:
                value = record[icon].get_client(record) or 'tryton-public'
            else:
                value = icon
            self.button.set_image(common.IconFactory.get_image(
                    value, gtk.ICON_SIZE_SMALL_TOOLBAR))

    def set_tooltips(self):
        value = self.entry.get_text()
        if value:
            self.tooltips.enable()
            self.tooltips.set_tip(self.button, value)
        else:
            self.tooltips.set_tip(self.button, '')
            self.tooltips.disable()

    def _readonly_set(self, value):
        super(URL, self)._readonly_set(value)
        if value:
            self.entry.hide()
        else:
            self.entry.show()
        if value and CONFIG['client.fast_tabbing']:
            self.widget.set_focus_chain([self.button])
        else:
            self.widget.set_focus_chain([self.entry])
        self.button.set_sensitive(True)

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
