# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import gtk
import gobject
import gettext
import tryton.common as common
from tryton.config import CONFIG, TRYTON_ICON
import tryton.rpc as rpc

_ = gettext.gettext


class DBBackupDrop(object):
    """
    Widget for database backup and drop.
    """
    def refreshlist(self, host, port):
        self.combo_database.hide()
        self.combo_database_label.hide()
        self.combo_database_entry.hide()
        dbprogress = common.DBProgress(host, port)

        def callback(dbs):
            if dbs is None:
                self.combo_database_label.set_label('<b>' +
                    _('Could not connect to server!') + '</b>')
                self.combo_database_label.show()
            elif dbs == -1:
                self.combo_database_label.set_label('<b>' +
                    _('This client version is not compatible '
                        'with the server!')
                    + '</b>')
                self.combo_database_label.show()
            elif dbs == -2:
                self.combo_database_entry.show()
                self.combo_database_entry.grab_focus()
            elif dbs == 0:
                self.combo_database_label.set_label('<b>'
                    + _('No database found, you must create one!') + '</b>')
                self.combo_database_label.show()
            else:
                self.combo_database.show()
        dbprogress.update(self.combo_database, self.db_progressbar, callback)

    def refreshlist_ask(self, widget=None):
        res = common.request_server(self.entry_server_connection)
        if not res:
            return None
        host, port = res
        self.refreshlist(host, port)
        return (host, port)

    def event_show_button_ok(self, widget, event, data=None):
        """
        This event method decide by rules if the Create button will be
        sensitive or insensitive. The general rule is, all given fields
        must be filled, then the Create button is set to sensitive. This
        event method doesn't check the valid of single entrys.
        """
        if (self.entry_server_connection.get_text() != ""
                and (self.combo_database.get_active_text() != ""
                    or self.combo_database_entry.get_text() != "")
                and self.entry_serverpasswd.get_text() != ""):
            widget.unset_flags(gtk.HAS_DEFAULT)
            self.button_ok.set_sensitive(True)
            self.button_ok.set_flags(gtk.CAN_DEFAULT)
            self.button_ok.set_flags(gtk.HAS_DEFAULT)
            self.button_ok.set_flags(gtk.CAN_FOCUS)
            self.button_ok.set_flags(gtk.RECEIVES_DEFAULT)
            self.button_ok.grab_default()
        else:
            self.button_ok.set_sensitive(False)

    def __init__(self, function=None):
        # This widget is used for creating and droping a database!
        if function == "backup":
            dialog_title = _("Backup a database")
            button_ok_text = _("Backup")
            button_ok_tooltip = _("Backup the choosen database.")
            button_ok_icon = "tryton-save-as"
            label_subtitle_text = _("Choose a Tryton database to backup:")
        elif function == "drop":
            dialog_title = _("Delete a database")
            button_ok_text = _("Delete")
            button_ok_tooltip = _("Delete the choosen database.")
            button_ok_icon = "tryton-delete"
            label_subtitle_text = _("Choose a Tryton database to delete:")
        else:
            return None

        self.parent = common.get_toplevel_window()
        self.dialog = gtk.Dialog(title=dialog_title, parent=self.parent,
            flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
            | gtk.WIN_POS_CENTER_ON_PARENT)
        self.dialog.set_has_separator(True)
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.connect("key-press-event", self.event_show_button_ok)
        self.tooltips = common.Tooltips()
        self.dialog.add_button("gtk-cancel",
            gtk.RESPONSE_CANCEL)
        self.button_ok = gtk.Button(button_ok_text)
        self.button_ok.set_flags(gtk.CAN_DEFAULT)
        self.button_ok.set_flags(gtk.HAS_DEFAULT)
        self.button_ok.set_sensitive(False)
        img_connect = gtk.Image()
        img_connect.set_from_stock(button_ok_icon, gtk.ICON_SIZE_BUTTON)
        self.button_ok.set_image(img_connect)
        self.tooltips.set_tip(self.button_ok, button_ok_tooltip)
        self.dialog.add_action_widget(self.button_ok, gtk.RESPONSE_OK)
        self.dialog.set_default_response(gtk.RESPONSE_OK)
        self.dialog_vbox = gtk.VBox()

        table = gtk.Table(5, 3, False)
        table.set_border_width(10)
        table.set_row_spacings(3)
        table.set_col_spacings(3)
        self.dialog_vbox.pack_start(table, True, False, 0)

        label_subtitle = gtk.Label()
        label_subtitle.set_markup("<b>" + label_subtitle_text + "</b>")
        label_subtitle.set_justify(gtk.JUSTIFY_LEFT)
        label_subtitle.set_alignment(0, 1)
        label_subtitle.set_padding(9, 5)
        table.attach(label_subtitle, 0, 3, 0, 1, yoptions=False,
            xoptions=gtk.FILL)

        hseparator = gtk.HSeparator()
        table.attach(hseparator, 0, 3, 1, 2, yoptions=False)

        self.label_server = gtk.Label(_("Server Connection:"))
        self.label_server.set_alignment(1, 0.5)
        self.label_server.set_padding(3, 3)
        table.attach(self.label_server, 0, 1, 2, 3, yoptions=False,
            xoptions=gtk.FILL)

        self.entry_server_connection = gtk.Entry()
        self.entry_server_connection.set_sensitive(False)
        self.entry_server_connection.unset_flags(gtk.CAN_FOCUS)
        self.entry_server_connection.set_editable(False)
        self.label_server.set_mnemonic_widget(self.entry_server_connection)
        self.tooltips.set_tip(self.entry_server_connection, _("This is the "
                "URL of the server. Use server 'localhost' and port '8000' "
                "if the server is installed on this computer. "
                "Click on 'Change' to change the address."))
        table.attach(self.entry_server_connection, 1, 2, 2, 3,
                yoptions=gtk.FILL)

        self.button_server_change = gtk.Button(_("C_hange"), stock=None,
            use_underline=True)
        img_button_server_change = gtk.Image()
        img_button_server_change.set_from_stock('tryton-preferences-system',
            gtk.ICON_SIZE_BUTTON)
        self.button_server_change.set_image(img_button_server_change)
        table.attach(self.button_server_change, 2, 3, 2, 3, yoptions=False)

        self.label_database = gtk.Label()
        self.label_database.set_text(_("Database:"))
        self.label_database.set_alignment(1, 0.5)
        self.label_database.set_padding(3, 3)
        table.attach(self.label_database, 0, 1, 3, 4, yoptions=False,
            xoptions=gtk.FILL)

        vbox_combo = gtk.VBox(homogeneous=True)
        self.combo_database = gtk.ComboBox()
        dbstore = gtk.ListStore(gobject.TYPE_STRING)
        cell = gtk.CellRendererText()
        self.combo_database.pack_start(cell, True)
        self.combo_database.add_attribute(cell, 'text', 0)
        self.combo_database.set_model(dbstore)
        self.db_progressbar = gtk.ProgressBar()
        self.combo_database_label = gtk.Label()
        self.combo_database_label.set_use_markup(True)
        self.combo_database_label.set_alignment(0, 1)
        self.combo_database_entry = gtk.Entry()
        vbox_combo.pack_start(self.combo_database)
        vbox_combo.pack_start(self.combo_database_label)
        vbox_combo.pack_start(self.db_progressbar)
        vbox_combo.pack_start(self.combo_database_entry)
        width, height = 0, 0
        # Compute size_request of box in order to prevent "form jumping"
        for child in vbox_combo.get_children():
            cwidth, cheight = child.size_request()
            width, height = max(width, cwidth), max(height, cheight)
        vbox_combo.set_size_request(width, height)
        table.attach(vbox_combo, 1, 3, 3, 4, yoptions=False)

        self.label_serverpasswd = gtk.Label(_("Tryton Server Password:"))
        self.label_serverpasswd.set_justify(gtk.JUSTIFY_RIGHT)
        self.label_serverpasswd.set_alignment(1, 0.5)
        self.label_serverpasswd.set_padding(3, 3)
        table.attach(self.label_serverpasswd, 0, 1, 4, 5, yoptions=False,
            xoptions=gtk.FILL)

        self.entry_serverpasswd = gtk.Entry()
        self.entry_serverpasswd.set_visibility(False)
        self.entry_serverpasswd.set_activates_default(True)
        self.label_serverpasswd.set_mnemonic_widget(self.entry_serverpasswd)
        self.tooltips.set_tip(self.entry_serverpasswd, _("This is the "
                "password of the Tryton server. It doesn't belong to a "
                "real user. This password is usually defined in the trytond "
                "configuration."))
        table.attach(self.entry_serverpasswd, 1, 3, 4, 5, yoptions=False)

        self.entry_serverpasswd.grab_focus()
        self.dialog.vbox.pack_start(self.dialog_vbox)

    def run(self):
        self.dialog.set_default_response(gtk.RESPONSE_OK)
        self.dialog.show_all()

        self.entry_server_connection.set_text(
            '%(login.server)s:%(login.port)s' % CONFIG)
        self.refreshlist(CONFIG['login.server'], CONFIG['login.port'])

        self.button_server_change.connect_after('clicked',
            self.refreshlist_ask)

        while True:
            database = False
            url = False
            passwd = False
            res = self.dialog.run()
            if res == gtk.RESPONSE_OK:
                if self.combo_database.get_visible():
                    database = self.combo_database.get_active_text()
                elif self.combo_database_entry.get_visible():
                    database = self.combo_database_entry.get_text()
                else:
                    continue
                url = self.entry_server_connection.get_text()
                passwd = self.entry_serverpasswd.get_text()
                break
            if res != gtk.RESPONSE_OK:
                self.dialog.destroy()
                rpc.logout()
                break
        self.parent.present()
        self.dialog.destroy()

        return (url, database, passwd)
