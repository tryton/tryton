# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gdk, Gtk

import tryton.common as common
from .widget import Widget
from tryton.common.completion import get_completion, update_completion
from tryton.common.domain_parser import quote
from tryton.common.underline import set_underline
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm

_ = gettext.gettext


class Many2Many(Widget):
    expand = True

    def __init__(self, view, attrs):
        super(Many2Many, self).__init__(view, attrs)

        self.widget = Gtk.Frame()
        self.widget.set_shadow_type(Gtk.ShadowType.NONE)
        self.widget.get_accessible().set_name(attrs.get('string', ''))
        vbox = Gtk.VBox(homogeneous=False, spacing=5)
        self.widget.add(vbox)
        self._readonly = True
        self._required = False
        self._position = 0

        hbox = Gtk.HBox(homogeneous=False, spacing=0)
        hbox.set_border_width(2)

        self.title = Gtk.Label(
            label=set_underline(attrs.get('string', '')),
            use_underline=True, halign=Gtk.Align.START)
        hbox.pack_start(self.title, expand=True, fill=True, padding=0)

        hbox.pack_start(Gtk.VSeparator(), expand=False, fill=True, padding=0)

        tooltips = common.Tooltips()

        self.wid_text = Gtk.Entry()
        self.wid_text.set_placeholder_text(_('Search'))
        self.wid_text.set_property('width_chars', 13)
        self.wid_text.connect('focus-out-event', self._focus_out)
        self.focus_out = True
        hbox.pack_start(self.wid_text, expand=True, fill=True, padding=0)

        if int(self.attrs.get('completion', 1)):
            self.wid_completion = get_completion(
                create=self.attrs.get('create', True)
                and common.MODELACCESS[self.attrs['relation']]['create'])
            self.wid_completion.connect('match-selected',
                self._completion_match_selected)
            self.wid_completion.connect('action-activated',
                self._completion_action_activated)
            self.wid_text.set_completion(self.wid_completion)
            self.wid_text.connect('changed', self._update_completion)
        else:
            self.wid_completion = None

        self.but_add = Gtk.Button(can_focus=False)
        tooltips.set_tip(self.but_add, _('Add existing record'))
        self.but_add.connect('clicked', self._sig_add)
        self.but_add.add(common.IconFactory.get_image(
                'tryton-add', Gtk.IconSize.SMALL_TOOLBAR))
        self.but_add.set_relief(Gtk.ReliefStyle.NONE)
        hbox.pack_start(self.but_add, expand=False, fill=False, padding=0)

        self.but_remove = Gtk.Button(can_focus=False)
        tooltips.set_tip(self.but_remove, _('Remove selected record'))
        self.but_remove.connect('clicked', self._sig_remove)
        self.but_remove.add(common.IconFactory.get_image(
                'tryton-remove', Gtk.IconSize.SMALL_TOOLBAR))
        self.but_remove.set_relief(Gtk.ReliefStyle.NONE)
        hbox.pack_start(self.but_remove, expand=False, fill=False, padding=0)

        tooltips.enable()

        frame = Gtk.Frame()
        frame.add(hbox)
        frame.set_shadow_type(Gtk.ShadowType.OUT)
        vbox.pack_start(frame, expand=False, fill=True, padding=0)

        self.screen = Screen(attrs['relation'],
            view_ids=attrs.get('view_ids', '').split(','),
            mode=['tree'], views_preload=attrs.get('views', {}),
            order=attrs.get('order'),
            row_activate=self._on_activate,
            readonly=True,
            limit=None)
        self.screen.signal_connect(self, 'record-message', self._sig_label)

        vbox.pack_start(self.screen.widget, expand=True, fill=True, padding=0)

        self.title.set_mnemonic_widget(
            self.screen.current_view.mnemonic_widget)

        self.screen.widget.connect('key_press_event', self.on_keypress)
        self.wid_text.connect('key_press_event', self.on_keypress)

    def on_keypress(self, widget, event):
        editable = self.wid_text.get_editable()
        activate_keys = [Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab]
        remove_keys = [Gdk.KEY_Delete, Gdk.KEY_KP_Delete]
        if not self.wid_completion:
            activate_keys.append(Gdk.KEY_Return)
        if widget == self.screen.widget:
            if event.keyval == Gdk.KEY_F3 and editable:
                self._sig_add()
                return True
            elif event.keyval == Gdk.KEY_F2:
                self._sig_edit()
                return True
            elif event.keyval in remove_keys and editable:
                self._sig_remove()
                return True
        elif widget == self.wid_text:
            if event.keyval == Gdk.KEY_F3:
                self._sig_new()
                return True
            elif event.keyval == Gdk.KEY_F2:
                self._sig_add()
                return True
            elif event.keyval in activate_keys and self.wid_text.get_text():
                self._sig_add()
                self.wid_text.grab_focus()
        return False

    def destroy(self):
        self.wid_text.disconnect_by_func(self._focus_out)
        self.screen.destroy()

    def _sig_add(self, *args):
        if not self.focus_out:
            return
        domain = self.field.domain_get(self.record)
        add_remove = self.record.expr_eval(self.attrs.get('add_remove'))
        if add_remove:
            domain = [domain, add_remove]
        context = self.field.get_search_context(self.record)
        order = self.field.get_search_order(self.record)
        value = self.wid_text.get_text()

        self.focus_out = False

        def callback(result):
            self.focus_out = True
            if result:
                ids = [x[0] for x in result]
                self.screen.load(ids, modified=True)
                self.screen.display(res_id=ids[0])
            self.screen.set_cursor()
            self.wid_text.set_text('')
        win = WinSearch(self.attrs['relation'], callback, sel_multi=True,
            context=context, domain=domain, order=order,
            view_ids=self.attrs.get('view_ids', '').split(','),
            views_preload=self.attrs.get('views', {}),
            new=self.attrs.get('create', True),
            title=self.attrs.get('string'))
        win.screen.search_filter(quote(value))
        if len(win.screen.group) == 1:
            win.response(None, Gtk.ResponseType.OK)
        else:
            win.show()

    def _sig_remove(self, *args):
        self.screen.remove(remove=True)

    def _on_activate(self):
        self._sig_edit()

    def _get_screen_form(self):
        domain = self.field.domain_get(self.record)
        add_remove = self.record.expr_eval(self.attrs.get('add_remove'))
        if add_remove:
            domain = [domain, add_remove]
        context = self.field.get_context(self.record)
        # Remove the first tree view as mode is form only
        view_ids = self.attrs.get('view_ids', '').split(',')[1:]
        return Screen(self.attrs['relation'], domain=domain,
            view_ids=view_ids,
            mode=['form'], views_preload=self.attrs.get('views', {}),
            context=context)

    def _sig_edit(self):
        if not self.screen.current_record:
            return
        # Create a new screen that is not linked to the parent otherwise on the
        # save of the record will trigger the save of the parent
        screen = self._get_screen_form()
        screen.load([self.screen.current_record.id])

        def callback(result):
            if result:
                screen.current_record.save()
                # Force a reload on next display
                self.screen.current_record.cancel()
                # Force a display to clear the CellCache
                self.screen.display()
        WinForm(screen, callback, title=self.attrs.get('string'))

    def _sig_new(self):
        screen = self._get_screen_form()

        def callback(result):
            self.focus_out = True
            if result:
                record = screen.current_record
                self.screen.load([record.id], modified=True)
            self.wid_text.set_text('')
            self.wid_text.grab_focus()

        self.focus_out = False
        WinForm(screen, callback, new=True, save_current=True,
            title=self.attrs.get('string'), rec_name=self.wid_text.get_text())

    def _readonly_set(self, value):
        self._readonly = value
        self._set_button_sensitive()
        self.wid_text.set_sensitive(not value)
        self.wid_text.set_editable(not value)
        self._set_label_state()

    def _required_set(self, value):
        self._required = value
        self._set_label_state()

    def _set_label_state(self):
        common.apply_label_attributes(
            self.title, self._readonly, self._required)

    def _set_button_sensitive(self):
        if self.record and self.field:
            field_size = self.record.expr_eval(self.attrs.get('size'))
            m2m_size = len(self.field.get_eval(self.record))
            size_limit = (field_size is not None
                and m2m_size >= field_size >= 0)
        else:
            size_limit = False

        self.but_add.set_sensitive(bool(
                not self._readonly
                and not size_limit))
        self.but_remove.set_sensitive(bool(
                not self._readonly
                and self._position))

    def _sig_label(self, screen, signal_data):
        self._position = signal_data[0]
        self._set_button_sensitive()

    def display(self):
        super(Many2Many, self).display()
        if not self.field:
            self.screen.new_group()
            self.screen.current_record = None
            self.screen.parent = None
            self.screen.display()
            return False
        new_group = self.field.get_client(self.record)
        if id(self.screen.group) != id(new_group):
            self.screen.group = new_group
        self.screen.display()
        return True

    def set_value(self):
        self.screen.current_view.set_value()
        return True

    def _completion_match_selected(self, completion, model, iter_):
        record_id, = model.get(iter_, 1)
        self.screen.load([record_id], modified=True)
        self.wid_text.set_text('')
        self.wid_text.grab_focus()

        completion_model = self.wid_completion.get_model()
        completion_model.clear()
        completion_model.search_text = self.wid_text.get_text()
        return True

    def _update_completion(self, widget):
        if self._readonly:
            return
        if not self.record:
            return
        model = self.attrs['relation']
        update_completion(self.wid_text, self.record, self.field, model)

    def _completion_action_activated(self, completion, index):
        if index == 0:
            self._sig_add()
            self.wid_text.grab_focus()
        elif index == 1:
            self._sig_new()
