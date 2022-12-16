#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import os
import sys
import gettext
import urlparse
import gobject
import gtk
import tryton.rpc as rpc
from tryton.config import CONFIG, TRYTON_ICON, PIXMAPS_DIR, DATA_DIR, \
        get_config_dir
import tryton.common as common
from tryton.action import Action
from tryton.gui.window import Window
from tryton.gui.window.preference import Preference
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
import base64
import tryton.translate as translate
import tryton.plugins
import pango
import time
try:
    import igemacintegration
except ImportError:
    igemacintegration = None
try:
    import gtkspell
except:
    gtkspell = None

_ = gettext.gettext


_MAIN = []

class Main(object):
    window = None

    def __init__(self):
        super(Main, self).__init__()

        self.window = gtk.Window()
        self._width = int(CONFIG['client.default_width'])
        self._height = int(CONFIG['client.default_height'])
        self.window.set_default_size(self._width, self._height)
        self.window.set_resizable(True)
        self.window.set_title('Tryton')
        self.window.set_icon(TRYTON_ICON)
        self.window.connect("destroy", Main.sig_quit)
        self.window.connect("delete_event", self.sig_delete)
        self.window.connect('configure_event', self.sig_configure)

        self.accel_group = gtk.AccelGroup()
        self.window.add_accel_group(self.accel_group)

        gtk.accel_map_add_entry('<tryton>/File/Connect', gtk.keysyms.O,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/File/Quit', gtk.keysyms.Q,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/New', gtk.keysyms.N,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Save', gtk.keysyms.S,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Duplicate', gtk.keysyms.D,
                gtk.gdk.CONTROL_MASK|gtk.gdk.SHIFT_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Delete', gtk.keysyms.D,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Find', gtk.keysyms.F,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Next', gtk.keysyms.Page_Down,
                0)
        gtk.accel_map_add_entry('<tryton>/Form/Previous', gtk.keysyms.Page_Up,
                0)
        gtk.accel_map_add_entry('<tryton>/Form/Switch View', gtk.keysyms.L,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Menu', gtk.keysyms.T,
                gtk.gdk.CONTROL_MASK)
        gtk.accel_map_add_entry('<tryton>/Form/Home', gtk.keysyms.H,
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
        gtk.accel_map_add_entry('<tryton>/Form/Print', gtk.keysyms.P,
                gtk.gdk.CONTROL_MASK)

        if hasattr(gtk, 'accel_map_load'):
            gtk.accel_map_load(os.path.join(get_config_dir(), 'accel.map'))

        self.tooltips = common.Tooltips()

        toolbar = gtk.Toolbar()
        self.toolbar = toolbar
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        toolbar.set_style(gtk.TOOLBAR_BOTH)

        self.vbox = gtk.VBox()
        self.window.add(self.vbox)

        self.status_hbox = None
        self.menubar = None
        self.menuitem_user = None
        self.menuitem_form = None
        self.menuitem_plugins = None

        self.set_statusbar()
        self.set_menubar()

        if igemacintegration:
            self.macmenu = igemacintegration.MacMenu()
            quit_item = gtk.MenuItem(_('Quit'))
            quit_item.connect('activate', self.sig_close)
            self.macmenu.set_quit_menu_item(quit_item)
            self.macdock = igemacintegration.MacDock()
            self.macdock.connect('quit-activate', self.sig_close)

        self.vbox.pack_start(toolbar, False, True)

        self.buttons = {}
        self._set_toolbar()
        self.set_toolbar_label()

        self.notebook = gtk.Notebook()
        self.notebook.popup_enable()
        self.notebook.set_scrollable(True)
        self.notebook.connect_after('switch-page', self._sig_page_changt)
        self.vbox.pack_start(self.notebook, True, True)

        self.window.show_all()

        self.pages = []
        self.previous_pages = {}
        self.current_page = 0
        self.last_page = 0

        if CONFIG['client.modepda']:
            self.radiomenuitem_pda.set_active(True)
        else:
            self.radiomenuitem_normal.set_active(True)
        self.sb_set()

        settings = gtk.settings_get_default()
        settings.set_property('gtk-button-images', True)
        settings.set_property('gtk-can-change-accels',
                CONFIG['client.can_change_accelerators'])
        try:
            settings.set_property('gtk-keynav-cursor-only', True)
        except TypeError:
            pass

        self.sig_toolbar_show()
        self.sig_statusbar_show()

        if os.name in ('nt', 'mac') or \
                (hasattr(os, 'uname') and os.uname()[0] == 'Darwin'):
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

        menuitem_form = gtk.MenuItem(_('For_m'))
        if self.menuitem_form:
            menuitem_form.set_sensitive(
                    self.menuitem_form.get_property('sensitive'))
        else:
            menuitem_form.set_sensitive(False)
        self.menuitem_form = menuitem_form
        menubar.add(menuitem_form)

        menu_form = self._set_menu_form()
        menuitem_form.set_submenu(menu_form)
        menu_form.set_accel_group(self.accel_group)
        menu_form.set_accel_path('<tryton>/Form')

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
        self.menuitem_shortcut = menuitem_shortcut
        self.menuitem_shortcut.set_sensitive(False)
        menubar.add(menuitem_shortcut)
        menuitem_shortcut.set_accel_path('<tryton>/Shortcuts')

        menuitem_help = gtk.MenuItem(_('_Help'))
        menubar.add(menuitem_help)

        menu_help = self._set_menu_help()
        menuitem_help.set_submenu(menu_help)
        menu_help.set_accel_group(self.accel_group)
        menu_help.set_accel_path('<tryton>/Help')

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

        menu_file.add(gtk.SeparatorMenuItem())

        imagemenuitem_close = gtk.ImageMenuItem(_('_Quit...'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-log-out', gtk.ICON_SIZE_MENU)
        imagemenuitem_close.set_image(image)
        imagemenuitem_close.connect('activate', self.sig_close)
        imagemenuitem_close.set_accel_path('<tryton>/File/Quit')
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

    def _set_menu_form(self):
        menu_form = gtk.Menu()

        imagemenuitem_new = gtk.ImageMenuItem(_('_New'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-new', gtk.ICON_SIZE_MENU)
        imagemenuitem_new.set_image(image)
        imagemenuitem_new.connect('activate', self._sig_child_call, 'but_new')
        imagemenuitem_new.set_accel_path('<tryton>/Form/New')
        menu_form.add(imagemenuitem_new)

        imagemenuitem_save = gtk.ImageMenuItem(_('_Save'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-save', gtk.ICON_SIZE_MENU)
        imagemenuitem_save.set_image(image)
        imagemenuitem_save.connect('activate', self._sig_child_call, 'but_save')
        imagemenuitem_save.set_accel_path('<tryton>/Form/Save')
        menu_form.add(imagemenuitem_save)

        imagemenuitem_copy = gtk.ImageMenuItem(_('_Duplicate'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-copy', gtk.ICON_SIZE_MENU)
        imagemenuitem_copy.set_image(image)
        imagemenuitem_copy.connect('activate', self._sig_child_call, 'but_copy')
        imagemenuitem_copy.set_accel_path('<tryton>/Form/Duplicate')
        menu_form.add(imagemenuitem_copy)

        imagemenuitem_delete = gtk.ImageMenuItem(_('_Delete...'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-delete', gtk.ICON_SIZE_MENU)
        imagemenuitem_delete.set_image(image)
        imagemenuitem_delete.connect('activate', self._sig_child_call, 'but_remove')
        imagemenuitem_delete.set_accel_path('<tryton>/Form/Delete')
        menu_form.add(imagemenuitem_delete)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_search = gtk.ImageMenuItem(_('_Find...'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-find', gtk.ICON_SIZE_MENU)
        imagemenuitem_search.set_image(image)
        imagemenuitem_search.connect('activate', self._sig_child_call, 'but_search')
        imagemenuitem_search.set_accel_path('<tryton>/Form/Find')
        menu_form.add(imagemenuitem_search)

        imagemenuitem_next = gtk.ImageMenuItem(_('_Next'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-go-next', gtk.ICON_SIZE_MENU)
        imagemenuitem_next.set_image(image)
        imagemenuitem_next.connect('activate', self._sig_child_call, 'but_next')
        imagemenuitem_next.set_accel_path('<tryton>/Form/Next')
        menu_form.add(imagemenuitem_next)

        imagemenuitem_previous = gtk.ImageMenuItem(_('_Previous'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-go-previous', gtk.ICON_SIZE_MENU)
        imagemenuitem_previous.set_image(image)
        imagemenuitem_previous.connect('activate', self._sig_child_call, 'but_previous')
        imagemenuitem_previous.set_accel_path('<tryton>/Form/Previous')
        menu_form.add(imagemenuitem_previous)

        imagemenuitem_switch = gtk.ImageMenuItem(_('_Switch View'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-fullscreen', gtk.ICON_SIZE_MENU)
        imagemenuitem_switch.set_image(image)
        imagemenuitem_switch.connect('activate', self._sig_child_call, 'but_switch')
        imagemenuitem_switch.set_accel_path('<tryton>/Form/Switch View')
        menu_form.add(imagemenuitem_switch)

        imagemenuitem_menu = gtk.ImageMenuItem(_('_Menu'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-start-here', gtk.ICON_SIZE_MENU)
        imagemenuitem_menu.set_image(image)
        imagemenuitem_menu.connect('activate', self.sig_win_menu)
        imagemenuitem_menu.set_accel_path('<tryton>/Form/Menu')
        menu_form.add(imagemenuitem_menu)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_home = gtk.ImageMenuItem(_('_Home'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-go-home', gtk.ICON_SIZE_MENU)
        imagemenuitem_home.set_image(image)
        imagemenuitem_home.connect('activate', self.sig_home_new)
        imagemenuitem_home.set_accel_path('<tryton>/Form/Home')
        menu_form.add(imagemenuitem_home)

        imagemenuitem_close = gtk.ImageMenuItem(_('_Close Tab'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-close', gtk.ICON_SIZE_MENU)
        imagemenuitem_close.set_image(image)
        imagemenuitem_close.connect('activate', self.sig_win_close)
        imagemenuitem_close.set_accel_path('<tryton>/Form/Close')
        menu_form.add(imagemenuitem_close)

        imagemenuitem_win_prev = gtk.ImageMenuItem(_('_Previous Tab'), self.accel_group)
        imagemenuitem_win_prev.connect('activate', self.sig_win_prev)
        imagemenuitem_win_prev.set_accel_path('<tryton>/Form/Previous Tab')
        menu_form.add(imagemenuitem_win_prev)

        imagemenuitem_win_next = gtk.ImageMenuItem(_('_Next Tab'), self.accel_group)
        imagemenuitem_win_next.connect('activate', self.sig_win_next)
        imagemenuitem_win_next.set_accel_path('<tryton>/Form/Next Tab')
        menu_form.add(imagemenuitem_win_next)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_log = gtk.ImageMenuItem(_('View _Logs...'))
        imagemenuitem_log.connect('activate', self._sig_child_call, 'but_log')
        menu_form.add(imagemenuitem_log)

        imagemenuitem_goto_id = gtk.ImageMenuItem(_('_Go to Record ID...'),
                self.accel_group)
        imagemenuitem_goto_id.connect('activate', self._sig_child_call,
                'but_goto_id')
        imagemenuitem_goto_id.set_accel_path('<tryton>/Form/Goto')
        menu_form.add(imagemenuitem_goto_id)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_reload = gtk.ImageMenuItem(_('_Reload/Undo'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-refresh', gtk.ICON_SIZE_MENU)
        imagemenuitem_reload.set_image(image)
        imagemenuitem_reload.connect('activate', self._sig_child_call,
                'but_reload')
        imagemenuitem_reload.set_accel_path('<tryton>/Form/Reload')
        menu_form.add(imagemenuitem_reload)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_action = gtk.ImageMenuItem(_('_Actions...'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-executable', gtk.ICON_SIZE_MENU)
        imagemenuitem_action.set_image(image)
        imagemenuitem_action.connect('activate', self._sig_child_call,
                'but_action')
        imagemenuitem_action.set_accel_path('<tryton>/Form/Actions')
        menu_form.add(imagemenuitem_action)

        imagemenuitem_print = gtk.ImageMenuItem(_('_Print...'), self.accel_group)
        image = gtk.Image()
        image.set_from_stock('tryton-print', gtk.ICON_SIZE_MENU)
        imagemenuitem_print.set_image(image)
        imagemenuitem_print.connect('activate', self._sig_child_call,
                'but_print')
        imagemenuitem_print.set_accel_path('<tryton>/Form/Print')
        menu_form.add(imagemenuitem_print)

        menu_form.add(gtk.SeparatorMenuItem())

        imagemenuitem_export = gtk.ImageMenuItem(_('_Export Data...'))
        image = gtk.Image()
        image.set_from_stock('tryton-save-as', gtk.ICON_SIZE_MENU)
        imagemenuitem_export.set_image(image)
        imagemenuitem_export.connect('activate', self._sig_child_call,
                'but_save_as')
        imagemenuitem_export.set_accel_path('<tryton>/Form/Export Data')
        menu_form.add(imagemenuitem_export)

        menuitem_import = gtk.MenuItem(_('_Import Data...'))
        menuitem_import.connect('activate', self._sig_child_call,
                'but_import')
        menuitem_import.set_accel_path('<tryton>/Form/Import Data')
        menu_form.add(menuitem_import)
        return menu_form

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

        checkmenuitem_toolbar = gtk.CheckMenuItem(_('Toolbar'))
        checkmenuitem_toolbar.connect('activate',
                lambda menuitem: self.sig_toolbar_change(menuitem.get_active()))
        checkmenuitem_toolbar.set_accel_path('<tryton>/Options/Form/Toolbar')
        menu_form.add(checkmenuitem_toolbar)
        if CONFIG['form.toolbar']:
            checkmenuitem_toolbar.set_active(True)

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

        menu_help.add(gtk.SeparatorMenuItem())

        imagemenuitem_about = gtk.ImageMenuItem(_('_About...'))
        image = gtk.Image()
        image.set_from_stock('gtk-about', gtk.ICON_SIZE_MENU)
        imagemenuitem_about.set_image(image)
        imagemenuitem_about.connect('activate', self.sig_about)
        imagemenuitem_about.set_accel_path('<tryton>/Help/About')
        menu_help.add(imagemenuitem_about)
        return menu_help

    def _set_toolbar(self):
        toolbutton_new = gtk.ToolButton('tryton-new')
        toolbutton_new.set_use_underline(True)
        self.toolbar.insert(toolbutton_new, -1)
        toolbutton_new.connect('clicked', self._sig_child_call, 'but_new')
        self.buttons['but_new'] = toolbutton_new

        toolbutton_save = gtk.ToolButton('tryton-save')
        toolbutton_save.set_use_underline(True)
        self.toolbar.insert(toolbutton_save, -1)
        toolbutton_save.connect('clicked', self._sig_child_call, 'but_save')
        self.buttons['but_save'] = toolbutton_save

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_remove = gtk.ToolButton('tryton-delete')
        toolbutton_remove.set_use_underline(True)
        self.toolbar.insert(toolbutton_remove, -1)
        toolbutton_remove.connect('clicked', self._sig_child_call, 'but_remove')
        self.buttons['but_remove'] = toolbutton_remove

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_search = gtk.ToolButton('tryton-find')
        toolbutton_search.set_use_underline(True)
        self.toolbar.insert(toolbutton_search, -1)
        toolbutton_search.connect('clicked', self._sig_child_call, 'but_search')
        self.buttons['but_search'] = toolbutton_search

        toolbutton_previous = gtk.ToolButton('tryton-go-previous')
        self.toolbar.insert(toolbutton_previous, -1)
        toolbutton_previous.connect('clicked', self._sig_child_call, 'but_previous')
        self.buttons['but_previous'] = toolbutton_previous

        toolbutton_next = gtk.ToolButton('tryton-go-next')
        self.toolbar.insert(toolbutton_next, -1)
        toolbutton_next.connect('clicked', self._sig_child_call, 'but_next')
        self.buttons['but_next'] = toolbutton_next

        toolbutton_switch = gtk.ToolButton('tryton-fullscreen')
        self.toolbar.insert(toolbutton_switch, -1)
        toolbutton_switch.connect('clicked', self._sig_child_call, 'but_switch')
        self.buttons['but_switch'] = toolbutton_switch

        toolbutton_reload = gtk.ToolButton('tryton-refresh')
        toolbutton_reload.set_use_underline(True)
        self.toolbar.insert(toolbutton_reload, -1)
        toolbutton_reload.connect('clicked', self._sig_child_call, 'but_reload')
        self.buttons['but_reload'] = toolbutton_reload

        toolbutton_menu = gtk.ToolButton('tryton-start-here')
        self.toolbutton_menu = toolbutton_menu
        self.toolbar.insert(toolbutton_menu, -1)
        toolbutton_menu.connect('clicked', self.sig_win_menu)
        self.buttons['but_menu'] = toolbutton_menu

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_action = gtk.ToolButton('tryton-executable')
        self.toolbar.insert(toolbutton_action, -1)
        toolbutton_action.connect('clicked', self._sig_child_call, 'but_action')
        self.buttons['but_action'] = toolbutton_action

        toolbutton_print = gtk.ToolButton('tryton-print')
        self.toolbar.insert(toolbutton_print, -1)
        toolbutton_print.connect('clicked', self._sig_child_call, 'but_print')
        self.buttons['but_print'] = toolbutton_print

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_attach = gtk.ToolButton('tryton-attachment')
        self.toolbar.insert(toolbutton_attach, -1)
        toolbutton_attach.connect('clicked', self._sig_child_call, 'but_attach')
        self.buttons['but_attach'] = toolbutton_attach

        self.toolbar.insert(gtk.SeparatorToolItem(), -1)

        toolbutton_request = gtk.ToolButton('tryton-mail-message')
        self.toolbutton_request = toolbutton_request
        self.toolbar.insert(toolbutton_request, -1)
        toolbutton_request.connect('clicked', self.sig_request_open)
        self.buttons['but_request'] = toolbutton_request

    def set_toolbar_label(self):
        labels = {
            'but_new': _('_New'),
            'but_save': _('_Save'),
            'but_remove': _('_Delete'),
            'but_search': _('_Find'),
            'but_previous': _('Previous'),
            'but_next': _('Next'),
            'but_switch': _('Switch'),
            'but_reload': _('_Reload'),
            'but_menu': _('Menu'),
            'but_action': _('Action'),
            'but_print': _('Print'),
            'but_attach': _('Attachment(0)'),
            'but_request': _('Request'),
        }
        tooltips = {
            'but_new': _('Create a new record'),
            'but_save': _('Save this record'),
            'but_remove': _('Delete this record'),
            'but_search': _('Find records'),
            'but_previous': _('Previous Record'),
            'but_next': _('Next Record'),
            'but_switch': _('Switch view'),
            'but_reload': _('Reload'),
            'but_menu': _('Menu'),
            'but_action': _('Action'),
            'but_print': _('Print'),
            'but_attach': _('Add an attachment to the record'),
            'but_request': _('Request'),
        }
        for i in self.buttons:
            self.buttons[i].set_label(labels[i])
            self.tooltips.set_tip(self.buttons[i], tooltips[i])

    @staticmethod
    def get_main():
        return _MAIN[0]

    def shortcut_set(self, shortcuts=None):
        def _action_shortcut(widget, action):
            Action.exec_keyword('tree_open', self.window, {
                'model': 'ir.ui.menu',
                'id': action,
                'ids': [action],
                })
        if shortcuts is None:
            user = rpc._USER
            try:
                shortcuts = rpc.execute('model', 'ir.ui.view_sc', 'get_sc',
                        user, 'ir.ui.menu', rpc.CONTEXT)
            except:
                shortcuts = []
        menu = gtk.Menu()
        for shortcut in shortcuts:
            menuitem = gtk.MenuItem(shortcut['name'])
            menuitem.connect('activate', _action_shortcut, shortcut['res_id'])
            menu.add(menuitem)
        menu.show_all()
        self.menuitem_shortcut.set_submenu(menu)
        self.menuitem_shortcut.set_sensitive(True)

    def shortcut_unset(self):
        menu = gtk.Menu()
        menu.show_all()
        self.menuitem_shortcut.set_submenu(menu)
        self.menuitem_shortcut.set_sensitive(False)

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

    def sig_toolbar_change(self, value):
        CONFIG['form.toolbar'] = value
        return self.sig_toolbar_show()

    def sig_toolbar_show(self):
        toolbar = CONFIG['form.toolbar']
        if toolbar:
            self.toolbar.show()
        else:
            self.toolbar.hide()

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
            self.toolbar.set_style(False)
        elif option == 'both':
            self.toolbar.set_style(gtk.TOOLBAR_BOTH)
        elif option == 'text':
            self.toolbar.set_style(gtk.TOOLBAR_TEXT)
        elif option == 'icons':
            self.toolbar.set_style(gtk.TOOLBAR_ICONS)

    @staticmethod
    def sig_form_tab(option):
        CONFIG['client.form_tab'] = option

    def sig_file_actions(self, widget):
        FileActions(self.window).run()

    def sig_email(self, widget):
        Email(self.window).run()

    def sig_win_next(self, widget):
        page = self.notebook.get_current_page()
        if page == len(self.pages) - 1:
            page = -1
        self.notebook.set_current_page(page + 1)

    def sig_win_prev(self, widget):
        page = self.notebook.get_current_page()
        self.notebook.set_current_page(page - 1)

    def sig_user_preferences(self, widget):
        win = Preference(rpc._USER, self.window)
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
                    self.set_toolbar_label()
                    self.shortcut_set()
                    self.set_statusbar()
                    self.request_set()
                    self.sig_reload_menu()
                CONFIG['client.lang'] = prefs['language']
            CONFIG.save()
        self.window.present()
        return True

    def sig_win_close(self, widget):
        self._sig_child_call(widget, 'but_close')

    def sig_request_new(self, widget):
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx['active_test'] = False
        return Window.create(None, 'res.request', False, [
            ], 'form', mode=['form', 'tree'], window=self.window,
            context=ctx)

    def sig_request_open(self, widget):
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx['active_test'] = False
        try:
            ids1, ids2 = self.request_set(True)
        except Exception, exception:
            if common.process_exception(exception, self.window):
                ids1, ids2 = self.request_set(True)
            else:
                raise
        ids = ids1 + ids2
        return Window.create(False, 'res.request', ids, [
            ], 'form', mode=['tree', 'form'], window=self.window,
            context=ctx)

    def request_set(self, exception=False):
        try:
            if not rpc._USER:
                return
            if not exception:
                res = rpc.execute('model', 'res.request', 'request_get')
                if not res:
                    return ([], [])
                ids, ids2 = res
            else:
                ids, ids2 = rpc.execute('model', 'res.request', 'request_get')
            label = _('Requests (%s/%s)') % (len(ids), len(ids2))
            self.buttons['but_request'].set_label(label)
            self.tooltips.set_tip(self.buttons['but_request'], label)
            if not ids:
                self.buttons['but_request'].set_stock_id('tryton-mail-message')
            else:
                self.buttons['but_request'].set_stock_id(
                        'tryton-mail-message-new')
            message = _('Waiting requests: %s received - %s sent') % (len(ids),
                        len(ids2))
            self.sb_requests.set_text(message)
            return (ids, ids2)
        except:
            if exception:
                raise
            return ([], [])

    def sig_login(self, widget=None, dbname=False, res=None):
        if not self.sig_logout(widget, disconnect=False):
            return
        if not res:
            try:
                dblogin = DBLogin(self.window)
                res = dblogin.run(dbname, self.window)
            except Exception, exception:
                if exception.args == ('QueryCanceled',):
                    return False
                common.process_exception(exception, self.window)
                return
        self.window.present()
        try:
            log_response = rpc.login(*res)
        except Exception, exception:
            common.process_exception(exception, self.window)
            return
        self.refresh_ssl()
        if log_response > 0:
            try:
                prefs = rpc.execute('model', 'res.user', 'get_preferences',
                        False, rpc.CONTEXT)
            except:
                prefs = None
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
                    self.set_toolbar_label()
                    self.shortcut_set()
                    self.set_statusbar()
                    self.request_set()
                CONFIG['client.lang'] = prefs['language']
            CONFIG.save()
        elif log_response == -1:
            common.message(_('Connection error!\n' \
                    'Unable to connect to the server!'), self.window)
        elif log_response == -2:
            common.message(_('Connection error!\n' \
                    'Bad username or password!'), self.window)
            return self.sig_login()
        if not self.menuitem_shortcut.get_property('sensitive'):
            self.shortcut_set()
        self.toolbutton_menu.set_sensitive(True)
        self.toolbutton_request.set_sensitive(True)
        self.menuitem_user.set_sensitive(True)
        self.menuitem_form.set_sensitive(True)
        self.menuitem_plugins.set_sensitive(True)
        self.notebook.grab_focus()
        return True

    def sig_logout(self, widget, disconnect=True):
        res = True
        while res:
            wid = self._wid_get()
            if wid:
                if 'but_close' in wid.handlers:
                    res = wid.handlers['but_close']()
                if not res:
                    return False
                res = self._win_del()
            else:
                res = False
        self.sb_username.set_text('')
        self.sb_servername.set_text('')
        self.sb_requests.set_text('')
        self.shortcut_unset()
        self.toolbutton_menu.set_sensitive(False)
        self.toolbutton_request.set_sensitive(False)
        self.toolbutton_request.set_label(_('Request'))
        self.menuitem_user.set_sensitive(False)
        self.menuitem_form.set_sensitive(False)
        self.menuitem_plugins.set_sensitive(False)
        if disconnect:
            rpc.logout()
        self.refresh_ssl()
        return True

    def refresh_ssl(self):
        if rpc.SECURE:
            info = ''
            if hasattr(rpc._SOCK.ssl_sock, 'server'):
                info = str(rpc._SOCK.ssl_sock.server())
            self.tooltips.set_tip(self.secure_img, _('SSL connection') + \
                    '\n' + info)
            self.secure_img.show()
        else:
            self.secure_img.hide()
            self.tooltips.set_tip(self.secure_img, '')

    def sig_tips(self, *args):
        Tips(self.window)

    def sig_about(self, widget):
        About(self.window)

    def sig_shortcuts(self, widget):
        Shortcuts(self.window).run()

    def sig_reload_menu(self):
        res = False
        for page in range(len(self.pages)):
            if self.pages[page].model == 'ir.ui.menu':
                self.pages[page].sig_reload()
                hbox = self.notebook.get_tab_label(self.pages[page].widget)
                label = hbox.get_children()[0]
                label.set_text(_('Menu'))
                res = True
        return res

    def sig_win_menu(self, widget=None, quiet=True, prefs=None):
        for page in range(len(self.pages)):
            if self.pages[page].model == 'ir.ui.menu':
                page_num = self.notebook.page_num(self.pages[page].widget)
                self.notebook.set_current_page(page_num)
                return True
        res = self.sig_win_new(widget, menu_type='menu', quiet=quiet,
                prefs=prefs)
        return res

    def sig_win_new(self, widget=None, menu_type='menu', quiet=True,
            except_id=False, prefs=None):
        if not prefs:
            args = ('model', 'res.user', 'get_preferences', False, rpc.CONTEXT)
            try:
                prefs = rpc.execute(*args)
            except Exception, exception:
                prefs = common.process_exception(exception, self.window, *args)
                if not prefs:
                    return False
        self.sb_username.set_text(prefs.get('status_bar', ''))
        self.sb_servername.set_text('%s@%s:%d/%s' % (rpc._USERNAME,
            rpc._SOCK.hostname, rpc._SOCK.port, rpc._DATABASE))
        if not prefs[menu_type]:
            if quiet:
                return False
            common.warning(_('You can not log into the system!\n' \
                    'Verify if you have a menu defined on your user.'),
                    'Access Denied!', self.window)
            rpc.logout()
            self.refresh_ssl()
            return False
        act_id = prefs[menu_type]
        if except_id and act_id == except_id:
            return act_id
        Action.execute(act_id, {}, self.window)
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
        tryton.plugins.execute(datas, self.window)

    @staticmethod
    def sig_quit(widget=None):
        CONFIG['client.default_width'] = Main.get_main()._width
        CONFIG['client.default_height'] = Main.get_main()._height
        CONFIG.save()
        if hasattr(gtk, 'accel_map_save'):
            gtk.accel_map_save(os.path.join(get_config_dir(), 'accel.map'))
        gtk.main_quit()

    def sig_close(self, widget):
        if common.sur(_("Do you really want to quit?"), parent=self.window):
            if not self.sig_logout(widget):
                return False
            Main.sig_quit()

    def sig_delete(self, widget, event):
        if common.sur(_("Do you really want to quit?"), parent=self.window):
            if not self.sig_logout(widget):
                return True
            return False
        return True

    def sig_configure(self, widget, event):
        if hasattr(event, 'width') \
                and hasattr(event, 'height'):
            self._width =  int(event.width)
            self._height = int(event.height)
        return False

    def win_add(self, page):
        previous_page_id = self.notebook.get_current_page()
        previous_widget = self.notebook.get_nth_page(previous_page_id)
        self.previous_pages[page] = previous_widget
        self.pages.append(page)
        hbox = gtk.HBox()
        name = page.name
        if page.model == 'ir.ui.menu':
            name = _('Menu')
        label = gtk.Label(name)
        self.tooltips.set_tip(label, page.name)
        self.tooltips.enable()
        label.set_alignment(0.0, 0.5)
        hbox.pack_start(label, expand=True, fill=True)
        layout = label.get_layout()
        w, h = layout.get_size()
        icon_w, icon_h = gtk.icon_size_lookup(gtk.ICON_SIZE_SMALL_TOOLBAR)
        if (w / pango.SCALE) > 120 - icon_w:
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
        hbox.set_size_request(120, -1)
        label_menu = gtk.Label(page.name)
        label_menu.set_alignment(0.0, 0.5)
        self.notebook.append_page_menu(page.widget, hbox, label_menu)
        if hasattr(self.notebook, 'set_tab_reorderable'):
            self.notebook.set_tab_reorderable(page.widget, True)
        self.notebook.set_current_page(-1)
        page.signal_connect(self, 'attachment-count', self._attachment_count)

    def sb_set(self, view=None):
        if not view:
            view = self._wid_get()
        for i in self.buttons:
            if i in ('but_menu', 'but_request'):
                continue
            if self.buttons[i]:
                self.buttons[i].set_sensitive(
                        bool(view and (i in view.handlers)))
        if hasattr(view, 'update_attachment_count'):
            view.update_attachment_count()
        else:
            self._attachment_count(view, 0)

    def _attachment_count(self, widget, signal_data):
        label = _('Attachment(%d)') % signal_data
        self.buttons['but_attach'].set_label(label)
        if signal_data:
            self.buttons['but_attach'].set_stock_id('tryton-attachment-hi')
        else:
            self.buttons['but_attach'].set_stock_id('tryton-attachment')

    def _sig_remove_book(self, widget, page_widget):
        for page in self.pages:
            if page.widget == page_widget:
                page_num = self.notebook.page_num(page.widget)
                self.notebook.set_current_page(page_num)
                if 'but_close' in page.handlers:
                    res = page.handlers['but_close']()
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
            self.sb_set()

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

            self.notebook.set_current_page(next_page_id)
        return self.notebook.get_current_page() != -1

    def _wid_get(self):
        page_id = self.notebook.get_current_page()
        if page_id == -1:
            return None
        page_widget = self.notebook.get_nth_page(page_id)
        for page in self.pages:
            if page.widget == page_widget:
                return page
        return None

    def _sig_child_call(self, widget, button_name):
        wid = self._wid_get()
        if wid:
            res = True
            if button_name in wid.handlers:
                res = wid.handlers[button_name]()
            if button_name == 'but_close' and res:
                self._win_del()

    def _sig_page_changt(self, notebook, page, page_num):
        self.last_page = self.current_page
        self.current_page = self.notebook.get_current_page()
        self.sb_set()

    def sig_db_new(self, widget):
        if not self.sig_logout(widget):
            return False
        dia = DBCreate(self.sig_login)
        res = dia.run(self.window)
        if res:
            CONFIG.save()
        return res

    def sig_db_drop(self, widget):
        if not self.sig_logout(widget):
            return False
        dialog = DBBackupDrop(self.window, function='drop')
        url, dbname, passwd = dialog.run(self.window)
        if not dbname:
            rpc.logout()
            Main.get_main().refresh_ssl()
            return

        host, port = url.rsplit(':', 1)
        sure = common.sur_3b(_("You are going to delete a Tryton " \
                "database.\nAre you really sure to proceed?"), self.window)
        if sure == "ko" or sure == "cancel":
            return
        rpcprogress = common.RPCProgress('db_exec', (host, int(port), 'drop',
            dbname, passwd), self.window)
        try:
            rpcprogress.run()
        except Exception, exception:
            self.refresh_ssl()
            if exception[0] == "AccessDenied":
                common.warning(_("Wrong Tryton Server Password" \
                        "\nPlease try again."), self.window,
                        _('Access denied!'))
                self.sig_db_drop(self.window)
            else:
                common.warning(_('Database drop failed with ' \
                        'error message:\n') + str(exception[0]), \
                        self.window, _('Database drop failed!'))
            return
        self.refresh_ssl()
        common.message(_("Database dropped successfully!"), \
                parent=self.window)

    def sig_db_restore(self, widget=None):
        if not self.sig_logout(widget):
            return False
        filename = common.file_selection(_('Open Backup File to Restore...'), \
                parent=self.window, preview=False)
        if not filename:
            return
        dialog = DBRestore(self.window, filename=filename)
        url, dbname, passwd, update = dialog.run(self.window)
        if dbname:
            file_p = open(filename, 'rb')
            data_b64 = base64.encodestring(file_p.read())
            file_p.close()
            host, port = url.rsplit(':' , 1)
            rpcprogress = common.RPCProgress('db_exec', (host, int(port),
                'restore', dbname, passwd, data_b64, update), self.window)
            try:
                res = rpcprogress.run()
            except Exception, exception:
                self.refresh_ssl()
                if exception[0] == \
                        "Couldn't restore database with password":
                    common.warning(_("It is not possible to restore a " \
                            "password protected database.\n" \
                            "Backup and restore needed to be proceed " \
                            "manual."), self.window, \
                            _('Database is password protected!'))
                elif exception[0] == "AccessDenied":
                    common.warning(_("Wrong Tryton Server Password.\n" \
                            "Please try again."), self.window, \
                            _('Access denied!'))
                    self.sig_db_restore(self.window)
                else:
                    common.warning(_('Database restore failed with ' \
                            'error message:\n') + str(exception[0]), \
                            self.window, _('Database restore failed!'))
                return
            self.refresh_ssl()
            if res:
                common.message(_("Database restored successfully!"), \
                        parent=self.window)
            else:
                common.message(_('Database restore failed!'), \
                        parent=self.window)

    def sig_db_dump(self, widget=None):
        if not self.sig_logout(widget):
            return False
        dialog = DBBackupDrop(self.window, function='backup')
        url, dbname, passwd = dialog.run(self.window)

        if not (dbname and url and passwd):
            rpc.logout()
            Main.get_main().refresh_ssl()
            return

        host, port = url.rsplit(':', 1)
        rpcprogress = common.RPCProgress('db_exec', (host, int(port), 'dump',
            dbname, passwd), self.window)
        try:
            dump_b64 = rpcprogress.run()
        except Exception, exception:
            if exception[0] == "Couldn't dump database with password":
                common.warning(_("It is not possible to dump a password " \
                        "protected Database.\nBackup and restore " \
                        "needed to be proceed manual."),
                        self.window, _('Database is password protected!'))
            elif exception[0] == "AccessDenied":
                common.warning(_("Wrong Tryton Server Password.\n" \
                        "Please try again."), self.window,
                        _('Access denied!'))
                self.sig_db_dump(self.window)
            else:
                common.warning(_('Database dump failed with ' \
                        'error message:\n') + str(exception[0]), \
                        self.window, _('Database dump failed!'))
            rpc.logout()
            Main.get_main().refresh_ssl()
            return

        self.refresh_ssl()
        dump = base64.decodestring(dump_b64)

        filename = common.file_selection(_('Save As...'), \
                action=gtk.FILE_CHOOSER_ACTION_SAVE, parent=self.window, \
                preview=False,
                filename=dbname + '-' + time.strftime('%Y%m%d%H%M') + '.dump')

        if filename:
            file_ = open(filename, 'wb')
            file_.write(dump)
            file_.close()
            common.message(_("Database backuped successfully!"), \
                    parent=self.window)
        else:
            rpc.logout()
            Main.get_main().refresh_ssl()
