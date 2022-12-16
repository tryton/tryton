# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import gtk
import gobject
import gettext
import tryton.common as common
from tryton.config import CONFIG
import tryton.rpc as rpc

_ = gettext.gettext


class DBRestore(object):
    def event_show_button_restore(self, widget, event, data=None):
        """
        This event method decide by rules if the restore button will be
        sensitive or insensitive. The general rule is, all given fields
        must be filled, then the restore button is set to sensitive. This
        event method doesn't check the valid of single entrys.
        """
        if (self.entry_server_url.get_text() != ""
                and self.entry_server_password.get_text() != ""
                and self.entry_server_url.get_text() != ""
                and self.entry_db_name.get_text() != ""):
            widget.unset_flags(gtk.HAS_DEFAULT)
            self.button_restore.set_sensitive(True)
            self.button_restore.set_flags(gtk.CAN_DEFAULT)
            self.button_restore.set_flags(gtk.HAS_DEFAULT)
            self.button_restore.set_flags(gtk.CAN_FOCUS)
            self.button_restore.set_flags(gtk.RECEIVES_DEFAULT)
            self.button_restore.grab_default()
        else:
            self.button_restore.set_sensitive(False)

    def entry_insert_text(self, entry, new_text, new_text_length, position):
        """
        This event method checks each text input for the PostgreSQL
        database name. It allows the following rules:
        - Allowed characters are alpha-nummeric [A-Za-z0-9] and underscore (_)
        - First character must be a letter
        """
        if new_text.isalnum() or new_text == '_':
            _hid = entry.get_data('handlerid')
            entry.handler_block(_hid)
            _pos = entry.get_position()
            if _pos == 0 and not new_text.isalpha():
                new_text = ""
            _pos = entry.insert_text(new_text, _pos)
            entry.handler_unblock(_hid)

            def _move_cursor():
                if not entry.props.window:
                    return
                with gtk.gdk.lock:
                    entry.set_position(_pos)
                    return False
            gobject.idle_add(_move_cursor)
        entry.stop_emission("insert-text")

    def __init__(self, filename=None):
        """
        Database restore widget
        """
        self.parent = common.get_toplevel_window()
        self.dialog = gtk.Dialog(title=_("Restore Database"),
            parent=self.parent, flags=gtk.DIALOG_MODAL
            | gtk.WIN_POS_CENTER_ON_PARENT)
        vbox = gtk.VBox()
        self.dialog.vbox.pack_start(vbox)
        self.tooltips = common.Tooltips()
        table = gtk.Table(6, 3, False)
        table.set_border_width(9)
        table.set_row_spacings(3)
        table.set_col_spacings(3)
        vbox.pack_start(table)
        self.label_server_url = gtk.Label(_("Server Connection:"))
        self.label_server_url.set_size_request(117, -1)
        self.label_server_url.set_alignment(1, 0.5)
        self.label_server_url.set_padding(3, 3)
        table.attach(self.label_server_url, 0, 1, 0, 1, yoptions=gtk.FILL)
        self.entry_server_url = gtk.Entry()
        self.entry_server_url.set_sensitive(False)
        self.entry_server_url.unset_flags(gtk.CAN_FOCUS)
        self.entry_server_url.set_editable(False)
        self.entry_server_url.set_activates_default(True)
        self.entry_server_url.set_width_chars(16)
        self.label_server_url.set_mnemonic_widget(self.entry_server_url)
        self.tooltips.set_tip(self.entry_server_url, _("This is the URL of "
                "the server. Use server 'localhost' and port '8000' if "
                "the server is installed on this computer. Click on "
                "'Change' to change the address."))
        table.attach(self.entry_server_url, 1, 2, 0, 1, yoptions=gtk.FILL)
        self.button_server_change = gtk.Button(_("C_hange"), stock=None,
            use_underline=True)
        img_button_server_change = gtk.Image()
        img_button_server_change.set_from_stock(
            'tryton-preferences-system', gtk.ICON_SIZE_BUTTON)
        self.button_server_change.set_image(img_button_server_change)
        self.tooltips.set_tip(self.button_server_change, _("Setup the "
                "server connection..."))
        table.attach(self.button_server_change, 2, 3, 0, 1, yoptions=gtk.FILL)
        self.label_server_password = gtk.Label(_("Tryton Server Password:"))
        self.label_server_password.set_justify(gtk.JUSTIFY_RIGHT)
        self.label_server_password.set_alignment(1, 0.5)
        self.label_server_password.set_padding(3, 3)
        table.attach(self.label_server_password, 0, 1, 1, 2, yoptions=gtk.FILL)
        self.entry_server_password = gtk.Entry()
        self.entry_server_password.set_visibility(False)
        self.entry_server_password.set_activates_default(True)
        self.entry_server_password.set_width_chars(16)
        self.label_server_password.set_mnemonic_widget(
            self.entry_server_password)
        self.tooltips.set_tip(self.entry_server_password, _("This is the "
                "password of the Tryton server. It doesn't belong to a "
                "real user. This password is usually defined in the trytond "
                "configuration."))
        table.attach(self.entry_server_password, 1, 3, 1, 2, yoptions=gtk.FILL)
        self.hseparator = gtk.HSeparator()
        table.attach(self.hseparator, 0, 3, 2, 3, yoptions=gtk.FILL)
        label_filename = gtk.Label()
        label_filename.set_markup(_("File to Restore:"))
        label_filename.set_alignment(1, 0.5)
        table.attach(label_filename, 0, 1, 3, 4, yoptions=gtk.FILL)
        entry_filename = gtk.Label()
        entry_filename.set_markup("<tt>" + filename + "</tt>")
        table.attach(entry_filename, 1, 3, 3, 4, yoptions=gtk.FILL)
        self.entry_db_name = gtk.Entry()
        self.entry_db_name.set_visibility(True)
        self.entry_db_name.set_activates_default(True)
        self.entry_db_name.set_width_chars(16)
        self.entry_db_name.set_max_length(63)
        handlerid = self.entry_db_name.connect("insert-text",
            self.entry_insert_text)
        self.entry_db_name.set_data('handlerid', handlerid)
        self.tooltips.set_tip(self.entry_db_name, _("Choose the name of "
                "the database to be restored.\n"
                "Allowed characters are alphanumerical or _ (underscore)\n"
                "You need to avoid all accents, space or special "
                "characters! \nExample: tryton"))
        table.attach(self.entry_db_name, 1, 3, 4, 5, yoptions=gtk.FILL)
        label_db_name = gtk.Label(_("New Database Name:"))
        label_db_name.set_alignment(1, 0.5)
        label_db_name.set_mnemonic_widget(self.entry_db_name)
        table.attach(label_db_name, 0, 1, 4, 5, yoptions=gtk.FILL)
        label_db_update = gtk.Label(_('Update Database:'))
        label_db_update.set_alignment(1, 0.5)
        table.attach(label_db_update, 0, 1, 5, 6, yoptions=gtk.FILL)
        self.check_update = gtk.CheckButton()
        label_db_update.set_mnemonic_widget(self.check_update)
        self.tooltips.set_tip(self.check_update, _('Check for an automatic '
                'database update after restoring a database from a previous '
                'Tryton version.'))
        self.check_update.set_active(True)
        table.attach(self.check_update, 1, 3, 5, 6, yoptions=gtk.FILL)
        # Buttons and events
        self.dialog.connect("key-press-event",
            self.event_show_button_restore)
        self.dialog.add_button("gtk-cancel",
            gtk.RESPONSE_CANCEL)
        self.button_restore = gtk.Button(_('Restore'))
        self.button_restore.set_flags(gtk.CAN_DEFAULT)
        self.button_restore.set_flags(gtk.HAS_DEFAULT)
        self.button_restore.set_sensitive(False)
        img_restore = gtk.Image()
        img_restore.set_from_stock('tryton-folder-saved-search',
            gtk.ICON_SIZE_BUTTON)
        self.button_restore.set_image(img_restore)
        self.tooltips.set_tip(self.button_restore,
            _('Restore the database from file.'))
        self.dialog.add_action_widget(self.button_restore, gtk.RESPONSE_OK)
        self.dialog.set_default_response(gtk.RESPONSE_OK)

        self.entry_server_password.grab_focus()

    def run(self):
        """
        Database Restore widget run part
        """
        self.dialog.show_all()

        self.entry_server_url.set_text('%(login.server)s:%(login.port)s' %
            CONFIG)
        while True:
            database = False
            passwd = False
            url = False
            update = False
            # TODO: This needs to be unified with the other widgets
            self.button_server_change.connect_after('clicked',
                lambda a, b: common.request_server(b),
                self.entry_server_url)
            res = self.dialog.run()
            if res == gtk.RESPONSE_OK:
                database = self.entry_db_name.get_text()
                url = self.entry_server_url.get_text()
                passwd = self.entry_server_password.get_text()
                update = self.check_update.get_active()
                break
            else:
                self.dialog.destroy()
                rpc.logout()
                break
        self.parent.present()
        self.dialog.destroy()

        return url, database, passwd, update
