# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

import gtk
from .widget import Widget, TranslateMixin
from tryton.config import CONFIG

try:
    from gi.repository import GtkSpell
except ImportError:
    GtkSpell = None

logger = logging.getLogger(__name__)


class TextBox(Widget, TranslateMixin):
    expand = True

    def __init__(self, view, attrs):
        super(TextBox, self).__init__(view, attrs)

        self.widget = gtk.VBox()
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        self.scrolledwindow.set_size_request(-1, 80)

        self.textview = self.mnemonic_widget = self._get_textview()
        self.textview.connect('focus-out-event',
            lambda x, y: self._focus_out())
        self.textview.connect('key-press-event', self.send_modified)
        self.scrolledwindow.add(self.textview)
        self.scrolledwindow.show_all()

        self.button = None
        if attrs.get('translate'):
            self.button = self.translate_button()
            self.widget.pack_end(self.button, False, False)

        self.widget.pack_end(self.scrolledwindow)

    def _get_textview(self):
        if self.attrs.get('size'):
            textbuffer = TextBufferLimitSize(int(self.attrs['size']))
            textview = gtk.TextView()
            textview.set_buffer(textbuffer)
        else:
            textview = gtk.TextView()
        textview.set_wrap_mode(gtk.WRAP_WORD)
        # TODO better tab solution
        textview.set_accepts_tab(False)
        return textview

    def translate_widget(self):
        box = gtk.VBox()
        scrolledwindow = gtk.ScrolledWindow()
        scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
            gtk.POLICY_AUTOMATIC)
        scrolledwindow.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        scrolledwindow.set_size_request(-1, 80)

        textview = self._get_textview()
        scrolledwindow.add(textview)
        box.pack_end(scrolledwindow)
        return box

    def translate_widget_set(self, widget, value):
        textview = widget.get_children()[-1].get_child()
        self.set_buffer(value, textview)

    def translate_widget_get(self, widget):
        textview = widget.get_children()[-1].get_child()
        return self.get_buffer(textview)

    def translate_widget_set_readonly(self, widget, value):
        textview = widget.get_children()[-1].get_child()
        textview.set_editable(not value)
        textview.props.sensitive = not value

    def _readonly_set(self, value):
        super(TextBox, self)._readonly_set(value)
        self.textview.set_editable(not value)
        if self.button:
            self.button.set_sensitive(not value)
        if value and CONFIG['client.fast_tabbing']:
            self.widget.set_focus_chain([])
        else:
            self.widget.unset_focus_chain()

    @property
    def modified(self):
        if self.record and self.field:
            return self.field.get_client(self.record) != self.get_value()
        return False

    def get_value(self):
        return self.get_buffer(self.textview)

    def set_value(self, record, field):
        field.set_client(record, self.get_value())

    def set_buffer(self, value, textview):
        buf = textview.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        iter_start = buf.get_start_iter()
        buf.insert(iter_start, value)

    def get_buffer(self, textview):
        buf = textview.get_buffer()
        iter_start = buf.get_start_iter()
        iter_end = buf.get_end_iter()
        return buf.get_text(iter_start, iter_end, False).decode('utf-8')

    def display(self, record, field):
        super(TextBox, self).display(record, field)
        value = field and field.get(record)
        if not value:
            value = ''
        self.set_buffer(value, self.textview)
        if (GtkSpell
                and self.textview.get_editable()
                and self.attrs.get('spell')
                and CONFIG['client.spellcheck']):
            checker = GtkSpell.Checker.get_from_text_view(self.textview)

            if self.record:
                language = self.record.expr_eval(self.attrs['spell'])
                if not checker:
                    checker = GtkSpell.Checker()
                    checker.attach(self.textview)
                if checker.get_language() != language:
                    try:
                        checker.set_language(language)
                    except Exception:
                        logger.debug(
                            'Could not set spell checker to "%s"', language)
                        checker.detach()
            elif checker:
                checker.detach()


class TextBufferLimitSize(gtk.TextBuffer):
    __gsignals__ = {
        'insert-text': 'override',
        }

    def __init__(self, max_length):
        super(TextBufferLimitSize, self).__init__()
        self.max_length = max_length

    def do_insert_text(self, iter, text, length):
        free_chars = self.max_length - self.get_char_count()
        # Slice operation needs an unicode string to work as expected
        text = text.decode('utf-8')[0:free_chars].encode('utf-8')
        length = len(text)
        return gtk.TextBuffer.do_insert_text(self, iter, text, length)
