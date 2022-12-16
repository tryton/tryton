# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import configparser
import gtk
import gobject
import os
import gettext
import threading
import logging

from gi.repository import Gtk

from tryton import __version__
import tryton.common as common
from tryton.config import CONFIG, TRYTON_ICON, PIXMAPS_DIR, get_config_dir
import tryton.rpc as rpc
from tryton.common.underline import set_underline

_ = gettext.gettext
logger = logging.getLogger(__name__)


class DBListEditor(object):

    def __init__(self, parent, profile_store, profiles, callback):
        self.profiles = profiles
        self.current_database = None
        self.old_profile, self.current_profile = None, None
        self.db_cache = None
        self.updating_db = False

        # GTK Stuffs
        self.parent = parent
        self.dialog = gtk.Dialog(title=_('Profile Editor'), parent=parent,
            flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        self.ok_button = self.dialog.add_button(
            set_underline(_("Close")), gtk.RESPONSE_CLOSE)
        self.dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.dialog.set_icon(TRYTON_ICON)

        tooltips = common.Tooltips()

        hpaned = gtk.HPaned()
        vbox_profiles = gtk.VBox(homogeneous=False, spacing=6)
        self.cell = gtk.CellRendererText()
        self.cell.set_property('editable', True)
        self.cell.connect('editing-started', self.edit_started)
        self.profile_tree = gtk.TreeView()
        self.profile_tree.set_model(profile_store)
        self.profile_tree.insert_column_with_attributes(-1, _('Profile'),
            self.cell, text=0)
        self.profile_tree.connect('cursor-changed', self.profile_selected)
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(self.profile_tree)
        self.add_button = gtk.Button()
        self.add_button.set_image(common.IconFactory.get_image(
                'tryton-add', gtk.ICON_SIZE_BUTTON))
        tooltips.set_tip(self.add_button, _("Add new profile"))
        self.add_button.connect('clicked', self.profile_create)
        self.remove_button = gtk.Button()
        self.remove_button.set_image(common.IconFactory.get_image(
                'tryton-remove', gtk.ICON_SIZE_BUTTON))
        tooltips.set_tip(self.remove_button, _("Remove selected profile"))
        self.remove_button.get_style_context().add_class(
            Gtk.STYLE_CLASS_DESTRUCTIVE_ACTION)
        self.remove_button.connect('clicked', self.profile_delete)
        bbox = Gtk.ButtonBox()
        bbox.pack_start(self.remove_button)
        bbox.pack_start(self.add_button)
        vbox_profiles.pack_start(scroll, expand=True, fill=True)
        vbox_profiles.pack_start(bbox, expand=False, fill=True)
        hpaned.add1(vbox_profiles)

        table = gtk.Table(4, 2, homogeneous=False)
        table.set_row_spacings(3)
        table.set_col_spacings(3)
        host = gtk.Label(set_underline(_('Host:')))
        host.set_use_underline(True)
        host.set_alignment(1, 0.5)
        host.set_padding(3, 3)
        self.host_entry = gtk.Entry()
        self.host_entry.connect('focus-out-event', self.display_dbwidget)
        self.host_entry.connect('changed', self.update_profiles, 'host')
        self.host_entry.set_activates_default(True)
        host.set_mnemonic_widget(self.host_entry)
        table.attach(host, 0, 1, 1, 2, yoptions=False, xoptions=gtk.FILL)
        table.attach(self.host_entry, 1, 2, 1, 2, yoptions=False)
        database = gtk.Label(set_underline(_('Database:')))
        database.set_use_underline(True)
        database.set_alignment(1, 0.5)
        database.set_padding(3, 3)
        self.database_entry = gtk.Entry()
        self.database_entry.connect('changed', self.dbentry_changed)
        self.database_entry.connect('changed', self.update_profiles,
            'database')
        self.database_entry.set_activates_default(True)
        self.database_label = gtk.Label()
        self.database_label.set_use_markup(True)
        self.database_label.set_alignment(0, 0.5)
        self.database_combo = gtk.ComboBox()
        dbstore = gtk.ListStore(gobject.TYPE_STRING)
        cell = gtk.CellRendererText()
        self.database_combo.pack_start(cell, True)
        self.database_combo.add_attribute(cell, 'text', 0)
        self.database_combo.set_model(dbstore)
        self.database_combo.connect('changed', self.dbcombo_changed)
        self.database_progressbar = gtk.ProgressBar()
        self.database_progressbar.set_text(_('Fetching databases list'))
        db_box = gtk.VBox(homogeneous=True)
        db_box.pack_start(self.database_entry)
        db_box.pack_start(self.database_combo)
        db_box.pack_start(self.database_label)
        db_box.pack_start(self.database_progressbar)
        # Compute size_request of box in order to prevent "form jumping"
        width, height = 0, 0
        for child in db_box.get_children():
            cwidth, cheight = child.size_request()
            width, height = max(width, cwidth), max(height, cheight)
        db_box.set_size_request(width, height)
        table.attach(database, 0, 1, 2, 3, yoptions=False, xoptions=gtk.FILL)
        table.attach(db_box, 1, 2, 2, 3, yoptions=False)
        username = gtk.Label(set_underline(_('Username:')))
        username.set_use_underline(True)
        username.set_alignment(1, 0.5)
        username.set_padding(3, 3)
        self.username_entry = gtk.Entry()
        self.username_entry.connect('changed', self.update_profiles,
            'username')
        username.set_mnemonic_widget(self.username_entry)
        self.username_entry.set_activates_default(True)
        table.attach(username, 0, 1, 3, 4, yoptions=False, xoptions=gtk.FILL)
        table.attach(self.username_entry, 1, 2, 3, 4, yoptions=False)
        hpaned.add2(table)
        hpaned.set_position(250)

        self.dialog.vbox.pack_start(hpaned)
        self.dialog.set_default_size(640, 350)
        self.dialog.set_default_response(gtk.RESPONSE_CLOSE)

        self.dialog.connect('close', lambda *a: False)
        self.dialog.connect('response', self.response)
        self.callback = callback

    def response(self, widget, response):
        if self.callback:
            self.callback(self.current_profile['name'])
        self.parent.present()
        self.dialog.destroy()

    def run(self, profile_name):
        self.clear_entries()  # must be done before show_all for windows
        self.dialog.show_all()
        model = self.profile_tree.get_model()
        if model:
            for i, row in enumerate(model):
                if row[0] == profile_name:
                    break
            else:
                i = 0
            self.profile_tree.get_selection().select_path((i,))
            self.profile_selected(self.profile_tree)

    def _current_profile(self):
        model, selection = self.profile_tree.get_selection().get_selected()
        if not selection:
            return {'name': None, 'iter': None}
        return {'name': model[selection][0], 'iter': selection}

    def clear_entries(self):
        for entryname in ('host', 'database', 'username'):
            entry = getattr(self, '%s_entry' % entryname)
            entry.handler_block_by_func(self.update_profiles)
            entry.set_text('')
            entry.handler_unblock_by_func(self.update_profiles)
        self.current_database = None
        self.database_combo.set_active(-1)
        self.database_combo.get_model().clear()
        self.hide_database_info()

    def hide_database_info(self):
        self.database_entry.hide()
        self.database_combo.hide()
        self.database_label.hide()
        self.database_progressbar.hide()

    def profile_create(self, button):
        self.clear_entries()
        model = self.profile_tree.get_model()
        model.append(['', False])
        column = self.profile_tree.get_column(0)
        self.profile_tree.set_cursor(len(model) - 1, column,
            start_editing=True)
        self.db_cache = None

    def profile_delete(self, button):
        self.clear_entries()
        model, selection = self.profile_tree.get_selection().get_selected()
        if not selection:
            return
        profile_name = model[selection][0]
        self.profiles.remove_section(profile_name)
        del model[selection]

    def profile_selected(self, treeview):
        self.old_profile = self.current_profile
        self.current_profile = self._current_profile()
        if not self.current_profile['name']:
            return
        if self.updating_db:
            self.current_profile = self.old_profile
            selection = treeview.get_selection()
            selection.select_iter(self.old_profile['iter'])
            return
        fields = ('host', 'database', 'username')
        for field in fields:
            entry = getattr(self, '%s_entry' % field)
            try:
                entry_value = self.profiles.get(self.current_profile['name'],
                    field)
            except configparser.NoOptionError:
                entry_value = ''
            entry.set_text(entry_value)
            if field == 'database':
                self.current_database = entry_value

        self.display_dbwidget(None, None)

    def edit_started(self, renderer, editable, path):
        if isinstance(editable, gtk.Entry):
            editable.connect('focus-out-event', self.edit_profilename,
                renderer, path)

    def edit_profilename(self, editable, event, renderer, path):
        newtext = editable.get_text()
        model = self.profile_tree.get_model()
        try:
            oldname = model[path][0]
        except IndexError:
            return
        if oldname == newtext == '':
            del model[path]
            return
        elif oldname == newtext or newtext == '':
            return
        elif newtext in self.profiles.sections():
            if not oldname:
                del model[path]
            return
        elif oldname in self.profiles.sections():
            self.profiles.add_section(newtext)
            for itemname, value in self.profiles.items(oldname):
                self.profiles.set(newtext, itemname, value)
            self.profiles.remove_section(oldname)
            model[path][0] = newtext
        else:
            model[path][0] = newtext
            self.profiles.add_section(newtext)
        self.current_profile = self._current_profile()
        self.host_entry.grab_focus()

    def update_profiles(self, editable, entryname):
        new_value = editable.get_text()
        if not new_value:
            return
        section = self._current_profile()['name']
        self.profiles.set(section, entryname, new_value)
        self.validate_profile(section)

    def validate_profile(self, profile_name):
        model, selection = self.profile_tree.get_selection().get_selected()
        if not selection:
            return
        active = all(self.profiles.has_option(profile_name, option)
            for option in ('host', 'database'))
        model[selection][1] = active

    @classmethod
    def test_server_version(cls, host, port):
        '''
        Tests if the server version is compatible with the client version
        It returns None if no information on server version is available.
        '''
        version = rpc.server_version(host, port)
        if not version:
            return None
        return version.split('.')[:2] == __version__.split('.')[:2]

    def refresh_databases(self, host, port):
        self.dbs_updated = threading.Event()
        threading.Thread(target=self.refresh_databases_start,
            args=(host, port)).start()
        gobject.timeout_add(100, self.refresh_databases_end, host, port)

    def refresh_databases_start(self, host, port):
        dbs = None
        try:
            dbs = rpc.db_list(host, port)
        except Exception:
            pass
        finally:
            self.dbs = dbs
            self.dbs_updated.set()

    def refresh_databases_end(self, host, port):
        if not self.dbs_updated.isSet():
            self.database_progressbar.show()
            self.database_progressbar.pulse()
            return True
        self.database_progressbar.hide()
        dbs = self.dbs

        label = None
        if self.test_server_version(host, port) is False:
            label = _('Incompatible version of the server')
        elif dbs is None:
            label = _('Could not connect to the server')
        if label:
            self.database_label.set_label('<b>%s</b>' % label)
            self.database_label.show()
        else:
            liststore = self.database_combo.get_model()
            liststore.clear()
            index = -1
            for db_num, db_name in enumerate(dbs):
                liststore.append([db_name])
                if self.current_database and db_name == self.current_database:
                    index = db_num
            if index == -1:
                index = 0
            self.database_combo.set_active(index)
            self.database_entry.set_text(self.current_database
                if self.current_database else '')
            if dbs:
                self.database_combo.show()
            else:
                self.database_entry.show()
        self.db_cache = (host, port, self.current_profile['name'])

        self.add_button.set_sensitive(True)
        self.remove_button.set_sensitive(True)
        self.ok_button.set_sensitive(True)
        self.cell.set_property('editable', True)
        self.host_entry.set_sensitive(True)
        self.updating_db = False
        return False

    def display_dbwidget(self, entry, event):
        netloc = self.host_entry.get_text()
        host = common.get_hostname(netloc)
        if not host:
            return
        port = common.get_port(netloc)
        if (host, port, self.current_profile['name']) == self.db_cache:
            return
        if self.updating_db:
            return

        self.hide_database_info()
        self.add_button.set_sensitive(False)
        self.remove_button.set_sensitive(False)
        self.ok_button.set_sensitive(False)
        self.cell.set_property('editable', False)
        self.host_entry.set_sensitive(False)
        self.updating_db = True
        self.refresh_databases(host, port)

    def dbcombo_changed(self, combobox):
        dbname = combobox.get_active_text()
        if dbname:
            self.current_database = dbname
            self.profiles.set(self.current_profile['name'], 'database', dbname)
            self.validate_profile(self.current_profile['name'])

    def dbentry_changed(self, entry):
        dbname = entry.get_text()
        if dbname:
            self.current_database = dbname
            self.profiles.set(self.current_profile['name'], 'database', dbname)
            self.validate_profile(self.current_profile['name'])

    def insert_text_port(self, entry, new_text, new_text_length, position):
        value = entry.get_text()
        position = entry.get_position()
        new_value = value[:position] + new_text + value[position:]
        try:
            int(new_value)
        except ValueError:
            entry.stop_emission('insert-text')


class DBLogin(object):
    def __init__(self):
        # Fake windows to avoid warning about Dialog without transient
        self._window = gtk.Window()
        self.dialog = gtk.Dialog(title=_('Login'), flags=gtk.DIALOG_MODAL)
        self.dialog.set_transient_for(self._window)
        self.dialog.set_icon(TRYTON_ICON)
        self.dialog.set_position(gtk.WIN_POS_CENTER_ALWAYS)

        tooltips = common.Tooltips()
        button_cancel = gtk.Button(_('_Cancel'), use_underline=True)
        tooltips.set_tip(button_cancel,
            _('Cancel connection to the Tryton server'))
        self.dialog.add_action_widget(button_cancel, gtk.RESPONSE_CANCEL)
        self.button_connect = gtk.Button(_('C_onnect'), use_underline=True)
        self.button_connect.get_style_context().add_class(
            Gtk.STYLE_CLASS_SUGGESTED_ACTION)
        self.button_connect.set_can_default(True)
        tooltips.set_tip(self.button_connect, _('Connect the Tryton server'))
        self.dialog.add_action_widget(self.button_connect, gtk.RESPONSE_OK)
        self.dialog.set_default_response(gtk.RESPONSE_OK)
        alignment = gtk.Alignment(yalign=0, yscale=0, xscale=1)
        self.table_main = gtk.Table(3, 3, False)
        self.table_main.set_border_width(0)
        self.table_main.set_row_spacings(3)
        self.table_main.set_col_spacings(3)
        alignment.add(self.table_main)
        self.dialog.vbox.pack_start(alignment, True, True, 0)

        image = gtk.Image()
        image.set_from_file(os.path.join(PIXMAPS_DIR, 'tryton.png'))
        image.set_alignment(0.5, 1)
        ebox = gtk.EventBox()
        ebox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#1b2019"))
        ebox.add(image)
        self.table_main.attach(ebox, 0, 3, 0, 1, ypadding=2)

        self.profile_store = gtk.ListStore(gobject.TYPE_STRING,
            gobject.TYPE_BOOLEAN)
        self.combo_profile = gtk.ComboBox()
        cell = gtk.CellRendererText()
        self.combo_profile.pack_start(cell, True)
        self.combo_profile.add_attribute(cell, 'text', 0)
        self.combo_profile.add_attribute(cell, 'sensitive', 1)
        self.combo_profile.set_model(self.profile_store)
        self.combo_profile.connect('changed', self.profile_changed)
        self.profile_label = gtk.Label(set_underline(_('Profile:')))
        self.profile_label.set_use_underline(True)
        self.profile_label.set_justify(gtk.JUSTIFY_RIGHT)
        self.profile_label.set_alignment(1, 0.5)
        self.profile_label.set_padding(3, 3)
        self.profile_label.set_mnemonic_widget(self.combo_profile)
        self.profile_button = gtk.Button(set_underline(_('Manage...')),
            use_underline=True)
        self.profile_button.connect('clicked', self.profile_manage)
        self.table_main.attach(self.profile_label, 0, 1, 1, 2,
            xoptions=gtk.FILL)
        self.table_main.attach(self.combo_profile, 1, 2, 1, 2)
        self.table_main.attach(self.profile_button, 2, 3, 1, 2,
            xoptions=gtk.FILL)
        self.expander = gtk.Expander()
        self.expander.set_label(_('Host / Database information'))
        self.expander.connect('notify::expanded', self.expand_hostspec)
        self.table_main.attach(self.expander, 0, 3, 3, 4)
        self.label_host = gtk.Label(set_underline(_('Host:')))
        self.label_host.set_use_underline(True)
        self.label_host.set_justify(gtk.JUSTIFY_RIGHT)
        self.label_host.set_alignment(1, 0.5)
        self.label_host.set_padding(3, 3)
        self.entry_host = gtk.Entry()
        self.entry_host.connect_after('focus-out-event',
            self.clear_profile_combo)
        self.entry_host.set_activates_default(True)
        self.label_host.set_mnemonic_widget(self.entry_host)
        self.table_main.attach(self.label_host, 0, 1, 4, 5, xoptions=gtk.FILL)
        self.table_main.attach(self.entry_host, 1, 3, 4, 5)
        self.label_database = gtk.Label(set_underline(_('Database:')))
        self.label_database.set_use_underline(True)
        self.label_database.set_justify(gtk.JUSTIFY_RIGHT)
        self.label_database.set_alignment(1, 0.5)
        self.label_database.set_padding(3, 3)
        self.entry_database = gtk.Entry()
        self.entry_database.connect_after('focus-out-event',
            self.clear_profile_combo)
        self.entry_database.set_activates_default(True)
        self.label_database.set_mnemonic_widget(self.entry_database)
        self.table_main.attach(self.label_database, 0, 1, 5, 6,
            xoptions=gtk.FILL)
        self.table_main.attach(self.entry_database, 1, 3, 5, 6)
        self.entry_login = gtk.Entry()
        self.entry_login.set_activates_default(True)
        self.table_main.attach(self.entry_login, 1, 3, 6, 7)
        label_username = gtk.Label(set_underline(_("User name:")))
        label_username.set_use_underline(True)
        label_username.set_alignment(1, 0.5)
        label_username.set_padding(3, 3)
        label_username.set_mnemonic_widget(self.entry_login)
        self.table_main.attach(label_username, 0, 1, 6, 7, xoptions=gtk.FILL)

        # Profile informations
        self.profile_cfg = os.path.join(get_config_dir(), 'profiles.cfg')
        self.profiles = configparser.ConfigParser()
        if not os.path.exists(self.profile_cfg):
            short_version = '.'.join(__version__.split('.', 2)[:2])
            name = 'demo%s.tryton.org' % short_version
            self.profiles.add_section(name)
            self.profiles.set(name, 'host', name)
            self.profiles.set(name, 'database', 'demo%s' % short_version)
            self.profiles.set(name, 'username', 'demo')
        else:
            try:
                self.profiles.read(self.profile_cfg)
            except configparser.ParsingError:
                logger.error("Fail to parse profiles.cfg", exc_info=True)
        for section in self.profiles.sections():
            active = all(self.profiles.has_option(section, option)
                for option in ('host', 'database'))
            self.profile_store.append([section, active])

    def profile_manage(self, widget):
        def callback(profile_name):
            with open(self.profile_cfg, 'w') as configfile:
                self.profiles.write(configfile)

            for idx, row in enumerate(self.profile_store):
                if row[0] == profile_name and row[1]:
                    self.combo_profile.set_active(idx)
                    self.profile_changed(self.combo_profile)
                    break

        dia = DBListEditor(self.dialog, self.profile_store, self.profiles,
            callback)
        active_profile = self.combo_profile.get_active()
        profile_name = None
        if active_profile != -1:
            profile_name = self.profile_store[active_profile][0]
        dia.run(profile_name)

    def profile_changed(self, combobox):
        position = combobox.get_active()
        if position == -1:
            return
        profile = self.profile_store[position][0]
        try:
            username = self.profiles.get(profile, 'username')
        except configparser.NoOptionError:
            username = ''
        host = self.profiles.get(profile, 'host')
        self.entry_host.set_text('%s' % host)
        self.entry_database.set_text(self.profiles.get(profile, 'database'))
        if username:
            self.entry_login.set_text(username)
        else:
            self.entry_login.set_text('')

    def clear_profile_combo(self, *args):
        netloc = self.entry_host.get_text()
        host = common.get_hostname(netloc)
        port = common.get_port(netloc)
        database = self.entry_database.get_text().strip()
        login = self.entry_login.get_text()
        for idx, profile_info in enumerate(self.profile_store):
            if not profile_info[1]:
                continue
            profile = profile_info[0]
            try:
                profile_host = self.profiles.get(profile, 'host')
                profile_db = self.profiles.get(profile, 'database')
                profile_login = self.profiles.get(profile, 'username')
            except configparser.NoOptionError:
                continue
            if (host == common.get_hostname(profile_host)
                    and port == common.get_port(profile_host)
                    and database == profile_db
                    and (not login or login == profile_login)):
                break
        else:
            idx = -1
        self.combo_profile.set_active(idx)
        return False

    def expand_hostspec(self, expander, *args):
        visibility = expander.props.expanded
        self.entry_host.props.visible = visibility
        self.label_host.props.visible = visibility
        self.entry_database.props.visible = visibility
        self.label_database.props.visible = visibility

    def run(self):
        profile_name = CONFIG['login.profile']
        can_use_profile = self.profiles.has_section(profile_name)
        if can_use_profile:
            for (configname, option) in [
                    ('login.host', 'host'),
                    ('login.db', 'database'),
                    ]:
                try:
                    value = self.profiles.get(profile_name, option)
                except configparser.NoOptionError:
                    value = None
                if value != CONFIG[configname]:
                    can_use_profile = False
                    break

        if can_use_profile:
            for idx, row in enumerate(self.profile_store):
                if row[0] == profile_name:
                    self.combo_profile.set_active(idx)
                    break
        else:
            self.combo_profile.set_active(-1)
            host = CONFIG['login.host'] if CONFIG['login.host'] else ''
            self.entry_host.set_text(host)
            db = CONFIG['login.db'] if CONFIG['login.db'] else ''
            self.entry_database.set_text(db)
            self.entry_login.set_text(CONFIG['login.login'])
            self.clear_profile_combo()
        self.dialog.show_all()

        self.entry_login.grab_focus()

        # Reshow dialog for gtk-quarks
        self.dialog.reshow_with_initial_size()
        self.expander.set_expanded(CONFIG['login.expanded'])
        # The previous action did not called expand_hostspec
        self.expand_hostspec(self.expander)

        response, result = None, ('', '', '', '')
        while not all(result):
            response = self.dialog.run()
            if response != gtk.RESPONSE_OK:
                break
            self.clear_profile_combo()
            active_profile = self.combo_profile.get_active()
            if active_profile != -1:
                profile = self.profile_store[active_profile][0]
            else:
                profile = ''
            host = self.entry_host.get_text()
            hostname = common.get_hostname(host)
            port = common.get_port(host)
            test = DBListEditor.test_server_version(hostname, port)
            if not test:
                if test is False:
                    common.warning('',
                        _('Incompatible version of the server'),
                        parent=self.dialog)
                else:
                    common.warning('',
                        _('Could not connect to the server'),
                        parent=self.dialog)
                continue
            database = self.entry_database.get_text()
            login = self.entry_login.get_text()
            CONFIG['login.profile'] = profile
            CONFIG['login.host'] = host
            CONFIG['login.db'] = database
            CONFIG['login.expanded'] = self.expander.props.expanded
            CONFIG['login.login'] = login
            result = (
                hostname, port, database, self.entry_login.get_text())

        self.dialog.destroy()
        self._window.destroy()
        return response == gtk.RESPONSE_OK
