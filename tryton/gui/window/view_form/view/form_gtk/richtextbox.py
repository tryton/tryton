# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from weakref import WeakKeyDictionary

from gi.repository import Gtk

from .textbox import TextBox
from tryton.common.htmltextbuffer import normalize_markup
from tryton.common.richtext import (
    register_format, set_content, get_content, add_toolbar)
from tryton.config import CONFIG


class RichTextBox(TextBox):

    def __init__(self, view, attrs):
        super(RichTextBox, self).__init__(view, attrs)
        self.toolbar = None
        self.tag_widgets = WeakKeyDictionary()
        self.tags = {}
        self.colors = {}
        if int(self.attrs.get('toolbar', 1)):
            self.toolbar = add_toolbar(self.textview)
            self.toolbar.set_style({
                    'default': False,
                    'both': Gtk.ToolbarStyle.BOTH,
                    'text': Gtk.ToolbarStyle.TEXT,
                    'icons': Gtk.ToolbarStyle.ICONS,
                    }[CONFIG['client.toolbar']])
            self.widget.pack_start(
                self.toolbar, expand=False, fill=True, padding=0)

    def _get_textview(self):
        textview = super(RichTextBox, self)._get_textview()
        register_format(textview)
        return textview

    def translate_widget(self):
        widget = super(RichTextBox, self).translate_widget()
        textview = widget.get_children()[-1].get_child()
        if self.toolbar:
            widget.pack_start(
                add_toolbar(textview), expand=False, fill=True, padding=0)
        return widget

    def translate_widget_set_readonly(self, widget, value):
        super(RichTextBox, self).translate_widget_set_readonly(widget, value)
        if self.toolbar:
            toolbar = widget.get_children()[0]
            for n in range(toolbar.get_n_items()):
                tool = toolbar.get_nth_item(n)
                tool.set_sensitive(not value)

    def set_value(self):
        # avoid modification of not normalized value
        value = self.get_value()
        prev_value = self.field.get_client(self.record) or ''
        if value == normalize_markup(prev_value):
            value = prev_value
        self.field.set_client(self.record, value)

    @property
    def modified(self):
        if self.record and self.field:
            value = normalize_markup(self.field.get_client(self.record) or '')
            return value != self.get_value()
        return False

    def set_buffer(self, value, textview):
        set_content(textview, value)

    def get_buffer(self, textview):
        return get_content(textview)

    def _readonly_set(self, value):
        super(RichTextBox, self)._readonly_set(value)
        if self.toolbar:
            self.toolbar.set_sensitive(not value)
