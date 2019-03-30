# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from gi.repository import Gdk, GLib, Gtk

import tryton.common as common
from tryton.common import RPCExecute, RPCException
from tryton.common import TRYTON_ICON
from tryton.common.underline import set_underline
from tryton.common.widget_style import widget_class
from tryton.gui import Main
from tryton.gui.window.nomodal import NoModal

_ = gettext.gettext


class Widget(object):
    expand = False
    default_width_chars = 25

    def __init__(self, view, attrs):
        super(Widget, self).__init__()
        self.view = view
        self.attrs = attrs
        self.widget = None
        self.mnemonic_widget = None
        self.visible = True
        self._readonly = False

    @property
    def field_name(self):
        return self.attrs['name']

    @property
    def model_name(self):
        return self.view.screen.model_name

    @property
    def record(self):
        return self.view.record

    @property
    def field(self):
        if self.record:
            return self.record.group.fields[self.field_name]
        return None

    def destroy(self):
        pass

    def sig_activate(self, widget=None):
        # emulate a focus_out so that the onchange is called if needed
        self._focus_out()

    def _readonly_set(self, readonly):
        self._readonly = readonly

    def _required_set(self, required):
        pass

    def _invisible_widget(self):
        return self.widget

    @property
    def _invalid_widget(self):
        return self.widget

    @property
    def _required_widget(self):
        return self.widget

    @property
    def modified(self):
        return False

    def send_modified(self, *args):
        def send(value):
            if not self.widget.props.window:
                return
            if self.record and self.get_value() == value:
                self.record.signal('record-modified')

        def get_value():
            if not self.widget.props.window:
                return
            GLib.timeout_add(300, send, self.get_value())
        # Wait the current event is finished to retreive the value
        GLib.idle_add(get_value)
        return False

    def invisible_set(self, value):
        widget = self._invisible_widget()
        if value and value != '0':
            self.visible = False
            widget.hide()
        else:
            self.visible = True
            widget.show()

    def _focus_out(self, *args):
        if not self.field:
            return False
        if not self.visible:
            return False
        self.set_value()

    def display(self):
        if not self.field:
            self._readonly_set(self.attrs.get('readonly', True))
            self.invisible_set(self.attrs.get('invisible', False))
            self._required_set(False)
            return
        states = self.field.get_state_attrs(self.record)
        readonly = self.attrs.get('readonly', states.get('readonly', False))
        if self.view.screen.readonly:
            readonly = True
        self._readonly_set(readonly)
        widget_class(self.widget, 'readonly', readonly)
        self._required_set(not readonly and states.get('required', False))
        widget_class(
            self._required_widget, 'required',
            not readonly and states.get('required', False))
        invalid = states.get('invalid', False)
        widget_class(self._invalid_widget, 'invalid', not readonly and invalid)
        self.invisible_set(self.attrs.get(
                'invisible', states.get('invisible', False)))

    def set_value(self):
        pass


