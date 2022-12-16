# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gettext
import gtk
import pango
from gi.repository import Gtk

import tryton.common as common
from tryton.config import CONFIG
from tryton.gui import Main
from .infobar import InfoBar

_ = gettext.gettext


class ToolbarItem(object):
    def __init__(self, id, label,
            tooltip=None, icon_name=None, accel_path=None, toggle=False):
        self.id = id
        self.label = label
        self.tooltip = tooltip
        self.icon_name = icon_name
        self.accel_path = accel_path
        self.toggle = toggle

    @property
    def menu(self):
        return True

    @property
    def toolbar(self):
        return bool(self.tooltip)


class TabContent(InfoBar):

    def __init__(self, **attributes):
        super(TabContent, self).__init__()
        self.attributes = attributes.copy()

    @property
    def menu_def(self):
        return [
            ToolbarItem(
                id='switch',
                label=_("_Switch View"),
                tooltip=_("Switch View"),
                icon_name='tryton-switch',
                accel_path='<tryton>/Form/Switch View'),
            ToolbarItem(
                id='previous',
                label=_("_Previous"),
                tooltip=_("Previous Record"),
                icon_name='tryton-back',
                accel_path='<tryton>/Form/Previous'),
            ToolbarItem(
                id='next',
                label=_("_Next"),
                tooltip=_("Next Record"),
                icon_name='tryton-forward',
                accel_path='<tryton>/Form/Next'),
            ToolbarItem(
                id='search',
                label=_("_Search"),
                icon_name='tryton-search',
                accel_path='<tryton>/Form/Search'),
            None,
            ToolbarItem(
                id='new',
                label=_("_New"),
                tooltip=_("Create a new record"),
                icon_name='tryton-create',
                accel_path='<tryton>/Form/New'),
            ToolbarItem(
                id='save',
                label=_("_Save"),
                tooltip=_("Save this record"),
                icon_name='tryton-save',
                accel_path='<tryton>/Form/Save'),
            ToolbarItem(
                id='reload',
                label=_("_Reload/Undo"),
                tooltip=_("Reload/Undo"),
                icon_name='tryton-refresh',
                accel_path='<tryton>/Form/Reload'),
            ToolbarItem(
                id='copy',
                label=_("_Duplicate"),
                icon_name='tryton-copy',
                accel_path='<tryton>/Form/Duplicate'),
            ToolbarItem(
                id='remove',
                label=_("_Delete..."),
                icon_name='tryton-delete',
                accel_path='<tryton>/Form/Delete'),
            None,
            ToolbarItem(
                id='logs',
                label=_("View _Logs..."),
                icon_name='tryton-log'),
            ToolbarItem(
                id='revision' if self.model in common.MODELHISTORY else None,
                label=_("Show revisions..."),
                icon_name='tryton-history'),
            None,
            ToolbarItem(
                id='attach',
                label=_("A_ttachments..."),
                tooltip=_("Add an attachment to the record"),
                icon_name='tryton-attach',
                accel_path='<tryton>/Form/Attachments',
                toggle=True),
            ToolbarItem(
                id='note',
                label=_("_Notes..."),
                tooltip=_("Add a note to the record"),
                icon_name='tryton-note',
                accel_path='<tryton>/Form/Notes'),
            ToolbarItem(
                id='action',
                label=_("_Actions..."),
                icon_name='tryton-launch',
                accel_path='<tryton>/Form/Actions'),
            ToolbarItem(
                id='relate',
                label=_("_Relate..."),
                icon_name='tryton-link',
                accel_path='<tryton>/Form/Relate'),
            None,
            ToolbarItem(
                id='print_open',
                label=_("_Report..."),
                icon_name='tryton-open',
                accel_path='<tryton>/Form/Report'),
            ToolbarItem(
                id='print_email',
                label=_("_E-Mail..."),
                icon_name='tryton-email',
                accel_path='<tryton>/Form/Email'),
            ToolbarItem(
                id='print',
                label=_("_Print..."),
                icon_name='tryton-print',
                accel_path='<tryton>/Form/Print'),
            None,
            ToolbarItem(
                id='export',
                label=_("_Export Data..."),
                icon_name='tryton-export',
                accel_path='<tryton>/Form/Export Data'),
            ToolbarItem(
                id='import',
                label=_("_Import Data..."),
                icon_name='tryton-import',
                accel_path='<tryton>/Form/Import Data'),
            ToolbarItem(
                id='copy_url',
                label=_("Copy _URL..."),
                icon_name='tryton-public',
                accel_path='<tryton>/Form/Copy URL'),
            None,
            ToolbarItem(
                id='win_close',
                label=_("_Close Tab"),
                icon_name='tryton-close',
                accel_path='<tryton>/Form/Close'),
            ]

    def create_tabcontent(self):
        self.buttons = {}
        self.menu_buttons = {}
        self.tooltips = common.Tooltips()
        self.accel_group = Main().accel_group

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
        title.set_label(common.ellipsize(self.name, 80))
        title.set_padding(10, 4)
        title.set_alignment(0.0, 0.5)
        title.set_size_request(0, -1)  # Allow overflow
        title.set_max_width_chars(1)
        title.set_ellipsize(pango.ELLIPSIZE_END)
        title.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#000000"))
        title.show()

        menu = Gtk.MenuButton.new()
        menu.set_relief(Gtk.ReliefStyle.NONE)
        menu.set_popup(self.set_menu_form())
        menu.show()

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
        frame_menu.add(menu)
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
                if item.toggle:
                    toolitem = gtk.ToggleToolButton()
                    toolitem.connect('toggled', callback)
                else:
                    toolitem = gtk.ToolButton()
                    toolitem.connect('clicked', callback)
                toolitem.set_icon_widget(
                    common.IconFactory.get_image(
                        item.icon_name, gtk.ICON_SIZE_LARGE_TOOLBAR))
                toolitem.set_label(item.label)
                toolitem.set_use_underline(True)
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

                if item.icon_name:
                    menuitem.set_image(
                        common.IconFactory.get_image(
                            item.icon_name, gtk.ICON_SIZE_MENU))
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

    def compare(self, model, attributes):
        return False
