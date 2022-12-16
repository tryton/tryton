#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
from interface import WidgetInterface
import tryton.rpc as rpc
from tryton.config import CONFIG

try:
    import gtkspell
except Exception:
    gtkspell = None


class TextBox(WidgetInterface):

    def __init__(self, field_name, model_name, window, attrs=None):
        super(TextBox, self).__init__(field_name, model_name, window,
                attrs=attrs)

        self.widget = gtk.HBox()
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        self.scrolledwindow.set_size_request(-1, 80)

        self.textview = gtk.TextView()
        self.textview.set_wrap_mode(gtk.WRAP_WORD)
        #TODO better tab solution
        self.textview.set_accepts_tab(False)
        self.textview.connect('focus-in-event', lambda x, y: self._focus_in())
        self.textview.connect('focus-out-event', lambda x, y: self._focus_out())
        self.scrolledwindow.add(self.textview)
        self.scrolledwindow.show_all()

        self.widget.pack_start(self.scrolledwindow)
        self.lang = None

    def grab_focus(self):
        return self.textview.grab_focus()

    def _readonly_set(self, value):
        super(TextBox, self)._readonly_set(value)
        self.textview.set_editable(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.textview])
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

    def _color_widget(self):
        return self.textview

    def set_value(self, record, field):
        buf = self.textview.get_buffer()
        iter_start = buf.get_start_iter()
        iter_end = buf.get_end_iter()
        current_text = buf.get_text(iter_start, iter_end, False)
        field.set_client(record, current_text or False)

    def display(self, record, field):
        super(TextBox, self).display(record, field)
        value = field and field.get(record)
        if not value:
            value = ''
        buf = self.textview.get_buffer()
        buf.delete(buf.get_start_iter(), buf.get_end_iter())
        iter_start = buf.get_start_iter()
        buf.insert(iter_start, value)

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

    def display_value(self):
        lines = (self.field.get_client(self.record) or '').split('\n')
        if len(lines) > 1:
            return lines[0] + '...'
        else:
            return lines[0]
