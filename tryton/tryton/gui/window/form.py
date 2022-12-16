#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
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
from tryton.signal_event import SignalEvent
from tryton.common import message, sur, sur_3b, COLOR_SCHEMES, timezoned_date
import tryton.common as common
from tryton.translate import date_format
from tryton.common import RPCExecute, RPCException
from tryton import plugins

from tabcontent import TabContent

_ = gettext.gettext


class Form(SignalEvent, TabContent):
    "Form"

    toolbar_def = [
        ('new', 'tryton-new', _('New'), _('Create a new record'),
            'sig_new'),
        ('save', 'tryton-save', _('Save'), _('Save this record'),
            'sig_save'),
        ('switch', 'tryton-fullscreen', _('Switch'), _('Switch view'),
            'sig_switch'),
        ('reload', 'tryton-refresh', _('_Reload'), _('Reload'),
            'sig_reload'),
        (None,) * 5,
        ('previous', 'tryton-go-previous', _('Previous'),
            _('Previous Record'), 'sig_previous'),
        ('next', 'tryton-go-next', _('Next'), _('Next Record'),
            'sig_next'),
        (None,) * 5,
        ('attach', 'tryton-attachment', _('Attachment(0)'),
            _('Add an attachment to the record'), 'sig_attach'),
    ]
    menu_def = [
        (_('_New'), 'tryton-new', 'sig_new', '<tryton>/Form/New'),
        (_('_Save'), 'tryton-save', 'sig_save', '<tryton>/Form/Save'),
        (_('_Switch View'), 'tryton-fullscreen', 'sig_switch',
            '<tryton>/Form/Switch View'),
        (_('_Reload/Undo'), 'tryton-refresh', 'sig_reload',
            '<tryton>/Form/Reload'),
        (_('_Duplicate'), 'tryton-copy', 'sig_copy',
            '<tryton>/Form/Duplicate'),
        (_('_Delete...'), 'tryton-delete', 'sig_remove',
            '<tryton>/Form/Delete'),
        (None,) * 4,
        (_('_Previous'), 'tryton-go-previous', 'sig_previous',
            '<tryton>/Form/Previous'),
        (_('_Next'), 'tryton-go-next', 'sig_next', '<tryton>/Form/Next'),
        (_('_Search'), 'tryton-find', 'sig_search', '<tryton>/Form/Search'),
        (_('View _Logs...'), None, 'sig_logs', None),
        (None,) * 4,
        (_('_Close Tab'), 'tryton-close', 'sig_win_close',
            '<tryton>/Form/Close'),
        (None,) * 4,
        (_('A_ttachments...'), 'tryton-attachment', 'sig_attach',
            '<tryton>/Form/Attachments'),
        (_('_Actions...'), 'tryton-executable', 'sig_action',
            '<tryton>/Form/Actions'),
        (_('_Relate...'), 'tryton-go-jump', 'sig_relate',
            '<tryton>/Form/Relate'),
        (None,) * 4,
        (_('_Report...'), 'tryton-print-open', 'sig_print_open',
            '<tryton>/Form/Report'),
        (_('_E-Mail...'), 'tryton-print-email', 'sig_print_email',
            '<tryton>/Form/Email'),
        (_('_Print...'), 'tryton-print', 'sig_print',
            '<tryton>/Form/Print'),
        (None,) * 4,
        (_('_Export Data...'), 'tryton-save-as', 'sig_save_as',
            '<tryton>/Form/Export Data'),
        (_('_Import Data...'), None, 'sig_import',
            '<tryton>/Form/Import Data'),
    ]

    def __init__(self, model, res_id=False, domain=None, mode=None,
            view_ids=None, context=None, name=False, limit=None,
            auto_refresh=False, search_value=None, tab_domain=None):
        super(Form, self).__init__()

        if not mode:
            mode = ['tree', 'form']
        if domain is None:
            domain = []
        if view_ids is None:
            view_ids = []
        if context is None:
            context = {}

        self.model = model
        self.res_id = res_id
        self.domain = domain
        self.mode = mode
        self.context = context
        self.auto_refresh = auto_refresh
        self.view_ids = view_ids
        self.dialogs = []

        self.screen = Screen(self.model, mode=mode, context=self.context,
            view_ids=view_ids, domain=domain, limit=limit,
            readonly=bool(auto_refresh), search_value=search_value,
            tab_domain=tab_domain)
        self.screen.widget.show()

        if not name:
            self.name = self.screen.current_view.title
        else:
            self.name = name

        self.create_tabcontent()

        access = common.MODELACCESS[self.model]
        for button, access_type in (
                ('new', 'create'),
                ('save', 'write'),
                ):
            self.buttons[button].props.sensitive = access[access_type]

        self.screen.signal_connect(self, 'record-message',
            self._record_message)
        self.screen.signal_connect(self, 'record-modified',
            lambda *a: gobject.idle_add(self._record_modified, *a))
        self.screen.signal_connect(self, 'record-saved', self._record_saved)
        self.screen.signal_connect(self, 'attachment-count',
                self._attachment_count)

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

        if auto_refresh and int(auto_refresh):
            gobject.timeout_add(int(auto_refresh) * 1000, self.sig_reload)

    def get_toolbars(self):
        try:
            return RPCExecute('model', self.model, 'view_toolbar_get',
                context=self.context)
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
            and self.domain == value.domain
            and self.mode == value.mode
            and self.view_ids == value.view_ids
            and self.context == value.context
            and self.name == value.name
            and self.screen.limit == value.screen.limit
            and self.auto_refresh == value.auto_refresh
            and self.screen.search_value == value.screen.search_value)

    def destroy(self):
        self.screen.destroy()
        self.screen = None
        self.widget = None
        #self.scrolledwindow.destroy()
        #self.scrolledwindow = None

    def sel_ids_get(self):
        return self.screen.sel_ids_get()

    def ids_get(self):
        return self.screen.ids_get()

    def id_get(self):
        return self.screen.id_get()

    def sig_attach(self, widget=None):
        record_id = self.id_get()
        if record_id is False or record_id < 0:
            return
        Attachment(self.model, record_id,
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
        record_id = self.id_get()
        self.buttons['attach'].props.sensitive = bool(
            record_id >= 0 and record_id is not False)

    def sig_switch(self, widget=None):
        if not self.modified_save():
            return
        self.screen.switch_view()

    def sig_logs(self, widget=None):
        obj_id = self.id_get()
        if obj_id < 0 or obj_id is False:
            self.message_info(_('You have to select one record!'))
            return False

        fields = [
            ('id', _('ID:')),
            ('create_uid.rec_name', _('Creation User:')),
            ('create_date', _('Creation Date:')),
            ('write_uid.rec_name', _('Latest Modification by:')),
            ('write_date', _('Latest Modification Date:')),
        ]

        try:
            res = RPCExecute('model', self.model, 'read', [obj_id],
                [x[0] for x in fields], context=self.context)
        except RPCException:
            return
        message_str = ''
        for line in res:
            for (key, val) in fields:
                value = str(line.get(key, False) or '/')
                if line.get(key, False) \
                        and key in ('create_date', 'write_date'):
                    display_format = date_format() + ' %H:%M:%S'
                    date = timezoned_date(line[key])
                    value = common.datetime_strftime(date, display_format)
                message_str += val + ' ' + value + '\n'
        message_str += _('Model:') + ' ' + self.model
        message(message_str)
        return True

    def sig_remove(self, widget=None):
        if not common.MODELACCESS[self.model]['delete']:
            return
        if self.screen.current_view.view_type == 'form':
            msg = _('Are you sure to remove this record?')
        else:
            msg = _('Are you sure to remove those records?')
        if sur(msg):
            if not self.screen.remove(delete=True, force_remove=True):
                self.message_info(_('Records not removed!'))
            else:
                self.message_info(_('Records removed!'), 'green')

    def sig_import(self, widget=None):
        while(self.screen.view_to_load):
            self.screen.load_view_to_load()
        fields = {}
        for name, field in self.screen.group.fields.iteritems():
            fields[name] = field.attrs
        WinImport(self.model)

    def sig_save_as(self, widget=None):
        while self.screen.view_to_load:
            self.screen.load_view_to_load()
        fields = {}
        for name, field in self.screen.group.fields.iteritems():
            fields[name] = field.attrs
        WinExport(self.model, self.ids_get(), context=self.context)

    def sig_new(self, widget=None, autosave=True):
        if not common.MODELACCESS[self.model]['create']:
            return
        if autosave:
            if not self.modified_save():
                return
        self.screen.new()
        self.message_info('')
        self.activate_save()

    def sig_copy(self, widget=None):
        if not common.MODELACCESS[self.model]['create']:
            return
        if not self.modified_save():
            return
        res_ids = self.sel_ids_get()
        try:
            new_ids = RPCExecute('model', self.model, 'copy', res_ids, {},
                context=self.context)
        except RPCException:
            return
        self.screen.load(new_ids)
        self.message_info(_('Working now on the duplicated record(s)!'),
            'green')

    def sig_save(self, widget=None):
        if not common.MODELACCESS[self.model]['write']:
            return
        if self.screen.save_current():
            self.message_info(_('Record saved!'), 'green')
            return True
        else:
            self.message_info(_('Invalid form!'))
            return False

    def sig_previous(self, widget=None):
        if not self.modified_save():
            return
        self.screen.display_prev()
        self.message_info('')
        self.activate_save()

    def sig_next(self, widget=None):
        if not self.modified_save():
            return
        self.screen.display_next()
        self.message_info('')
        self.activate_save()

    def sig_reload(self, test_modified=True):
        if not hasattr(self, 'screen'):
            return False
        if test_modified and self.screen.modified():
            res = sur_3b(_('This record has been modified\n'
                    'do you want to save it ?'))
            if res == 'ok':
                self.sig_save(None)
            elif res == 'ko':
                pass
            else:
                return False
        self.screen.cancel_current()
        set_cursor = False
        if self.screen.current_view.view_type != 'form':
            obj_id = self.id_get()
            self.screen.search_filter(self.screen.screen_container.get_text())
            for record in self.screen.group:
                if record.id == obj_id:
                    self.screen.current_record = record
                    set_cursor = True
                    break
        self.screen.display(set_cursor=set_cursor)
        self.message_info('')
        self.activate_save()
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

        def menu_position(menu):
            parent = widget.get_toplevel()
            parent_x, parent_y = parent.window.get_origin()
            widget_allocation = widget.get_allocation()
            return (
                widget_allocation.x + parent_x,
                widget_allocation.y + widget_allocation.height + parent_y,
                False
            )
        menu.show_all()
        menu.popup(None, None, menu_position, 0, 0)

    def message_info(self, message, color='red'):
        if message:
            self.info_label.set_label(message)
            self.eb_info.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(
                COLOR_SCHEMES.get(color, 'white')))
            self.eb_info.show_all()
        else:
            self.info_label.set_label('')
            self.eb_info.hide()

    def _record_message(self, screen, signal_data):
        name = '_'
        if signal_data[0]:
            name = str(signal_data[0])
        for button_id in ('print', 'action', 'relate', 'email', 'open', 'save',
                'attach'):
            button = self.buttons[button_id]
            can_be_sensitive = getattr(button, '_can_be_sensitive', True)
            button.props.sensitive = (bool(signal_data[0])
                and can_be_sensitive)
        button_switch = self.buttons['switch']
        button_switch.props.sensitive = self.screen.number_of_views > 1

        msg = name + ' / ' + str(signal_data[1])
        if signal_data[1] < signal_data[2]:
            msg += _(' of ') + str(signal_data[2])
        self.status_label.set_text(msg)
        self.message_info('')
        self.activate_save()

    def _record_modified(self, screen, signal_data):
        # As it is called via idle_add, the form could have been destroyed in
        # the meantime.
        if screen == self.screen:
            self.activate_save()

    def _record_saved(self, screen, signal_data):
        self.activate_save()
        self.update_attachment_count()

    def modified_save(self):
        self.screen.current_view.set_value()
        if self.screen.modified():
            value = sur_3b(
                _('This record has been modified\n'
                    'do you want to save it ?'))
            if value == 'ok':
                return self.sig_save(None)
            if value == 'ko':
                return self.sig_reload(test_modified=False)
            return False
        return True

    def sig_close(self, widget=None):
        for dialog in self.dialogs[:]:
            dialog.destroy()
        return self.modified_save()

    def _action(self, action, atype):
        action = action.copy()
        if not self.screen.save_current():
            return
        record_id = self.screen.id_get()
        record_ids = self.screen.sel_ids_get()
        action = Action.evaluate(action, atype, self.screen.current_record)
        data = {
            'model': self.screen.model_name,
            'id': record_id,
            'ids': record_ids,
        }
        Action._exec_action(action, data, self.context)

    def activate_save(self):
        self.buttons['save'].props.sensitive = self.screen.modified()

    def sig_win_close(self, widget):
        Main.get_main().sig_win_close(widget)

    def create_toolbar(self, toolbars):
        gtktoolbar = super(Form, self).create_toolbar(toolbars)

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
                tbutton._can_be_sensitive = bool(tbutton._menu.get_children())
            else:
                tbutton = gtk.SeparatorToolItem()
            gtktoolbar.insert(tbutton, -1)

        return gtktoolbar

    def _create_popup_menu(self, widget, keyword, actions, special_action):
        menu = gtk.Menu()
        menu.connect('deactivate', self._popup_menu_hide, widget)

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
        if keyword == 'action':
            menu.add(gtk.SeparatorMenuItem())
            for plugin in plugins.MODULES:
                for name, func in plugin.get_plugins(self.model):
                    menuitem = gtk.MenuItem('_' + name)
                    menuitem.set_use_underline(True)
                    menuitem.connect('activate', lambda m, func: func({
                                'model': self.model,
                                'ids': self.id_get(),
                                'id': self.id_get(),
                                }), func)
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

    def set_cursor(self):
        if self.screen:
            self.screen.set_cursor(reset_view=False)
