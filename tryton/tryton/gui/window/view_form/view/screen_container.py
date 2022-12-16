#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
import operator
import gobject
import collections

import tryton.common as common
from tryton.common.domain_parser import quote
from tryton.translate import date_format
from tryton.config import TRYTON_ICON
from tryton.pyson import PYSONDecoder

_ = gettext.gettext


class ScreenContainer(object):

    def __init__(self):
        self.viewport = gtk.Viewport()
        self.viewport.set_shadow_type(gtk.SHADOW_NONE)
        self.vbox = gtk.VBox(spacing=3)
        self.vbox.pack_end(self.viewport)
        self.filter_vbox = None
        self.filter_button = None
        self.but_prev = None
        self.but_next = None
        self.alternate_viewport = gtk.Viewport()
        self.alternate_viewport.set_shadow_type(gtk.SHADOW_NONE)
        self.alternate_view = False
        self.search_window = None
        self.search_table = None

    def widget_get(self):
        return self.vbox

    def set_screen(self, screen):
        self.screen = screen

        tooltips = common.Tooltips()
        if self.filter_vbox is not None:
            return
        self.filter_vbox = gtk.VBox(spacing=0)
        self.filter_vbox.set_border_width(0)
        hbox = gtk.HBox(homogeneous=False, spacing=0)
        self.filter_button = gtk.ToggleButton()
        self.filter_button.set_use_underline(True)
        self.filter_button.set_label(_('F_ilters'))
        self.filter_button.set_relief(gtk.RELIEF_NONE)
        self.filter_button.set_alignment(0.0, 0.5)
        self.filter_button.connect('toggled', self.search_box)
        hbox.pack_start(self.filter_button, expand=False, fill=False)

        self.search_entry = gtk.Entry()
        self.search_entry.set_alignment(0.0)
        self.completion = gtk.EntryCompletion()
        self.completion.set_model(gtk.ListStore(str))
        self.completion.set_text_column(0)
        self.completion.props.inline_completion = True
        if hasattr(self.completion.props, 'inline_selection'):
            self.completion.props.inline_selection = True
        if hasattr(self.completion.props, 'popup_set_width'):
            self.completion.props.popup_set_width = False
        self.completion.connect('match-selected', self.match_selected)
        self.search_entry.connect('activate', self.activate)
        self.search_entry.set_completion(self.completion)
        self.search_entry.connect('key-press-event', self.key_press)
        self.search_entry.connect('focus-in-event', self.focus_in)

        hbox.pack_start(self.search_entry, expand=True, fill=True)

        but_find = gtk.Button()
        tooltips.set_tip(but_find, _('Find'))
        but_find.connect('clicked', self.do_search)
        img_find = gtk.Image()
        img_find.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_find.set_alignment(0.5, 0.5)
        but_find.add(img_find)
        but_find.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_find, expand=False, fill=False)

        but_clear = gtk.Button()
        tooltips.set_tip(but_clear, _('Clear'))
        but_clear.connect('clicked', self.clear)
        img_clear = gtk.Image()
        img_clear.set_from_stock('tryton-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_clear.set_alignment(0.5, 0.5)
        but_clear.add(img_clear)
        but_clear.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_clear, expand=False, fill=False)

        but_prev = gtk.Button()
        self.but_prev = but_prev
        tooltips.set_tip(but_prev, _('Previous'))
        but_prev.connect('clicked', self.search_prev)
        img_prev = gtk.Image()
        img_prev.set_from_stock('tryton-go-previous',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_prev.set_alignment(0.5, 0.5)
        but_prev.add(img_prev)
        but_prev.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_prev, expand=False, fill=False)

        but_next = gtk.Button()
        self.but_next = but_next
        tooltips.set_tip(but_next, _('Next'))
        but_next.connect('clicked', self.search_next)
        img_next = gtk.Image()
        img_next.set_from_stock('tryton-go-next',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_next.set_alignment(0.5, 0.5)
        but_next.add(img_next)
        but_next.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_next, expand=False, fill=False)

        hbox.show_all()
        hbox.set_focus_chain([self.search_entry])
        self.filter_vbox.pack_start(hbox, expand=True, fill=False)

        hseparator = gtk.HSeparator()
        hseparator.show()
        self.filter_vbox.pack_start(hseparator, expand=True, fill=False)

        self.vbox.pack_start(self.filter_vbox, expand=False, fill=True)

        self.but_next.set_sensitive(False)
        self.but_prev.set_sensitive(False)

        tooltips.enable()

    def show_filter(self):
        if self.filter_vbox:
            self.filter_vbox.show()

    def hide_filter(self):
        if self.filter_vbox:
            self.filter_vbox.hide()
        if self.filter_button and self.filter_button.get_active():
            self.filter_button.set_active(False)
            self.filter_button.toggled()

    def set(self, widget):
        if self.alternate_view:
            if self.alternate_viewport.get_child():
                self.alternate_viewport.remove(
                        self.alternate_viewport.get_child())
            if widget == self.viewport.get_child():
                self.viewport.remove(self.viewport.get_child())
            self.alternate_viewport.add(widget)
            self.alternate_viewport.show_all()
            return
        if self.viewport.get_child():
            self.viewport.remove(self.viewport.get_child())
        self.viewport.add(widget)
        self.viewport.show_all()

    def update(self):
        res = self.screen.search_complete(self.get_text())
        model = self.completion.get_model()
        model.clear()
        for r in res:
            model.append([r.strip()])

    def clear(self, widget=None):
        self.search_entry.set_text('')

    def get_text(self):
        return self.search_entry.get_text().decode('utf-8')

    def set_text(self, value):
        return self.search_entry.set_text(value)

    def search_next(self, widget=None):
        self.screen.search_next(self.get_text())

    def search_prev(self, widget=None):
        self.screen.search_prev(self.get_text())

    def match_selected(self, completion, model, iter):
        def callback():
            self.update()
            self.search_entry.emit('changed')
        gobject.idle_add(callback)

    def activate(self, widget):
        if not self.search_entry.get_selection_bounds():
            self.do_search(widget)

    def do_search(self, widget=None):
        self.screen.search_filter(self.get_text())

    def set_cursor(self, new=False, reset_view=True):
        if self.filter_vbox:
            self.search_entry.grab_focus()

    def key_press(self, widget, event):
        gobject.idle_add(self.update)

    def focus_in(self, widget, event):
        self.update()
        self.search_entry.emit('changed')

    def search_box(self, button):
        def key_press(window, event):
            if event.keyval == gtk.keysyms.Escape:
                button.set_active(False)
                window.hide()

        def search():
            button.set_active(False)
            self.search_window.hide()
            text = ''
            for label, entry in self.search_table.fields:
                if isinstance(entry, gtk.ComboBox):
                    value = entry.get_active_text()
                else:
                    value = entry.get_text()
                if value:
                    text += label + ' ' + quote(value) + ' '
            self.set_text(text)
            self.do_search()

        def date_activate(entry):
            entry._focus_out(entry, None)
            search()

        if not self.search_window:
            self.search_window = gtk.Window()
            self.search_window.set_transient_for(button.get_toplevel())
            self.search_window.set_type_hint(
                gtk.gdk.WINDOW_TYPE_HINT_POPUP_MENU)
            self.search_window.set_destroy_with_parent(True)
            self.search_window.set_title('Tryton')
            self.search_window.set_icon(TRYTON_ICON)
            self.search_window.set_decorated(False)
            if hasattr(self.search_window, 'set_deletable'):
                self.search_window.set_deletable(False)
            self.search_window.connect('key-press-event', key_press)
            vbox = gtk.VBox()
            fields = [f for f in self.screen.domain_parser.fields.itervalues()
                if f.get('searchable', True)]
            if (not hasattr(collections, 'OrderedDict')
                    or not isinstance(self.screen.domain_parser.fields,
                        collections.OrderedDict)):
                fields.sort(key=operator.itemgetter('string'))
            self.search_table = gtk.Table(rows=len(fields), columns=2)
            self.search_table.set_border_width(5)
            self.search_table.set_row_spacings(2)
            self.search_table.set_col_spacings(2)

            # Fill table with fields
            self.search_table.fields = []
            for i, field in enumerate(fields):
                label = gtk.Label(field['string'])
                label.set_alignment(0.0, 0.5)
                self.search_table.attach(label, 0, 1, i, i + 1)
                if field['type'] in ('boolean', 'selection'):
                    if hasattr(gtk, 'ComboBoxText'):
                        entry = gtk.ComboBoxText()
                    else:
                        entry = gtk.combo_box_new_text()
                    entry.append_text('')
                    if field['type'] == 'boolean':
                        selections = (_('True'), _('False'))
                    else:
                        selections = tuple(x[1] for x in field['selection'])
                    for selection in selections:
                        entry.append_text(selection)
                elif field['type'] in ('date', 'datetime', 'time'):
                    if field['type'] == 'date':
                        format_ = date_format()
                    elif field['type'] in ('datetime', 'time'):
                        format_ = PYSONDecoder({}).decode(field['format'])
                        if field['type'] == 'datetime':
                            format_ = date_format() + ' ' + format_
                    entry = common.date_widget.DateEntry(format_)
                    entry.connect('activate', date_activate)
                else:
                    entry = gtk.Entry()
                    entry.connect('activate', lambda *a: search())
                self.search_table.attach(entry, 1, 2, i, i + 1)
                self.search_table.fields.append((field['string'] + ':', entry))

            scrolled = gtk.ScrolledWindow()
            scrolled.add_with_viewport(self.search_table)
            scrolled.set_shadow_type(gtk.SHADOW_NONE)
            vbox.pack_start(scrolled, expand=True, fill=True)
            find_button = gtk.Button(_('Find'))
            find_button.connect('clicked', lambda *a: search())
            find_img = gtk.Image()
            find_img.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
            find_button.set_image(find_img)
            hbuttonbox = gtk.HButtonBox()
            hbuttonbox.set_spacing(5)
            hbuttonbox.pack_start(find_button)
            hbuttonbox.set_layout(gtk.BUTTONBOX_END)
            vbox.pack_start(hbuttonbox, expand=False, fill=True)
            self.search_window.add(vbox)
            vbox.show_all()

            # Disable scrolling:
            scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
            # See what changed:
            new_size = self.search_window.size_request()
            # Reenable scrolling:
            scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            self.search_window.set_default_size(*new_size)

        parent = button.get_toplevel()
        button_x, button_y = button.translate_coordinates(parent,
            *parent.window.get_origin())
        button_allocation = button.get_allocation()

        # Resize the window to not be out of the screen
        width, height = self.search_window.get_default_size()
        screen = self.search_window.get_screen()
        screen_width = screen.get_width()
        screen_height = screen.get_height()
        delta_width = screen_width - (button_x + width)
        delta_height = screen_height - (button_y + button_allocation.height
            + height)
        if delta_width < 0:
            width += delta_width
        if delta_height < 0:
            height += delta_height
        self.search_window.resize(width, height)

        # Move the window under the button
        self.search_window.move(button_x,
            button_y + button_allocation.height)

        from tryton.gui.main import Main
        page = Main.get_main().get_page()
        if button.get_active():
            if page and self.search_window not in page.dialogs:
                page.dialogs.append(self.search_window)
            self.search_window.show()
        else:
            self.search_window.hide()
            if page and self.search_window in page.dialogs:
                page.dialogs.remove(self.search_window)
