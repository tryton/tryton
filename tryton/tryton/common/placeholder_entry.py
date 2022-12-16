# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk


if hasattr(gtk.Entry, 'set_placeholder_text'):
    PlaceholderEntry = gtk.Entry
else:
    class PlaceholderEntry(gtk.Entry):

        _placeholder = ''
        _default = True

        def __init__(self, *args, **kwargs):
            super(PlaceholderEntry, self).__init__(*args, **kwargs)
            style = self.get_style()
            self._text_color_normal = style.text[gtk.STATE_NORMAL]
            self._text_color_placeholder = style.text[gtk.STATE_INSENSITIVE]
            self.connect('focus-in-event', PlaceholderEntry._focus_in)
            self.connect('focus-out-event', PlaceholderEntry._focus_out)

        def _focus_in(self, event):
            if self._default:
                super(PlaceholderEntry, self).set_text('')
                self.modify_text(gtk.STATE_NORMAL, self._text_color_normal)
            self._default = False

        def _focus_out(self, event=None):
            if super(PlaceholderEntry, self).get_text() == '':
                super(PlaceholderEntry, self).set_text(self._placeholder)
                self.modify_text(gtk.STATE_NORMAL,
                    self._text_color_placeholder)
                self._default = True
            else:
                self.modify_text(gtk.STATE_NORMAL, self._text_color_normal)
                self._default = False

        def set_placeholder_text(self, text):
            self._placeholder = text
            if not self.has_focus():
                if self._default:
                    super(PlaceholderEntry, self).set_text('')
                self._focus_out()

        def get_text(self):
            if self._default:
                return ''
            return super(PlaceholderEntry, self).get_text()

        def set_text(self, text):
            super(PlaceholderEntry, self).set_text(text)
            if not self.has_focus():
                self._focus_out()

if __name__ == '__main__':
    win = gtk.Window()
    win.set_title('PlaceholderEntry')

    def cb(window, event):
        gtk.main_quit()
    win.connect('delete-event', cb)
    vbox = gtk.VBox()
    win.add(vbox)

    entry = gtk.Entry()
    vbox.pack_start(entry)

    placeholder_entry = PlaceholderEntry()
    placeholder_entry.set_placeholder_text('Placeholder')
    # Set twice to check placeholder does not become text
    placeholder_entry.set_placeholder_text('Placeholder')
    vbox.pack_start(placeholder_entry)

    win.show_all()
    gtk.main()
