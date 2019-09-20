# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import gettext

from gi.repository import Gdk, GLib, GObject, Gtk

import tryton.common as common
from tryton.common.domain_parser import quote
from tryton.common.treeviewcontrol import TreeViewControl
from tryton.common.datetime_ import Date, Time, DateTime, add_operators
from tryton.common.number_entry import NumberEntry
from tryton.pyson import PYSONDecoder

_ = gettext.gettext


class Between(Gtk.HBox):
    _changed_signal = None

    def __init__(self, _entry=Gtk.Entry):
        super().__init__()
        self.from_ = _entry()
        self.pack_start(self.from_, expand=True, fill=True, padding=0)
        self.pack_start(
            Gtk.Label(label=_('..')), expand=False, fill=False, padding=0)
        self.to = _entry()
        self.pack_start(self.to, expand=True, fill=True, padding=0)

        if self._changed_signal:
            self.from_.connect_after(
                self._changed_signal, self._from_changed)

    @property
    def _connect_widgets(self):
        return [self.from_, self.to]

    def connect(self, signal, callback):
        for widget in self._connect_widgets:
            try:
                widget.connect(signal, callback)
            except TypeError:
                pass

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

    def _get_value(self, entry):
        raise NotImplementedError

    def set_value(self, from_, to):
        self._set_value(self.from_, from_)
        self._set_value(self.to, to)

    def _set_value(self, entry, value):
        raise NotImplementedError

    def _from_changed(self, widget):
        self._set_value(self.to, self._get_value(self.from_))


class WithOperators:
    def __init__(self, entry):
        self.entry = entry

    def __call__(self):
        return add_operators(self.entry())


class BetweenDates(Between):
    _entry = None

    def __init__(self, format_=None):
        super().__init__(WithOperators(self._entry))
        if format_:
            self.from_.props.format = format_
            self.to.props.format = format_

    def _set_value(self, entry, value):
        entry.props.value = value


class Dates(BetweenDates):
    _entry = Date
    _changed_signal = 'date-changed'

    def _get_value(self, widget):
        value = widget.props.value
        if value:
            return value.strftime(widget.props.format)


class Times(BetweenDates):
    _entry = Time
    _changed_signal = 'time-changed'

    @property
    def _connect_widgets(self):
        return [self.from_.get_child(), self.to.get_child()]

    def _get_value(self, widget):
        value = widget.props.value
        if value:
            return datetime.time.strftime(value, widget.props.format)


class DateTimes(BetweenDates):
    _entry = DateTime
    _changed_signal = 'datetime-changed'

    def __init__(self, date_format, time_format):
        super().__init__()
        self.from_.props.date_format = date_format
        self.to.props.date_format = date_format
        self.from_.props.time_format = time_format
        self.to.props.time_format = time_format

    @property
    def _connect_widgets(self):
        return self.from_.get_children() + self.to.get_children()

    def _get_value(self, widget):
        value = widget.props.value
        if value:
            return value.strftime(
                widget.props.date_format + ' ' + widget.props.time_format)


class Numbers(Between):
    _changed_signal = 'changed'

    def __init__(self):
        super().__init__(NumberEntry)

    def _get_value(self, widget):
        return widget.get_text()

    def _set_value(self, entry, value):
        entry.set_text(value or '')


