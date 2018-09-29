# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

import gtk
import gettext
import gobject

import tryton.common as common
from tryton.gui import Main
from tryton.common.domain_parser import quote
from tryton.common.treeviewcontrol import TreeViewControl
from tryton.common.datetime_ import Date, Time, DateTime, add_operators
from tryton.pyson import PYSONDecoder

_ = gettext.gettext


class Dates(gtk.HBox):

    def __init__(self, format_=None, _entry=Date):
        super(Dates, self).__init__()
        self.from_ = add_operators(_entry())
        self.pack_start(self.from_, expand=True, fill=True)
        self.pack_start(gtk.Label(_('..')), expand=False, fill=False)
        self.to = add_operators(_entry())
        self.pack_start(self.to, expand=True, fill=True)
        if format_:
            self.from_.props.format = format_
            self.to.props.format = format_

    def _get_value(self, widget):
        value = widget.props.value
        if value:
            return common.datetime_strftime(value, widget.props.format)

    def get_value(self):
        from_ = self._get_value(self.from_)
        to = self._get_value(self.to)
        if from_ and to:
            if from_ != to:
                return '%s..%s' % (quote(from_), quote(to))
            else:
                return quote(from_)
        elif from_:
            return '>=%s' % quote(from_)
        elif to:
            return '<=%s' % quote(to)

    @property
    def _widgets(self):
        return [self.from_, self.to]

    def connect_activate(self, callback):
        for widget in self._widgets:
            if isinstance(widget, Date):
                widget.connect('activate', callback)
            elif isinstance(widget, Time):
                widget.get_child().connect('activate', callback)

    def connect_combo(self, callback):
        for widget in self._widgets:
            if isinstance(widget, Time):
                widget.connect('notify::popup-shown', callback)

    def set_values(self, from_, to):
        self.from_.props.value = from_
        self.to.props.value = to


class Times(Dates):

    def __init__(self, format_, _entry=Time):
        super(Times, self).__init__(_entry=_entry)

    def _get_value(self, widget):
        value = widget.props.value
        if value:
            return datetime.time.strftime(value, widget.props.format)


class DateTimes(Dates):

    def __init__(self, date_format, time_format, _entry=DateTime):
        super(DateTimes, self).__init__(_entry=_entry)
        self.from_.props.date_format = date_format
        self.to.props.date_format = date_format
        self.from_.props.time_format = time_format
        self.to.props.time_format = time_format

    def _get_value(self, widget):
        value = widget.props.value
        if value:
            return common.datetime_strftime(value,
                widget.props.date_format + ' ' + widget.props.time_format)

    @property
    def _widgets(self):
        return self.from_.get_children() + self.to.get_children()


class Selection(gtk.ScrolledWindow):

    def __init__(self, selections):
        super(Selection, self).__init__()
        self.treeview = TreeViewControl()
        model = gtk.ListStore(gobject.TYPE_STRING)
        for selection in selections:
            model.append((selection,))
        self.treeview.set_model(model)

        column = gtk.TreeViewColumn()
        cell = gtk.CellRendererText()
        column.pack_start(cell)
        column.add_attribute(cell, 'text', 0)
        self.treeview.append_column(column)
        self.treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.treeview.set_headers_visible(False)
        self.add(self.treeview)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        self.set_min_content_height(min(20 * len(selections), 200))
        self.set_max_content_height(200)

    def get_value(self):
        values = []
        model, paths = self.treeview.get_selection().get_selected_rows()
        if not paths:
            return
        for path in paths:
            iter_ = model.get_iter(path)
            values.append(model.get_value(iter_, 0))
        return ';'.join(quote(v) for v in values)