class TranslateDialog(NoModal):

    def __init__(self, widget, languages, readonly):
        NoModal.__init__(self)
        self.widget = widget
        self.win = Gtk.Dialog(
            title=_('Translation'), transient_for=self.parent,
            destroy_with_parent=True)
        Main().add_window(self.win)
        self.win.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.win.set_icon(TRYTON_ICON)
        self.win.connect('response', self.response)
        self.win.set_default_size(*self.default_size())

        self.accel_group = Gtk.AccelGroup()
        self.win.add_accel_group(self.accel_group)

        cancel_button = self.win.add_button(
            set_underline(_("Cancel")), Gtk.ResponseType.CANCEL)
        cancel_button.set_image(
            common.IconFactory.get_image('tryton-cancel', Gtk.IconSize.BUTTON))
        cancel_button.set_always_show_image(True)
        ok_button = self.win.add_button(
            set_underline(_("OK")), Gtk.ResponseType.OK)
        ok_button.set_image(
            common.IconFactory.get_image('tryton-ok', Gtk.IconSize.BUTTON))
        ok_button.set_always_show_image(True)
        ok_button.add_accelerator(
            'clicked', self.accel_group, Gdk.KEY_Return,
            Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)

        tooltips = common.Tooltips()

        self.widgets = {}
        grid = Gtk.Grid(column_spacing=3, row_spacing=3)
        for i, language in enumerate(languages):
            label = language['name'] + _(':')
            label = Gtk.Label(
                label=label,
                halign=Gtk.Align.END,
                valign=(Gtk.Align.START if self.widget.expand
                    else Gtk.Align.FILL))
            grid.attach(label, 0, i, 1, 1)

            context = dict(
                language=language['code'],
                fuzzy_translation=False,
                )
            try:
                value = RPCExecute('model', self.widget.record.model_name,
                    'read', [self.widget.record.id], [self.widget.field_name],
                    context={'language': language['code']}
                    )[0][self.widget.field_name]
            except RPCException:
                return
            context['fuzzy_translation'] = True
            try:
                fuzzy_value = RPCExecute('model',
                    self.widget.record.model_name, 'read',
                    [self.widget.record.id], [self.widget.field_name],
                    context=context)[0][self.widget.field_name]
            except RPCException:
                return
            if fuzzy_value is None:
                fuzzy_value = ''
            widget = self.widget.translate_widget()
            label.set_mnemonic_widget(widget)
            self.widget.translate_widget_set(widget, fuzzy_value)
            self.widget.translate_widget_set_readonly(widget, True)
            widget.set_vexpand(self.widget.expand)
            widget.set_hexpand(True)
            grid.attach(widget, 1, i, 1, 1)
            editing = Gtk.CheckButton()
            editing.connect('toggled', self.editing_toggled, widget)
            editing.props.sensitive = not readonly
            tooltips.set_tip(editing, _('Edit'))
            grid.attach(editing, 2, i, 1, 1)
            fuzzy = Gtk.CheckButton()
            fuzzy.set_active(value != fuzzy_value)
            fuzzy.props.sensitive = False
            tooltips.set_tip(fuzzy, _('Fuzzy'))
            grid.attach(fuzzy, 4, i, 1, 1)
            self.widgets[language['code']] = (widget, editing, fuzzy)

        tooltips.enable()
        vbox = Gtk.VBox()
        vbox.pack_start(grid, expand=self.widget.expand, fill=True, padding=0)
        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.NONE)
        viewport.add(vbox)
        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolledwindow.set_shadow_type(Gtk.ShadowType.NONE)
        scrolledwindow.add(viewport)
        self.win.vbox.pack_start(
            scrolledwindow, expand=True, fill=True, padding=0)
        self.win.show_all()

        self.register()
        self.show()

    def editing_toggled(self, editing, widget):
        self.widget.translate_widget_set_readonly(widget,
            not editing.get_active())

    def response(self, win, response):
        if response == Gtk.ResponseType.OK:
            for code, widget in self.widgets.items():
                widget, editing, fuzzy = widget
                if not editing.get_active():
                    continue
                value = self.widget.translate_widget_get(widget)
                context = dict(
                    language=code,
                    fuzzy_translation=False,
                    )
                try:
                    RPCExecute('model', self.widget.record.model_name, 'write',
                        [self.widget.record.id], {
                            self.widget.field_name: value,
                            }, context=context)
                except RPCException:
                    pass
            self.widget.record.cancel()
            self.widget.view.display()
        self.destroy()

    def destroy(self):
        self.win.destroy()
        NoModal.destroy(self)

    def show(self):
        self.win.show()

    def hide(self):
        self.win.hide()


class TranslateMixin:

    def translate_button(self):
        button = Gtk.Button()
        button.set_image(common.IconFactory.get_image(
                'tryton-translate', Gtk.IconSize.SMALL_TOOLBAR))
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.connect('clicked', self.translate)
        return button

    def translate(self, *args):
        self.view.set_value()
        if self.record.id < 0 or self.record.modified:
            common.message(
                _('You need to save the record before adding translations.'))
            return

        try:
            lang_ids = RPCExecute('model', 'ir.lang', 'search', [
                    ('translatable', '=', True),
                    ])
        except RPCException:
            return

        if not lang_ids:
            common.message(_('No other language available.'))
            return
        try:
            languages = RPCExecute('model', 'ir.lang', 'read', lang_ids,
                ['code', 'name'])
        except RPCException:
            return

        self.translate_dialog(languages)

    def translate_dialog(self, languages):
        TranslateDialog(self, languages, self._readonly)

    def translate_widget(self):
        raise NotImplementedError

    def translate_widget_set(self, widget, value):
        raise NotImplementedError

    def translate_widget_get(self, widget):
        raise NotImplementedError

    def translate_widget_set_readonly(self, widget, value):
        raise NotImplementedError
