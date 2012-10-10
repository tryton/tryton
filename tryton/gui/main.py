#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import os
import sys
import socket
import gettext
from urlparse import urlparse
import urllib
import gobject
import gtk
try:
    import simplejson as json
except ImportError:
    import json
import webbrowser
import tryton.rpc as rpc
from tryton.config import CONFIG, TRYTON_ICON, PIXMAPS_DIR, DATA_DIR, \
        get_config_dir
import tryton.common as common
from tryton.action import Action
from tryton.exceptions import TrytonServerError, TrytonError
from tryton.gui.window import Window
from tryton.gui.window.preference import Preference
from tryton.gui.window import Limit
from tryton.gui.window import FileActions
from tryton.gui.window import Email
from tryton.gui.window.dblogin import DBLogin
from tryton.gui.window.dbcreate import DBCreate
from tryton.gui.window.dbdumpdrop import DBBackupDrop
from tryton.gui.window.tips import Tips
from tryton.gui.window.about import About
from tryton.gui.window.shortcuts import Shortcuts
from tryton.gui.window.dbrestore import DBRestore
import re
import tryton.translate as translate
import tryton.plugins
import pango
import time
import threading
try:
    import gtk_osxapplication
except ImportError:
    gtk_osxapplication = None
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
        self.window.set_title('Tryton')
        self.window.set_icon(TRYTON_ICON)
        self.window.connect("destroy", Main.sig_quit)
        self.window.connect("delete_event", self.sig_close)
        self.window.connect('configure_event', self.sig_configure)
        self.window.connect('window_state_event', self.sig_window_state)

        self.accel_group = gtk.AccelGroup()
        self.window.add_accel_group(self.accel_group)

        self.macapp = None
        if gtk_osxapplication is not None:
            self.macapp = gtk_osxapplication.OSXApplication()
            self.macapp.connect("NSApplicationBlockTermination", self.sig_close)

        gtk.accel_map_add_entry('<tryton>/File/Connect', gtk.keysyms.O,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/File/Quit', gtk.keysyms.Q,
                gtk.gdk.CONTROL_MASK)
        if sys.platform != 'darwin':
            gtk.accel_map_add_entry('<tryton>/User/Menu Reload', gtk.keysyms.T,
                    gtk.gdk.MOD1_MASK)
        gtk.accel_map_add_entry('<tryton>/User/Menu Toggle', gtk.keysyms.T,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/User/Home', gtk.keysyms.H,
                gtk.gdk.CONTROL_MASK)

        gtk.accel_map_add_entry('<tryton>/Form/New', gtk.keysyms.N,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Save', gtk.keysyms.S,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Duplicate', gtk.keysyms.D,
                gtk.gdk.CONTROL_MASK|gtk.gdk.SHIFT_MASK)
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
        gtk.accel_map_add_entry('<tryton>/Form/Previous Tab', gtk.keysyms.Page_Up,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Next Tab', gtk.keysyms.Page_Down,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Goto', gtk.keysyms.G,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Reload', gtk.keysyms.R,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Actions', gtk.keysyms.E,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Report', gtk.keysyms.P,
                gtk.gdk.CONTROL_MASK)

        if hasattr(gtk, 'accel_map_load'):
            gtk.accel_map_load(os.path.join(get_config_dir(), 'accel.map'))

        self.tooltips = common.Tooltips()

        self.vbox = gtk.VBox()
        self.window.add(self.vbox)

        self.status_hbox = None
        self.menubar = None
        self.menuitem_user = None
        self.menuitem_plugins = None
        self.menuitem_shortcut = None

        if self.macapp is not None:
            self.macapp.ready()

        self.buttons = {}

        self.pane = gtk.HPaned()
        self.menu_screen = None
        self.vbox.pack_start(self.pane, True, True)

        self.notebook = gtk.Notebook()
        self.notebook.popup_enable()
        self.notebook.set_scrollable(True)
        self.notebook.connect_after('switch-page', self._sig_page_changt)

        self.pane.add2(self.notebook)

        self.set_statusbar()
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
        for setting, value in (
                ('gtk-button-images', True),
                ('gtk-can-change-accels',
                    CONFIG['client.can_change_accelerators']),
                ('gtk-keynav-cursor-only', True)):
            try:
                settings.set_property(setting, value)
            except TypeError:
                pass

        self.sig_statusbar_show()

        if os.name == 'nt' or sys.platform == 'darwin':
            # Disable actions, on win32 we use os.startfile
            # and on mac we use /usr/bin/open
            self.menuitem_actions.set_sensitive(False)

        # Adding a timer the check to requests
        gobject.timeout_add(5 * 60 * 1000, self.request_set)
        _MAIN.append(self)

    def set_menubar(self):
        if self.menubar:
            self.menubar.destroy()
        menubar = gtk.MenuBar()
        self.menubar = menubar
        self.vbox.pack_start(menubar, False, True)
        self.vbox.reorder_child(menubar, 0)

        menuitem_file = gtk.MenuItem(_('_File'))
        menubar.add(menuitem_file)

        menu_file = self._set_menu_file()
        menuitem_file.set_submenu(menu_file)
        menu_file.set_accel_group(self.accel_group)
        menu_file.set_accel_path('<tryton>/File')

        menuitem_user = gtk.MenuItem(_('_User'))
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

        menuitem_options = gtk.MenuItem(_('_Options'))
        menubar.add(menuitem_options)

        menu_options = self._set_menu_options()
        menuitem_options.set_submenu(menu_options)
        menu_options.set_accel_group(self.accel_group)
        menu_options.set_accel_path('<tryton>/Options')

        menuitem_plugins = gtk.MenuItem(_('_Plugins'))
        if self.menuitem_plugins:
            menuitem_plugins.set_sensitive(
                    self.menuitem_plugins.get_property('sensitive'))
        else:
            menuitem_plugins.set_sensitive(False)
        self.menuitem_plugins = menuitem_plugins
        menubar.add(menuitem_plugins)

        menu_plugins = self._set_menu_plugins()
        menuitem_plugins.set_submenu(menu_plugins)
        menu_plugins.set_accel_group(self.accel_group)
        menu_plugins.set_accel_path('<tryton>/Plugins')

        menuitem_shortcut = gtk.MenuItem(_('_Shortcuts'))
        if self.menuitem_shortcut:
            menuitem_shortcut.set_sensitive(
                self.menuitem_shortcut.get_property('sensitive'))
        else:
            menuitem_shortcut.set_sensitive(False)
        self.menuitem_shortcut = menuitem_shortcut
        menubar.add(menuitem_shortcut)
        menuitem_shortcut.set_accel_path('<tryton>/Shortcuts')
        def shortcut_activate(widget):
            if (not menuitem_shortcut.get_submenu()
                    or not menuitem_shortcut.get_submenu().get_children()):
                self.shortcut_set()
        menuitem_shortcut.connect('select', shortcut_activate)

        menuitem_help = gtk.MenuItem(_('_Help'))
        menubar.add(menuitem_help)

        menu_help = self._set_menu_help()
        menuitem_help.set_submenu(menu_help)
        menu_help.set_accel_group(self.accel_group)
        menu_help.set_accel_path('<tryton>/Help')

        if self.macapp is not None:
            self.menubar.set_no_show_all(True)
            self.macapp.set_menu_bar(self.menubar)
            self.macapp.insert_app_menu_item(self.aboutitem,0)
            menuitem_file.show_all()
            menuitem_user.show_all()
            menuitem_options.show_all()
            menuitem_plugins.show_all()
            menuitem_shortcut.show_all()
            menuitem_help.show_all()
        else:
            self.menubar.show_all()

    def set_statusbar(self):
        update = True
        if not self.status_hbox:
            self.status_hbox = gtk.HBox(spacing=2)
            update = False
            self.vbox.pack_end(self.status_hbox, False, True, padding=2)

        if not update:
            self.sb_username = gtk.Label()
            self.sb_username.set_alignment(0.0, 0.5)
            self.status_hbox.pack_start(self.sb_username, True, True, padding=5)

            self.sb_requests = gtk.Label()
            self.sb_requests.set_alignment(0.5, 0.5)
            self.status_hbox.pack_start(self.sb_requests, True, True,
                    padding=5)

            self.sb_servername = gtk.Label()
            self.sb_servername.set_alignment(1.0, 0.5)
            self.status_hbox.pack_start(self.sb_servername, True, True,
                    padding=5)

            self.secure_img = gtk.Image()
            self.secure_img.set_from_stock('tryton-lock', gtk.ICON_SIZE_MENU)
            self.status_hbox.pack_start(self.secure_img, False, True, padding=2)

            self.status_hbox.show_all()

    def _set_menu_file(self):
        menu_file = gtk.Menu()

        imagemenuitem_connect = gtk.ImageMenuItem(_('_Connect...'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-connect', gtk.ICON_SIZE_MENU)
        imagemenuitem_connect.set_image(image)
        imagemenuitem_connect.connect('activate', self.sig_login)
        imagemenuitem_connect.set_accel_path('<tryton>/File/Connect')
        menu_file.add(imagemenuitem_connect)

        imagemenuitem_disconnect = gtk.ImageMenuItem(_('_Disconnect'))
        image = gtk.Image()
        image.set_from_stock('tryton-disconnect', gtk.ICON_SIZE_MENU)
        imagemenuitem_disconnect.set_image(image)
        imagemenuitem_disconnect.connect('activate', self.sig_logout)
        imagemenuitem_disconnect.set_accel_path('<tryton>/File/Disconnect')
        menu_file.add(imagemenuitem_disconnect)

        menu_file.add(gtk.SeparatorMenuItem())

        imagemenuitem_database = gtk.ImageMenuItem(_('Data_base'))
        image = gtk.Image()
        image.set_from_stock('tryton-system-file-manager', gtk.ICON_SIZE_MENU)
        imagemenuitem_database.set_image(image)
        menu_file.add(imagemenuitem_database)

        menu_database = gtk.Menu()
        menu_database.set_accel_group(self.accel_group)
        menu_database.set_accel_path('<tryton>/File/Database')
        imagemenuitem_database.set_submenu(menu_database)

        imagemenuitem_db_new = gtk.ImageMenuItem(_('_New Database...'))
        image = gtk.Image()
        image.set_from_stock('tryton-folder-new', gtk.ICON_SIZE_MENU)
        imagemenuitem_db_new.set_image(image)
        imagemenuitem_db_new.connect('activate', self.sig_db_new)
        imagemenuitem_db_new.set_accel_path('<tryton>/File/Database/New Database')
        menu_database.add(imagemenuitem_db_new)

        imagemenuitem_db_restore = gtk.ImageMenuItem(_('_Restore Database...'))
        image = gtk.Image()
        image.set_from_stock('tryton-folder-saved-search', gtk.ICON_SIZE_MENU)
        imagemenuitem_db_restore.set_image(image)
        imagemenuitem_db_restore.connect('activate', self.sig_db_restore)
        imagemenuitem_db_restore.set_accel_path('<tryton>/File/Database/Restore Database')
        menu_database.add(imagemenuitem_db_restore)

        imagemenuitem_db_dump = gtk.ImageMenuItem(_('_Backup Database...'))
        image = gtk.Image()
        image.set_from_stock('tryton-save-as', gtk.ICON_SIZE_MENU)
        imagemenuitem_db_dump.set_image(image)
        imagemenuitem_db_dump.connect('activate', self.sig_db_dump)
        imagemenuitem_db_dump.set_accel_path('<tryton>/File/Database/Backup Database')
        menu_database.add(imagemenuitem_db_dump)

        imagemenuitem_db_drop = gtk.ImageMenuItem(_('Dro_p Database...'))
        image = gtk.Image()
        image.set_from_stock('tryton-delete', gtk.ICON_SIZE_MENU)
        imagemenuitem_db_drop.set_image(image)
        imagemenuitem_db_drop.connect('activate', self.sig_db_drop)
        imagemenuitem_db_drop.set_accel_path('<tryton>/File/Database/Drop Database')
        menu_database.add(imagemenuitem_db_drop)


        imagemenuitem_close = gtk.ImageMenuItem(_('_Quit...'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-log-out', gtk.ICON_SIZE_MENU)
        imagemenuitem_close.set_image(image)
        imagemenuitem_close.connect('activate', self.sig_close)
        imagemenuitem_close.set_accel_path('<tryton>/File/Quit')
        if self.macapp is None:
            menu_file.add(gtk.SeparatorMenuItem())
            menu_file.add(imagemenuitem_close)
        return menu_file

    def _set_menu_user(self):
        menu_user = gtk.Menu()

        imagemenuitem_preference = gtk.ImageMenuItem(_('_Preferences...'))
        image = gtk.Image()
        image.set_from_stock('tryton-preferences-system-session',
                gtk.ICON_SIZE_MENU)
        imagemenuitem_preference.set_image(image)
        imagemenuitem_preference.connect('activate', self.sig_user_preferences)
        imagemenuitem_preference.set_accel_path('<tryton>/User/Preferences')
        menu_user.add(imagemenuitem_preference)

        menu_user.add(gtk.SeparatorMenuItem())

        imagemenuitem_menu = gtk.ImageMenuItem(_('_Menu Reload'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-start-here', gtk.ICON_SIZE_MENU)
        imagemenuitem_menu.set_image(image)
        imagemenuitem_menu.connect('activate', self.sig_win_menu)
        imagemenuitem_menu.set_accel_path('<tryton>/User/Menu Reload')
        menu_user.add(imagemenuitem_menu)

        imagemenuitem_menu_toggle = gtk.ImageMenuItem(_('_Menu Toggle'),
                self.accel_group)
        imagemenuitem_menu_toggle.connect('activate', lambda *a: self.menu_toggle())
        imagemenuitem_menu_toggle.set_accel_path('<tryton>/User/Menu Toggle')
        menu_user.add(imagemenuitem_menu_toggle)


        imagemenuitem_home = gtk.ImageMenuItem(_('_Home'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-go-home', gtk.ICON_SIZE_MENU)
        imagemenuitem_home.set_image(image)
        imagemenuitem_home.connect('activate', self.sig_home_new)
        imagemenuitem_home.set_accel_path('<tryton>/User/Home')
        menu_user.add(imagemenuitem_home)

        menu_user.add(gtk.SeparatorMenuItem())

        imagemenuitem_send_request = gtk.ImageMenuItem(_('_Send a Request'))
        image = gtk.Image()
        image.set_from_stock('tryton-mail-message-new', gtk.ICON_SIZE_MENU)
        imagemenuitem_send_request.set_image(image)
        imagemenuitem_send_request.connect('activate', self.sig_request_new)
        imagemenuitem_send_request.set_accel_path('<tryton>/User/Send a Request')
        menu_user.add(imagemenuitem_send_request)

        imagemenuitem_open_request = gtk.ImageMenuItem(_('_Read my Requests'))
        image = gtk.Image()
        image.set_from_stock('tryton-mail-message', gtk.ICON_SIZE_MENU)
        imagemenuitem_open_request.set_image(image)
        imagemenuitem_open_request.connect('activate', self.sig_request_open)
        imagemenuitem_open_request.set_accel_path('<tryton>/User/Read my Requests')
        menu_user.add(imagemenuitem_open_request)
        return menu_user

    def _set_menu_options(self):
        menu_options = gtk.Menu()

        menuitem_toolbar = gtk.MenuItem(_('_Toolbar'))
        menu_options.add(menuitem_toolbar)

        menu_toolbar = gtk.Menu()
        menu_toolbar.set_accel_group(self.accel_group)
        menu_toolbar.set_accel_path('<tryton>/Options/Toolbar')
        menuitem_toolbar.set_submenu(menu_toolbar)

        radiomenuitem_default = gtk.RadioMenuItem(label=_('_Default'))
        radiomenuitem_default.connect('activate',
                lambda x: self.sig_toolbar('default'))
        radiomenuitem_default.set_accel_path('<tryton>/Options/Toolbar/Default')
        menu_toolbar.add(radiomenuitem_default)
        if (CONFIG['client.toolbar'] or 'both') == 'default':
            radiomenuitem_default.set_active(True)

        radiomenuitem_both = gtk.RadioMenuItem(group=radiomenuitem_default,
                label=_('_Text and Icons'))
        radiomenuitem_both.connect('activate',
                lambda x: self.sig_toolbar('both'))
        radiomenuitem_both.set_accel_path(
                '<tryton>/Options/Toolbar/Text and Icons')
        menu_toolbar.add(radiomenuitem_both)
        if (CONFIG['client.toolbar'] or 'both') == 'both':
            radiomenuitem_both.set_active(True)

        radiomenuitem_icons = gtk.RadioMenuItem(group=radiomenuitem_default,
                label=_('_Icons'))
        radiomenuitem_icons.connect('activate',
                lambda x: self.sig_toolbar('icons'))
        radiomenuitem_icons.set_accel_path('<tryton>/Options/Toolbar/Icons')
        menu_toolbar.add(radiomenuitem_icons)
        if (CONFIG['client.toolbar'] or 'both') == 'icons':
            radiomenuitem_icons.set_active(True)

        radiomenuitem_text = gtk.RadioMenuItem(group=radiomenuitem_default,
                label=_('_Text'))
        radiomenuitem_text.connect('activate',
                lambda x: self.sig_toolbar('text'))
        radiomenuitem_text.set_accel_path('<tryton>/Options/Toolbar/Text')
        menu_toolbar.add(radiomenuitem_text)
        if (CONFIG['client.toolbar'] or 'both') == 'text':
            radiomenuitem_text.set_active(True)

        # Menubar accelerators
        menuitem_menubar = gtk.MenuItem(_('_Menubar'))
        menu_options.add(menuitem_menubar)

        menu_menubar = gtk.Menu()
        menu_menubar.set_accel_group(self.accel_group)
        menu_menubar.set_accel_path('<tryton>/Options/Menubar')
        menuitem_menubar.set_submenu(menu_menubar)

        checkmenuitem_accel = gtk.CheckMenuItem(_('Change Accelerators'))
        checkmenuitem_accel.connect('activate',
                lambda menuitem: self.sig_accel_change(menuitem.get_active()))
        checkmenuitem_accel.set_accel_path('<tryton>/Options/Menubar/Accel')
        menu_menubar.add(checkmenuitem_accel)
        if CONFIG['client.can_change_accelerators']:
            checkmenuitem_accel.set_active(True)

        menuitem_mode = gtk.MenuItem(_('_Mode'))
        menu_options.add(menuitem_mode)

        menu_mode = gtk.Menu()
        menu_mode.set_accel_group(self.accel_group)
        menu_mode.set_accel_path('<tryton>/Options/Mode')
        menuitem_mode.set_submenu(menu_mode)

        radiomenuitem_normal = gtk.RadioMenuItem(label=_('_Normal'))
        self.radiomenuitem_normal = radiomenuitem_normal
        radiomenuitem_normal.connect('activate',
                lambda x: self.sig_mode_change(False))
        radiomenuitem_normal.set_accel_path('<tryton>/Options/Mode/Normal')
        menu_mode.add(radiomenuitem_normal)

        radiomenuitem_pda = gtk.RadioMenuItem(group=radiomenuitem_normal,
                label=_('_PDA'))
        self.radiomenuitem_pda = radiomenuitem_pda
        radiomenuitem_pda.connect('activate',
                lambda x: self.sig_mode_change(True))
        radiomenuitem_pda.set_accel_path('<tryton>/Options/Mode/PDA')
        menu_mode.add(radiomenuitem_pda)

        menuitem_form = gtk.MenuItem(_('_Form'))
        menu_options.add(menuitem_form)

        menu_form = gtk.Menu()
        menu_form.set_accel_group(self.accel_group)
        menu_form.set_accel_path('<tryton>/Options/Form')
        menuitem_form.set_submenu(menu_form)

        checkmenuitem_statusbar = gtk.CheckMenuItem(_('Statusbar'))
        checkmenuitem_statusbar.connect('activate',
                lambda menuitem: self.sig_statusbar_change(menuitem.get_active()))
        checkmenuitem_statusbar.set_accel_path('<tryton>/Options/Form/Statusbar')
        menu_form.add(checkmenuitem_statusbar)
        if CONFIG['form.statusbar']:
            checkmenuitem_statusbar.set_active(True)

        checkmenuitem_save_width_height = gtk.CheckMenuItem(_('Save Width/Height'))
        checkmenuitem_save_width_height.connect('activate',
                lambda menuitem: CONFIG.__setitem__('client.save_width_height',
                    menuitem.get_active()))
        checkmenuitem_save_width_height.set_accel_path(
                '<tryton>/Options/Form/Save Width Height')
        menu_form.add(checkmenuitem_save_width_height)
        if CONFIG['client.save_width_height']:
            checkmenuitem_save_width_height.set_active(True)

        checkmenuitem_save_tree_state = gtk.CheckMenuItem(
            _('Save Tree Expanded State'))
        checkmenuitem_save_tree_state.connect('activate',
            lambda menuitem: CONFIG.__setitem__(
                'client.save_tree_expanded_state',
                menuitem.get_active()))
        checkmenuitem_save_tree_state.set_accel_path(
            '<tryton>/Options/Form/Save Tree Expanded State')
        menu_form.add(checkmenuitem_save_tree_state)
        if CONFIG['client.save_tree_expanded_state']:
            checkmenuitem_save_tree_state.set_active(True)

        if gtkspell:
            checkmenuitem_spellcheck = gtk.CheckMenuItem(_('Spell Checking'))
            checkmenuitem_spellcheck.connect('activate',
                    lambda menuitem: CONFIG.__setitem__('client.spellcheck',
                        menuitem.get_active()))
            checkmenuitem_spellcheck.set_accel_path(
                    '<tryton>/Options/Form/Spell Checking')
            menu_form.add(checkmenuitem_spellcheck)
            if CONFIG['client.spellcheck']:
                checkmenuitem_spellcheck.set_active(True)

        menuitem_tab = gtk.MenuItem(_('Tabs Position'))
        menu_form.add(menuitem_tab)

        menu_tab = gtk.Menu()
        menu_tab.set_accel_group(self.accel_group)
        menu_tab.set_accel_path('<tryton>/Options/Tabs Position')
        menuitem_tab.set_submenu(menu_tab)

        radiomenuitem_top = gtk.RadioMenuItem(label=_('Top'))
        radiomenuitem_top.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab', 'top'))
        radiomenuitem_top.set_accel_path('<tryton>/Options/Tabs Position/Top')
        menu_tab.add(radiomenuitem_top)
        if (CONFIG['client.form_tab'] or 'left') == 'top':
            radiomenuitem_top.set_active(True)

        radiomenuitem_left = gtk.RadioMenuItem(group=radiomenuitem_top,
                label=_('Left'))
        radiomenuitem_left.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab', 'left'))
        radiomenuitem_left.set_accel_path('<tryton>/Options/Tabs Position/Left')
        menu_tab.add(radiomenuitem_left)
        if (CONFIG['client.form_tab'] or 'left') == 'left':
            radiomenuitem_left.set_active(True)

        radiomenuitem_right = gtk.RadioMenuItem(group=radiomenuitem_top,
                label=_('Right'))
        radiomenuitem_right.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab', 'right'))
        radiomenuitem_right.set_accel_path('<tryton>/Options/Tabs Position/Right')
        menu_tab.add(radiomenuitem_right)
        if (CONFIG['client.form_tab'] or 'left') == 'right':
            radiomenuitem_right.set_active(True)

        radiomenuitem_bottom = gtk.RadioMenuItem(group=radiomenuitem_top,
                label=_('Bottom'))
        radiomenuitem_bottom.connect('activate',
                lambda x: CONFIG.__setitem__('client.form_tab', 'bottom'))
        radiomenuitem_bottom.set_accel_path('<tryton>/Options/Tabs Position/Bottom')
        menu_tab.add(radiomenuitem_bottom)
        if (CONFIG['client.form_tab'] or 'left') == 'bottom':
            radiomenuitem_bottom.set_active(True)

        menuitem_limit = gtk.MenuItem(_('Search Limit...'))
        self.menuitem_limit = menuitem_limit
        menuitem_limit.connect('activate', self.sig_limit)
        menuitem_limit.set_accel_path('<tryton>/Options/Search Limit')
        menu_options.add(menuitem_limit)

        menuitem_actions = gtk.MenuItem(_('File _Actions...'))
        self.menuitem_actions = menuitem_actions
        menuitem_actions.connect('activate', self.sig_file_actions)
        menuitem_actions.set_accel_path('<tryton>/Options/File Actions')
        menu_options.add(menuitem_actions)

        menuitem_email = gtk.MenuItem(_('_Email...'))
        self.menuitem_email = menuitem_email
        menuitem_email.connect('activate', self.sig_email)
        menuitem_email.set_accel_path('<tryton>/Options/Email')
        menu_options.add(menuitem_email)

        menu_options.add(gtk.SeparatorMenuItem())

        imagemenuitem_opt_save = gtk.ImageMenuItem(_('_Save Options'))
        image = gtk.Image()
        image.set_from_stock('tryton-save', gtk.ICON_SIZE_MENU)
        imagemenuitem_opt_save.set_image(image)
        imagemenuitem_opt_save.connect('activate', lambda x: CONFIG.save())
        imagemenuitem_opt_save.set_accel_path('<tryton>/Options/Save Options')
        menu_options.add(imagemenuitem_opt_save)
        return menu_options

    def _set_menu_plugins(self):
        menu_plugins = gtk.Menu()

        imagemenuitem_plugin_execute = gtk.ImageMenuItem(_('_Execute a Plugin'))
        image = gtk.Image()
        image.set_from_stock('tryton-executable', gtk.ICON_SIZE_MENU)
        imagemenuitem_plugin_execute.set_image(image)
        imagemenuitem_plugin_execute.connect('activate', self.sig_plugin_execute)
        imagemenuitem_plugin_execute.set_accel_path(
                '<tryton>/Plugins/Execute a Plugin')
        menu_plugins.add(imagemenuitem_plugin_execute)
        return menu_plugins

    def _set_menu_help(self):
        menu_help = gtk.Menu()

        imagemenuitem_tips = gtk.ImageMenuItem(_('_Tips...'))
        image = gtk.Image()
        image.set_from_stock('tryton-information', gtk.ICON_SIZE_MENU)
        imagemenuitem_tips.set_image(image)
        imagemenuitem_tips.connect('activate', self.sig_tips)
        imagemenuitem_tips.set_accel_path('<tryton>/Help/Tips')
        menu_help.add(imagemenuitem_tips)

        imagemenuitem_shortcuts = gtk.ImageMenuItem(_('_Keyboard Shortcuts...'))
        image = gtk.Image()
        image.set_from_stock('tryton-help', gtk.ICON_SIZE_MENU)
        imagemenuitem_shortcuts.set_image(image)
        imagemenuitem_shortcuts.connect('activate', self.sig_shortcuts)
        imagemenuitem_shortcuts.set_accel_path('<tryton>/Help/Keyboard Shortcuts')
        menu_help.add(imagemenuitem_shortcuts)


        imagemenuitem_about = gtk.ImageMenuItem(_('_About...'))
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

    def shortcut_set(self):
        def _action_shortcut(widget, action):
            Action.exec_keyword('tree_open', {
                'model': 'ir.ui.menu',
                'id': action,
                'ids': [action],
                })
            self.shortcut_unset()

        def _add_shortcut(widget):
            ids = self.menu_screen.sel_ids_get()
            if not ids:
                return
            try:
                values = rpc.execute('model', self.menu_screen.model_name,
                        'read', ids, ['rec_name'], rpc.CONTEXT)
            except TrytonServerError, exception:
                common.process_exception(exception)
                return
            try:
                for value in values:
                    rpc.execute('model', 'ir.ui.view_sc', 'create', {
                        'name': value['rec_name'],
                        'res_id': value['id'],
                        'user_id': rpc._USER,
                        'resource': self.menu_screen.model_name,
                        }, rpc.CONTEXT)
            except TrytonServerError, exception:
                common.process_exception(exception)
            self.shortcut_unset()

        def _manage_shortcut(widget):
            Window.create(False, 'ir.ui.view_sc', False,
                    domain=[('user_id', '=', rpc._USER)],
                    mode=['tree', 'form'])
            self.shortcut_unset()

        user = rpc._USER
        try:
            shortcuts = rpc.execute('model', 'ir.ui.view_sc', 'get_sc',
                    user, 'ir.ui.menu', rpc.CONTEXT)
        except TrytonServerError:
            shortcuts = []
        menu = self.menuitem_shortcut.get_submenu()
        if not menu:
            menu = gtk.Menu()
        for shortcut in shortcuts:
            menuitem = gtk.MenuItem(shortcut['name'])
            menuitem.connect('activate', _action_shortcut, shortcut['res_id'])
            menu.add(menuitem)
        menu.add(gtk.MenuItem())
        add_shortcut = gtk.MenuItem(_('Add Shortcut'))
        add_shortcut.connect('activate', _add_shortcut)
        menu.add(add_shortcut)
        manage_shortcut = gtk.MenuItem(_('Manage Shortcut'))
        manage_shortcut.connect('activate', _manage_shortcut)
        menu.add(manage_shortcut)
        menu.show_all()
        self.menuitem_shortcut.set_submenu(menu)

    def shortcut_unset(self):
        self.menuitem_shortcut.remove_submenu()
        # Set a submenu to get keyboard shortcut working
        self.menuitem_shortcut.set_submenu(gtk.Menu())

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

    def sig_statusbar_change(self, value):
        CONFIG['form.statusbar'] = value
        return self.sig_statusbar_show()

    def sig_statusbar_show(self):
        statusbar = CONFIG['form.statusbar']
        if statusbar:
            self.status_hbox.show()
        else:
            self.status_hbox.hide()

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

    @staticmethod
    def sig_form_tab(option):
        CONFIG['client.form_tab'] = option

    def sig_limit(self, widget):
        Limit().run()

    def sig_file_actions(self, widget):
        FileActions().run()

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

    def sig_user_preferences(self, widget):
        if not self.close_pages():
            return False
        win = Preference(rpc._USER)
        if win.run():
            rpc.context_reload()
            prefs = rpc.execute('model', 'res.user',
                    'get_preferences', False, rpc.CONTEXT)
            if prefs and 'language_direction' in prefs:
                translate.set_language_direction(prefs['language_direction'])
                CONFIG['client.language_direction'] = prefs['language_direction']
            self.sb_username.set_text(prefs.get('status_bar', ''))
            if prefs and 'language' in prefs:
                translate.setlang(prefs['language'], prefs.get('locale'))
                if CONFIG['client.lang'] != prefs['language']:
                    self.set_menubar()
                    self.shortcut_unset()
                    self.set_statusbar()
                    self.request_set()
                    self.sig_win_menu()
                CONFIG['client.lang'] = prefs['language']
            CONFIG.save()
        self.sig_win_menu()
        return True

    def sig_win_close(self, widget):
        self._sig_remove_book(widget,
                self.notebook.get_nth_page(self.notebook.get_current_page()))

    def sig_request_new(self, widget):
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx['active_test'] = False
        return Window.create(None, 'res.request', False, [ ],
                mode=['form', 'tree'], context=ctx)

    def sig_request_open(self, widget):
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx['active_test'] = False
        try:
            ids1, ids2 = self.request_set(True)
        except TrytonServerError, exception:
            if common.process_exception(exception):
                ids1, ids2 = self.request_set(True)
            else:
                raise
        ids = ids1 + ids2
        return Window.create(False, 'res.request', ids, [ ],
                mode=['tree', 'form'], context=ctx)

    def request_set(self, exception=False):
        try:
            if not rpc._USER:
                return
            if not exception:
                res = rpc.execute('model', 'res.request', 'request_get',
                        rpc.CONTEXT)
                if not res:
                    return ([], [])
                ids, ids2 = res
            else:
                ids, ids2 = rpc.execute('model', 'res.request', 'request_get',
                        rpc.CONTEXT)
            label = _('Requests (%s/%s)') % (len(ids), len(ids2))
            message = _('Waiting requests: %s received - %s sent') % (len(ids),
                        len(ids2))
            self.sb_requests.set_text(message)
            return (ids, ids2)
        except (TrytonServerError, socket.error):
            if exception:
                raise
            return ([], [])

    def sig_login(self, widget=None, res=None):
        if not self.sig_logout(widget, disconnect=False):
            return
        if not res:
            try:
                res = DBLogin().run()
            except TrytonError, exception:
                if exception.faultCode == 'QueryCanceled':
                    return False
            except TrytonServerError, exception:
                common.process_exception(exception)
                return
        try:
            log_response = rpc.login(*res)
        except TrytonServerError, exception:
            common.process_exception(exception)
            return
        rpc.context_reload()
        self.refresh_ssl()
        if log_response > 0:
            try:
                prefs = rpc.execute('model', 'res.user', 'get_preferences',
                        False, rpc.CONTEXT)
            except TrytonServerError:
                prefs = None
            common.ICONFACTORY.load_icons()
            if prefs and 'language_direction' in prefs:
                translate.set_language_direction(prefs['language_direction'])
                CONFIG['client.language_direction'] = prefs['language_direction']
            menu_id = self.sig_win_menu(quiet=False, prefs=prefs)
            if menu_id:
                self.sig_home_new(quiet=True, except_id=menu_id, prefs=prefs)
            self.request_set()
            if prefs and 'language' in prefs:
                translate.setlang(prefs['language'], prefs.get('locale'))
                if CONFIG['client.lang'] != prefs['language']:
                    self.set_menubar()
                    self.shortcut_unset()
                    self.set_statusbar()
                    self.request_set()
                CONFIG['client.lang'] = prefs['language']
            CONFIG.save()
        elif log_response == -1:
            common.message(_('Connection error!\n' \
                    'Unable to connect to the server!'))
        elif log_response == -2:
            common.message(_('Connection error!\n' \
                    'Bad username or password!'))
            return self.sig_login()
        self.shortcut_unset()
        self.menuitem_shortcut.set_sensitive(True)
        self.menuitem_user.set_sensitive(True)
        self.menuitem_plugins.set_sensitive(True)
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
        if self.pane.get_child1():
            self.pane.remove(self.pane.get_child1())
            if self.pane.get_position():
                CONFIG['menu.pane'] = self.pane.get_position()
        if self.menu_screen:
            self.menu_screen.destroy()
            self.menu_screen = None
        return True

    def sig_logout(self, widget=None, disconnect=True):
        if not self.close_pages():
            return False
        self.sb_username.set_text('')
        self.sb_servername.set_text('')
        self.sb_requests.set_text('')
        self.shortcut_unset()
        self.menuitem_shortcut.set_sensitive(False)
        self.menuitem_user.set_sensitive(False)
        self.menuitem_plugins.set_sensitive(False)
        if disconnect:
            rpc.logout()
        self.refresh_ssl()
        return True

    def refresh_ssl(self):
        if rpc.CONNECTION is not None and rpc.CONNECTION.ssl:
            self.tooltips.set_tip(self.secure_img, _('SSL connection'))
            self.secure_img.show()
        else:
            self.secure_img.hide()
            self.tooltips.set_tip(self.secure_img, '')

    def sig_tips(self, *args):
        Tips()

    def sig_about(self, widget):
        About()

    def sig_shortcuts(self, widget):
        Shortcuts().run()

    def menu_toggle(self, nohide=False):
        has_focus = True
        if (self.menu_screen
                and self.menu_screen.current_view.view_type == 'tree'):
            try:
                has_focus = self.menu_screen.current_view.widget_tree.has_focus()
            except AttributeError:
                has_focus = (self.menu_screen.current_view.widget_tree.flags()
                        & gtk.HAS_FOCUS)
        if self.pane.get_position() and has_focus:
            CONFIG['menu.pane'] = self.pane.get_position()
            if not nohide:
                self.pane.set_position(0)
                self.notebook.grab_focus()
        else:
            self.pane.set_position(int(CONFIG['menu.pane']))
            if self.menu_screen:
                self.menu_screen.current_view.set_cursor()

    def sig_win_menu(self, widget=None, quiet=True, prefs=None):
        if self.pane.get_child1():
            self.pane.remove(self.pane.get_child1())
            if self.pane.get_position():
                CONFIG['menu.pane'] = self.pane.get_position()
        self.menu_screen = None
        self.menu_toggle(nohide=True)
        res = self.sig_win_new(widget, menu_type='menu', quiet=quiet,
                prefs=prefs)
        return res

    def sig_win_new(self, widget=None, menu_type='menu', quiet=True,
            except_id=False, prefs=None):
        if not prefs:
            args = ('model', 'res.user', 'get_preferences', False, rpc.CONTEXT)
            try:
                prefs = rpc.execute(*args)
            except TrytonServerError, exception:
                prefs = common.process_exception(exception, *args)
                if not prefs:
                    return False
        self.sb_username.set_text(prefs.get('status_bar', ''))
        self.sb_servername.set_text('%s@%s:%d/%s' % (rpc._USERNAME,
            rpc._HOST, rpc._PORT, rpc._DATABASE))
        if not prefs[menu_type]:
            if quiet:
                return False
            common.warning(_('You can not log into the system!\n' \
                    'Verify if you have a menu defined on your user.'),
                    'Access Denied!')
            rpc.logout()
            self.refresh_ssl()
            return False
        act_id = prefs[menu_type]
        if except_id and act_id == except_id:
            return act_id
        Action.execute(act_id, {})
        return act_id

    def sig_home_new(self, widget=None, quiet=True, except_id=False,
            prefs=None):
        return self.sig_win_new(widget, menu_type='action', quiet=quiet,
                except_id=except_id, prefs=prefs)

    def sig_plugin_execute(self, widget):
        page = self.notebook.get_current_page()
        if page == -1:
            return
        datas = {
                'model': self.pages[page].model,
                'ids': self.pages[page].ids_get(),
                'id': self.pages[page].id_get(),
                }
        tryton.plugins.execute(datas)

    @classmethod
    def sig_quit(cls, widget=None):
        rpc.logout()
        CONFIG['client.default_width'] = Main.get_main()._width
        CONFIG['client.default_height'] = Main.get_main()._height
        CONFIG.save()
        if hasattr(gtk, 'accel_map_save'):
            gtk.accel_map_save(os.path.join(get_config_dir(), 'accel.map'))

        cls.tryton_client.quit_mainloop()

    def sig_close(self, widget, event=None):
        if not self.sig_logout(widget):
            return True
        Main.sig_quit()

    def sig_configure(self, widget, event):
        if hasattr(event, 'width') \
                and hasattr(event, 'height'):
            self._width =  int(event.width)
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
                    page_num = self.notebook.page_num(other_page.widget)
                    other_page.widget.props.visible = True
                    self.notebook.set_current_page(page_num)
                    return
        if not self.pane.get_child1():
            screen = page.screen
            screen.screen_container.alternate_view = True
            screen.switch_view(view_type=screen.current_view.view_type)
            self.pane.pack1(screen.screen_container.alternate_viewport)
            self.menu_screen = screen
            screen.display(set_cursor=True)
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
        icon_w, icon_h = gtk.icon_size_lookup(gtk.ICON_SIZE_SMALL_TOOLBAR)
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
        button.unset_flags(gtk.CAN_FOCUS)
        button.add(img)
        self.tooltips.set_tip(button, _('Close Tab'))
        button.connect('clicked', self._sig_remove_book, page.widget)
        hbox.pack_start(button, expand=False, fill=False)

        def on_style_set(widget, prevstyle):
            x, y = gtk.icon_size_lookup_for_settings(button.get_settings(),
                    gtk.ICON_SIZE_MENU)
            button.set_size_request(x, y)
        hbox.connect("style-set", on_style_set)

        hbox.show_all()
        hbox.set_size_request(TAB_SIZE, -1)
        label_menu = gtk.Label(page.name)
        label_menu.set_alignment(0.0, 0.5)
        self.notebook.insert_page_menu(page.widget, hbox, label_menu, page_id)
        if hasattr(self.notebook, 'set_tab_reorderable'):
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
            self.menu_screen.current_view.set_cursor()
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
        for dialog in current_form.dialogs:
            dialog.show()

    def sig_db_new(self, widget):
        if not self.sig_logout(widget):
            return False
        dia = DBCreate(CONFIG['login.server'], int(CONFIG['login.port']),
            sig_login=self.sig_login)
        res = dia.run()
        if res:
            CONFIG.save()
        return res

    def sig_db_drop(self, widget=None):
        if not self.sig_logout(widget):
            return False
        url, dbname, passwd = DBBackupDrop(function='drop').run()
        if not dbname:
            rpc.logout()
            Main.get_main().refresh_ssl()
            return

        host, port = url.rsplit(':', 1)
        sure = common.sur_3b(_("You are going to delete a Tryton " \
                "database.\nAre you really sure to proceed?"))
        if sure == "ko" or sure == "cancel":
            return
        rpcprogress = common.RPCProgress('db_exec', (host, int(port), 'drop',
            dbname, passwd))
        try:
            rpcprogress.run()
        except TrytonServerError, exception:
            self.refresh_ssl()
            if exception.faultCode == "AccessDenied":
                common.warning(_("Wrong Tryton Server Password" \
                        "\nPlease try again."),
                        _('Access denied!'))
                self.sig_db_drop()
            else:
                common.warning(_('Database drop failed with error message:\n')
                    + str(exception.faultCode), _('Database drop failed!'))
            return
        self.refresh_ssl()
        common.message(_("Database dropped successfully!"))

    def sig_db_restore(self, widget):
        if not self.sig_logout(widget):
            return False
        filename = common.file_selection(_('Open Backup File to Restore...'),
            preview=False)
        if not filename:
            return
        dialog = DBRestore(filename=filename)
        url, dbname, passwd, update = dialog.run()
        if dbname:
            with open(filename, 'rb') as file_p:
                data = file_p.read()
            host, port = url.rsplit(':' , 1)
            rpcprogress = common.RPCProgress('db_exec', (host, int(port),
                'restore', dbname, passwd, buffer(data), update))
            try:
                res = rpcprogress.run()
            except TrytonServerError, exception:
                self.refresh_ssl()
                if exception.faultCode == \
                        "Couldn't restore database with password":
                    common.warning(_("It is not possible to restore a " \
                            "password protected database.\n" \
                            "Backup and restore needed to be proceed " \
                            "manual."),
                            _('Database is password protected!'))
                elif exception.faultCode == "AccessDenied":
                    common.warning(_("Wrong Tryton Server Password.\n" \
                            "Please try again."),
                            _('Access denied!'))
                    self.sig_db_restore()
                else:
                    common.warning(_('Database restore failed with ' \
                            'error message:\n') + str(exception.faultCode), \
                            _('Database restore failed!'))
                return
            self.refresh_ssl()
            if res:
                common.message(_("Database restored successfully!"))
            else:
                common.message(_('Database restore failed!'))

    def sig_db_dump(self, widget):
        if not self.sig_logout(widget):
            return False
        dialog = DBBackupDrop(function='backup')
        url, dbname, passwd = dialog.run()

        if not (dbname and url and passwd):
            rpc.logout()
            Main.get_main().refresh_ssl()
            return

        host, port = url.rsplit(':', 1)
        rpcprogress = common.RPCProgress('db_exec', (host, int(port), 'dump',
            dbname, passwd))
        try:
            dump = rpcprogress.run()
        except TrytonServerError, exception:
            if exception.faultCode == "Couldn't dump database with password":
                common.warning(_("It is not possible to dump a password " \
                        "protected Database.\nBackup and restore " \
                        "needed to be proceed manual."),
                        _('Database is password protected!'))
            elif exception.faultCode == "AccessDenied":
                common.warning(_("Wrong Tryton Server Password.\n" \
                        "Please try again."),
                        _('Access denied!'))
                self.sig_db_dump()
            else:
                common.warning(_('Database dump failed with ' \
                        'error message:\n') + str(exception.faultCode),
                        _('Database dump failed!'))
            rpc.logout()
            Main.get_main().refresh_ssl()
            return

        self.refresh_ssl()

        filename = common.file_selection(_('Save As...'),
            action=gtk.FILE_CHOOSER_ACTION_SAVE, preview=False,
            filename=dbname + '-' + time.strftime('%Y%m%d%H%M') + '.dump')

        if filename:
            with open(filename, 'wb') as file_:
                file_.write(dump)
            common.message(_("Database backuped successfully!"))
        else:
            rpc.logout()
            Main.get_main().refresh_ssl()

    def _open_url(self, url):
        url = urllib.unquote(url)
        urlp = urlparse(url)
        if not urlp.scheme == 'tryton':
            return
        urlp = urlparse('http' + url[6:])
        hostname, port = (urlp.netloc.split(':', 1)
                + [CONFIG.defaults['login.port']])[:2]
        database, path = (urlp.path[1:].split('/', 1) + [None])[:2]
        if (not path or
                hostname != rpc._HOST or
                int(port) != rpc._PORT or
                database != rpc._DATABASE):
            return
        type_, path = (path.split('/', 1) + [''])[:2]
        params = {}
        if urlp.params:
            try:
                params = dict(param.split('=', 1)
                        for param in urlp.params.split('&'))
            except ValueError:
                return

        def open_model(path):
            model, path = (path.split('/', 1) + [''])[:2]
            if not model:
                return
            res_id = False
            mode = None
            try:
                view_ids = json.loads(params.get('views', 'false'))
                limit = json.loads(params.get('limit', 'null'))
                auto_refresh = json.loads(params.get('auto_refresh', 'false'))
                name = json.loads(params.get('window_name', 'false'))
                search_value = json.loads(params.get('search_value', '{}'))
                domain = json.loads(params.get('domain', '[]'))
                context = json.loads(params.get('context', '{}'))
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
                    auto_refresh=auto_refresh, search_value=search_value)
            except Exception:
                # Prevent crashing the client
                return

        def open_wizard(wizard):
            if not wizard:
                return
            try:
                data = json.loads(params.get('data', '{}'))
                direct_print = json.loads(params.get('direct_print', 'false'))
                email_print = json.loads(params.get('email_print', 'false'))
                email = json.loads(params.get('email', 'null'))
                name = json.loads(params.get('name', 'false'))
                window = json.loads(params.get('window', 'false'))
                context = json.loads(params.get('context', '{}'))
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
                data = json.loads(params.get('data'))
                direct_print = json.loads(params.get('direct_print', 'false'))
                email_print = json.loads(params.get('email_print', 'false'))
                email = json.loads(params.get('email', 'null'))
                name = json.loads(params.get('name', 'false'))
                context = json.loads(params.get('context', '{}'))
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

    def open_url(self, url):
        def idle_open_url():
            with gtk.gdk.lock:
                self._open_url(url)
                return False
        gobject.idle_add(idle_open_url)
