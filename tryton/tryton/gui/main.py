# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os
import sys
import gettext
from urlparse import urlparse, parse_qsl
import urllib
import gobject
import gtk
import json
import webbrowser
import threading

import tryton.rpc as rpc
from tryton.common import RPCExecute, RPCException, RPCContextReload
from tryton.config import CONFIG, TRYTON_ICON, get_config_dir
import tryton.common as common
from tryton.pyson import PYSONDecoder
from tryton.jsonrpc import object_hook
from tryton.action import Action
from tryton.exceptions import TrytonServerError, TrytonError, \
    TrytonServerUnavailable
from tryton.gui.window import Window
from tryton.gui.window.preference import Preference
from tryton.gui.window import Limit
from tryton.gui.window import Email
from tryton.gui.window.dblogin import DBLogin
from tryton.gui.window.tips import Tips
from tryton.gui.window.about import About
from tryton.gui.window.shortcuts import Shortcuts
from tryton.common.cellrendererclickablepixbuf import \
    CellRendererClickablePixbuf
import tryton.translate as translate
import tryton.plugins
from tryton.common.placeholder_entry import PlaceholderEntry
import pango
if os.environ.get('GTKOSXAPPLICATION'):
    import gtkosx_application
else:
    gtkosx_application = None
try:
    import gtkspell
except ImportError:
    gtkspell = None

_ = gettext.gettext


_MAIN = []
TAB_SIZE = 120


