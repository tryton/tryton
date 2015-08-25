# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
from .widget import Widget, TranslateMixin
from tryton.config import CONFIG

try:
    import gtkspell
except ImportError:
    gtkspell = None


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

        hbox = gtk.HBox()
        hbox.pack_start(self.scrolledwindow)
        self.widget.pack_end(hbox)
        self.lang = None

        self.button = None
        if attrs.get('translate'):
            self.button = self.translate_button()
            hbox.pack_start(self.button, False, False)

    def _get_textview(self):
        if self.attrs.get('size'):
            textbuffer = TextBufferLimitSize(int(self.attrs['size']))
            textview = gtk.TextView(textbuffer)
        else:
            textview = gtk.TextView()
        textview.set_wrap_mode(gtk.WRAP_WORD)
        # TODO better tab solution
        textview.set_accepts_tab(False)
        return textview

    def translate_widget(self):
        scrolledwindow = gtk.ScrolledWindow()
        scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
            gtk.POLICY_AUTOMATIC)
        scrolledwindow.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        scrolledwindow.set_size_request(-1, 80)

        textview = self._get_textview()
        scrolledwindow.add(textview)
        return scrolledwindow

    @staticmethod
    def translate_widget_set(widget, value):
        textview = widget.get_child()
        buf = textview.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        buf.insert(buf.get_start_iter(), value or '')

    @staticmethod
    def translate_widget_get(widget):
        textview = widget.get_child()
        buf = textview.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(),
            False).decode('utf-8')

    @staticmethod
    def translate_widget_set_readonly(widget, value):
        textview = widget.get_child()
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
        if gtkspell:
            spell = None
            try:
                spell = gtkspell.get_from_text_view(self.textview)
            except Exception:
                pass

            if not value and self.attrs.get('spell') \
                    and CONFIG['client.spellcheck'] \
                    and self.record:
                language = self.record.expr_eval(self.attrs['spell'])
                try:
                    if not spell:
                        spell = gtkspell.Spell(self.textview)
                    if self.lang != language:
                        try:
                            spell.set_language(language)
                        except Exception:
                            spell.detach()
                            del spell
                        self.lang = language
                except Exception:
                    pass
            elif spell:
                spell.detach()
                del spell

    @property
    def modified(self):
        if self.record and self.field:
            return self.field.get_client(self.record) != self.get_value()
        return False

    def get_value(self):
        buf = self.textview.get_buffer()
        iter_start = buf.get_start_iter()
        iter_end = buf.get_end_iter()
        return buf.get_text(iter_start, iter_end, False).decode('utf-8')

    def set_value(self, record, field):
        field.set_client(record, self.get_value())

    def set_buffer(self, value):
        if value == self.get_value():
            return
        buf = self.textview.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        iter_start = buf.get_start_iter()
        buf.insert(iter_start, value)

    def display(self, record, field):
        super(TextBox, self).display(record, field)
        value = field and field.get(record)
        if not value:
            value = ''
        self.set_buffer(value)
        if gtkspell:
            spell = None
            try:
                spell = gtkspell.get_from_text_view(self.textview)
            except Exception:
                pass

            if self.attrs.get('spell') and CONFIG['client.spellcheck'] \
                    and self.record:
                language = self.record.expr_eval(self.attrs['spell'])
                try:
                    if not spell:
                        spell = gtkspell.Spell(self.textview)
                    if self.lang != language:
                        try:
                            spell.set_language(language)
                        except Exception:
                            spell.detach()
                            del spell
                        self.lang = language
                except Exception:
                    pass
            elif spell:
                spell.detach()
                del spell


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