class Selection(Gtk.ScrolledWindow):

    def __init__(self, selections):
        super(Selection, self).__init__()
        self.treeview = TreeViewControl()
        model = Gtk.ListStore(GObject.TYPE_STRING)
        for selection in selections:
            model.append((selection,))
        self.treeview.set_model(model)

        column = Gtk.TreeViewColumn()
        cell = Gtk.CellRendererText()
        column.pack_start(cell, expand=True)
        column.add_attribute(cell, 'text', 0)
        self.treeview.append_column(column)
        self.treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.treeview.set_headers_visible(False)
        self.add(self.treeview)
        self.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
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
        self.viewport = Gtk.Viewport()
        self.viewport.set_shadow_type(Gtk.ShadowType.NONE)
        self.vbox = Gtk.VBox(spacing=3)
        self.alternate_viewport = Gtk.Viewport()
        self.alternate_viewport.set_shadow_type(Gtk.ShadowType.NONE)
        self.alternate_view = False
        self.search_popover = None
        self.search_grid = None
        self.last_search_text = ''
        self.tab_domain = tab_domain or []
        self.tab_counter = []

        tooltips = common.Tooltips()

        self.filter_vbox = Gtk.VBox(spacing=0)
        self.filter_vbox.set_border_width(0)
        hbox = Gtk.HBox(homogeneous=False, spacing=0)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text(_('Search'))
        self.search_entry.set_alignment(0.0)
        self.search_entry.set_icon_from_pixbuf(
            Gtk.EntryIconPosition.PRIMARY,
            common.IconFactory.get_pixbuf('tryton-filter', Gtk.IconSize.MENU))
        self.search_entry.set_icon_tooltip_text(
            Gtk.EntryIconPosition.PRIMARY, _('Open filters'))
        self.completion = Gtk.EntryCompletion()
        self.completion.set_model(Gtk.ListStore(str))
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

        hbox.pack_start(self.search_entry, expand=True, fill=True, padding=0)

        def popup(widget):
            menu = widget._menu
            for child in menu.get_children():
                menu.remove(child)
            if not widget.props.active:
                menu.popdown()
                return

            def menu_position(menu, data=None):
                widget_allocation = widget.get_allocation()
                x, y = widget.get_window().get_root_coords(
                    widget_allocation.x, widget_allocation.y)
                return (x, y + widget_allocation.height, False)

            for id_, name, domain in self.bookmarks():
                menuitem = Gtk.MenuItem(label=name)
                menuitem.connect('activate', self.bookmark_activate, domain)
                menu.add(menuitem)

            menu.show_all()
            if hasattr(menu, 'popup_at_widget'):
                menu.popup_at_widget(
                    widget, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST,
                    Gtk.get_current_event())
            else:
                menu.popup(None, None, menu_position, 0, 0)

        def deactivate(menuitem, togglebutton):
            togglebutton.props.active = False

        but_bookmark = Gtk.ToggleButton()
        self.but_bookmark = but_bookmark
        tooltips.set_tip(but_bookmark, _('Show bookmarks of filters'))
        but_bookmark.add(common.IconFactory.get_image(
                'tryton-bookmarks', Gtk.IconSize.SMALL_TOOLBAR))
        but_bookmark.set_relief(Gtk.ReliefStyle.NONE)
        menu = Gtk.Menu()
        menu.set_property('reserve-toggle-size', False)
        menu.connect('deactivate', deactivate, but_bookmark)
        but_bookmark._menu = menu
        but_bookmark.connect('toggled', popup)
        hbox.pack_start(but_bookmark, expand=False, fill=False, padding=0)

        but_active = Gtk.ToggleButton()
        self.but_active = but_active
        self._set_active_tooltip()
        but_active.add(common.IconFactory.get_image(
                'tryton-archive', Gtk.IconSize.SMALL_TOOLBAR))
        but_active.set_relief(Gtk.ReliefStyle.NONE)
        but_active.connect('toggled', self.search_active)
        hbox.pack_start(but_active, expand=False, fill=False, padding=0)

        but_prev = Gtk.Button()
        self.but_prev = but_prev
        tooltips.set_tip(but_prev, _('Previous'))
        but_prev.connect('clicked', self.search_prev)
        but_prev.add(common.IconFactory.get_image(
                'tryton-back', Gtk.IconSize.SMALL_TOOLBAR))
        but_prev.set_relief(Gtk.ReliefStyle.NONE)
        hbox.pack_start(but_prev, expand=False, fill=False, padding=0)

        but_next = Gtk.Button()
        self.but_next = but_next
        tooltips.set_tip(but_next, _('Next'))
        but_next.connect('clicked', self.search_next)
        but_next.add(common.IconFactory.get_image(
                'tryton-forward', Gtk.IconSize.SMALL_TOOLBAR))
        but_next.set_relief(Gtk.ReliefStyle.NONE)
        hbox.pack_start(but_next, expand=False, fill=False, padding=0)

        hbox.show_all()
        self.filter_vbox.pack_start(hbox, expand=False, fill=False, padding=0)

        hseparator = Gtk.HSeparator()
        hseparator.show()
        self.filter_vbox.pack_start(
            hseparator, expand=False, fill=False, padding=0)

        if self.tab_domain:
            self.notebook = Gtk.Notebook()
            try:
                self.notebook.props.homogeneous = True
            except AttributeError:
                # No more supported by GTK+3
                pass
            self.notebook.set_scrollable(True)
            for name, domain, count in self.tab_domain:
                hbox = Gtk.HBox(spacing=3)
                label = Gtk.Label(label='_' + name)
                label.set_use_underline(True)
                hbox.pack_start(label, expand=True, fill=True, padding=0)
                counter = Gtk.Label()
                hbox.pack_start(counter, expand=False, fill=True, padding=0)
                hbox.show_all()
                self.notebook.append_page(Gtk.VBox(), hbox)
                self.tab_counter.append(counter)
            self.filter_vbox.pack_start(
                self.notebook, expand=True, fill=True, padding=0)
            self.notebook.show_all()
            # Set the current page before connecting to switch-page to not
            # trigger the search a second times.
            self.notebook.set_current_page(0)
            self.notebook.get_nth_page(0).pack_end(
                self.viewport, expand=True, fill=True, padding=0)
            self.notebook.connect('switch-page', self.switch_page)
            self.notebook.connect_after('switch-page', self.switch_page_after)
            filter_expand = True
        else:
            self.notebook = None
            self.vbox.pack_end(
                self.viewport, expand=True, fill=True, padding=0)
            filter_expand = False

        self.vbox.pack_start(
            self.filter_vbox, expand=filter_expand, fill=True, padding=0)

        self.but_next.set_sensitive(False)
        self.but_prev.set_sensitive(False)

        tooltips.enable()

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
                    ).pack_end(
                        self.viewport, expand=True, fill=True, padding=0)

    def hide_filter(self):
        if self.filter_vbox:
            self.filter_vbox.hide()
        if self.notebook:
            self.notebook.set_show_tabs(False)
            if self.viewport not in self.vbox.get_children():
                self.notebook.get_nth_page(self.notebook.get_current_page()
                    ).remove(self.viewport)
                self.vbox.pack_end(
                    self.viewport, expand=True, fill=True, padding=0)

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
            self.search_entry.set_icon_activatable(
                Gtk.EntryIconPosition.SECONDARY, bool(current_text))
            self.search_entry.set_icon_sensitive(
                Gtk.EntryIconPosition.SECONDARY, bool(current_text))
            for id_, name, domain in self.bookmarks():
                text = self.screen.domain_parser.string(domain)
                domain = self.screen.domain_parser.parse(text)
                if (text == current_text
                        or domain == current_domain):
                    self.search_entry.set_icon_from_pixbuf(
                        Gtk.EntryIconPosition.SECONDARY,
                        common.IconFactory.get_pixbuf(
                            'tryton-bookmark', Gtk.IconSize.MENU))
                    self.search_entry.set_icon_tooltip_text(
                        Gtk.EntryIconPosition.SECONDARY,
                        _('Remove this bookmark'))
                    return id_
        self.search_entry.set_icon_from_pixbuf(
            Gtk.EntryIconPosition.SECONDARY,
            common.IconFactory.get_pixbuf(
                'tryton-bookmark-border', Gtk.IconSize.MENU))
        if current_text:
            self.search_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _('Bookmark this filter'))
        elif self.search_entry.get_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY):
            self.search_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, None)

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
        new_page.pack_end(self.viewport, expand=True, fill=True, padding=0)

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
        GLib.idle_add(callback)

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
        GLib.idle_add(keypress)

    def icon_press(self, widget, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.PRIMARY:
            self.search_box(widget)
        elif icon_pos == Gtk.EntryIconPosition.SECONDARY:
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

        def search():
            self.search_popover.popdown()
            text = ''
            for label, entry in self.search_grid.fields:
                if isinstance(entry, Gtk.ComboBoxText):
                    value = quote(entry.get_active_text()) or None
                elif isinstance(entry, (Between, Selection)):
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

        if not self.search_popover:
            self.search_popover = Gtk.Popover()
            self.search_popover.set_relative_to(widget)

            vbox = Gtk.VBox()
            fields = [f for f in self.screen.domain_parser.fields.values()
                if f.get('searchable', True) and '.' not in f['name']]
            self.search_grid = Gtk.Grid(column_spacing=3, row_spacing=3)

            # Fill table with fields
            self.search_grid.fields = []
            for i, field in enumerate(fields):
                label = Gtk.Label(
                    label=field['string'],
                    halign=Gtk.Align.START, valign=Gtk.Align.START)
                self.search_grid.attach(label, 0, i, 1, 1)
                if field['type'] == 'boolean':
                    entry = Gtk.ComboBoxText()
                    entry.append_text('')
                    selections = (_('True'), _('False'))
                    for selection in selections:
                        entry.append_text(selection)
                elif field['type'] in ['selection', 'multiselection']:
                    selections = tuple(x[1] for x in field['selection'])
                    entry = Selection(selections)
                    entry.set_vexpand(True)
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
                    entry.connect('activate', lambda *a: search())
                elif field['type'] in ['integer', 'float', 'numeric']:
                    entry = Numbers()
                    entry.connect('activate', lambda *a: search())
                else:
                    entry = Gtk.Entry()
                    entry.connect('activate', lambda *a: search())
                label.set_mnemonic_widget(entry)
                self.search_grid.attach(entry, 1, i, 1, 1)
                self.search_grid.fields.append((field['string'], entry))

            scrolled = Gtk.ScrolledWindow()
            scrolled.add(self.search_grid)
            scrolled.set_shadow_type(Gtk.ShadowType.NONE)
            scrolled.set_policy(
                Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            vbox.pack_start(scrolled, expand=True, fill=True, padding=0)
            find_button = Gtk.Button(label=_('Find'))
            find_button.connect('clicked', lambda *a: search())
            find_button.set_image(common.IconFactory.get_image(
                    'tryton-search', Gtk.IconSize.SMALL_TOOLBAR))
            find_button.set_can_default(True)
            self.search_popover.set_default_widget(find_button)
            hbuttonbox = Gtk.HButtonBox()
            hbuttonbox.pack_start(
                find_button, expand=False, fill=False, padding=0)
            hbuttonbox.set_layout(Gtk.ButtonBoxStyle.END)
            vbox.pack_start(hbuttonbox, expand=False, fill=True, padding=0)
            self.search_popover.add(vbox)
            vbox.show_all()
            scrolled.set_size_request(
                -1, min(self.search_grid.get_preferred_height()[1], 400))

        self.search_popover.set_pointing_to(
            widget.get_icon_area(Gtk.EntryIconPosition.PRIMARY))
        self.search_popover.popup()
        if self.search_grid.fields:
            self.search_grid.fields[0][1].grab_focus()

        if self.last_search_text.strip() != self.get_text().strip():
            for label, entry in self.search_grid.fields:
                if isinstance(entry, Gtk.ComboBoxText):
                    entry.set_active(-1)
                elif isinstance(entry, Between):
                    entry.set_value(None, None)
                elif isinstance(entry, Selection):
                    entry.treeview.get_selection().unselect_all()
                else:
                    entry.set_text('')
