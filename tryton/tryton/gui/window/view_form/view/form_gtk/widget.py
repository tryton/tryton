# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject
import gettext

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
        return self.view.screen.current_record

    @property
    def field(self):
        if self.record:
            return self.record.group.fields[self.field_name]

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
            gobject.timeout_add(300, send, self.get_value())
        # Wait the current event is finished to retreive the value
        gobject.idle_add(get_value)
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
        self.set_value(self.record, self.field)

    def display(self, record, field):
        if not field:
            self._readonly_set(self.attrs.get('readonly', True))
            self.invisible_set(self.attrs.get('invisible', False))
            self._required_set(False)
            return
        states = field.get_state_attrs(record)
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

    def set_value(self, record, field):
        pass


class TranslateDialog(NoModal):

    def __init__(self, widget, languages, readonly):
        NoModal.__init__(self)
        self.widget = widget
        self.win = gtk.Dialog(_('Translation'), self.parent,
            gtk.DIALOG_DESTROY_WITH_PARENT)
        Main().add_window(self.win)
        self.win.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.win.set_icon(TRYTON_ICON)
        self.win.connect('response', self.response)
        parent_allocation = self.parent.get_allocation()
        self.win.set_default_size(-1, min(400, parent_allocation.height))

        self.accel_group = gtk.AccelGroup()
        self.win.add_accel_group(self.accel_group)

        cancel_button = self.win.add_button(
            set_underline(_("Cancel")), gtk.RESPONSE_CANCEL)
        cancel_button.set_image(common.IconFactory.get_image(
                    'tryton-cancel', gtk.ICON_SIZE_BUTTON))
        cancel_button.set_always_show_image(True)
        ok_button = self.win.add_button(
            set_underline(_("OK")), gtk.RESPONSE_OK)
        ok_button.set_image(common.IconFactory.get_image(
                'tryton-ok', gtk.ICON_SIZE_BUTTON))
        ok_button.set_always_show_image(True)
        ok_button.add_accelerator(
            'clicked', self.accel_group, gtk.keysyms.Return,
            gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

        tooltips = common.Tooltips()

        self.widgets = {}
        table = gtk.Table(len(languages), 4)
        table.set_homogeneous(False)
        table.set_col_spacings(3)
        table.set_row_spacings(2)
        table.set_border_width(1)
        for i, language in enumerate(languages):
            label = language['name'] + _(':')
            label = gtk.Label(label)
            label.set_alignment(1.0, 0.0 if self.widget.expand else 0.5)
            table.attach(label, 0, 1, i, i + 1, xoptions=gtk.FILL, xpadding=2)

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
            yopt = 0
            if self.widget.expand:
                yopt = gtk.EXPAND | gtk.FILL
            table.attach(widget, 1, 2, i, i + 1, yoptions=yopt)
            editing = gtk.CheckButton()
            editing.connect('toggled', self.editing_toggled, widget)
            editing.props.sensitive = not readonly
            tooltips.set_tip(editing, _('Edit'))
            table.attach(editing, 2, 3, i, i + 1, xoptions=gtk.FILL)
            fuzzy = gtk.CheckButton()
            fuzzy.set_active(value != fuzzy_value)
            fuzzy.props.sensitive = False
            tooltips.set_tip(fuzzy, _('Fuzzy'))
            table.attach(fuzzy, 4, 5, i, i + 1, xoptions=gtk.FILL)
            self.widgets[language['code']] = (widget, editing, fuzzy)

        tooltips.enable()
        vbox = gtk.VBox()
        vbox.pack_start(table, self.widget.expand, True)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(vbox)
        scrolledwindow = gtk.ScrolledWindow()
        scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        scrolledwindow.add(viewport)
        self.win.vbox.pack_start(scrolledwindow, True, True)
        self.win.show_all()

        self.register()
        self.show()

    def editing_toggled(self, editing, widget):
        self.widget.translate_widget_set_readonly(widget,
            not editing.get_active())

    def response(self, win, response):
        if response == gtk.RESPONSE_OK:
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
        button = gtk.Button()
        button.set_image(common.IconFactory.get_image(
                'tryton-translate', gtk.ICON_SIZE_SMALL_TOOLBAR))
        button.set_relief(gtk.RELIEF_NONE)
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

        TranslateDialog(self, languages, self._readonly)

    def translate_widget(self):
        raise NotImplemented

    def translate_widget_set(self, widget, value):
        raise NotImplemented

    def translate_widget_get(self, widget):
        raise NotImplemented

    def translate_widget_set_readonly(self, widget, value):
        raise NotImplemented