class ScreenContainer(object):

    def __init__(self, tab_domain):
        self.viewport = gtk.Viewport()
        self.viewport.set_shadow_type(gtk.SHADOW_NONE)
        self.vbox = gtk.VBox(spacing=3)
        self.alternate_viewport = gtk.Viewport()
        self.alternate_viewport.set_shadow_type(gtk.SHADOW_NONE)
        self.alternate_view = False
        self.search_window = None
        self.search_table = None
        self.last_search_text = ''
        self.tab_domain = tab_domain or []
        self.tab_counter = []

        tooltips = common.Tooltips()

        self.filter_vbox = gtk.VBox(spacing=0)
        self.filter_vbox.set_border_width(0)
        hbox = gtk.HBox(homogeneous=False, spacing=0)

        self.search_entry = gtk.Entry()
        self.search_entry.set_placeholder_text(_('Search'))
        self.search_entry.set_alignment(0.0)
        self.search_entry.set_icon_from_pixbuf(
            gtk.ENTRY_ICON_PRIMARY,
            common.IconFactory.get_pixbuf('tryton-filter', gtk.ICON_SIZE_MENU))
        self.search_entry.set_icon_tooltip_text(
            gtk.ENTRY_ICON_PRIMARY, _('Open filters'))
        self.completion = gtk.EntryCompletion()
        self.completion.set_model(gtk.ListStore(str))
        self.completion.set_text_column(0)
        self.completion.props.inline_selection = True
        self.completion.props.popup_set_width = False
        self.completion.set_match_func(lambda *a: True)
        self.completion.connect('match-selected', self.match_selected)
        self.search_entry.connect('activate', self.activate)
        self.search_entry.set_completion(self.completion)
        self.search_entry.connect('key-press-event', self.key_press)
        self.search_entry.connect('focus-in-event', self.focus_in)
        self.search_entry.connect('icon-press', self.icon_press)

        hbox.pack_start(self.search_entry, expand=True, fill=True)

        def popup(widget):
            menu = widget._menu
            for child in menu.get_children():
                menu.remove(child)
            if not widget.props.active:
                menu.popdown()
                return

            def menu_position(menu, data=None):
                widget_allocation = widget.get_allocation()
                if hasattr(widget.window, 'get_root_coords'):
                    x, y = widget.window.get_root_coords(
                        widget_allocation.x, widget_allocation.y)
                else:
                    x, y = widget.window.get_origin()
                    x += widget_allocation.x
                    y += widget_allocation.y
                return (x, y + widget_allocation.height, False)

            for id_, name, domain in self.bookmarks():
                menuitem = gtk.MenuItem(name)
                menuitem.connect('activate', self.bookmark_activate, domain)
                menu.add(menuitem)

            menu.show_all()
            menu.popup(None, None, menu_position, 0, 0)

        def deactivate(menuitem, togglebutton):
            togglebutton.props.active = False

        but_active = gtk.ToggleButton()
        self.but_active = but_active
        self._set_active_tooltip()
        but_active.add(common.IconFactory.get_image(
                'tryton-archive', gtk.ICON_SIZE_SMALL_TOOLBAR))
        but_active.set_relief(gtk.RELIEF_NONE)
        but_active.connect('toggled', self.search_active)
        hbox.pack_start(but_active, expand=False, fill=False)

        but_bookmark = gtk.ToggleButton()
        self.but_bookmark = but_bookmark
        tooltips.set_tip(but_bookmark, _('Show bookmarks of filters'))
        but_bookmark.add(common.IconFactory.get_image(
                'tryton-bookmarks', gtk.ICON_SIZE_SMALL_TOOLBAR))
        but_bookmark.set_relief(gtk.RELIEF_NONE)
        menu = gtk.Menu()
        menu.set_property('reserve-toggle-size', False)
        menu.connect('deactivate', deactivate, but_bookmark)
        but_bookmark._menu = menu
        but_bookmark.connect('toggled', popup)
        hbox.pack_start(but_bookmark, expand=False, fill=False)

        but_prev = gtk.Button()
        self.but_prev = but_prev
        tooltips.set_tip(but_prev, _('Previous'))
        but_prev.connect('clicked', self.search_prev)
        but_prev.add(common.IconFactory.get_image(
                'tryton-back', gtk.ICON_SIZE_SMALL_TOOLBAR))
        but_prev.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_prev, expand=False, fill=False)

        but_next = gtk.Button()
        self.but_next = but_next
        tooltips.set_tip(but_next, _('Next'))
        but_next.connect('clicked', self.search_next)
        but_next.add(common.IconFactory.get_image(
                'tryton-forward', gtk.ICON_SIZE_SMALL_TOOLBAR))
        but_next.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_next, expand=False, fill=False)

        hbox.show_all()
        hbox.set_focus_chain([self.search_entry])
        self.filter_vbox.pack_start(hbox, expand=False, fill=False)

        hseparator = gtk.HSeparator()
        hseparator.show()
        self.filter_vbox.pack_start(hseparator, expand=False, fill=False)

        if self.tab_domain:
            self.notebook = gtk.Notebook()
            try:
                self.notebook.props.homogeneous = True
            except AttributeError:
                # No more supported by GTK+3
                pass
            self.notebook.set_scrollable(True)
            for name, domain, count in self.tab_domain:
                hbox = gtk.HBox(spacing=3)
                label = gtk.Label('_' + name)
                label.set_use_underline(True)
                hbox.pack_start(label, expand=True, fill=True)
                counter = gtk.Label()
                hbox.pack_start(counter, expand=False, fill=True)
                hbox.show_all()
                self.notebook.append_page(gtk.VBox(), hbox)
                self.tab_counter.append(counter)
            self.filter_vbox.pack_start(self.notebook, expand=True, fill=True)
            self.notebook.show_all()
            # Set the current page before connecting to switch-page to not
            # trigger the search a second times.
            self.notebook.set_current_page(0)
            self.notebook.get_nth_page(0).pack_end(self.viewport)
            self.notebook.connect('switch-page', self.switch_page)
            self.notebook.connect_after('switch-page', self.switch_page_after)
            filter_expand = True
        else:
            self.notebook = None
            self.vbox.pack_end(self.viewport)
            filter_expand = False

        self.vbox.pack_start(self.filter_vbox, expand=filter_expand, fill=True)

        self.but_next.set_sensitive(False)
        self.but_prev.set_sensitive(False)

        tooltips.enable()

    def destroy(self):
        if self.search_window:
            self.search_window.hide()

    def widget_get(self):
        return self.vbox

    def set_screen(self, screen):
        self.screen = screen
        self.but_bookmark.set_sensitive(bool(list(self.bookmarks())))
        self.bookmark_match()

    def show_filter(self):
        if self.filter_vbox:
            self.filter_vbox.show()
        if self.notebook:
            self.notebook.set_show_tabs(True)
            if self.viewport in self.vbox.get_children():
                self.vbox.remove(self.viewport)
                self.notebook.get_nth_page(self.notebook.get_current_page()
                    ).pack_end(self.viewport)

    def hide_filter(self):
        if self.filter_vbox:
            self.filter_vbox.hide()
        if self.notebook:
            self.notebook.set_show_tabs(False)
            if self.viewport not in self.vbox.get_children():
                self.notebook.get_nth_page(self.notebook.get_current_page()
                    ).remove(self.viewport)
                self.vbox.pack_end(self.viewport)

    def set(self, widget):
        viewport1 = self.viewport
        viewport2 = self.alternate_viewport
        if self.alternate_view:
            viewport1, viewport2 = viewport2, viewport1

        if viewport1.get_child():
            viewport1.remove(viewport1.get_child())
        if widget == viewport2.get_child():
            viewport2.remove(widget)
        viewport1.add(widget)
        viewport1.show_all()

    def update(self):
        res = self.screen.search_complete(self.get_text())
        model = self.completion.get_model()
        model.clear()
        for r in res:
            model.append([r.strip()])

    def get_text(self):
        return self.search_entry.get_text()

    def set_text(self, value):
        self.search_entry.set_text(value)
        self.bookmark_match()

    def bookmarks(self):
        for id_, name, domain in common.VIEW_SEARCH[self.screen.model_name]:
            if self.screen.domain_parser.stringable(domain):
                yield id_, name, domain

    def bookmark_activate(self, menuitem, domain):
        self.set_text(self.screen.domain_parser.string(domain))
        self.do_search()

    def bookmark_match(self):
        current_text = self.get_text()
        if current_text:
            current_domain = self.screen.domain_parser.parse(current_text)
            self.search_entry.set_icon_activatable(gtk.ENTRY_ICON_SECONDARY,
                bool(current_text))
            self.search_entry.set_icon_sensitive(gtk.ENTRY_ICON_SECONDARY,
                bool(current_text))
            for id_, name, domain in self.bookmarks():
                text = self.screen.domain_parser.string(domain)
                domain = self.screen.domain_parser.parse(text)
                if (text == current_text
                        or domain == current_domain):
                    self.search_entry.set_icon_from_pixbuf(
                        gtk.ENTRY_ICON_SECONDARY,
                        common.IconFactory.get_pixbuf(
                            'tryton-bookmark', gtk.ICON_SIZE_MENU))
                    self.search_entry.set_icon_tooltip_text(
                        gtk.ENTRY_ICON_SECONDARY, _('Remove this bookmark'))
                    return id_
        self.search_entry.set_icon_from_pixbuf(
            gtk.ENTRY_ICON_SECONDARY,
            common.IconFactory.get_pixbuf(
                'tryton-bookmark-border', gtk.ICON_SIZE_MENU))
        if current_text:
            self.search_entry.set_icon_tooltip_text(gtk.ENTRY_ICON_SECONDARY,
                _('Bookmark this filter'))
        elif self.search_entry.get_icon_tooltip_text(gtk.ENTRY_ICON_SECONDARY):
            self.search_entry.set_icon_tooltip_text(gtk.ENTRY_ICON_SECONDARY,
                None)

    def search_next(self, widget=None):
        self.screen.search_next(self.get_text())

    def search_prev(self, widget=None):
        self.screen.search_prev(self.get_text())

    def search_active(self, widget=None):
        self._set_active_tooltip()
        self.screen.search_filter(self.get_text())

    def _set_active_tooltip(self):
        if self.but_active.get_active():
            tooltip = _('Show active records')
        else:
            tooltip = _('Show inactive records')
        tooltips = common.Tooltips()
        tooltips.set_tip(self.but_active, tooltip)

    def switch_page(self, notebook, page, page_num):
        current_page = notebook.get_nth_page(notebook.get_current_page())
        current_page.remove(self.viewport)

        new_page = notebook.get_nth_page(page_num)
        new_page.pack_end(self.viewport)

    def switch_page_after(self, notebook, page, page_num):
        self.do_search()
        notebook.grab_focus()
        self.screen.count_tab_domain()

    def get_tab_domain(self):
        if not self.notebook:
            return []
        idx = self.notebook.get_current_page()
        if idx < 0:
            return []
        return self.tab_domain[idx][1]

    def set_tab_counter(self, count, idx=None):
        if not self.tab_counter or not self.notebook:
            return
        if idx is None:
            idx = self.notebook.get_current_page()
        if idx < 0:
            return
        label = self.tab_counter[idx]
        tooltip = common.Tooltips()
        if count is None:
            label.set_label('')
            tooltip.set_tip(label, '')
        else:
            tooltip.set_tip(label, '%d' % count)
            fmt = '(%d)'
            if count > 99:
                fmt = '(%d+)'
                count = 99
            label.set_label(fmt % count)

    def match_selected(self, completion, model, iter):
        def callback():
            if not self.search_entry.props.window:
                return
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
        def keypress():
            if not self.search_entry.props.window:
                return
            self.update()
            self.bookmark_match()
        gobject.idle_add(keypress)

    def icon_press(self, widget, icon_pos, event):
        if icon_pos == gtk.ENTRY_ICON_PRIMARY:
            self.search_box(widget)
        elif icon_pos == gtk.ENTRY_ICON_SECONDARY:
            model_name = self.screen.model_name
            id_ = self.bookmark_match()
            if not id_:
                text = self.get_text()
                if not text:
                    return
                name = common.ask(_('Bookmark Name:'))
                if not name:
                    return
                domain = self.screen.domain_parser.parse(text)
                common.VIEW_SEARCH.add(model_name, name, domain)
                self.set_text(self.screen.domain_parser.string(domain))
            else:
                common.VIEW_SEARCH.remove(model_name, id_)
            # Refresh icon and bookmark button
            self.bookmark_match()
            self.but_bookmark.set_sensitive(bool(list(self.bookmarks())))

    def focus_in(self, widget, event):
        self.update()
        self.search_entry.emit('changed')

    def search_box(self, widget):
        def window_hide(window, *args):
            window.hide()
            self.search_entry.grab_focus()

        def key_press(widget, event):
            if event.keyval == gtk.keysyms.Escape:
                window_hide(widget)
                return True
            return False

        def search():
            self.search_window.hide()
            text = ''
            for label, entry in self.search_table.fields:
                if isinstance(entry, gtk.ComboBox):
                    value = quote(entry.get_active_text()) or None
                elif isinstance(entry, (Dates, Selection)):
                    value = entry.get_value()
                else:
                    value = quote(entry.get_text()) or None
                if value is not None:
                    text += quote(label) + ': ' + value + ' '
            self.set_text(text)
            self.do_search()
            # Store text after doing the search
            # because domain parser could simplify the text
            self.last_search_text = self.get_text()

        if not self.search_window:
            self.search_window = gtk.Window()
            Main().add_window(self.search_window)
            self.search_window.set_transient_for(widget.get_toplevel())
            self.search_window.set_type_hint(
                gtk.gdk.WINDOW_TYPE_HINT_POPUP_MENU)
            self.search_window.set_destroy_with_parent(True)
            self.search_window.set_decorated(False)
            self.search_window.set_deletable(False)
            self.search_window.connect('delete-event', window_hide)
            self.search_window.connect('key-press-event', key_press)
            self.search_window.connect('focus-out-event', window_hide)

            def toggle_window_hide(combobox, shown):
                if combobox.props.popup_shown:
                    self.search_window.handler_block_by_func(window_hide)
                else:
                    self.search_window.handler_unblock_by_func(window_hide)

            vbox = gtk.VBox()
            fields = [f for f in self.screen.domain_parser.fields.values()
                if f.get('searchable', True)]
            self.search_table = gtk.Table(rows=len(fields), columns=2)
            self.search_table.set_homogeneous(False)
            self.search_table.set_border_width(5)
            self.search_table.set_row_spacings(2)
            self.search_table.set_col_spacings(2)

            # Fill table with fields
            self.search_table.fields = []
            for i, field in enumerate(fields):
                label = gtk.Label(field['string'])
                label.set_alignment(0.0, 0.0)
                self.search_table.attach(label, 0, 1, i, i + 1,
                    yoptions=gtk.FILL)
                yoptions = False
                if field['type'] == 'boolean':
                    if hasattr(gtk, 'ComboBoxText'):
                        entry = gtk.ComboBoxText()
                    else:
                        entry = gtk.combo_box_new_text()
                    entry.connect('notify::popup-shown', toggle_window_hide)
                    entry.append_text('')
                    selections = (_('True'), _('False'))
                    for selection in selections:
                        entry.append_text(selection)
                elif field['type'] == 'selection':
                    selections = tuple(x[1] for x in field['selection'])
                    entry = Selection(selections)
                    yoptions = gtk.FILL | gtk.EXPAND
                elif field['type'] in ('date', 'datetime', 'time'):
                    date_format = common.date_format(
                        self.screen.context.get('date_format'))
                    if field['type'] == 'date':
                        entry = Dates(date_format)
                    elif field['type'] in ('datetime', 'time'):
                        time_format = PYSONDecoder({}).decode(field['format'])
                        if field['type'] == 'time':
                            entry = Times(time_format)
                        elif field['type'] == 'datetime':
                            entry = DateTimes(date_format, time_format)
                    entry.connect_activate(lambda *a: search())
                    entry.connect_combo(toggle_window_hide)
                else:
                    entry = gtk.Entry()
                    entry.connect('activate', lambda *a: search())
                label.set_mnemonic_widget(entry)
                self.search_table.attach(entry, 1, 2, i, i + 1,
                    yoptions=yoptions)
                self.search_table.fields.append((field['string'], entry))

            scrolled = gtk.ScrolledWindow()
            scrolled.add_with_viewport(self.search_table)
            scrolled.set_shadow_type(gtk.SHADOW_NONE)
            scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            vbox.pack_start(scrolled, expand=True, fill=True)
            find_button = gtk.Button(_('Find'))
            find_button.connect('clicked', lambda *a: search())
            find_button.set_image(common.IconFactory.get_image(
                    'tryton-search', gtk.ICON_SIZE_SMALL_TOOLBAR))
            hbuttonbox = gtk.HButtonBox()
            hbuttonbox.set_spacing(5)
            hbuttonbox.pack_start(find_button)
            hbuttonbox.set_layout(gtk.BUTTONBOX_END)
            vbox.pack_start(hbuttonbox, expand=False, fill=True)
            self.search_window.add(vbox)
            vbox.show_all()

            new_size = list(map(sum, list(zip(self.search_table.size_request(),
                    scrolled.size_request()))))
            self.search_window.set_default_size(*new_size)

        parent = widget.get_toplevel()
        widget_x, widget_y = widget.translate_coordinates(parent, 0, 0)
        widget_allocation = widget.get_allocation()

        # Resize the window to not be out of the parent
        width, height = self.search_window.get_default_size()
        allocation = parent.get_allocation()
        delta_width = allocation.width - (widget_x + width)
        delta_height = allocation.height - (widget_y + widget_allocation.height
            + height)
        if delta_width < 0:
            width += delta_width
        if delta_height < 0:
            height += delta_height
        self.search_window.resize(width, height)

        # Move the window under the button
        if hasattr(widget.window, 'get_root_coords'):
            x, y = widget.window.get_root_coords(
                widget_allocation.x, widget_allocation.y)
        else:
            x, y = widget.window.get_origin()
        self.search_window.move(
            x, y + widget_allocation.height)
        self.search_window.show()
        self.search_window.grab_focus()

        if self.last_search_text.strip() != self.get_text().strip():
            for label, entry in self.search_table.fields:
                if isinstance(entry, gtk.ComboBox):
                    entry.set_active(-1)
                elif isinstance(entry, Dates):
                    entry.set_values(None, None)
                elif isinstance(entry, Selection):
                    entry.treeview.get_selection().unselect_all()
                else:
                    entry.set_text('')
            if self.search_table.fields:
                self.search_table.fields[0][1].grab_focus()
