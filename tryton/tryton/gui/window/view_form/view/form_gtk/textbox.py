# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging

from gi.repository import Gtk, Gdk
try:
    from gi.repository import GtkSpell
except ImportError:
    GtkSpell = None

from .widget import Widget, TranslateMixin
from tryton.config import CONFIG


logger = logging.getLogger(__name__)


class TextBox(Widget, TranslateMixin):
    expand = True

    def __init__(self, view, attrs):
        super(TextBox, self).__init__(view, attrs)

        self.widget = Gtk.VBox()
        self.scrolledwindow = Gtk.ScrolledWindow()
        self.scrolledwindow.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.scrolledwindow.set_size_request(100, 100)

        self.textview = self.mnemonic_widget = self._get_textview()
        self.textview.connect('focus-out-event',
            lambda x, y: self._focus_out())
        self.textview.connect('key-press-event', self.send_modified)
        # The click is grabbed by ListBox widget in this case user can never
        # set the input with a click
        self.textview.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.textview.connect_after('button-press-event', self._button_press)
        self.scrolledwindow.add(self.textview)
        self.scrolledwindow.show_all()

        self.button = None
        if attrs.get('translate'):
            self.button = self.translate_button()
            self.widget.pack_end(
                self.button, expand=False, fill=False, padding=0)

        self.widget.pack_end(
            self.scrolledwindow, expand=True, fill=True, padding=0)

    def _get_textview(self):
        if self.attrs.get('size'):
            textbuffer = TextBufferLimitSize(int(self.attrs['size']))
            textview = Gtk.TextView()
            textview.set_buffer(textbuffer)
        else:
            textview = Gtk.TextView()
        textview.set_wrap_mode(Gtk.WrapMode.WORD)
        # TODO better tab solution
        textview.set_accepts_tab(False)
        return textview

    def _button_press(self, textview, event):
        textview.grab_focus()
        return True

    def translate_widget(self):
        box = Gtk.VBox()
        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolledwindow.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scrolledwindow.set_size_request(-1, 80)

        textview = self._get_textview()
        scrolledwindow.add(textview)
        box.pack_end(scrolledwindow, expand=True, fill=True, padding=0)
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

    @property
    def modified(self):
        if self.record and self.field:
            return self.field.get_client(self.record) != self.get_value()
        return False

    def get_value(self):
        return self.get_buffer(self.textview)

    def set_value(self):
        self.field.set_client(self.record, self.get_value())

    def set_buffer(self, value, textview):
        buf = textview.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        iter_start = buf.get_start_iter()
        buf.insert(iter_start, value)

    def get_buffer(self, textview):
        buf = textview.get_buffer()
        iter_start = buf.get_start_iter()
        iter_end = buf.get_end_iter()
        return buf.get_text(iter_start, iter_end, False)

    def display(self):
        super(TextBox, self).display()
        value = self.field and self.field.get(self.record)
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


class TextBufferLimitSize(Gtk.TextBuffer):
    __gsignals__ = {
        'insert-text': 'override',
        }

    def __init__(self, max_length):
        super(TextBufferLimitSize, self).__init__()
        self.max_length = max_length

    def do_insert_text(self, iter, text, length):
        free_chars = self.max_length - self.get_char_count()
        text = text[0:free_chars]
        length = len(text)
        return Gtk.TextBuffer.do_insert_text(self, iter, text, length)
