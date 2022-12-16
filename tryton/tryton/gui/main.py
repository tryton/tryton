# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gettext
import json
import logging
import os
import sys
import threading
import traceback
import webbrowser
from urllib.parse import urlparse, parse_qsl, unquote

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

import tryton.common as common
import tryton.plugins
import tryton.rpc as rpc
import tryton.translate as translate
from tryton.action import Action
from tryton.common import RPCExecute, RPCException, RPCContextReload
from tryton.common.cellrendererclickablepixbuf import \
        CellRendererClickablePixbuf
from tryton.config import CONFIG, TRYTON_ICON, get_config_dir
from tryton.exceptions import TrytonError, TrytonServerUnavailable
from tryton.gui.window import Window
from tryton.jsonrpc import object_hook
from tryton.pyson import PYSONDecoder

_ = gettext.gettext
logger = logging.getLogger(__name__)
_PRIORITIES = [getattr(Gio.NotificationPriority, p)
    for p in ('LOW', 'NORMAL', 'HIGH', 'URGENT')]


class Main(Gtk.Application):
    window = None
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def do_startup(self):
        Gtk.Application.do_startup(self)

        action = Gio.SimpleAction.new('preferences', None)
        action.connect('activate', lambda *a: self.preferences())
        self.add_action(action)
        self.set_accels_for_action('app.preferences', ['<Primary>comma'])

        action = Gio.SimpleAction.new('menu-search', None)
        action.connect(
            'activate', lambda *a: self.global_search_entry.grab_focus())
        self.add_action(action)
        self.set_accels_for_action('app.menu-search', ['<Primary>k'])

        action = Gio.SimpleAction.new('menu-toggle', None)
        action.connect('activate', lambda *a: self.menu_toggle())
        self.add_action(action)
        self.set_accels_for_action('app.menu-toggle', ['<Primary>m'])

        toolbar_variant = GLib.Variant.new_string(
            CONFIG['client.toolbar'] or 'both')
        action = Gio.SimpleAction.new_stateful(
            'toolbar', toolbar_variant.get_type(), toolbar_variant)
        action.connect('change-state', self.on_change_toolbar)
        self.add_action(action)

        def on_change_action_boolean(action, value, key):
            action.set_state(value)
            CONFIG[key] = value.get_boolean()
            if key == 'client.check_version' and CONFIG[key]:
                common.check_version(self.info)

        for name, key in [
                ('mode-pda', 'client.modepda'),
                ('save-tree-width', 'client.save_tree_width'),
                ('save-tree-state', 'client.save_tree_state'),
                ('spell-checking', 'client.spellcheck'),
                ('check-version', 'client.check_version'),
                ]:
            variant = GLib.Variant.new_boolean(CONFIG[key])
            action = Gio.SimpleAction.new_stateful(name, None, variant)
            action.connect('change-state', on_change_action_boolean, key)
            self.add_action(action)

        action = Gio.SimpleAction.new('tab-previous', None)
        action.connect('activate', lambda *a: self.win_prev())
        self.add_action(action)
        self.set_accels_for_action('app.tab-previous', ['<Primary><Shift>Tab'])

        action = Gio.SimpleAction.new('tab-next', None)
        action.connect('activate', lambda *a: self.win_next())
        self.add_action(action)
        self.set_accels_for_action('app.tab-next', ['<Primary>Tab'])

        action = Gio.SimpleAction.new('search-limit', None)
        action.connect('activate', lambda *a: self.edit_limit())
        self.add_action(action)

        action = Gio.SimpleAction.new('email', None)
        action.connect('activate', lambda *a: self.edit_email())
        self.add_action(action)

        self._shortcuts = None
        action = Gio.SimpleAction.new('shortcuts', None)
        action.connect('activate', lambda *a: self.shortcuts())
        self.add_action(action)
        self.set_accels_for_action('app.shortcuts', ['<Primary>F1'])

        action = Gio.SimpleAction.new('about', None)
        action.connect('activate', lambda *a: self.about())
        self.add_action(action)

        action = Gio.SimpleAction.new('quit', None)
        action.connect('activate', self.on_quit)
        self.add_action(action)
        self.set_accels_for_action('app.quit', ['<Primary>q'])

    def do_activate(self):
        if self.window:
            self.window.present()
            return

        self.window = Gtk.ApplicationWindow(application=self, title="Tryton")
        self.window.set_default_size(960, 720)
        self.window.maximize()
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_resizable(True)
        self.window.set_icon(TRYTON_ICON)
        self.window.connect("destroy", self.on_quit)
        self.window.connect("delete_event", self.on_quit)

        self.header = Gtk.HeaderBar.new()
        self.header.set_show_close_button(True)
        self.window.set_titlebar(self.header)
        self.set_title()

        menu = Gio.Menu.new()
        menu.append(_("Preferences..."), 'app.preferences')

        section = Gio.Menu.new()
        toolbar = Gio.Menu.new()
        section.append_submenu(_("Toolbar"), toolbar)
        toolbar.append(_("Default"), 'app.toolbar::default')
        toolbar.append(_("Text and Icons"), 'app.toolbar::both')
        toolbar.append(_("Text"), 'app.toolbar::text')
        toolbar.append(_("Icons"), 'app.toolbar::icons')

        form = Gio.Menu.new()
        section.append_submenu(_("Form"), form)
        form.append(_("Save Column Width"), 'app.save-tree-width')
        form.append(_("Save Tree State"), 'app.save-tree-state')
        form.append(_("Spell Checking"), 'app.spell-checking')

        section.append(_("PDA Mode"), 'app.mode-pda')
        section.append(_("Search Limit..."), 'app.search-limit')
        section.append(_("Email..."), 'app.email')
        section.append(_("Check Version"), 'app.check-version')

        menu.append_section(_("Options"), section)

        section = Gio.Menu.new()
        section.append(_("Keyboard Shortcuts..."), 'app.shortcuts')
        section.append(_("About..."), 'app.about')
        menu.append_section(_("Help"), section)

        primary_menu = Gtk.MenuButton.new()
        primary_menu.set_menu_model(menu)
        self.header.pack_end(primary_menu)

        menu = Gtk.Button.new()
        menu.set_relief(Gtk.ReliefStyle.NONE)
        menu.set_image(
            common.IconFactory.get_image('tryton-menu', Gtk.IconSize.BUTTON))
        menu.connect('clicked', self.menu_toggle)
        self.header.pack_start(menu)

        favorite = Gtk.MenuButton.new()
        favorite.set_relief(Gtk.ReliefStyle.NONE)
        favorite.set_image(common.IconFactory.get_image(
                'tryton-bookmarks', Gtk.IconSize.BUTTON))
        self.menu_favorite = Gtk.Menu.new()
        favorite.set_popup(self.menu_favorite)
        favorite.connect('clicked', self.favorite_set)
        self.header.pack_start(favorite)

        self.set_global_search()
        self.header.pack_start(self.global_search_entry)

        self.accel_group = Gtk.AccelGroup()
        self.window.add_accel_group(self.accel_group)

        Gtk.AccelMap.add_entry(
            '<tryton>/Form/New', Gdk.KEY_N, Gdk.ModifierType.CONTROL_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Save', Gdk.KEY_S, Gdk.ModifierType.CONTROL_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Duplicate', Gdk.KEY_D,
            Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Delete', Gdk.KEY_D, Gdk.ModifierType.CONTROL_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Next', Gdk.KEY_Page_Down, 0)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Previous', Gdk.KEY_Page_Up, 0)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Switch View', Gdk.KEY_L,
            Gdk.ModifierType.CONTROL_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Close', Gdk.KEY_W, Gdk.ModifierType.CONTROL_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Reload', Gdk.KEY_R, Gdk.ModifierType.CONTROL_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Attachments', Gdk.KEY_T,
            Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Notes', Gdk.KEY_O,
            Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Relate', Gdk.KEY_R,
            Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Actions', Gdk.KEY_E, Gdk.ModifierType.CONTROL_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Report', Gdk.KEY_P, Gdk.ModifierType.CONTROL_MASK)
        Gtk.AccelMap.add_entry(
            '<tryton>/Form/Search', Gdk.KEY_F, Gdk.ModifierType.CONTROL_MASK)

        Gtk.AccelMap.load(os.path.join(get_config_dir(), 'accel.map'))

        self.tooltips = common.Tooltips()

        self.vbox = Gtk.VBox()
        self.window.add(self.vbox)

        self.buttons = {}

        self.info = Gtk.VBox()
        self.vbox.pack_start(self.info, expand=False, fill=True, padding=0)
        if CONFIG['client.check_version']:
            common.check_version(self.info)
            GLib.timeout_add_seconds(
                int(CONFIG['download.frequency']), common.check_version,
                self.info)

        self.pane = Gtk.HPaned()
        self.vbox.pack_start(self.pane, expand=True, fill=True, padding=0)
        self.pane.set_position(int(CONFIG['menu.pane']))

        self.menu_screen = None
        self.menu = Gtk.VBox()
        self.menu.set_vexpand(True)
        self.pane.add1(self.menu)

        self.notebook = Gtk.Notebook()
        self.notebook.popup_enable()
        self.notebook.set_scrollable(True)
        self.notebook.connect_after('switch-page', self._sig_page_changt)
        self.pane.add2(self.notebook)

        self.window.show_all()

        self.pages = []
        self.previous_pages = {}
        self.current_page = 0
        self.last_page = 0
        self.dialogs = []

        # Register plugins
        tryton.plugins.register()

        self.set_title()  # Adds username/profile while password is asked
        try:
            common.Login()
        except Exception as exception:
            if (not isinstance(exception, TrytonError)
                    or exception.faultCode != 'QueryCanceled'):
                common.error(exception, traceback.format_exc())
            return self.quit()
        self.get_preferences()

    def do_command_line(self, cmd):
        self.do_activate()
        arguments = cmd.get_arguments()
        if len(arguments) > 1:
            url = arguments[1]
            self.open_url(url)
        return True

    def do_shutdown(self):
        Gtk.Application.do_shutdown(self)
        common.Logout()
        CONFIG.save()
        Gtk.AccelMap.save(os.path.join(get_config_dir(), 'accel.map'))

    def on_quit(self, *args):
        try:
            if not self.close_pages():
                return True
        except TrytonServerUnavailable:
            pass
        rpc.logout()
        self.quit()

    def set_global_search(self):
        self.global_search_entry = Gtk.Entry.new()
        self.global_search_entry.set_width_chars(20)
        global_search_completion = Gtk.EntryCompletion()
        global_search_completion.set_match_func(lambda *a: True)
        global_search_completion.set_model(
            Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, int, str))
        pixbuf_cell = Gtk.CellRendererPixbuf()
        global_search_completion.pack_start(pixbuf_cell, expand=True)
        global_search_completion.add_attribute(pixbuf_cell, 'pixbuf', 0)
        text_cell = Gtk.CellRendererText()
        global_search_completion.pack_start(text_cell, expand=True)
        global_search_completion.add_attribute(text_cell, "markup", 1)
        global_search_completion.props.popup_set_width = True
        self.global_search_entry.set_completion(global_search_completion)

        def match_selected(completion, model, iter_):
            model, record_id, model_name = model.get(iter_, 2, 3, 4)
            if model == self.menu_screen.model_name:
                # ids is not defined to prevent to add suffix
                Action.exec_keyword('tree_open', {
                        'model': model,
                        'id': record_id,
                        })
            else:
                Window.create(model,
                    res_id=record_id,
                    mode=['form', 'tree'],
                    name=model_name)
            self.global_search_entry.set_text('')
            return True

        global_search_completion.connect('match-selected', match_selected)

        def update(widget, search_text, callback=None):
            def end():
                if callback:
                    callback()
                return False
            if search_text != widget.get_text():
                return end()
            gmodel = global_search_completion.get_model()
            if not search_text or not gmodel:
                gmodel.clear()
                gmodel.search_text = search_text
                return end()
            if getattr(gmodel, 'search_text', None) == search_text:
                return end()

            def set_result(result):
                try:
                    result = result()
                except RPCException:
                    result = []
                if search_text != widget.get_text():
                    if callback:
                        callback()
                    return False
                gmodel.clear()
                for r in result:
                    _, model, model_name, record_id, record_name, icon = r
                    if icon:
                        text = common.to_xml(record_name)
                        pixbuf = common.IconFactory.get_pixbuf(
                            icon, Gtk.IconSize.BUTTON)
                    else:
                        text = '<b>%s:</b>\n %s' % (
                            common.to_xml(model_name),
                            common.to_xml(record_name))
                        pixbuf = None
                    gmodel.append([pixbuf, text, model, record_id, model_name])
                gmodel.search_text = search_text
                # Force display of popup
                widget.emit('changed')
                end()

            RPCExecute('model', 'ir.model', 'global_search', search_text,
                CONFIG['client.limit'], self.menu_screen.model_name,
                context=self.menu_screen.context, callback=set_result)
            return False

        def changed(widget):
            search_text = widget.get_text()
            GLib.timeout_add(300, update, widget, search_text)

        def activate(widget):
            def message():
                gmodel = global_search_completion.get_model()
                if not len(gmodel):
                    common.message(_('No result found.'))
                else:
                    widget.emit('changed')
            search_text = widget.get_text()
            update(widget, search_text, message)

        self.global_search_entry.connect('changed', changed)
        self.global_search_entry.connect('activate', activate)

    def set_title(self, value=''):
        if CONFIG['login.profile']:
            login_info = CONFIG['login.profile']
        else:
            login_info = '%s@%s/%s' % (
                CONFIG['login.login'],
                CONFIG['login.host'],
                CONFIG['login.db'])
        titles = []
        if value:
            titles.append(value)
        titles.append(CONFIG['client.title'])
        self.header.set_title(' - '.join(titles))
        self.header.set_subtitle(login_info)
        try:
            style_context = self.header.get_style_context()
        except AttributeError:
            pass
        else:
            for name in style_context.list_classes():
                if name.startswith('profile-'):
                    style_context.remove_class(name)
            if CONFIG['login.profile']:
                style_context.add_class(
                    'profile-%s' % CONFIG['login.profile'])

    def favorite_set(self, *args):
        if self.menu_favorite.get_children():
            return True

        def _action_favorite(widget, id_):
            event = Gtk.get_current_event()
            allow_similar = (event.state & Gdk.ModifierType.MOD1_MASK
                or event.state & Gdk.ModifierType.SHIFT_MASK)
            with Window(allow_similar=allow_similar):
                # ids is not defined to prevent to add suffix
                Action.exec_keyword('tree_open', {
                        'model': self.menu_screen.model_name,
                        'id': id_,
                        })

        def _manage_favorites(widget):
            Window.create(self.menu_screen.model_name + '.favorite',
                mode=['tree', 'form'],
                name=_("Favorites"))
        try:
            favorites = RPCExecute('model',
                self.menu_screen.model_name + '.favorite', 'get',
                process_exception=False)
        except Exception:
            return False
        for id_, name, icon in favorites:
            menuitem = Gtk.MenuItem(label=name)
            menuitem.connect('activate', _action_favorite, id_)
            self.menu_favorite.add(menuitem)
        self.menu_favorite.add(Gtk.SeparatorMenuItem())
        manage_favorites = Gtk.MenuItem(label=_("Manage..."),
            use_underline=True)
        manage_favorites.connect('activate', _manage_favorites)
        self.menu_favorite.add(manage_favorites)
        self.menu_favorite.show_all()
        return True

    def favorite_unset(self):
        for child in self.menu_favorite.get_children():
            self.menu_favorite.remove(child)

    def on_change_toolbar(self, action, value):
        action.set_state(value)
        option = value.get_string()
        CONFIG['client.toolbar'] = option
        if option == 'default':
            barstyle = False
        elif option == 'both':
            barstyle = Gtk.ToolbarStyle.BOTH
        elif option == 'text':
            barstyle = Gtk.ToolbarStyle.TEXT
        elif option == 'icons':
            barstyle = Gtk.ToolbarStyle.ICONS
        for page_idx in range(self.notebook.get_n_pages()):
            page = self.get_page(page_idx)
            page.toolbar.set_style(barstyle)

    def edit_limit(self):
        from tryton.gui.window.limit import Limit
        Limit().run()

    def edit_email(self):
        from tryton.gui.window.email_ import Email
        Email().run()

    def win_next(self):
        page = self.notebook.get_current_page()
        if page == len(self.pages) - 1:
            page = -1
        self.notebook.set_current_page(page + 1)

    def win_prev(self):
        page = self.notebook.get_current_page()
        self.notebook.set_current_page(page - 1)

    def get_preferences(self):
        RPCContextReload()
        try:
            prefs = RPCExecute('model', 'res.user', 'get_preferences', False)
        except RPCException:
            prefs = {}

        threads = []
        for target in (
                common.IconFactory.load_icons,
                common.MODELACCESS.load_models,
                common.MODELHISTORY.load_history,
                common.VIEW_SEARCH.load_searches,
                ):
            t = threading.Thread(target=target)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        if prefs and 'language_direction' in prefs:
            translate.set_language_direction(prefs['language_direction'])
            CONFIG['client.language_direction'] = \
                prefs['language_direction']
        self.sig_win_menu(prefs=prefs)
        for action_id in prefs.get('actions', []):
            Action.execute(action_id, {})
        self.set_title(prefs.get('status_bar', ''))
        if prefs and 'language' in prefs:
            translate.setlang(prefs['language'], prefs.get('locale'))
            if CONFIG['client.lang'] != prefs['language']:
                self.favorite_unset()
            CONFIG['client.lang'] = prefs['language']
        # Set placeholder after language is set to get correct translation
        self.global_search_entry.set_placeholder_text(_("Action"))
        CONFIG.save()

    def preferences(self):
        from tryton.gui.window.preference import Preference
        if not self.close_pages():
            return False
        Preference(rpc._USER, self.get_preferences)

    def sig_win_close(self, widget=None):
        self._sig_remove_book(widget,
            self.notebook.get_nth_page(self.notebook.get_current_page()))

    def close_pages(self):
        if self.notebook.get_n_pages():
            if not common.sur(
                    _('The following action requires to close all tabs.\n'
                    'Do you want to continue?')):
                return False
        res = True
        while res:
            wid = self.get_page()
            if wid:
                if not wid.sig_close():
                    return False
                res = self._win_del()
            else:
                res = False
        if self.menu_screen:
            self.menu_screen.save_tree_state()
        if self.menu.get_visible():
            CONFIG['menu.pane'] = self.pane.get_position()
        return True

    def about(self):
        from tryton.gui.window.about import About
        About()

    def shortcuts(self):
        if self._shortcuts:
            self._shortcuts.destroy()
        self._shortcuts = window = Gtk.ShortcutsWindow()
        window.set_transient_for(common.get_toplevel_window())
        window.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        window.set_destroy_with_parent(True)
        self.add_window(window)

        section = Gtk.ShortcutsSection()
        section.props.section_name = 'app'
        section.props.title = _("Application Shortcuts")
        section.props.visible = True

        group = Gtk.ShortcutsGroup()
        group.props.title = _("Global")
        section.add(group)

        for action, title in [
                ('app.preferences', _("Preferences")),
                ('app.menu-search', _("Search menu")),
                ('app.menu-toggle', _("Toggle menu")),
                ('app.tab-previous', _("Previous tab"), ),
                ('app.tab-next', _("Next tab")),
                ('app.shortcuts', _("Shortcuts")),
                ('app.quit', _("Quit")),
                ]:
            shortcut = Gtk.ShortcutsShortcut()
            shortcut.props.title = title
            accels = self.get_accels_for_action(action)
            if accels:
                shortcut.props.accelerator = ' '.join(accels)
                group.add(shortcut)

        window.add(section)

        for name, title, groups in [
                ('entry', _("Edition Shortcuts"), [
                        (_("Text Entries"), [
                                ('<Primary>x', _("Cut selected text")),
                                ('<Primary>c', _("Copy selected text")),
                                ('<Primary>v', _("Paste copied text")),
                                ('Tab', _("Next entry")),
                                ('<Shift>Tab', _("Previous entry")),
                                ]),
                        (_("Relation Entries"), [
                                ('F3', _("Create new relation")),
                                ('F2', _("Open/Search relation")),
                                ]),
                        (_("List Entries"), [
                                ('F4', _("Switch view")),
                                ('F3', _("Create/Select new line")),
                                ('F2', _("Open relation")),
                                ('Delete',
                                    _("Mark line for deletion/removal")),
                                ('<Ctrl>Delete', _("Mark line for removal")),
                                ('Insert', _("Unmark line for deletion")),
                                ]),
                        ]),
                ('tree', _("List/Tree Shortcuts"), [
                        (_("Move Cursor"), [
                                ('Right', _("Move right")),
                                ('Left', _("Move left")),
                                ('Up', _("Move up")),
                                ('Down', _("Move down")),
                                ('Page_Up', _("Move up of one page")),
                                ('Page_Down', _("Move down of one page")),
                                ('Home', _("Move to top")),
                                ('End', _("Move to bottom")),
                                ('BackSpace', _("Move to parent")),
                                ]),
                        (_("Selection"), [
                                ('<Ctrl>a <Ctrl>slash', _("Select all")),
                                ('<Shift><Ctrl>a <Shift><Ctrl>slash',
                                    _("Unselect all")),
                                ('BackSpace', _("Select parent")),
                                ('space', _("Select/Activate current row")),
                                ('<Shift>space Return',
                                    _("Select/Activate current row")),
                                ('<Ctrl>space', _("Toggle selection")),
                                ]),
                        (_("Expand/Collapse"), [
                                ('plus', _("Expand row")),
                                ('minus', _("Collapse row")),
                                ('space', _("Toggle row")),
                                ('<Shift>Left', _("Collapse all rows")),
                                ('<Shift>Right', _("Expand all rows")),
                                ]),
                        ]),
                ]:
            section = Gtk.ShortcutsSection()
            section.props.section_name = name
            section.props.title = title
            section.props.visible = True

            for title, shortcuts in groups:
                group = Gtk.ShortcutsGroup()
                group.props.title = title
                section.add(group)

                for accelerator, title in shortcuts:
                    shortcut = Gtk.ShortcutsShortcut()
                    shortcut.props.title = title
                    shortcut.props.accelerator = accelerator
                    group.add(shortcut)

            window.add(section)

        window.show_all()

    def menu_toggle(self, *args):
        if self.menu.get_visible():
            CONFIG['menu.pane'] = self.pane.get_position()
            self.pane.set_position(0)
            self.notebook.grab_focus()
            self.menu.set_visible(False)
        else:
            self.pane.set_position(int(CONFIG['menu.pane']))
            self.menu.set_visible(True)
            if self.menu_screen:
                self.menu_screen.set_cursor()

    def menu_row_activate(self):
        screen = self.menu_screen
        record_id = (screen.current_record.id
            if screen.current_record else None)
        # ids is not defined to prevent to add suffix
        return Action.exec_keyword('tree_open', {
                'model': screen.model_name,
                'id': record_id,
                }, warning=False)

    def sig_win_menu(self, prefs=None):
        from tryton.gui.window.view_form.screen import Screen

        if not prefs:
            try:
                prefs = RPCExecute('model', 'res.user', 'get_preferences',
                    False)
            except RPCException:
                return False

        if self.menu_screen:
            self.menu_screen.save_tree_state()
        for child in self.menu.get_children():
            self.menu.remove(child)

        action = PYSONDecoder().decode(prefs['pyson_menu'])
        view_ids = []
        if action.get('views', []):
            view_ids = [x[0] for x in action['views']]
        elif action.get('view_id', False):
            view_ids = [action['view_id'][0]]
        ctx = rpc.CONTEXT.copy()
        decoder = PYSONDecoder(ctx)
        action_ctx = decoder.decode(action.get('pyson_context') or '{}')
        domain = decoder.decode(action['pyson_domain'])
        screen = Screen(action['res_model'], mode=['tree'], view_ids=view_ids,
            domain=domain, context=action_ctx, readonly=True, limit=None,
            row_activate=self.menu_row_activate)
        # Use alternate view to not show search box
        screen.screen_container.alternate_view = True
        screen.switch_view(view_type=screen.current_view.view_type)

        self.menu.pack_start(
            screen.screen_container.alternate_viewport,
            expand=True, fill=True, padding=0)
        treeview = screen.current_view.treeview
        treeview.set_headers_visible(False)

        # Favorite column
        column = Gtk.TreeViewColumn()
        column.name = None
        column._type = None
        favorite_renderer = CellRendererClickablePixbuf()
        column.pack_start(favorite_renderer, expand=False)

        def favorite_setter(column, cell, store, iter_, user_data=None):
            menu = store.get_value(iter_, 0)
            favorite = menu.value.get('favorite')
            if favorite:
                icon = 'tryton-star'
            elif favorite is False:
                icon = 'tryton-star-border'
            else:
                icon = None
            if icon:
                pixbuf = common.IconFactory.get_pixbuf(
                    icon, Gtk.IconSize.MENU)
            else:
                pixbuf = None
            cell.set_property('pixbuf', pixbuf)
        column.set_cell_data_func(favorite_renderer, favorite_setter)

        def toggle_favorite(renderer, path, treeview):
            if treeview.props.window:
                self.toggle_favorite(renderer, path, treeview)
        favorite_renderer.connect('clicked',
            lambda *a: GLib.idle_add(toggle_favorite, *a), treeview)
        # Unset fixed height mode to add column
        treeview.set_fixed_height_mode(False)
        treeview.set_property(
            'enable-grid-lines', Gtk.TreeViewGridLines.NONE)
        treeview.append_column(column)

        screen.search_filter()
        screen.display(set_cursor=True)
        self.menu_screen = screen

    def toggle_favorite(self, renderer, path, treeview):
        store = treeview.get_model()
        iter_ = store.get_iter(path)
        menu = store.get_value(iter_, 0)
        favorite = menu.value.get('favorite')
        if favorite:
            value = False
            method = 'unset'
        elif favorite is False:
            value = True
            method = 'set'
        else:
            return
        try:
            RPCExecute('model', self.menu_screen.model_name + '.favorite',
                method, menu.id)
        except RPCException:
            return
        menu.value['favorite'] = value
        store.row_changed(path, iter_)
        self.favorite_unset()

    def win_set(self, page):
        current_page = self.notebook.get_current_page()
        page_num = self.notebook.page_num(page.widget)
        page.widget.props.visible = True
        self.notebook.set_current_page(page_num)
        # In order to focus the page
        if current_page == page_num:
            self._sig_page_changt(self.notebook, None, page_num)

    def win_add(self, page, hide_current=False):
        previous_page_id = self.notebook.get_current_page()
        previous_widget = self.notebook.get_nth_page(previous_page_id)
        if previous_widget and hide_current:
            page_id = previous_page_id + 1
        else:
            page_id = -1
        self.previous_pages[page] = previous_widget
        self.pages.append(page)
        hbox = Gtk.HBox(spacing=3)
        if page.icon:
            hbox.pack_start(
                common.IconFactory.get_image(
                    page.icon, Gtk.IconSize.SMALL_TOOLBAR),
                expand=False, fill=False, padding=0)
        name = page.name
        label = Gtk.Label(
            label=common.ellipsize(name, 20),
            halign=Gtk.Align.START)
        self.tooltips.set_tip(label, page.name)
        self.tooltips.enable()
        hbox.pack_start(label, expand=True, fill=True, padding=0)

        button = Gtk.Button()
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_can_focus(False)
        button.add(common.IconFactory.get_image(
                'tryton-close', Gtk.IconSize.MENU))
        self.tooltips.set_tip(button, _('Close Tab'))
        button.connect('clicked', self._sig_remove_book, page.widget)
        hbox.pack_start(button, expand=False, fill=False, padding=0)
        size = Gtk.IconSize.lookup(Gtk.IconSize.MENU)
        button.set_size_request(size.width, size.height)

        hbox.show_all()
        label_menu = Gtk.Label(
            label=page.name, halign=Gtk.Align.START)
        page.widget.props.margin = 3
        self.notebook.insert_page_menu(page.widget, hbox, label_menu, page_id)
        self.notebook.set_tab_reorderable(page.widget, True)
        self.notebook.set_current_page(page_id)

    def _sig_remove_book(self, widget, page_widget):
        for page in self.pages:
            if page.widget == page_widget:
                if not page.widget.props.sensitive:
                    return
                page_num = self.notebook.page_num(page.widget)
                self.notebook.set_current_page(page_num)
                res = page.sig_close()
                if not res:
                    return
        self._win_del(page_widget)

    def _win_del(self, page_widget=None):
        if page_widget:
            page_id = self.notebook.page_num(page_widget)
        else:
            page_id = int(self.notebook.get_current_page())
            page_widget = self.notebook.get_nth_page(page_id)
        if page_id != -1:
            page = None
            for i in range(len(self.pages)):
                if self.pages[i].widget == page_widget:
                    page = self.pages.pop(i)
                    page.signal_unconnect(self)
                    break
            self.notebook.remove_page(page_id)

            next_page_id = -1
            to_pop = []
            for i in self.previous_pages:
                if self.previous_pages[i] == page_widget:
                    to_pop.append(i)
                if i.widget == page_widget:
                    if self.previous_pages[i]:
                        next_page_id = self.notebook.page_num(
                                self.previous_pages[i])
                    to_pop.append(i)
            to_pop.reverse()
            for i in to_pop:
                self.previous_pages.pop(i)

            if hasattr(page, 'destroy'):
                page.destroy()
            del page

            current_widget = self.notebook.get_nth_page(next_page_id)
            if current_widget:
                current_widget.props.visible = True
            self.notebook.set_current_page(next_page_id)
        if not self.pages and self.menu_screen:
            self.menu_screen.set_cursor()
        return self.notebook.get_current_page() != -1

    def get_page(self, page_id=None):
        if page_id is None:
            page_id = self.notebook.get_current_page()
        if page_id == -1:
            return None
        page_widget = self.notebook.get_nth_page(page_id)
        for page in self.pages:
            if page.widget == page_widget:
                return page
        return None

    def _sig_page_changt(self, notebook, page, page_num):
        self.last_page = self.current_page
        last_form = self.get_page(self.current_page)
        if last_form:
            for dialog in last_form.dialogs:
                dialog.hide()

        self.current_page = self.notebook.get_current_page()
        current_form = self.get_page(self.current_page)

        def set_cursor():
            if self.current_page == self.notebook.get_current_page():
                current_form.set_cursor()
        # Using idle_add because the Gtk.TreeView grabs the focus at the
        # end of the event
        GLib.idle_add(set_cursor)
        for dialog in current_form.dialogs:
            dialog.show()

    def _open_url(self, url):
        urlp = urlparse(url)
        if not urlp.scheme == 'tryton':
            return
        urlp = urlparse('http' + url[6:])
        database, path = list(map(unquote,
            (urlp.path[1:].split('/', 1) + [''])[:2]))
        if not path:
            return
        type_, path = (path.split('/', 1) + [''])[:2]
        params = {}
        if urlp.params:
            try:
                params.update(dict(parse_qsl(urlp.params,
                            strict_parsing=True)))
            except ValueError:
                return

        def open_model(path):
            model, path = (path.split('/', 1) + [''])[:2]
            if not model:
                return
            res_id = None
            mode = None
            try:
                view_ids = json.loads(params.get('views', '[]'))
                limit = json.loads(params.get('limit', 'null'))
                name = json.loads(params.get('name', '""'))
                search_value = json.loads(params.get('search_value', '[]'),
                    object_hook=object_hook)
                domain = json.loads(params.get('domain', '[]'),
                    object_hook=object_hook)
                context = json.loads(params.get('context', '{}'),
                    object_hook=object_hook)
                context_model = params.get('context_model')
                tab_domain = json.loads(params.get('tab_domain', '[]'),
                    object_hook=object_hook)
            except ValueError:
                return
            if path:
                try:
                    res_id = int(path)
                except ValueError:
                    return
                mode = ['form', 'tree']
            try:
                Window.create(model,
                    view_ids=view_ids,
                    res_id=res_id,
                    domain=domain,
                    context=context,
                    context_model=context_model,
                    mode=mode,
                    name=name,
                    limit=limit,
                    search_value=search_value,
                    tab_domain=tab_domain)
            except Exception:
                # Prevent crashing the client
                return

        def open_wizard(wizard):
            if not wizard:
                return
            try:
                data = json.loads(params.get('data', '{}'),
                    object_hook=object_hook)
                direct_print = json.loads(params.get('direct_print', 'false'))
                email_print = json.loads(params.get('email_print', 'false'))
                email = json.loads(params.get('email', 'null'))
                name = json.loads(params.get('name', '""'))
                window = json.loads(params.get('window', 'false'))
                context = json.loads(params.get('context', '{}'),
                    object_hook=object_hook)
            except ValueError:
                return
            try:
                Window.create_wizard(wizard, data, direct_print=direct_print,
                    email_print=email_print, email=email, name=name,
                    context=context, window=window)
            except Exception:
                # Prevent crashing the client
                return

        def open_report(report):
            if not report:
                return
            try:
                data = json.loads(params.get('data'), object_hook=object_hook)
                direct_print = json.loads(params.get('direct_print', 'false'))
                email_print = json.loads(params.get('email_print', 'false'))
                email = json.loads(params.get('email', 'null'))
                context = json.loads(params.get('context', '{}'),
                    object_hook=object_hook)
            except ValueError:
                return
            try:
                Action.exec_report(report, data, direct_print=direct_print,
                    email_print=email_print, email=email, context=context)
            except Exception:
                # Prevent crashing the client
                return

        def open_url():
            try:
                url = json.loads(params.get('url', 'false'))
            except ValueError:
                return
            if url:
                webbrowser.open(url, new=2)

        if type_ == 'model':
            open_model(path)
        elif type_ == 'wizard':
            open_wizard(path)
        elif type_ == 'report':
            open_report(path)
        elif type_ == 'url':
            open_url()

        self.window.present()

    def open_url(self, url):
        def idle_open_url():
            self._open_url(url)
            return False
        GLib.idle_add(idle_open_url)

    def show_notification(self, title, msg, priority=1):
        notification = Gio.Notification.new(title)
        notification.set_body(msg)
        notification.set_priority(_PRIORITIES[priority])
        if sys.platform != 'win32' or GLib.glib_version >= (2, 57, 0):
            self.send_notification(None, notification)
