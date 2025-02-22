# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Form"
import csv
import gettext
import locale
import os
from itertools import zip_longest

from gi.repository import Gdk, GLib, Gtk

import tryton.common as common
from tryton import plugins
from tryton.action import Action
from tryton.common import RPCException, RPCExecute, sur, sur_3b, tempfile
from tryton.common.common import selection as selection_
from tryton.common.popup_menu import popup
from tryton.common.underline import set_underline
from tryton.gui import Main
from tryton.gui.window import Window
from tryton.gui.window.attachment import Attachment
from tryton.gui.window.email_ import Email
from tryton.gui.window.log import Log
from tryton.gui.window.note import Note
from tryton.gui.window.revision import Revision
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_export import WinExport
from tryton.gui.window.win_import import WinImport

from .tabcontent import TabContent

_ = gettext.gettext


class Form(TabContent):
    "Form"

    def __init__(self, model, res_id=None, name='', **attributes):
        super(Form, self).__init__(**attributes)

        self.model = model
        self.res_id = res_id
        self.mode = attributes.get('mode')
        self.view_ids = attributes.get('view_ids')
        self.dialogs = []

        if not name:
            name = common.MODELNAME.get(model)
        self.name = name

        loading_ids = res_id not in (None, False)
        if loading_ids:
            attributes.pop('tab_domain', None)
        self.screen = Screen(self.model, breadcrumb=[self.name], **attributes)
        self.screen.widget.show()
        self.screen.windows.append(self)

        self.create_tabcontent()

        self.set_buttons_sensitive()

        self.attachment_screen = None

        if loading_ids:
            if isinstance(res_id, int):
                res_id = [res_id]
            self.screen.load(res_id)
            if res_id:
                self.screen.current_record = self.screen.group.get(res_id[0])
            self.screen.display()
        else:
            if self.screen.current_view.view_type == 'form':
                self.sig_new(None, autosave=False)
            if self.screen.current_view.view_type \
                    in ('tree', 'graph', 'calendar'):
                self.screen.search_filter()

        self.update_revision()
        self.set_buttons_sensitive()

    def get_toolbars(self):
        try:
            return RPCExecute('model', self.model, 'view_toolbar_get',
                context=self.screen.context)
        except RPCException:
            return {}

    def create_tabcontent(self):
        super().create_tabcontent()

        self.attachment_preview = Gtk.Viewport()
        self.attachment_preview.set_shadow_type(Gtk.ShadowType.NONE)
        self.attachment_preview.show()
        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_shadow_type(Gtk.ShadowType.NONE)
        scrolledwindow.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolledwindow.add(self.attachment_preview)
        scrolledwindow.set_size_request(300, -1)
        self.main.pack2(scrolledwindow, resize=False, shrink=True)

    def widget_get(self):
        return self.screen.widget

    def compare(self, model, attributes):
        if not attributes:
            return False
        return (
            self.screen.view_index == 0
            and self.model == model
            and self.res_id == attributes.get('res_id')
            and self.attributes.get('domain') == attributes.get('domain')
            and self.attributes.get('view_ids') == attributes.get('view_ids')
            and (attributes.get('view_ids')
                or (self.attributes.get('mode') or ['tree', 'form']) == (
                    attributes.get('mode') or ['tree', 'form']))
            and self.screen.local_context == attributes.get('context')
            and self.attributes.get('search_value') == (
                attributes.get('search_value'))
            and self.attributes.get('tab_domain') == (
                attributes.get('tab_domain')))

    def __hash__(self):
        return id(self)

    def destroy(self):
        self.screen.destroy()

    def sig_attach(self, widget=None):
        def window(widget):
            return Attachment(
                record, lambda: self.refresh_resources(reload=True))

        def add_file(widget):
            filenames = common.file_selection(_("Select"), multi=True)
            if filenames:
                attachment = window(widget)
                for filename in filenames:
                    attachment.add_file(filename)

        def preview(widget):
            children = self.attachment_preview.get_children()
            for child in children:
                self.attachment_preview.remove(child)
            if widget.get_active():
                self.attachment_preview.add(
                    self._attachment_preview_widget())
                self.attachment_preview.get_parent().show()
                self.refresh_attachment_preview()
            else:
                self.attachment_screen = None
                self.attachment_preview.get_parent().hide()

        def activate(widget, callback):
            callback()

        button = self.buttons['attach']
        if widget != button:
            if button.props.sensitive:
                button.props.active = True
            return
        record = self.screen.current_record
        menu = button._menu = Gtk.Menu()
        for name, callback in Attachment.get_attachments(record):
            item = Gtk.MenuItem(label=name)
            item.connect('activate', activate, callback)
            menu.add(item)
        menu.add(Gtk.SeparatorMenuItem())
        add_item = Gtk.MenuItem(label=_("Add..."))
        add_item.connect('activate', add_file)
        menu.add(add_item)
        preview_item = Gtk.CheckMenuItem(label=_("Preview"))
        preview_item.set_active(bool(
                self.attachment_preview.get_children()))
        preview_item.connect('toggled', preview)
        menu.add(preview_item)
        manage_item = Gtk.MenuItem(label=_("Manage..."))
        manage_item.connect('activate', window)
        menu.add(manage_item)
        menu.show_all()
        menu.connect('deactivate', self._popup_menu_hide, button)
        self.action_popup(button)

    def _attachment_preview_widget(self):
        vbox = Gtk.VBox(homogeneous=False, spacing=2)
        vbox.set_margin_start(4)
        hbox = Gtk.HBox(homogeneous=False, spacing=0)
        hbox.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(hbox, expand=False, fill=True, padding=0)
        hbox.set_border_width(2)
        tooltips = common.Tooltips()

        but_prev = Gtk.Button()
        tooltips.set_tip(but_prev, _("Previous"))
        but_prev.add(common.IconFactory.get_image(
                'tryton-back', Gtk.IconSize.SMALL_TOOLBAR))
        but_prev.set_relief(Gtk.ReliefStyle.NONE)
        hbox.pack_start(but_prev, expand=False, fill=False, padding=0)

        label = Gtk.Label(label='(0,0)')
        hbox.pack_start(label, expand=False, fill=False, padding=0)

        but_next = Gtk.Button()
        tooltips.set_tip(but_next, _("Next"))
        but_next.add(common.IconFactory.get_image(
                'tryton-forward', Gtk.IconSize.SMALL_TOOLBAR))
        but_next.set_relief(Gtk.ReliefStyle.NONE)
        hbox.pack_start(but_next, expand=False, fill=False, padding=0)

        vbox.show_all()
        self.attachment_screen = screen = Screen(
            'ir.attachment', readonly=True, mode=['form'],
            context={
                'preview': True,
                })
        screen.widget.show()

        but_prev.connect('clicked', lambda *a: screen.display_prev())
        but_next.connect('clicked', lambda *a: screen.display_next())

        class Preview():
            def record_message(self, position, length, *args):
                label.set_text('(%s/%s)' % (position or '_', length))
                but_prev.set_sensitive(screen.has_prev())
                but_next.set_sensitive(screen.has_next())
        screen.windows.append(Preview())

        vbox.pack_start(screen.widget, expand=True, fill=True, padding=0)
        return vbox

    def refresh_attachment_preview(self, force=False):
        if not self.attachment_screen:
            return
        record = self.screen.current_record
        if not record:
            return
        resource = '%s,%s' % (record.model_name, record.id)
        domain = [
            ('resource', '=', resource),
            ('type', '=', 'data'),
            ]
        if self.attachment_screen.domain != domain or force:
            self.attachment_screen.domain = domain
            self.attachment_screen.search_filter()
            group = self.attachment_screen.group
            if group:
                self.attachment_screen.current_record = group[0]
                self.attachment_screen.display()

    def sig_note(self, widget=None):
        record = self.screen.current_record
        if not record or record.id < 0:
            return
        Note(record,
            lambda: self.refresh_resources(reload=True))

    def refresh_resources(self, reload=False):
        record = self.screen.current_record
        self.update_resources(
            record.get_resources(reload=reload) if record else None)
        if reload:
            self.refresh_attachment_preview(True)

    def update_resources(self, resources):
        if not resources:
            resources = {}
        record = self.screen.current_record
        sensitive = record.id >= 0 if record else False

        def update(name, label, icon, badge):
            button = self.buttons[name]
            button.set_label(label)
            image = common.IconFactory.get_image(
                icon, Gtk.IconSize.LARGE_TOOLBAR, badge=badge)
            image.show()
            button.set_icon_widget(image)
            button.props.sensitive = sensitive

        attachment_count = resources.get('attachment_count', 0)
        badge = 1 if attachment_count else None
        label = _("Attachment (%s)") % attachment_count
        update('attach', label, 'tryton-attach', badge)

        note_count = resources.get('note_count', 0)
        note_unread = resources.get('note_unread', 0)
        if note_unread:
            badge = 2
        elif note_count:
            badge = 1
        else:
            badge = None
        label = _("Note (%d/%d)") % (note_unread, note_count)
        update('note', label, 'tryton-note', badge)

    def sig_switch(self, widget=None):
        if not self.modified_save():
            return
        self.screen.switch_view()

    def sig_logs(self, widget=None):
        current_record = self.screen.current_record
        if not current_record or current_record.id < 0:
            self.info_bar_add(
                _('You have to select one record.'), Gtk.MessageType.INFO)
            return
        Log(current_record)

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
        tooltips = common.Tooltips()
        revision = self.screen.context.get('_datetime')
        if revision:
            format_ = self.screen.context.get('date_format', '%x')
            format_ += ' %H:%M:%S.%f'
            revision_label = ' @ %s' % revision.strftime(format_)
            label = common.ellipsize(
                self.name, 80 - len(revision_label)) + revision_label
            tooltip = self.name + revision_label
        else:
            label = common.ellipsize(self.name, 80)
            tooltip = self.name
        self.title.set_text(label)
        tooltips.set_tip(self.title, tooltip)
        self.set_buttons_sensitive()

    def set_buttons_sensitive(self):
        revision = self.screen.context.get('_datetime')
        if not revision:
            access = common.MODELACCESS[self.model]
            modified = self.screen.modified()
            for name, sensitive in [
                    ('new', access['create'] and not modified),
                    ('save',
                        (access['create'] or access['write'])
                        and modified and not self.screen.readonly),
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
        if (not common.MODELACCESS[self.model]['delete']
                or not self.screen.deletable):
            return
        if self.screen.current_view.view_type == 'form':
            msg = _('Are you sure to remove this record?')
        else:
            msg = _('Are you sure to remove those records?')
        if sur(msg):
            if not self.screen.remove(delete=True, force_remove=True):
                self.info_bar_add(
                    _('Records not removed.'), Gtk.MessageType.ERROR)
            else:
                self.info_bar_add(_('Records removed.'), Gtk.MessageType.INFO)
                self.screen.count_tab_domain(True)

    def sig_import(self, widget=None):
        WinImport(self.title.get_text(), self.model, self.screen.context)

    def sig_export(self, widget=None):
        if not self.modified_save():
            return
        export = WinExport(self.title.get_text(), self.screen)
        for name in self.screen.current_view.get_fields():
            type = self.screen.group.fields[name].attrs['type']
            if type == 'selection':
                export.sel_field(name + '.translated')
            elif type == 'reference':
                export.sel_field(name + '.translated')
                export.sel_field(name + '/rec_name')
            else:
                export.sel_field(name)

    def do_export(self, widget, export):
        if not self.modified_save():
            return
        if export.get('records') == 'listed':
            ids = [r.id for r in self.screen.listed_records]
            paths = self.screen.listed_paths
        else:
            ids = [r.id for r in self.screen.selected_records]
            paths = self.screen.selected_paths
        fields = [f['name'] for f in export['export_fields.']]
        data = RPCExecute(
            'model', self.model, 'export_data', ids, fields, export['header'],
            context=self.screen.context)
        delimiter = ','
        if os.name == 'nt' and ',' == locale.localeconv()['decimal_point']:
            delimiter = ';'
        fileno, fname = tempfile.mkstemp(
            '.csv', common.slugify(export['name']) + '_')
        with open(fname, 'w') as fp:
            writer = csv.writer(fp, delimiter=delimiter)
            for row, path in zip_longest(data, paths or []):
                indent = len(path) - 1 if path else 0
                if row:
                    writer.writerow(WinExport.format_row(row, indent=indent))
        os.close(fileno)
        common.file_open(fname, 'csv')

    def sig_new(self, widget=None, autosave=True):
        if not common.MODELACCESS[self.model]['create']:
            return
        if autosave:
            if not self.modified_save():
                return
        self.screen.new()
        self.info_bar_clear()
        self.set_buttons_sensitive()

    def sig_copy(self, widget=None):
        if not common.MODELACCESS[self.model]['create']:
            return
        if not self.modified_save():
            return
        if self.screen.copy():
            self.info_bar_add(
                _('Working now on the duplicated record(s).'),
                Gtk.MessageType.INFO)
            self.screen.count_tab_domain(True)

    def sig_save(self, widget=None):
        if widget:
            # Called from button so we must save the tree state
            self.screen.save_tree_state()
        if (self.screen.readonly
                or not (common.MODELACCESS[self.model]['write']
                    or common.MODELACCESS[self.model]['create'])):
            return
        if self.screen.save_current():
            self.info_bar_add(_('Record saved.'), Gtk.MessageType.INFO)
            self.screen.count_tab_domain(True)
            return True
        else:
            self.info_bar_add(
                self.screen.invalid_message(), Gtk.MessageType.ERROR)
            return False

    def sig_previous(self, widget=None):
        if not self.modified_save():
            return
        self.screen.display_prev()
        self.info_bar_clear()
        self.set_buttons_sensitive()

    def sig_next(self, widget=None):
        if not self.modified_save():
            return
        self.screen.display_next()
        self.info_bar_clear()
        self.set_buttons_sensitive()

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
        self.info_bar_clear()
        self.set_buttons_sensitive()
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

    def sig_email(self, widget):
        def is_report(action):
            return action['type'] == 'ir.action.report'

        if self.buttons['email'].props.sensitive:
            if not self.modified_save():
                return
            record = self.screen.current_record
            if not record or record.id < 0:
                return
            toolbars = self.get_toolbars()
            title = self.title.get_text()
            prints = filter(is_report, toolbars['print'])
            emails = {e['name']: e['id'] for e in toolbars['emails']}
            template = selection_(_("Template"), emails, alwaysask=True)
            if template:
                template = template[1]
            Email(
                '%s: %s' % (title, record.rec_name()), record, prints,
                template=template)

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
        popup(menu, widget)

    def record_message(self, position, size, max_size, record_id):
        def set_sensitive(button_id, sensitive):
            if button_id in self.buttons:
                self.buttons[button_id].props.sensitive = sensitive
            if button_id in self.menu_buttons:
                self.menu_buttons[button_id].props.sensitive = sensitive

        name = str(position) if position else '_'
        selected = len(self.screen.selected_records)
        view_type = self.screen.current_view.view_type
        next_view_type = self.screen.next_view_type
        has_views = self.screen.number_of_views > 1
        if selected > 1:
            name += '#%i' % selected
        for button_id in ['print', 'relate', 'email', 'open', 'attach']:
            button = self.buttons[button_id]
            can_be_sensitive = getattr(button, '_can_be_sensitive', True)
            if button_id in {'print', 'relate', 'email', 'open'}:
                action_type = button_id
                if button_id == 'open':
                    action_type = 'print'
                can_be_sensitive |= any(
                    b.attrs.get('keyword', 'action') == action_type
                    for b in self.screen.get_buttons())
            set_sensitive(button_id, bool(position) and can_be_sensitive)
        set_sensitive(
            'switch',
            (position or view_type == 'form' or next_view_type != 'form')
            and has_views)
        set_sensitive('remove', self.screen.deletable)
        set_sensitive('previous', self.screen.has_prev())
        set_sensitive('next', self.screen.has_next())

        if size < max_size:
            msg = "%s@%s/%s" % (
                name, common.humanize(size), common.humanize(max_size))
            if max_size >= self.screen.count_limit:
                msg += "+"
        else:
            msg = "%s/%s" % (name, common.humanize(size))
        self.status_label.set_text(msg)
        self.info_bar_clear()
        self.set_buttons_sensitive()
        self.refresh_attachment_preview()

    def record_modified(self):
        def _record_modified():
            # As it is called via idle_add, the form could have been destroyed
            # in the meantime.
            if self.widget_get().props.window:
                self.set_buttons_sensitive()
        GLib.idle_add(_record_modified)
        self.info_bar_refresh()

    def record_saved(self):
        self.set_buttons_sensitive()
        self.refresh_resources()

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
                record_id = self.screen.current_record.id
                if self.sig_reload(test_modified=False):
                    if record_id < 0:
                        return None
                    elif self.screen.current_record:
                        return record_id == self.screen.current_record.id
            return False
        return True

    def sig_close(self, widget=None):
        for dialog in reversed(self.dialogs[:]):
            dialog.destroy()
        modified_save = self.modified_save()
        return True if modified_save is None else modified_save

    def _action(self, action, atype):
        if not self.modified_save():
            return
        action = action.copy()
        record_id = (self.screen.current_record.id
            if self.screen.current_record else None)
        if action.get('records') == 'listed':
            record_ids = [r.id for r in self.screen.listed_records]
            record_paths = self.screen.listed_paths
        else:
            record_ids = [r.id for r in self.screen.selected_records]
            record_paths = self.screen.selected_paths
        data = {
            'model': self.screen.model_name,
            'model_context': (
                self.screen.context_screen.model_name
                if self.screen.context_screen else None),
            'id': record_id,
            'ids': record_ids,
            'paths': record_paths,
        }
        Action.execute(action, data, context=self.screen.local_context)

    def sig_win_close(self, widget):
        Main().sig_win_close(widget)

    def create_toolbar(self, toolbars):
        gtktoolbar = super(Form, self).create_toolbar(toolbars)

        attach_btn = self.buttons['attach']
        attach_btn.drag_dest_set(
            Gtk.DestDefaults.ALL, [
                Gtk.TargetEntry.new('text/uri-list', 0, 0),
                Gtk.TargetEntry.new('text/plain', 0, 0),
                ],
            Gdk.DragAction.MOVE | Gdk.DragAction.COPY)
        attach_btn.connect('drag_data_received',
            self.attach_drag_data_received)

        pos = gtktoolbar.get_item_index(self.buttons['email'])
        iconstock = {
            'print': 'tryton-print',
            'action': 'tryton-launch',
            'relate': 'tryton-link',
            'open': 'tryton-open',
        }
        for action_type, special_action, action_name, tooltip in (
                ('action', 'action', _('Action'), _('Launch action')),
                ('relate', 'relate', _('Relate'), _('Open related records')),
                (None,) * 4,
                ('print', 'open', _('Report'), _('Open report')),
                ('print', 'print', _('Print'), _('Print report')),
                ):
            if action_type is not None:
                tbutton = Gtk.ToggleToolButton()
                tbutton.set_icon_widget(common.IconFactory.get_image(
                        iconstock.get(special_action),
                        Gtk.IconSize.LARGE_TOOLBAR))
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
                tbutton = Gtk.SeparatorToolItem()
            gtktoolbar.insert(tbutton, pos)
            pos += 1

        exports = toolbars['exports']
        if exports:
            tbutton = self.buttons['open']
            tbutton._can_be_sensitive = True
            menu = tbutton._menu
            if menu.get_children():
                menu.add(Gtk.SeparatorMenuItem())
            for export in exports:
                menuitem = Gtk.MenuItem(set_underline(export['name']))
                menuitem.set_use_underline(True)
                menuitem.connect('activate', self.do_export, export)
                menu.add(menuitem)

        last_item = gtktoolbar.get_nth_item(gtktoolbar.get_n_items() - 1)
        if not isinstance(last_item, Gtk.SeparatorToolItem):
            gtktoolbar.insert(Gtk.SeparatorToolItem(), -1)

        url_button = Gtk.ToggleToolButton()
        url_button.set_icon_widget(
            common.IconFactory.get_image(
                'tryton-public', Gtk.IconSize.LARGE_TOOLBAR))
        url_button.set_label(_('_Copy URL'))
        url_button.set_use_underline(True)
        self.tooltips.set_tip(
            url_button, _('Copy URL into clipboard'))
        url_button._menu = url_menu = Gtk.Menu()
        url_menuitem = Gtk.MenuItem()
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
        menu = Gtk.Menu()
        menu.connect('deactivate', self._popup_menu_hide, widget)
        widget.connect('toggled', self._update_popup_menu, menu, keyword)

        for action in actions:
            new_action = action.copy()
            if special_action == 'print':
                new_action['direct_print'] = True
            menuitem = Gtk.MenuItem(label=set_underline(action['name']))
            menuitem.set_use_underline(True)
            menuitem.connect('activate', self._popup_menu_selected, widget,
                new_action, keyword)
            menu.add(menuitem)
        return menu

    def _popup_menu_selected(self, menuitem, togglebutton, action, keyword):
        event = Gtk.get_current_event()
        allow_similar = False
        if (event.state & Gdk.ModifierType.CONTROL_MASK
                or event.state & Gdk.ModifierType.MOD1_MASK):
            allow_similar = True
        with Window(hide_current=True, allow_similar=allow_similar):
            self._action(action, keyword)
        togglebutton.props.active = False

    def _popup_menu_hide(self, menuitem, togglebutton):
        togglebutton.props.active = False

    def _update_popup_menu(self, tbutton, menu, keyword):
        for item in menu.get_children():
            if getattr(item, '_update_action', False):
                menu.remove(item)

        buttons = [b for b in self.screen.get_buttons()
            if keyword == b.attrs.get('keyword', 'action')]
        if buttons and menu.get_children():
            separator = Gtk.SeparatorMenuItem()
            separator._update_action = True
            menu.add(separator)
        for button in buttons:
            menuitem = Gtk.MenuItem(
                label=set_underline(button.attrs.get('string', _('Unknown'))),
                use_underline=True)
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
            separator = Gtk.SeparatorMenuItem()
            separator._update_action = True
            menu.add(separator)
        for name, func in kw_plugins:
            menuitem = Gtk.MenuItem(label=set_underline(name))
            menuitem.set_use_underline(True)
            menuitem.connect('activate', lambda m, func: func({
                        'model': self.screen.model_name,
                        'model_context': (
                            self.screen.context_screen.model_name
                            if self.screen.context_screen else None),
                        'id': (self.screen.current_record.id
                            if self.screen.current_record else None),
                        'ids': [r.id
                            for r in self.screen.selected_records],
                        'paths': self.screen.selected_paths,
                        }), func)
            menuitem._update_action = True
            menu.add(menuitem)

    def url_copy(self, menuitem):
        url = self.screen.get_url(self.name)
        for selection in [
                Gdk.Atom.intern('PRIMARY', True),
                Gdk.Atom.intern('CLIPBOARD', True),
                ]:
            clipboard = Gtk.Clipboard.get(selection)
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
            lambda: self.refresh_resources(reload=True))
        if info == 0:
            if selection.get_uris():
                for uri in selection.get_uris():
                    # Win32 cut&paste terminates the list with a NULL character
                    if not uri or uri == '\0':
                        continue
                    win_attach.add_uri(uri)
            else:
                win_attach.add_uri(selection.get_text())
