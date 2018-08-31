# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Form"
import gettext
import gtk
import gobject
from tryton.gui.window.view_form.screen import Screen
from tryton.action import Action
from tryton.gui import Main
from tryton.gui.window import Window
from tryton.gui.window.win_export import WinExport
from tryton.gui.window.win_import import WinImport
from tryton.gui.window.attachment import Attachment
from tryton.gui.window.note import Note
from tryton.gui.window.revision import Revision
from tryton.signal_event import SignalEvent
from tryton.common import message, sur, sur_3b, timezoned_date
import tryton.common as common
from tryton.common import RPCExecute, RPCException
from tryton.common.datetime_strftime import datetime_strftime
from tryton import plugins

from tabcontent import TabContent

_ = gettext.gettext


class Form(SignalEvent, TabContent):
    "Form"

    def __init__(self, model, res_id=None, name='', **attributes):
        super(Form, self).__init__()

        self.model = model
        self.res_id = res_id
        self.mode = attributes.get('mode')
        self.view_ids = attributes.get('view_ids')
        self.dialogs = []

        self.screen = Screen(self.model, **attributes)
        self.screen.widget.show()

        self.name = name

        self.create_tabcontent()

        self.set_buttons_sensitive()

        self.screen.signal_connect(self, 'record-message',
            self._record_message)

        self.screen.signal_connect(self, 'record-modified',
            lambda *a: gobject.idle_add(self._record_modified, *a))
        self.screen.signal_connect(self, 'record-saved', self._record_saved)
        self.screen.signal_connect(self, 'attachment-count',
                self._attachment_count)
        self.screen.signal_connect(self, 'unread-note', self._unread_note)

        if res_id not in (None, False):
            if isinstance(res_id, (int, long)):
                res_id = [res_id]
            self.screen.load(res_id)
        else:
            if self.screen.current_view.view_type == 'form':
                self.sig_new(None, autosave=False)
            if self.screen.current_view.view_type \
                    in ('tree', 'graph', 'calendar'):
                self.screen.search_filter()

        self.update_revision()

    def get_toolbars(self):
        try:
            return RPCExecute('model', self.model, 'view_toolbar_get',
                context=self.screen.context)
        except RPCException:
            return {}

    def widget_get(self):
        return self.screen.widget

    def __eq__(self, value):
        if not value:
            return False
        if not isinstance(value, Form):
            return False
        return (self.model == value.model
            and self.res_id == value.res_id
            and self.screen.domain == value.screen.domain
            and self.mode == value.mode
            and self.view_ids == value.view_ids
            and self.screen.context == value.screen.context
            and self.name == value.name
            and self.screen.limit == value.screen.limit
            and self.screen.search_value == value.screen.search_value)

    def destroy(self):
        super(Form, self).destroy()
        self.screen.signal_unconnect(self)
        self.screen.destroy()

    def sig_attach(self, widget=None):
        record = self.screen.current_record
        if not record or record.id < 0:
            return
        Attachment(record,
            lambda: self.update_attachment_count(reload=True))

    def update_attachment_count(self, reload=False):
        record = self.screen.current_record
        if record:
            attachment_count = record.get_attachment_count(reload=reload)
        else:
            attachment_count = 0
        self._attachment_count(None, attachment_count)

    def _attachment_count(self, widget, signal_data):
        label = _('Attachment(%d)') % signal_data
        self.buttons['attach'].set_label(label)
        if signal_data:
            self.buttons['attach'].set_stock_id('tryton-attachment-hi')
        else:
            self.buttons['attach'].set_stock_id('tryton-attachment')
        record = self.screen.current_record
        self.buttons['attach'].props.sensitive = bool(
            record.id >= 0 if record else False)

    def sig_note(self, widget=None):
        record = self.screen.current_record
        if not record or record.id < 0:
            return
        Note(record,
            lambda: self.update_unread_note(reload=True))

    def update_unread_note(self, reload=False):
        record = self.screen.current_record
        if record:
            unread = record.get_unread_note(reload=reload)
        else:
            unread = 0
        self._unread_note(None, unread)

    def _unread_note(self, widget, signal_data):
        label = _('Note(%d)') % signal_data
        self.buttons['note'].set_label(label)
        if signal_data:
            self.buttons['note'].set_stock_id('tryton-note-hi')
        else:
            self.buttons['note'].set_stock_id('tryton-note')
        record = self.screen.current_record
        if not record or record.id < 0:
            sensitive = False
        else:
            sensitive = True
        self.buttons['note'].props.sensitive = sensitive

    def sig_switch(self, widget=None):
        if not self.modified_save():
            return
        self.screen.switch_view()

    def sig_logs(self, widget=None):
        current_record = self.screen.current_record
        if not current_record or current_record.id < 0:
            self.message_info(
                _('You have to select one record.'), gtk.MESSAGE_INFO)
            return False

        fields = [
            ('id', _('ID:')),
            ('create_uid.rec_name', _('Creation User:')),
            ('create_date', _('Creation Date:')),
            ('write_uid.rec_name', _('Latest Modification by:')),
            ('write_date', _('Latest Modification Date:')),
        ]

        try:
            res = RPCExecute('model', self.model, 'read', [current_record.id],
                [x[0] for x in fields], context=self.screen.context)
        except RPCException:
            return
        date_format = self.screen.context.get('date_format', '%x')
        datetime_format = date_format + ' %H:%M:%S.%f'
        message_str = ''
        for line in res:
            for (key, val) in fields:
                value = str(line.get(key, False) or '/')
                if line.get(key, False) \
                        and key in ('create_date', 'write_date'):
                    date = timezoned_date(line[key])
                    value = common.datetime_strftime(date, datetime_format)
                message_str += val + ' ' + value + '\n'
        message_str += _('Model:') + ' ' + self.model
        message(message_str)
        return True

    def sig_revision(self, widget=None):
        if not self.modified_save():
            return
        current_id = (self.screen.current_record.id
            if self.screen.current_record else None)
        try:
            revisions = RPCExecute('model', self.model, 'history_revisions',
                [r.id for r in self.screen.selected_records])
        except RPCException:
            return
        revision = self.screen.context.get('_datetime')
        format_ = self.screen.context.get('date_format', '%x')
        format_ += ' %H:%M:%S.%f'
        revision = Revision(revisions, revision, format_).run()
        # Prevent too old revision in form view
        if (self.screen.current_view.view_type == 'form'
                and revision
                and revision < revisions[-1][0]):
                revision = revisions[-1][0]
        if revision != self.screen.context.get('_datetime'):
            self.screen.clear()
            # Update root group context that will be propagated
            self.screen.group._context['_datetime'] = revision
            if self.screen.current_view.view_type != 'form':
                self.screen.search_filter(
                    self.screen.screen_container.get_text())
            else:
                # Test if record exist in revisions
                self.screen.load([current_id])
            self.screen.display(set_cursor=True)
            self.update_revision()

    def update_revision(self):
        revision = self.screen.context.get('_datetime')
        if revision:
            format_ = self.screen.context.get('date_format', '%x')
            format_ += ' %H:%M:%S.%f'
            revision = datetime_strftime(revision, format_)
            self.title.set_label('%s @ %s' % (self.name, revision))
        else:
            self.title.set_label(self.name)
        self.set_buttons_sensitive(revision)

    def set_buttons_sensitive(self, revision=None):
        if not revision:
            access = common.MODELACCESS[self.model]
            for name, sensitive in [
                    ('new', access['create']),
                    ('save', access['create'] or access['write']),
                    ('remove', access['delete']),
                    ('copy', access['create']),
                    ('import', access['create']),
                    ]:
                if name in self.buttons:
                    self.buttons[name].props.sensitive = sensitive
                if name in self.menu_buttons:
                    self.menu_buttons[name].props.sensitive = sensitive
        else:
            for name in ['new', 'save', 'remove', 'copy', 'import']:
                if name in self.buttons:
                    self.buttons[name].props.sensitive = False
                if name in self.menu_buttons:
                    self.menu_buttons[name].props.sensitive = False

    def sig_remove(self, widget=None):
        if not common.MODELACCESS[self.model]['delete']:
            return
        if self.screen.current_view.view_type == 'form':
            msg = _('Are you sure to remove this record?')
        else:
            msg = _('Are you sure to remove those records?')
        if sur(msg):
            if not self.screen.remove(delete=True, force_remove=True):
                self.message_info(_('Records not removed.'), gtk.MESSAGE_ERROR)
            else:
                self.message_info(_('Records removed.'), gtk.MESSAGE_INFO)
                self.screen.count_tab_domain()

    def sig_import(self, widget=None):
        WinImport(self.model, self.screen.context)

    def sig_export(self, widget=None):
        export = WinExport(self.model,
            [r.id for r in self.screen.selected_records],
            context=self.screen.context)
        for name in self.screen.current_view.get_fields():
            type = self.screen.group.fields[name].attrs['type']
            if type == 'selection':
                export.sel_field(name + '.translated')
            elif type == 'reference':
                export.sel_field(name + '.translated')
                export.sel_field(name + '/rec_name')
            else:
                export.sel_field(name)

    def sig_new(self, widget=None, autosave=True):
        if not common.MODELACCESS[self.model]['create']:
            return
        if autosave:
            if not self.modified_save():
                return
        self.screen.new()
        self.message_info()
        self.activate_save()

    def sig_copy(self, widget=None):
        if not common.MODELACCESS[self.model]['create']:
            return
        if not self.modified_save():
            return
        if self.screen.copy():
            self.message_info(_('Working now on the duplicated record(s).'),
                gtk.MESSAGE_INFO)
            self.screen.count_tab_domain()

    def sig_save(self, widget=None):
        if widget:
            # Called from button so we must save the tree state
            self.screen.save_tree_state()
        if not (common.MODELACCESS[self.model]['write']
                or common.MODELACCESS[self.model]['create']):
            return
        if self.screen.save_current():
            self.message_info(_('Record saved.'), gtk.MESSAGE_INFO)
            self.screen.count_tab_domain()
            return True
        else:
            self.message_info(self.screen.invalid_message(), gtk.MESSAGE_ERROR)
            return False

    def sig_previous(self, widget=None):
        if not self.modified_save():
            return
        self.screen.display_prev()
        self.message_info()
        self.activate_save()

    def sig_next(self, widget=None):
        if not self.modified_save():
            return
        self.screen.display_next()
        self.message_info()
        self.activate_save()

    def sig_reload(self, test_modified=True):
        if test_modified:
            if not self.modified_save():
                return False
        else:
            self.screen.save_tree_state(store=False)
        self.screen.cancel_current()
        set_cursor = False
        record_id = (self.screen.current_record.id
            if self.screen.current_record else None)
        if self.screen.current_view.view_type != 'form':
            self.screen.search_filter(self.screen.screen_container.get_text())
            for record in self.screen.group:
                if record.id == record_id:
                    self.screen.current_record = record
                    set_cursor = True
                    break
        self.screen.display(set_cursor=set_cursor)
        self.message_info()
        self.activate_save()
        self.screen.count_tab_domain()
        return True

    def sig_action(self, widget):
        if self.buttons['action'].props.sensitive:
            self.buttons['action'].props.active = True

    def sig_print(self, widget):
        if self.buttons['print'].props.sensitive:
            self.buttons['print'].props.active = True

    def sig_print_open(self, widget):
        if self.buttons['open'].props.sensitive:
            self.buttons['open'].props.active = True

    def sig_print_email(self, widget):
        if self.buttons['email'].props.sensitive:
            self.buttons['email'].props.active = True

    def sig_relate(self, widget):
        if self.buttons['relate'].props.sensitive:
            self.buttons['relate'].props.active = True

    def sig_copy_url(self, widget):
        if self.buttons['copy_url'].props.sensitive:
            self.buttons['copy_url'].props.active = True

    def sig_search(self, widget):
        search_container = self.screen.screen_container
        if hasattr(search_container, 'search_entry'):
            search_container.search_entry.grab_focus()

    def action_popup(self, widget):
        button, = widget.get_children()
        button.grab_focus()
        menu = widget._menu
        if not widget.props.active:
            menu.popdown()
            return

        def menu_position(menu, data):
            widget_allocation = widget.get_allocation()
            if hasattr(widget.window, 'get_root_coords'):
                x, y = widget.window.get_root_coords(
                    widget_allocation.x, widget_allocation.y)
            else:
                x, y = widget.window.get_origin()
                x += widget_allocation.x
                y += widget_allocation.y
            return (x, y + widget_allocation.height, False)
        menu.show_all()
        menu.popup(None, None, menu_position, 0, gtk.get_current_event_time(),
            None)

    def _record_message(self, screen, signal_data):
        name = '_'
        if signal_data[0]:
            name = str(signal_data[0])
        for button_id in ('print', 'relate', 'email', 'open', 'save',
                'attach'):
            button = self.buttons[button_id]
            can_be_sensitive = getattr(button, '_can_be_sensitive', True)
            if button_id in {'print', 'relate', 'email', 'open'}:
                action_type = button_id
                if button_id in {'email', 'open'}:
                    action_type = 'print'
                can_be_sensitive |= any(
                    b.attrs.get('keyword', 'action') == action_type
                    for b in screen.get_buttons())
            button.props.sensitive = (bool(signal_data[0])
                and can_be_sensitive)
        button_switch = self.buttons['switch']
        button_switch.props.sensitive = self.screen.number_of_views > 1

        msg = name + ' / ' + str(signal_data[1])
        if signal_data[1] < signal_data[2]:
            msg += _(' of ') + str(signal_data[2])
        self.status_label.set_text(msg)
        self.message_info()
        self.activate_save()

    def _record_modified(self, screen, signal_data):
        # As it is called via idle_add, the form could have been destroyed in
        # the meantime.
        if self.widget_get().props.window:
            self.activate_save()

    def _record_saved(self, screen, signal_data):
        self.activate_save()
        self.update_attachment_count()

    def modified_save(self):
        self.screen.save_tree_state()
        self.screen.current_view.set_value()
        if self.screen.modified():
            value = sur_3b(
                _('This record has been modified\n'
                    'do you want to save it?'))
            if value == 'ok':
                return self.sig_save(None)
            if value == 'ko':
                return self.sig_reload(test_modified=False)
            return False
        return True

    def sig_close(self, widget=None):
        for dialog in reversed(self.dialogs[:]):
            dialog.destroy()
        return self.modified_save()

    def _action(self, action, atype):
        action = action.copy()
        if not self.screen.save_current():
            return
        record_id = (self.screen.current_record.id
            if self.screen.current_record else None)
        record_ids = [r.id for r in self.screen.selected_records]
        action = Action.evaluate(action, atype, self.screen.current_record)
        data = {
            'model': self.screen.model_name,
            'id': record_id,
            'ids': record_ids,
        }
        Action._exec_action(action, data, self.screen.context)

    def activate_save(self):
        self.buttons['save'].props.sensitive = self.screen.modified()

    def sig_win_close(self, widget):
        Main.get_main().sig_win_close(widget)

    def create_toolbar(self, toolbars):
        gtktoolbar = super(Form, self).create_toolbar(toolbars)

        attach_btn = self.buttons['attach']
        target_entry = gtk.TargetEntry.new('text/uri-list', 0, 0)
        attach_btn.drag_dest_set(gtk.DEST_DEFAULT_ALL, [
                target_entry,
                ], gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
        attach_btn.connect('drag_data_received',
            self.attach_drag_data_received)

        iconstock = {
            'print': 'tryton-print',
            'action': 'tryton-executable',
            'relate': 'tryton-go-jump',
            'email': 'tryton-print-email',
            'open': 'tryton-print-open',
        }
        for action_type, special_action, action_name, tooltip in (
                ('action', 'action', _('Action'), _('Launch action')),
                ('relate', 'relate', _('Relate'), _('Open related records')),
                (None,) * 4,
                ('print', 'open', _('Report'), _('Open report')),
                ('print', 'email', _('E-Mail'), _('E-Mail report')),
                ('print', 'print', _('Print'), _('Print report')),
        ):
            if action_type is not None:
                tbutton = gtk.ToggleToolButton(iconstock.get(special_action))
                tbutton.set_label(action_name)
                tbutton._menu = self._create_popup_menu(tbutton,
                    action_type, toolbars[action_type], special_action)
                tbutton.connect('toggled', self.action_popup)
                self.tooltips.set_tip(tbutton, tooltip)
                self.buttons[special_action] = tbutton
                if action_type != 'action':
                    tbutton._can_be_sensitive = bool(
                        tbutton._menu.get_children())
            else:
                tbutton = gtk.SeparatorToolItem()
            gtktoolbar.insert(tbutton, -1)

        gtktoolbar.insert(gtk.SeparatorToolItem(), -1)

        url_button = gtk.ToggleToolButton('tryton-web-browser')
        url_button.set_label(_('_Copy URL'))
        url_button.set_use_underline(True)
        self.tooltips.set_tip(
            url_button, _('Copy URL into clipboard'))
        url_button._menu = url_menu = gtk.Menu()
        url_menuitem = gtk.MenuItem()
        url_menuitem.connect('activate', self.url_copy)
        url_menu.add(url_menuitem)
        url_menu.show_all()
        url_menu.connect('deactivate', self._popup_menu_hide, url_button)
        url_button.connect('toggled', self.url_set, url_menuitem)
        url_button.connect('toggled', self.action_popup)
        self.buttons['copy_url'] = url_button
        gtktoolbar.insert(url_button, -1)
        return gtktoolbar

    def _create_popup_menu(self, widget, keyword, actions, special_action):
        menu = gtk.Menu()
        menu.connect('deactivate', self._popup_menu_hide, widget)
        widget.connect('toggled', self._update_popup_menu, menu, keyword)

        for action in actions:
            new_action = action.copy()
            if special_action == 'print':
                new_action['direct_print'] = True
            elif special_action == 'email':
                new_action['email_print'] = True
            action_name = action['name']
            if '_' not in action_name:
                action_name = '_' + action_name
            menuitem = gtk.MenuItem(action_name)
            menuitem.set_use_underline(True)
            menuitem.connect('activate', self._popup_menu_selected, widget,
                new_action, keyword)
            menu.add(menuitem)
        return menu

    def _popup_menu_selected(self, menuitem, togglebutton, action, keyword):
        event = gtk.get_current_event()
        allow_similar = False
        if (event.state & gtk.gdk.CONTROL_MASK
                or event.state & gtk.gdk.MOD1_MASK):
            allow_similar = True
        with Window(hide_current=True, allow_similar=allow_similar):
            self._action(action, keyword)
        togglebutton.props.active = False

    def _popup_menu_hide(self, menuitem, togglebutton):
        togglebutton.props.active = False

    def _update_popup_menu(self, tbutton, menu, keyword):
        for item in menu.get_children():
            if (getattr(item, '_update_action', False)
                    or isinstance(item, gtk.SeparatorMenuItem)):
                menu.remove(item)

        buttons = [b for b in self.screen.get_buttons()
            if keyword == b.attrs.get('keyword', 'action')]
        if buttons and menu.get_children():
            menu.add(gtk.SeparatorMenuItem())
        for button in buttons:
            menuitem = gtk.ImageMenuItem()
            menuitem.set_label('_' + button.attrs.get('string', _('Unknown')))
            menuitem.set_use_underline(True)
            if button.attrs.get('icon'):
                icon = gtk.Image()
                icon.set_from_stock(button.attrs['icon'], gtk.ICON_SIZE_MENU)
                menuitem.set_image(icon)
            menuitem.connect('activate',
                lambda m, attrs: self.screen.button(attrs), button.attrs)
            menuitem._update_action = True
            menu.add(menuitem)

        kw_plugins = []
        for plugin in plugins.MODULES:
            for plugin_spec in plugin.get_plugins(self.model):
                name, func = plugin_spec[:2]
                try:
                    plugin_keyword = plugin_spec[2]
                except IndexError:
                    plugin_keyword = 'action'
                if keyword != plugin_keyword:
                    continue
                kw_plugins.append((name, func))

        if kw_plugins:
            menu.add(gtk.SeparatorMenuItem())
        for name, func in kw_plugins:
            menuitem = gtk.MenuItem('_' + name)
            menuitem.set_use_underline(True)
            menuitem.connect('activate', lambda m, func: func({
                        'model': self.model,
                        'ids': [r.id
                            for r in self.screen.selected_records],
                        'id': (self.screen.current_record.id
                            if self.screen.current_record else None),
                        }), func)
            menuitem._update_action = True
            menu.add(menuitem)

    def url_copy(self, menuitem):
        url = self.screen.get_url(self.name)
        for selection in [gtk.CLIPBOARD_PRIMARY, gtk.CLIPBOARD_CLIPBOARD]:
            clipboard = gtk.clipboard_get(selection)
            clipboard.set_text(url, -1)

    def url_set(self, button, menuitem):
        url = self.screen.get_url(self.name)
        size = 80
        if len(url) > size:
            url = url[:size // 2] + '...' + url[-size // 2:]
        menuitem.set_label(url)

    def set_cursor(self):
        if self.screen:
            self.screen.set_cursor(reset_view=False)

    def attach_drag_data_received(self, widget, context, x, y, selection, info,
            timestamp):
        record = self.screen.current_record
        if not record or record.id < 0:
            return
        win_attach = Attachment(record,
            lambda: self.update_attachment_count(reload=True))
        if info == 0:
            for uri in selection.get_uris():
                # Win32 cut&paste terminates the list with a NULL character
                if not uri or uri == '\0':
                    continue
                win_attach.add_uri(uri)