class Main(object):
    window = None
    tryton_client = None

    def __init__(self, tryton_client):
        super(Main, self).__init__()
        Main.tryton_client = tryton_client

        self.window = gtk.Window()
        self._width = int(CONFIG['client.default_width'])
        self._height = int(CONFIG['client.default_height'])
        if CONFIG['client.maximize']:
            self.window.maximize()
        self.window.set_default_size(self._width, self._height)
        self.window.set_resizable(True)
        self.set_title()
        self.window.set_icon(TRYTON_ICON)
        self.window.connect("destroy", Main.sig_quit)
        self.window.connect("delete_event", self.sig_close)
        self.window.connect('configure_event', self.sig_configure)
        self.window.connect('window_state_event', self.sig_window_state)

        self.accel_group = gtk.AccelGroup()
        self.window.add_accel_group(self.accel_group)

        self.macapp = None
        if gtkosx_application is not None:
            self.macapp = gtkosx_application.Application()
            self.macapp.connect("NSApplicationBlockTermination",
                self.sig_close)

        gtk.accel_map_add_entry('<tryton>/Connection/Connect', gtk.keysyms.O,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Connection/Quit', gtk.keysyms.Q,
                gtk.gdk.CONTROL_MASK)
        if sys.platform != 'darwin':
            gtk.accel_map_add_entry('<tryton>/User/Reload Menu', gtk.keysyms.T,
                    gtk.gdk.MOD1_MASK)
        gtk.accel_map_add_entry('<tryton>/User/Toggle Menu', gtk.keysyms.T,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/User/Global Search', gtk.keysyms.K,
            gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/User/Home', gtk.keysyms.H,
                gtk.gdk.CONTROL_MASK)

        gtk.accel_map_add_entry('<tryton>/Form/New', gtk.keysyms.N,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Save', gtk.keysyms.S,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Duplicate', gtk.keysyms.D,
                gtk.gdk.CONTROL_MASK | gtk.gdk.SHIFT_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Delete', gtk.keysyms.D,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Next', gtk.keysyms.Page_Down,
                0)
        gtk.accel_map_add_entry('<tryton>/Form/Previous', gtk.keysyms.Page_Up,
                0)
        gtk.accel_map_add_entry('<tryton>/Form/Switch View', gtk.keysyms.L,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Close', gtk.keysyms.W,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Previous Tab',
            gtk.keysyms.Page_Up, gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Next Tab',
            gtk.keysyms.Page_Down, gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Reload', gtk.keysyms.R,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Actions', gtk.keysyms.E,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Report', gtk.keysyms.P,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Search', gtk.keysyms.F,
            gtk.gdk.CONTROL_MASK)

        gtk.accel_map_load(os.path.join(get_config_dir(), 'accel.map'))

        self.tooltips = common.Tooltips()

        self.vbox = gtk.VBox()
        self.window.add(self.vbox)

        self.menubar = None
        self.global_search_entry = None
        self.menuitem_user = None
        self.menuitem_favorite = None

        self.buttons = {}

        self.pane = gtk.HPaned()
        self.vbox.pack_start(self.pane, True, True)
        self.pane.connect('button-press-event',
            self.on_paned_button_press_event)

        self.menu_screen = None
        self.menu_expander = gtk.Expander()
        self.menu_expander.connect('notify::expanded', self.menu_expanded)
        if self.menu_expander.get_direction() == gtk.TEXT_DIR_RTL:
            self.menu_expander.set_direction(gtk.TEXT_DIR_LTR)
        else:
            self.menu_expander.set_direction(gtk.TEXT_DIR_RTL)
        self.menu_expander.set_expanded(CONFIG['menu.expanded'])
        self.pane.add1(self.menu_expander)

        self.notebook = gtk.Notebook()
        self.notebook.popup_enable()
        self.notebook.set_scrollable(True)
        self.notebook.connect_after('switch-page', self._sig_page_changt)

        self.pane.add2(self.notebook)

        self.set_menubar()

        self.window.show_all()

        self.pages = []
        self.previous_pages = {}
        self.current_page = 0
        self.last_page = 0
        self.dialogs = []

        if CONFIG['client.modepda']:
            self.radiomenuitem_pda.set_active(True)
        else:
            self.radiomenuitem_normal.set_active(True)

        settings = gtk.settings_get_default()
        # Due to a bug in old version of pyGTk gtk-button-images can
        # not be set when there is no buttons
        gtk.Button()
        try:
            settings.set_property('gtk-button-images', True)
        except TypeError:
            pass
        try:
            settings.set_property('gtk-can-change-accels',
                CONFIG['client.can_change_accelerators'])
        except TypeError:
            pass

        # Register plugins
        tryton.plugins.register()

        if self.macapp is not None:
            self.macapp.ready()

        _MAIN.append(self)

    def set_menubar(self):
        if self.menubar:
            self.menubar.destroy()
        menubar = gtk.MenuBar()
        self.menubar = menubar

        self.vbox.pack_start(menubar, False, True)
        self.vbox.reorder_child(menubar, 0)

        menuitem_connection = gtk.MenuItem(
            _('_Connection'), use_underline=True)
        menubar.add(menuitem_connection)

        menu_connection = self._set_menu_connection()
        menuitem_connection.set_submenu(menu_connection)
        menu_connection.set_accel_group(self.accel_group)
        menu_connection.set_accel_path('<tryton>/Connection')

        menuitem_user = gtk.MenuItem(_('_User'), use_underline=True)
        if self.menuitem_user:
            menuitem_user.set_sensitive(
                    self.menuitem_user.get_property('sensitive'))
        else:
            menuitem_user.set_sensitive(False)
        self.menuitem_user = menuitem_user
        menubar.add(menuitem_user)

        menu_user = self._set_menu_user()
        menuitem_user.set_submenu(menu_user)
        menu_user.set_accel_group(self.accel_group)
        menu_user.set_accel_path('<tryton>/User')

        menuitem_options = gtk.MenuItem(_('_Options'), use_underline=True)
        menubar.add(menuitem_options)

        menu_options = self._set_menu_options()
        menuitem_options.set_submenu(menu_options)
        menu_options.set_accel_group(self.accel_group)
        menu_options.set_accel_path('<tryton>/Options')

        menuitem_favorite = gtk.MenuItem(_('Fa_vorites'), use_underline=True)
        if self.menuitem_favorite:
            menuitem_favorite.set_sensitive(
                self.menuitem_favorite.get_property('sensitive'))
        else:
            menuitem_favorite.set_sensitive(False)
        self.menuitem_favorite = menuitem_favorite
        menubar.add(menuitem_favorite)
        menuitem_favorite.set_accel_path('<tryton>/Favorites')

        def favorite_activate(widget):
            if (not menuitem_favorite.get_submenu()
                    or not menuitem_favorite.get_submenu().get_children()):
                self.favorite_set()
        menuitem_favorite.connect('select', favorite_activate)

        menuitem_help = gtk.MenuItem(_('_Help'), use_underline=True)
        menubar.add(menuitem_help)

        menu_help = self._set_menu_help()
        menuitem_help.set_submenu(menu_help)
        menu_help.set_accel_group(self.accel_group)
        menu_help.set_accel_path('<tryton>/Help')

        if self.macapp is not None:
            self.menubar.set_no_show_all(True)
            self.macapp.set_menu_bar(self.menubar)
            self.macapp.insert_app_menu_item(self.aboutitem, 0)
            menuitem_connection.show_all()
            menuitem_user.show_all()
            menuitem_options.show_all()
            menuitem_favorite.show_all()
            menuitem_help.show_all()
        else:
            self.menubar.show_all()

    def set_global_search(self):
        self.global_search_entry = PlaceholderEntry()
        self.global_search_entry.set_placeholder_text(_('Search'))
        global_search_completion = gtk.EntryCompletion()
        global_search_completion.set_match_func(lambda *a: True)
        global_search_completion.set_model(gtk.ListStore(
                gtk.gdk.Pixbuf, str, str, int, str))
        pixbuf_cell = gtk.CellRendererPixbuf()
        global_search_completion.pack_start(pixbuf_cell, False)
        global_search_completion.add_attribute(pixbuf_cell, 'pixbuf', 0)
        text_cell = gtk.CellRendererText()
        global_search_completion.pack_start(text_cell)
        global_search_completion.add_attribute(text_cell, "markup", 1)
        global_search_completion.props.popup_set_width = True
        self.global_search_entry.set_completion(global_search_completion)
        self.global_search_entry.set_icon_from_stock(gtk.ENTRY_ICON_PRIMARY,
            'gtk-find')

        def match_selected(completion, model, iter_):
            model, record_id, model_name = model.get(iter_, 2, 3, 4)
            if model == self.menu_screen.model_name:
                Action.exec_keyword('tree_open', {
                        'model': model,
                        'id': record_id,
                        'ids': [record_id],
                        }, context=self.menu_screen.context.copy())
            else:
                Window.create(False, model, res_id=record_id,
                    mode=['form', 'tree'], name=model_name)
            self.global_search_entry.set_text('')
            return True

        global_search_completion.connect('match-selected', match_selected)

        def update(widget, search_text, callback=None):
            def end():
                if callback:
                    callback()
                return False
            if search_text != widget.get_text().decode('utf-8'):
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
                if search_text != widget.get_text().decode('utf-8'):
                    if callback:
                        callback()
                    return False
                gmodel.clear()
                for r in result:
                    _, model, model_name, record_id, record_name, icon = r
                    if icon:
                        text = common.to_xml(record_name)
                        common.ICONFACTORY.register_icon(icon)
                        pixbuf = widget.render_icon(stock_id=icon,
                            size=gtk.ICON_SIZE_BUTTON, detail=None)
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
            search_text = widget.get_text().decode('utf-8')
            gobject.timeout_add(300, update, widget, search_text)

        def activate(widget):
            def message():
                gmodel = global_search_completion.get_model()
                if not len(gmodel):
                    common.message(_('No result found.'))
                else:
                    widget.emit('changed')
            search_text = widget.get_text().decode('utf-8')
            update(widget, search_text, message)

        self.global_search_entry.connect('changed', changed)
        self.global_search_entry.connect('activate', activate)

    def show_global_search(self):
        self.pane.get_child1().set_expanded(True)
        self.global_search_entry.grab_focus()

    def set_title(self, value=''):
        title = CONFIG['client.title']
        if value:
            title += ' - ' + value
        self.window.set_title(title)

    def _set_menu_connection(self):
        menu_connection = gtk.Menu()

        imagemenuitem_connect = gtk.ImageMenuItem(_('_Connect...'),
            self.accel_group)
        imagemenuitem_connect.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('tryton-connect', gtk.ICON_SIZE_MENU)
        imagemenuitem_connect.set_image(image)
        imagemenuitem_connect.connect('activate', self.sig_login)
        imagemenuitem_connect.set_accel_path('<tryton>/Connection/Connect')
        menu_connection.add(imagemenuitem_connect)

        imagemenuitem_disconnect = gtk.ImageMenuItem(_('_Disconnect'))
        imagemenuitem_disconnect.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('tryton-disconnect', gtk.ICON_SIZE_MENU)
        imagemenuitem_disconnect.set_image(image)
        imagemenuitem_disconnect.connect('activate', self.sig_logout)
        imagemenuitem_disconnect.set_accel_path(
            '<tryton>/Connection/Disconnect')
        menu_connection.add(imagemenuitem_disconnect)

        imagemenuitem_close = gtk.ImageMenuItem(_('_Quit...'),
            self.accel_group)
        imagemenuitem_close.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('tryton-log-out', gtk.ICON_SIZE_MENU)
        imagemenuitem_close.set_image(image)
        imagemenuitem_close.connect('activate', self.sig_close)
        imagemenuitem_close.set_accel_path('<tryton>/Connection/Quit')
        if self.macapp is None:
            menu_connection.add(gtk.SeparatorMenuItem())
            menu_connection.add(imagemenuitem_close)
        return menu_connection

    def _set_menu_user(self):
        menu_user = gtk.Menu()

        imagemenuitem_preference = gtk.ImageMenuItem(_('_Preferences...'))
        imagemenuitem_preference.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('tryton-preferences-system-session',
                gtk.ICON_SIZE_MENU)
        imagemenuitem_preference.set_image(image)
        imagemenuitem_preference.connect('activate', self.sig_user_preferences)
        imagemenuitem_preference.set_accel_path('<tryton>/User/Preferences')
        menu_user.add(imagemenuitem_preference)

        menu_user.add(gtk.SeparatorMenuItem())

        imagemenuitem_menu = gtk.ImageMenuItem(_('_Menu Reload'),
            self.accel_group)
        imagemenuitem_menu.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('tryton-start-here', gtk.ICON_SIZE_MENU)
        imagemenuitem_menu.set_image(image)
        imagemenuitem_menu.connect('activate', lambda *a: self.sig_win_menu())
        imagemenuitem_menu.set_accel_path('<tryton>/User/Reload Menu')
        menu_user.add(imagemenuitem_menu)

        imagemenuitem_menu_toggle = gtk.ImageMenuItem(_('_Menu Toggle'),
                self.accel_group)
        imagemenuitem_menu_toggle.set_use_underline(True)
        imagemenuitem_menu_toggle.connect('activate',
            lambda *a: self.menu_toggle())
        imagemenuitem_menu_toggle.set_accel_path('<tryton>/User/Toggle Menu')
        menu_user.add(imagemenuitem_menu_toggle)

        imagemenuitem_global_search = gtk.ImageMenuItem(_('_Global Search'),
            self.accel_group)
        imagemenuitem_global_search.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('gtk-find', gtk.ICON_SIZE_MENU)
        imagemenuitem_global_search.set_image(image)
        imagemenuitem_global_search.connect('activate', lambda *a:
            self.show_global_search())
        imagemenuitem_global_search.set_accel_path(
            '<tryton>/User/Global Search')
        menu_user.add(imagemenuitem_global_search)
        return menu_user

    def _set_menu_options(self):
        menu_options = gtk.Menu()

        menuitem_toolbar = gtk.MenuItem(_('_Toolbar'), use_underline=True)
        menu_options.add(menuitem_toolbar)

        menu_toolbar = gtk.Menu()
        menu_toolbar.set_accel_group(self.accel_group)
        menu_toolbar.set_accel_path('<tryton>/Options/Toolbar')
        menuitem_toolbar.set_submenu(menu_toolbar)

        radiomenuitem_default = gtk.RadioMenuItem(label=_('_Default'),
            use_underline=True)
        radiomenuitem_default.connect('activate',
                lambda x: self.sig_toolbar('default'))
        radiomenuitem_default.set_accel_path(
            '<tryton>/Options/Toolbar/Default')
        menu_toolbar.add(radiomenuitem_default)
        if (CONFIG['client.toolbar'] or 'both') == 'default':
            radiomenuitem_default.set_active(True)

        radiomenuitem_both = gtk.RadioMenuItem(group=radiomenuitem_default,
                label=_('_Text and Icons'), use_underline=True)
        radiomenuitem_both.connect('activate',
                lambda x: self.sig_toolbar('both'))
        radiomenuitem_both.set_accel_path(
                '<tryton>/Options/Toolbar/Text and Icons')
        menu_toolbar.add(radiomenuitem_both)
        if (CONFIG['client.toolbar'] or 'both') == 'both':
            radiomenuitem_both.set_active(True)

        radiomenuitem_icons = gtk.RadioMenuItem(group=radiomenuitem_default,
                label=_('_Icons'), use_underline=True)
        radiomenuitem_icons.connect('activate',
                lambda x: self.sig_toolbar('icons'))
        radiomenuitem_icons.set_accel_path('<tryton>/Options/Toolbar/Icons')
        menu_toolbar.add(radiomenuitem_icons)
        if (CONFIG['client.toolbar'] or 'both') == 'icons':
            radiomenuitem_icons.set_active(True)

        radiomenuitem_text = gtk.RadioMenuItem(group=radiomenuitem_default,
                label=_('_Text'), use_underline=True)
        radiomenuitem_text.connect('activate',
                lambda x: self.sig_toolbar('text'))
        radiomenuitem_text.set_accel_path('<tryton>/Options/Toolbar/Text')
        menu_toolbar.add(radiomenuitem_text)
        if (CONFIG['client.toolbar'] or 'both') == 'text':
            radiomenuitem_text.set_active(True)

        # Menubar accelerators
        menuitem_menubar = gtk.MenuItem(_('_Menubar'), use_underline=True)
        menu_options.add(menuitem_menubar)

        menu_menubar = gtk.Menu()
        menu_menubar.set_accel_group(self.accel_group)
        menu_menubar.set_accel_path('<tryton>/Options/Menubar')
        menuitem_menubar.set_submenu(menu_menubar)

        checkmenuitem_accel = gtk.CheckMenuItem(_('Change Accelerators'),
            use_underline=True)
        checkmenuitem_accel.connect('activate',
                lambda menuitem: self.sig_accel_change(menuitem.get_active()))
        checkmenuitem_accel.set_accel_path('<tryton>/Options/Menubar/Accel')
        menu_menubar.add(checkmenuitem_accel)
        if CONFIG['client.can_change_accelerators']:
            checkmenuitem_accel.set_active(True)

        menuitem_mode = gtk.MenuItem(_('_Mode'), use_underline=True)
        menu_options.add(menuitem_mode)

        menu_mode = gtk.Menu()
        menu_mode.set_accel_group(self.accel_group)
        menu_mode.set_accel_path('<tryton>/Options/Mode')
        menuitem_mode.set_submenu(menu_mode)

        radiomenuitem_normal = gtk.RadioMenuItem(label=_('_Normal'),
            use_underline=True)
        self.radiomenuitem_normal = radiomenuitem_normal
        radiomenuitem_normal.connect('activate',
                lambda x: self.sig_mode_change(False))
        radiomenuitem_normal.set_accel_path('<tryton>/Options/Mode/Normal')
        menu_mode.add(radiomenuitem_normal)

        radiomenuitem_pda = gtk.RadioMenuItem(group=radiomenuitem_normal,
                label=_('_PDA'), use_underline=True)
        self.radiomenuitem_pda = radiomenuitem_pda
        radiomenuitem_pda.connect('activate',
                lambda x: self.sig_mode_change(True))
        radiomenuitem_pda.set_accel_path('<tryton>/Options/Mode/PDA')
        menu_mode.add(radiomenuitem_pda)

        menuitem_form = gtk.MenuItem(_('_Form'), use_underline=True)
        menu_options.add(menuitem_form)

        menu_form = gtk.Menu()
        menu_form.set_accel_group(self.accel_group)
        menu_form.set_accel_path('<tryton>/Options/Form')
        menuitem_form.set_submenu(menu_form)

        checkmenuitem_save_width_height = gtk.CheckMenuItem(
            _('Save Width/Height'), use_underline=True)
        checkmenuitem_save_width_height.connect('activate',
            lambda menuitem: CONFIG.__setitem__('client.save_width_height',
                menuitem.get_active()))
        checkmenuitem_save_width_height.set_accel_path(
            '<tryton>/Options/Form/Save Width Height')
        menu_form.add(checkmenuitem_save_width_height)
        if CONFIG['client.save_width_height']:
            checkmenuitem_save_width_height.set_active(True)

        checkmenuitem_save_tree_state = gtk.CheckMenuItem(
            _('Save Tree State'), use_underline=True)
        checkmenuitem_save_tree_state.connect('activate',
            lambda menuitem: CONFIG.__setitem__(
                'client.save_tree_state',
                menuitem.get_active()))
        checkmenuitem_save_tree_state.set_accel_path(
            '<tryton>/Options/Form/Save Tree State')
        menu_form.add(checkmenuitem_save_tree_state)
        if CONFIG['client.save_tree_state']:
            checkmenuitem_save_tree_state.set_active(True)

        checkmenuitem_fast_tabbing = gtk.CheckMenuItem(
            _('Fast Tabbing'), use_underline=True)
        checkmenuitem_fast_tabbing.connect('activate',
            lambda menuitem: CONFIG.__setitem__('client.fast_tabbing',
                menuitem.get_active()))
        checkmenuitem_fast_tabbing.set_accel_path(
            '<tryton>/Options/Form/Fast Tabbing')
        menu_form.add(checkmenuitem_fast_tabbing)
        checkmenuitem_fast_tabbing.set_active(CONFIG['client.fast_tabbing'])

        if gtkspell:
            checkmenuitem_spellcheck = gtk.CheckMenuItem(_('Spell Checking'),
                use_underline=True)
            checkmenuitem_spellcheck.connect('activate',
                    lambda menuitem: CONFIG.__setitem__('client.spellcheck',
                        menuitem.get_active()))
            checkmenuitem_spellcheck.set_accel_path(
                    '<tryton>/Options/Form/Spell Checking')
            menu_form.add(checkmenuitem_spellcheck)
            if CONFIG['client.spellcheck']:
                checkmenuitem_spellcheck.set_active(True)

        imagemenuitem_win_prev = gtk.ImageMenuItem(_('_Previous Tab'),
            self.accel_group)
        imagemenuitem_win_prev.set_use_underline(True)
        imagemenuitem_win_prev.connect('activate', self.sig_win_prev)
        imagemenuitem_win_prev.set_accel_path('<tryton>/Form/Previous Tab')
        menu_form.add(imagemenuitem_win_prev)

        imagemenuitem_win_next = gtk.ImageMenuItem(_('_Next Tab'),
            self.accel_group)
        imagemenuitem_win_next.set_use_underline(True)
        imagemenuitem_win_next.connect('activate', self.sig_win_next)
        imagemenuitem_win_next.set_accel_path('<tryton>/Form/Next Tab')
        menu_form.add(imagemenuitem_win_next)

        menuitem_limit = gtk.MenuItem(_('Search Limit...'), use_underline=True)
        self.menuitem_limit = menuitem_limit
        menuitem_limit.connect('activate', self.sig_limit)
        menuitem_limit.set_accel_path('<tryton>/Options/Search Limit')
        menu_options.add(menuitem_limit)

        menuitem_email = gtk.MenuItem(_('_Email...'), use_underline=True)
        self.menuitem_email = menuitem_email
        menuitem_email.connect('activate', self.sig_email)
        menuitem_email.set_accel_path('<tryton>/Options/Email')
        menu_options.add(menuitem_email)

        menu_options.add(gtk.SeparatorMenuItem())

        imagemenuitem_opt_save = gtk.ImageMenuItem(_('_Save Options'))
        imagemenuitem_opt_save.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('tryton-save', gtk.ICON_SIZE_MENU)
        imagemenuitem_opt_save.set_image(image)
        imagemenuitem_opt_save.connect('activate', lambda x: CONFIG.save())
        imagemenuitem_opt_save.set_accel_path('<tryton>/Options/Save Options')
        menu_options.add(imagemenuitem_opt_save)
        return menu_options

    def _set_menu_help(self):
        menu_help = gtk.Menu()

        imagemenuitem_tips = gtk.ImageMenuItem(_('_Tips...'))
        imagemenuitem_tips.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('tryton-information', gtk.ICON_SIZE_MENU)
        imagemenuitem_tips.set_image(image)
        imagemenuitem_tips.connect('activate', self.sig_tips)
        imagemenuitem_tips.set_accel_path('<tryton>/Help/Tips')
        menu_help.add(imagemenuitem_tips)

        imagemenuitem_shortcuts = gtk.ImageMenuItem(
            _('_Keyboard Shortcuts...'))
        imagemenuitem_shortcuts.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('tryton-help', gtk.ICON_SIZE_MENU)
        imagemenuitem_shortcuts.set_image(image)
        imagemenuitem_shortcuts.connect('activate', self.sig_shortcuts)
        imagemenuitem_shortcuts.set_accel_path(
            '<tryton>/Help/Keyboard Shortcuts')
        menu_help.add(imagemenuitem_shortcuts)

        imagemenuitem_about = gtk.ImageMenuItem(_('_About...'))
        imagemenuitem_about.set_use_underline(True)
        image = gtk.Image()
        image.set_from_stock('gtk-about', gtk.ICON_SIZE_MENU)
        imagemenuitem_about.set_image(image)
        imagemenuitem_about.connect('activate', self.sig_about)
        imagemenuitem_about.set_accel_path('<tryton>/Help/About')
        self.aboutitem = imagemenuitem_about
        if self.macapp is None:
            menu_help.add(gtk.SeparatorMenuItem())
            menu_help.add(imagemenuitem_about)

        return menu_help

    @staticmethod
    def get_main():
        return _MAIN[0]

    def favorite_set(self):
        if not self.menu_screen:
            return False

        def _action_favorite(widget, id_):
            event = gtk.get_current_event()
            allow_similar = (event.state & gtk.gdk.MOD1_MASK or
                             event.state & gtk.gdk.SHIFT_MASK)
            with Window(allow_similar=allow_similar):
                Action.exec_keyword('tree_open', {
                    'model': self.menu_screen.model_name,
                    'id': id_,
                    'ids': [id_],
                })

        def _manage_favorites(widget):
            Window.create(False, self.menu_screen.model_name + '.favorite',
                False, mode=['tree', 'form'], name=_('Manage Favorites'))
        try:
            favorites = RPCExecute('model',
                self.menu_screen.model_name + '.favorite', 'get',
                process_exception=False)
        except Exception:
            return False
        menu = self.menuitem_favorite.get_submenu()
        if not menu:
            menu = gtk.Menu()
        for id_, name, icon in favorites:
            if icon:
                common.ICONFACTORY.register_icon(icon)
                menuitem = gtk.ImageMenuItem(name)
                image = gtk.Image()
                image.set_from_stock(icon, gtk.ICON_SIZE_MENU)
                menuitem.set_image(image)
            else:
                menuitem = gtk.MenuItem(name)
            menuitem.connect('activate', _action_favorite, id_)
            menu.add(menuitem)
        menu.add(gtk.SeparatorMenuItem())
        manage_favorites = gtk.MenuItem(_('Manage Favorites'),
            use_underline=True)
        manage_favorites.connect('activate', _manage_favorites)
        menu.add(manage_favorites)
        menu.show_all()
        self.menuitem_favorite.set_submenu(menu)
        return True

    def favorite_unset(self):
        had_submenu = self.menuitem_favorite.get_submenu()
        self.menuitem_favorite.set_submenu(None)
        # Set a submenu to get keyboard shortcut working
        self.menuitem_favorite.set_submenu(gtk.Menu())

        if self.macapp and had_submenu:
            # As the select event is not managed by the mac menu,
            # it is done using a timeout
            gobject.timeout_add(1000, lambda: not self.favorite_set())

    def sig_accel_change(self, value):
        CONFIG['client.can_change_accelerators'] = value
        return self.sig_accel()

    def sig_accel(self):
        menubar = CONFIG['client.can_change_accelerators']
        settings = gtk.settings_get_default()
        if menubar:
            settings.set_property('gtk-can-change-accels', True)
        else:
            settings.set_property('gtk-can-change-accels', False)

    def sig_mode_change(self, pda_mode=False):
        CONFIG['client.modepda'] = pda_mode
        return

    def sig_toolbar(self, option):
        CONFIG['client.toolbar'] = option
        if option == 'default':
            barstyle = False
        elif option == 'both':
            barstyle = gtk.TOOLBAR_BOTH
        elif option == 'text':
            barstyle = gtk.TOOLBAR_TEXT
        elif option == 'icons':
            barstyle = gtk.TOOLBAR_ICONS
        for page_idx in range(self.notebook.get_n_pages()):
            page = self.get_page(page_idx)
            page.toolbar.set_style(barstyle)

    def sig_limit(self, widget):
        Limit().run()

    def sig_email(self, widget):
        Email().run()

    def sig_win_next(self, widget):
        page = self.notebook.get_current_page()
        if page == len(self.pages) - 1:
            page = -1
        self.notebook.set_current_page(page + 1)

    def sig_win_prev(self, widget):
        page = self.notebook.get_current_page()
        self.notebook.set_current_page(page - 1)

    def get_preferences(self):
        def _set_preferences(prefs):
            try:
                prefs = prefs()
            except RPCException:
                prefs = {}
            threads = []
            for target in (
                    common.ICONFACTORY.load_icons,
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
                    self.set_menubar()
                    self.favorite_unset()
                CONFIG['client.lang'] = prefs['language']
            # Set placeholder after language is set to get correct translation
            if self.global_search_entry:
                self.global_search_entry.set_placeholder_text(_('Search'))
            CONFIG.save()

        def _get_preferences():
            RPCExecute('model', 'res.user', 'get_preferences', False,
                callback=_set_preferences)

        RPCContextReload(_get_preferences)

    def sig_user_preferences(self, widget):
        if not self.close_pages():
            return False
        Preference(rpc._USER, self.get_preferences)

    def sig_win_close(self, widget=None):
        self._sig_remove_book(widget,
            self.notebook.get_nth_page(self.notebook.get_current_page()))

    def sig_login(self, widget=None):
        if not self.sig_logout(widget, disconnect=False):
            return
        language = CONFIG['client.lang']
        try:
            host, port, database, username = DBLogin().run()
        except TrytonError, exception:
            if exception.faultCode == 'QueryCanceled':
                return
            raise
        func = lambda parameters: rpc.login(
            host, port, database, username, parameters, language)
        try:
            common.Login(func)
        except Exception, exception:
            if (isinstance(exception, TrytonError)
                    and exception.faultCode == 'QueryCanceled'):
                return
            if (isinstance(exception, TrytonServerError)
                    and exception.faultCode.startswith('404')):
                return self.sig_login()
            common.process_exception(exception)
            return
        self.get_preferences()
        self.favorite_unset()
        self.menuitem_favorite.set_sensitive(True)
        self.menuitem_user.set_sensitive(True)
        if CONFIG.arguments:
            url = CONFIG.arguments.pop()
            self.open_url(url)
        return True

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
            self.menu_screen.destroy()
            self.menu_screen = None
        self.menu_expander_clear()
        return True

    def sig_logout(self, widget=None, disconnect=True):
        try:
            if not self.close_pages():
                return False
        except TrytonServerUnavailable:
            pass
        self.set_title()
        self.favorite_unset()
        self.menuitem_favorite.set_sensitive(False)
        self.menuitem_user.set_sensitive(False)
        if disconnect:
            rpc.logout()
        return True

    def sig_tips(self, *args):
        Tips()

    def sig_about(self, widget):
        About()

    def sig_shortcuts(self, widget):
        Shortcuts().run()

    def menu_toggle(self):
        expander = self.pane.get_child1()
        if expander:
            expander.set_expanded(not expander.get_expanded())

    @property
    def menu_expander_size(self):
        return self.menu_expander.style_get_property('expander-size')

    def menu_expanded(self, expander, *args):
        expanded = expander.get_expanded()
        CONFIG['menu.expanded'] = expanded
        if expanded:
            self.pane.set_position(int(CONFIG['menu.pane']))
            if self.menu_screen:
                self.menu_screen.set_cursor()
        else:
            CONFIG['menu.pane'] = self.pane.get_position()
            self.pane.set_position(self.menu_expander_size)
            self.notebook.grab_focus()

    def menu_expander_clear(self):
        if self.menu_expander.get_child():
            self.menu_expander.remove(self.menu_expander.get_child())
            expanded = self.menu_expander.get_expanded()
            CONFIG['menu.expanded'] = expanded
            if expanded:
                CONFIG['menu.pane'] = self.pane.get_position()

    def on_paned_button_press_event(self, paned, event):
        expander = self.pane.get_child1()
        if expander:
            return not expander.get_expanded()
        return False

    def sig_win_menu(self, prefs=None):
        from tryton.gui.window.view_form.screen import Screen

        if not prefs:
            try:
                prefs = RPCExecute('model', 'res.user', 'get_preferences',
                    False)
            except RPCException:
                return False

        vbox = gtk.VBox()
        if hasattr(vbox, 'set_vexpand'):
            vbox.set_vexpand(True)

        self.set_global_search()
        vbox.pack_start(self.global_search_entry, False, False)
        vbox.show_all()

        if self.menu_screen:
            self.menu_screen.save_tree_state()
        self.menu_screen = None
        self.menu_expander_clear()
        action = PYSONDecoder().decode(prefs['pyson_menu'])
        view_ids = False
        if action.get('views', []):
            view_ids = [x[0] for x in action['views']]
        elif action.get('view_id', False):
            view_ids = [action['view_id'][0]]
        ctx = rpc.CONTEXT.copy()
        decoder = PYSONDecoder(ctx)
        action_ctx = decoder.decode(action.get('pyson_context') or '{}')
        domain = decoder.decode(action['pyson_domain'])
        screen = Screen(action['res_model'], mode=['tree'], view_ids=view_ids,
            domain=domain, context=action_ctx, readonly=True)
        # Use alternate view to not show search box
        screen.screen_container.alternate_view = True
        screen.switch_view(view_type=screen.current_view.view_type)

        vbox.pack_start(screen.screen_container.alternate_viewport, True, True)
        treeview = screen.current_view.treeview
        treeview.set_headers_visible(False)

        self.menu_expander.add(vbox)

        # Favorite column
        column = gtk.TreeViewColumn()
        column.name = None
        column._type = None
        favorite_renderer = CellRendererClickablePixbuf()
        column.pack_start(favorite_renderer, expand=False)

        def favorite_setter(column, cell, store, iter_):
            menu = store.get_value(iter_, 0)
            favorite = menu.value.get('favorite')
            if favorite:
                stock_id = 'tryton-star'
            elif favorite is False:
                stock_id = 'tryton-unstar'
            else:
                stock_id = ''
            pixbuf = treeview.render_icon(stock_id=stock_id,
                size=gtk.ICON_SIZE_MENU, detail=None)
            cell.set_property('pixbuf', pixbuf)
        column.set_cell_data_func(favorite_renderer, favorite_setter)

        def toggle_favorite(renderer, path, treeview):
            if treeview.props.window:
                self.toggle_favorite(renderer, path, treeview)
        favorite_renderer.connect('clicked',
            lambda *a: gobject.idle_add(toggle_favorite, *a), treeview)
        # Unset fixed height mode to add column
        treeview.set_fixed_height_mode(False)
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

    @classmethod
    def sig_quit(cls, widget=None):
        rpc.logout()
        CONFIG['client.default_width'] = Main.get_main()._width
        CONFIG['client.default_height'] = Main.get_main()._height
        CONFIG.save()
        gtk.accel_map_save(os.path.join(get_config_dir(), 'accel.map'))

        cls.tryton_client.quit_mainloop()
        sys.exit()

    def sig_close(self, widget, event=None):
        if not self.sig_logout(widget):
            return True
        Main.sig_quit()

    def sig_configure(self, widget, event):
        if hasattr(event, 'width') \
                and hasattr(event, 'height'):
            self._width = int(event.width)
            self._height = int(event.height)
        return False

    def sig_window_state(self, widget, event):
        CONFIG['client.maximize'] = (event.new_window_state ==
                gtk.gdk.WINDOW_STATE_MAXIMIZED)
        return False

    def win_add(self, page, hide_current=False, allow_similar=True):
        if not allow_similar:
            for other_page in self.pages:
                if page == other_page:
                    current_page = self.notebook.get_current_page()
                    page_num = self.notebook.page_num(other_page.widget)
                    other_page.widget.props.visible = True
                    self.notebook.set_current_page(page_num)
                    # In order to focus the page
                    if current_page == page_num:
                        self._sig_page_changt(self.notebook, None, page_num)
                    return
        previous_page_id = self.notebook.get_current_page()
        previous_widget = self.notebook.get_nth_page(previous_page_id)
        if previous_widget and hide_current:
            prev_tab_label = self.notebook.get_tab_label(previous_widget)
            prev_tab_label.set_size_request(TAB_SIZE / 4, -1)
            close_button = prev_tab_label.get_children()[-1]
            close_button.hide()
            page_id = previous_page_id + 1
        else:
            page_id = -1
        self.previous_pages[page] = previous_widget
        self.pages.append(page)
        hbox = gtk.HBox(spacing=3)
        icon_w, icon_h = gtk.icon_size_lookup(gtk.ICON_SIZE_SMALL_TOOLBAR)[-2:]
        if page.icon is not None:
            common.ICONFACTORY.register_icon(page.icon)
            image = gtk.Image()
            image.set_from_stock(page.icon, gtk.ICON_SIZE_SMALL_TOOLBAR)
            hbox.pack_start(image, expand=False, fill=False)
            noise_size = 2 * icon_w + 3
        else:
            noise_size = icon_w + 3
        name = page.name
        label = gtk.Label(name)
        self.tooltips.set_tip(label, page.name)
        self.tooltips.enable()
        label.set_alignment(0.0, 0.5)
        hbox.pack_start(label, expand=True, fill=True)
        layout = label.get_layout()
        w, h = layout.get_size()
        if (w // pango.SCALE) > TAB_SIZE - noise_size:
            label2 = gtk.Label('...')
            self.tooltips.set_tip(label2, page.name)
            hbox.pack_start(label2, expand=False, fill=False)

        button = gtk.Button()
        img = gtk.Image()
        img.set_from_stock('tryton-close', gtk.ICON_SIZE_MENU)
        width, height = img.size_request()
        button.set_relief(gtk.RELIEF_NONE)
        button.set_can_focus(False)
        button.add(img)
        self.tooltips.set_tip(button, _('Close Tab'))
        button.connect('clicked', self._sig_remove_book, page.widget)
        hbox.pack_start(button, expand=False, fill=False)
        x, y = gtk.icon_size_lookup_for_settings(button.get_settings(),
            gtk.ICON_SIZE_MENU)[-2:]
        button.set_size_request(x, y)

        hbox.show_all()
        hbox.set_size_request(TAB_SIZE, -1)
        label_menu = gtk.Label(page.name)
        label_menu.set_alignment(0.0, 0.5)
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
        tab_label = notebook.get_tab_label(notebook.get_nth_page(page_num))
        tab_label.set_size_request(TAB_SIZE, -1)
        close_button = tab_label.get_children()[-1]
        close_button.show()
        if last_form:
            for dialog in last_form.dialogs:
                dialog.hide()

        self.current_page = self.notebook.get_current_page()
        current_form = self.get_page(self.current_page)

        def set_cursor():
            if self.current_page == self.notebook.get_current_page():
                current_form.set_cursor()
        # Using idle_add because the gtk.TreeView grabs the focus at the
        # end of the event
        gobject.idle_add(set_cursor)
        for dialog in current_form.dialogs:
            dialog.show()

    def _open_url(self, url):
        urlp = urlparse(url)
        if not urlp.scheme == 'tryton':
            return
        urlp = urlparse('http' + url[6:])
        hostname, port = map(urllib.unquote,
            (urlp.netloc.split(':', 1) + [CONFIG.defaults['login.port']])[:2])
        database, path = map(urllib.unquote,
            (urlp.path[1:].split('/', 1) + [''])[:2])
        if (not path or
                hostname != rpc._HOST or
                int(port) != rpc._PORT or
                database != rpc._DATABASE):
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
            res_id = False
            mode = None
            try:
                view_ids = json.loads(params.get('views', '[]'))
                limit = json.loads(params.get('limit', 'null'))
                name = json.loads(params.get('name', '""'))
                search_value = json.loads(params.get('search_value', '{}'),
                    object_hook=object_hook)
                domain = json.loads(params.get('domain', '[]'),
                    object_hook=object_hook)
                context = json.loads(params.get('context', '{}'),
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
                Window.create(view_ids, model, res_id=res_id, domain=domain,
                    context=context, mode=mode, name=name, limit=limit,
                    search_value=search_value)
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
            with gtk.gdk.lock:
                self._open_url(url)
                return False
        gobject.idle_add(idle_open_url)
