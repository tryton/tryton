#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import os
import re
import gettext
import tryton.common as common
from tryton.config import CONFIG, TRYTON_ICON, PIXMAPS_DIR
import tryton.rpc as rpc
from tryton.gui.window.dbcreate import DBCreate

_ = gettext.gettext


class DBLogin(object):
    def __init__(self, parent):
        self.dialog = gtk.Dialog(title=_('Login'), parent=parent,
            flags=gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT)
        self.dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.dialog.set_has_separator(True)
        self.dialog.set_icon(TRYTON_ICON)

        tooltips = common.Tooltips()
        button_cancel = gtk.Button(_('_Cancel'))
        img_cancel = gtk.Image()
        img_cancel.set_from_stock('tryton-cancel', gtk.ICON_SIZE_BUTTON)
        button_cancel.set_image(img_cancel)
        tooltips.set_tip(button_cancel, _('Cancel connection to the Tryton server'))
        self.dialog.add_action_widget(button_cancel, gtk.RESPONSE_CANCEL)
        self.button_connect = gtk.Button(_('C_onnect'))
        img_connect = gtk.Image()
        img_connect.set_from_stock('tryton-connect', gtk.ICON_SIZE_BUTTON)
        self.button_connect.set_image(img_connect)
        self.button_connect.set_flags(gtk.CAN_DEFAULT)
        tooltips.set_tip(self.button_connect, _('Connect the Tryton server'))
        self.dialog.add_action_widget(self.button_connect, gtk.RESPONSE_OK)
        self.dialog.set_default_response(gtk.RESPONSE_OK)
        image = gtk.Image()
        image.set_from_file(os.path.join(PIXMAPS_DIR, 'tryton.png'))
        image.set_alignment(0.5, 1)
        ebox = gtk.EventBox()
        ebox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#1b2019"))
        ebox.add(image)
        self.dialog.vbox.pack_start(ebox)
        table_main = gtk.Table(4, 3, False)
        table_main.set_border_width(10)
        table_main.set_row_spacings(3)
        table_main.set_col_spacings(3)
        self.dialog.vbox.pack_start(table_main, True, True, 0)
        vbox_combo = gtk.VBox()
        self.hbox_combo = gtk.HBox()
        self.combo_database = gtk.ComboBox()
        self.combo_label = gtk.Label()
        self.combo_label.set_use_markup(True)
        self.combo_label.set_alignment(0, 0.5)
        self.combo_button = gtk.Button(_('C_reate'))
        self.combo_button.connect('clicked', self.db_create)
        image = gtk.Image()
        image.set_from_stock('tryton-new', gtk.ICON_SIZE_BUTTON)
        self.combo_button.set_image(image)
        vbox_combo.pack_start(self.combo_database, True, True, 0)
        self.hbox_combo.pack_start(self.combo_label, True, True, 0)
        self.hbox_combo.pack_start(self.combo_button, False, False, 0)
        vbox_combo.pack_start(self.hbox_combo, True, True, 0)
        table_main.attach(vbox_combo, 1, 3, 1, 2)
        self.entry_password = gtk.Entry()
        self.entry_password.set_visibility(False)
        self.entry_password.set_activates_default(True)
        table_main.attach(self.entry_password, 1, 3, 3, 4)
        self.entry_login = gtk.Entry()
        self.entry_login.set_activates_default(True)
        table_main.attach(self.entry_login, 1, 3, 2, 3)
        self.label_server = gtk.Label()
        self.label_server.set_text(_("Server:"))
        self.label_server.set_alignment(1, 0.5)
        self.label_server.set_padding(3, 3)
        table_main.attach(self.label_server, 0, 1, 0, 1, xoptions=gtk.FILL)
        label_database = gtk.Label()
        label_database.set_text(_("Database:"))
        label_database.set_alignment(1, 0.5)
        label_database.set_padding(3, 3)
        table_main.attach(label_database, 0, 1, 1, 2, xoptions=gtk.FILL)
        self.entry_server = gtk.Entry()
        table_main.attach(self.entry_server, 1, 2, 0, 1)
        self.entry_server.set_sensitive(False)
        self.entry_server.unset_flags(gtk.CAN_FOCUS)
        self.entry_server.set_editable(False)
        self.entry_server.set_text("localhost")
        self.entry_server.set_activates_default(True)
        self.entry_server.set_width_chars(16)
        self.button_server = gtk.Button(label=_("C_hange"), stock=None,
            use_underline=True)
        tooltips.set_tip(self.button_server,
                _('Configure the Tryton server connection'))
        table_main.attach(self.button_server, 2, 3, 0, 1, xoptions=gtk.FILL)
        label_password = gtk.Label(str = _("Password:"))
        label_password.set_justify(gtk.JUSTIFY_RIGHT)
        label_password.set_alignment(1, 0.5)
        label_password.set_padding(3, 3)
        table_main.attach(label_password, 0, 1, 3, 4, xoptions=gtk.FILL)
        label_username = gtk.Label(str = _("User name:"))
        label_username.set_alignment(1, 0.5)
        label_username.set_padding(3, 3)
        table_main.attach(label_username, 0, 1, 2, 3, xoptions=gtk.FILL)
        self.entry_password.grab_focus()

    @staticmethod
    def refreshlist(widget, db_widget, label, button, host, port,
            butconnect=None):
        res = common.refresh_dblist(db_widget, host, port)
        if res is None or res == -1:
            if res is None:
                label.set_label('<b>' + _('Could not connect to server!') + \
                        '</b>')
            else:
                label.set_label('<b>' + \
                        _('Incompatible version of the server!') + '</b>')
            db_widget.hide()
            label.show()
            button.hide()
            if butconnect:
                butconnect.set_sensitive(False)
        elif res == 0:
            label.set_label('<b>' + \
                    _('No database found, you must create one!') + '</b>')
            db_widget.hide()
            label.show()
            button.show()
            if butconnect:
                butconnect.set_sensitive(False)
        else:
            label.hide()
            button.hide()
            db_widget.show()
            if butconnect:
                butconnect.set_sensitive(True)
        return res

    @staticmethod
    def refreshlist_ask(widget, server_widget, db_widget, label, button,
            butconnect=False, host=False, port=0, parent=None):
        res = common.request_server(server_widget, parent) or (host, port)
        if not res:
            return False
        host, port = res
        res = DBLogin.refreshlist(widget, db_widget, label, button, host, port,
                butconnect)
        if res:
            CONFIG['login.server'] = host
            CONFIG['login.port'] = port
        return res

    def db_create(self, widget):
        dia = DBCreate()
        dia.run(self.dialog)
        host = CONFIG['login.server']
        port = int(CONFIG['login.port'])
        DBLogin.refreshlist(None, self.combo_database,
                self.combo_label, self.combo_button, host, port,
                self.button_connect)
        return

    def run(self, dbname, parent):
        self.dialog.show_all()
        self.combo_label.hide()
        self.combo_button.hide()

        if not CONFIG['login.host']:
            self.label_server.hide()
            self.entry_server.hide()
            self.button_server.hide()

        host = CONFIG['login.server']
        port = int(CONFIG['login.port'])

        url = '%s:%d' % (host, port)
        self.entry_server.set_text(url)
        self.entry_login.set_text(CONFIG['login.login'])

        # construct the list of available db and select the last one used
        liststore = gtk.ListStore(str)
        self.combo_database.set_model(liststore)
        cell = gtk.CellRendererText()
        self.combo_database.pack_start(cell, True)
        self.combo_database.add_attribute(cell, 'text', 0)

        res = self.refreshlist(None, self.combo_database, self.combo_label,
                self.combo_button, host, port, self.button_connect)

        self.button_server.connect_after('clicked', DBLogin.refreshlist_ask,
                self.entry_server, self.combo_database, self.combo_label,
                self.combo_button, self.button_connect, host, port, self.dialog)
        if dbname:
            i = liststore.get_iter_root()
            while i:
                if liststore.get_value(i, 0)==dbname:
                    self.combo_database.set_active_iter(i)
                    break
                i = liststore.iter_next(i)

        # Reshow dialog for gtk-quarks
        self.dialog.reshow_with_initial_size()
        res = self.dialog.run()
        url_m = re.match('^([\w.:\-\d]+):(\d{1,5})$',
                self.entry_server.get_text() or '')
        if url_m:
            CONFIG['login.server'] = url_m.group(1)
            CONFIG['login.login'] = self.entry_login.get_text()
            CONFIG['login.port'] = url_m.group(2)
            CONFIG['login.db'] = self.combo_database.get_active_text()
            result = (self.entry_login.get_text(),
                self.entry_password.get_text(), url_m.group(1),
                int(url_m.group(2)), self.combo_database.get_active_text())
        else:
            parent.present()
            self.dialog.destroy()
            raise Exception('QueryCanceled')
        if res != gtk.RESPONSE_OK:
            parent.present()
            self.dialog.destroy()
            rpc.logout()
            from tryton.gui.main import Main
            Main.get_main().refresh_ssl()
            raise Exception('QueryCanceled')
        parent.present()
        self.dialog.destroy()
        return result

