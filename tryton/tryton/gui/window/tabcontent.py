# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gettext
import gtk
import pango

import tryton.common as common
from tryton.config import CONFIG
from tryton.gui import Main
from .infobar import InfoBar

_ = gettext.gettext


class ToolbarItem(object):
    def __init__(self, id, label,
            tooltip=None, stock_id=None, accel_path=None):
        self.id = id
        self.label = label
        self.tooltip = tooltip
        self.stock_id = stock_id
        self.accel_path = accel_path

    @property
    def menu(self):
        return True

    @property
    def toolbar(self):
        return bool(self.tooltip)


class TabContent(InfoBar):

    @property
    def menu_def(self):
        return [
            ToolbarItem(
                id='switch',
                label=_("_Switch View"),
                tooltip=_("Switch View"),
                stock_id='tryton-fullscreen',
                accel_path='<tryton>/Form/Switch View'),
            ToolbarItem(
                id='previous',
                label=_("_Previous"),
                tooltip=_("Previous Record"),
                stock_id='tryton-go-previous',
                accel_path='<tryton>/Form/Previous'),
            ToolbarItem(
                id='next',
                label=_("_Next"),
                tooltip=_("Next Record"),
                stock_id='tryton-go-next',
                accel_path='<tryton>/Form/Next'),
            ToolbarItem(
                id='search',
                label=_("_Search"),
                stock_id='tryton-find',
                accel_path='<tryton>/Form/Search'),
            None,
            ToolbarItem(
                id='new',
                label=_("_New"),
                tooltip=_("Create a new record"),
                stock_id='tryton-new',
                accel_path='<tryton>/Form/New'),
            ToolbarItem(
                id='save',
                label=_("_Save"),
                tooltip=_("Save this record"),
                stock_id='tryton-save',
                accel_path='<tryton>/Form/Save'),
            ToolbarItem(
                id='reload',
                label=_("_Reload/Undo"),
                tooltip=_("Reload/Undo"),
                stock_id='tryton-refresh',
                accel_path='<tryton>/Form/Reload'),
            ToolbarItem(
                id='copy',
                label=_("_Duplicate"),
                stock_id='tryton-copy',
                accel_path='<tryton>/Form/Duplicate'),
            ToolbarItem(
                id='remove',
                label=_("_Delete..."),
                stock_id='tryton-delete',
                accel_path='<tryton>/Form/Delete'),
            None,
            ToolbarItem(
                id='logs',
                label=_("View _Logs...")),
            ToolbarItem(
                id='revision' if self.model in common.MODELHISTORY else None,
                label=_("Show revisions..."),
                stock_id='tryton-clock'),
            None,
            ToolbarItem(
                id='attach',
                label=_("A_ttachments..."),
                tooltip=_("Add an attachment to the record"),
                stock_id='tryton-attachment',
                accel_path='<tryton>/Form/Attachments'),
            ToolbarItem(
                id='note',
                label=_("_Notes..."),
                tooltip=_("Add a note to the record"),
                stock_id='tryton-note',
                accel_path='<tryton>/Form/Notes'),
            ToolbarItem(
                id='action',
                label=_("_Actions..."),
                stock_id='tryton-executable',
                accel_path='<tryton>/Form/Actions'),
            ToolbarItem(
                id='relate',
                label=_("_Relate..."),
                stock_id='tryton-go-jump',
                accel_path='<tryton>/Form/Relate'),
            None,
            ToolbarItem(
                id='print_open',
                label=_("_Report..."),
                stock_id='tryton-print-open',
                accel_path='<tryton>/Form/Report'),
            ToolbarItem(
                id='print_email',
                label=_("_E-Mail..."),
                stock_id='tryton-print-email',
                accel_path='<tryton>/Form/Email'),
            ToolbarItem(
                id='print',
                label=_("_Print..."),
                stock_id='tryton-print',
                accel_path='<tryton>/Form/Print'),
            None,
            ToolbarItem(
                id='export',
                label=_("_Export Data..."),
                stock_id='tryton-save-as',
                accel_path='<tryton>/Form/Export Data'),
            ToolbarItem(
                id='import',
                label=_("_Import Data..."),
                accel_path='<tryton>/Form/Import Data'),
            ToolbarItem(
                id='copy_url',
                label=_("Copy _URL..."),
                stock_id='tryton-web-browser',
                accel_path='<tryton>/Form/Copy URL'),
            None,
            ToolbarItem(
                id='win_close',
                label=_("_Close Tab"),
                stock_id='tryton-close',
                accel_path='<tryton>/Form/Close'),
            ]

    def create_tabcontent(self):
        self.buttons = {}
        self.menu_buttons = {}
        self.tooltips = common.Tooltips()
        self.accel_group = Main.get_main().accel_group

        self.widget = gtk.VBox(spacing=3)
        self.widget.show()

        title_box = self.make_title_bar()
        self.widget.pack_start(title_box, expand=False, fill=True, padding=3)

        self.toolbar = self.create_toolbar(self.get_toolbars())
        self.toolbar.show_all()
        self.widget.pack_start(self.toolbar, False, True)

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(self.widget_get())
        viewport.show()
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        self.scrolledwindow.add(viewport)
        self.scrolledwindow.show()

        self.widget.pack_start(self.scrolledwindow)

        self.create_info_bar()
        self.widget.pack_start(self.info_bar, False, True)

    def make_title_bar(self):
        self.title = title = gtk.Label()
        title.modify_font(pango.FontDescription("bold 14"))
        title.set_label(self.name)
        title.set_padding(10, 4)
        title.set_alignment(0.0, 0.5)
        title.set_size_request(0, -1)  # Allow overflow
        title.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#000000"))
        title.show()

        title_menu = gtk.MenuBar()
        title_item = gtk.MenuItem('')
        title_item.remove(title_item.get_children()[0])
        menu_image = gtk.Image()
        menu_image.set_from_stock('tryton-preferences-system',
            gtk.ICON_SIZE_BUTTON)
        title_item.add(menu_image)
        title_item.set_submenu(self.set_menu_form())
        title_menu.append(title_item)
        title_menu.show_all()

        self.status_label = gtk.Label()
        self.status_label.set_padding(5, 4)
        self.status_label.set_alignment(0.0, 0.5)
        self.status_label.show()

        hbox = gtk.HBox()
        hbox.pack_start(title, expand=True, fill=True)
        hbox.pack_start(self.status_label, expand=False, fill=True)
        hbox.show()

        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        frame.add(hbox)
        frame.show()

        eb = gtk.EventBox()
        eb.add(frame)
        eb.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#ffffff"))
        eb.show()

        frame_menu = gtk.Frame()
        frame_menu.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        frame_menu.add(title_menu)
        frame_menu.show()

        title_box = gtk.HBox()
        title_box.pack_start(frame_menu, expand=False, fill=True)
        title_box.pack_start(eb, expand=True, fill=True)
        title_box.show()
        return title_box

    def create_base_toolbar(self, toolbar):
        previous = None
        for item in self.menu_def:
            if item and item.toolbar:
                callback = getattr(self, 'sig_%s' % item.id, None)
                if not callback:
                    continue
                toolitem = gtk.ToolButton(item.stock_id)
                toolitem.set_label(item.label)
                toolitem.set_use_underline(True)
                toolitem.connect('clicked', callback)
                self.tooltips.set_tip(toolitem, item.tooltip)
                self.buttons[item.id] = toolitem
            elif not item and previous:
                toolitem = gtk.SeparatorToolItem()
            else:
                continue
            previous = item
            toolbar.insert(toolitem, -1)

    def set_menu_form(self):
        menu_form = gtk.Menu()
        menu_form.set_accel_group(self.accel_group)
        menu_form.set_accel_path('<tryton>/Form')
        previous = None
        for item in self.menu_def:
            if item and item.menu:
                callback = getattr(self, 'sig_%s' % item.id, None)
                if not callback:
                    continue
                menuitem = gtk.ImageMenuItem(item.label, self.accel_group)
                menuitem.set_use_underline(True)
                menuitem.connect('activate', callback)

                if item.stock_id:
                    image = gtk.Image()
                    image.set_from_stock(item.stock_id, gtk.ICON_SIZE_MENU)
                    menuitem.set_image(image)
                if item.accel_path:
                    menuitem.set_accel_path(item.accel_path)
                self.menu_buttons[item.id] = menuitem
            elif not item and previous:
                menuitem = gtk.SeparatorMenuItem()
            else:
                continue
            previous = item
            menu_form.add(menuitem)

        menu_form.show_all()
        return menu_form

    def create_toolbar(self, toolbars):
        gtktoolbar = gtk.Toolbar()
        option = CONFIG['client.toolbar']
        if option == 'default':
            gtktoolbar.set_style(False)
        elif option == 'both':
            gtktoolbar.set_style(gtk.TOOLBAR_BOTH)
        elif option == 'text':
            gtktoolbar.set_style(gtk.TOOLBAR_TEXT)
        elif option == 'icons':
            gtktoolbar.set_style(gtk.TOOLBAR_ICONS)
        self.create_base_toolbar(gtktoolbar)
        return gtktoolbar
