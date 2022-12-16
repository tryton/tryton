#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
from tryton.rpc import RPCProxy
import tryton.rpc as rpc
from tryton.common import COLORS, process_exception, message
from tryton.config import TRYTON_ICON
from tryton.gui.window.view_form.view.form_gtk.preference \
        import WidgetFieldPreference
import gettext

_ = gettext.gettext

_ATTRS_BOOLEAN = {
    'required': False,
    'readonly': False
}

def field_pref_set(field, name, model, value, client_value, dependance,
        window, reset=False):
    dialog = WidgetFieldPreference(window, reset=reset)
    if dependance is None:
        dependance = []
    entry = dialog.entry_field_name
    entry.set_text(name)
    entry = dialog.entry_default_value
    entry.set_text((client_value and str(client_value)) or _('<empty>'))

    radio = dialog.radio_current_user

    vbox = dialog.vbox_condition
    widgets = {}
    addwidget = False
    widget = None
    if dependance:
        widget = gtk.RadioButton(widget, _('Always'))
        vbox.pack_start(widget)
    for (fname, name, fvalue, dvalue) in dependance:
        if fvalue:
            addwidget = True
            widget = gtk.RadioButton(widget, name + ' = ' + str(dvalue))
            widgets[(fname, fvalue)] = widget
            vbox.pack_start(widget)
    if not len(dependance) or not addwidget:
        vbox.pack_start(gtk.Label(_('Always applicable!')))
    vbox.show_all()

    res = dialog.run()

    clause = False
    for val in widgets.keys():
        if widgets[val].get_active():
            clause = val[0] + '=' + str(val[1])
            break
    user = False
    if radio.get_active():
        user = rpc._USER
    if res == gtk.RESPONSE_OK:
        if reset:
            method = 'reset_default'
        else:
            method = 'set_default'
        args = ('model', 'ir.default', method, model, field, clause,
                value, user, rpc.CONTEXT)
        try:
            rpc.execute(*args)
        except Exception, exception:
            process_exception(exception, window, *args)
        return True
    return False


class WidgetInterface(object):

    def __init__(self, window, parent=None, model=None, attrs=None):
        if attrs is None:
            attrs = {}
        self.parent = parent
        self.model = model
        self._window = window
        self._view = None
        self.attrs = attrs
        for key, val in _ATTRS_BOOLEAN.items():
            self.attrs[key] = attrs.get(key, False) not in ('False', '0', False)
        self.default_readonly = self.attrs.get('readonly', False)
        self._menu_entries = [
            (_('Set to default value'),
                lambda x: self._menu_sig_default_get(), 1),
            (_('Set as default'),
                lambda x: self._menu_sig_default_set(), 1),
            (_('Reset default'),
                lambda x: self._menu_sig_default_set(reset=True), 1),
        ]
        self.widget = None
        self.position = 0
        self.bg_color_active = None
        self.bg_color_insensitive = None
        self.base_color_normal = None
        self.base_color_insensitive = None
        self.fg_color_normal = None
        self.fg_color_insensitive = None
        self.text_color_normal = None
        self.visible = True

    def destroy(self):
        pass

    def _menu_sig_default_get(self):
        if self._view.modelfield.get_state_attrs(self._view.model)\
                .get('readonly', False):
            return False
        model = self._view.modelfield.parent.resource
        args = ('model', model, 'default_get', [self.attrs['name']])
        try:
            res = rpc.execute(*args)
        except Exception, exception:
            process_exception(exception, self._window, *args)
        self._view.modelfield.set(self._view.model,
                res.get(self.attrs['name'], False), modified=True)
        self.display(self._view.model, self._view.modelfield)

    def _menu_sig_default_set(self, reset=False):
        deps = []
        for wname, wviews in self._view.view_form.widgets.items():
            for wview in wviews:
                if wview.modelfield.attrs.get('change_default', False):
                    wvalue = wview.modelfield.get(self._view.model)
                    name = wview.modelfield.attrs.get('string', wname)
                    value = wview.modelfield.get_client(self._view.model)
                    deps.append((wname, name, wvalue, value))
        if not self._view.modelfield.validate(self._view.model):
            message(_('Invalid field!'), parent=self._window)
            return
        value = self._view.modelfield.get_default(self._view.model)
        client_value = self.display_value()
        model = self._view.modelfield.parent.resource
        field_pref_set(self._view.widget_name,
                self.attrs.get('string', self._view.widget_name), model,
                value, client_value, deps, self._window, reset=reset)

    def sig_activate(self, widget=None):
        # emulate a focus_out so that the onchange is called if needed
        self._focus_out()

    def _readonly_set(self, readonly):
        pass

    def _color_widget(self):
        return self.widget

    def _invisible_widget(self):
        return self.widget

    def grab_focus(self):
        return self.widget.grab_focus()

    def color_set(self, name):
        widget = self._color_widget()
        colormap = widget.get_colormap()
        style = widget.get_style()

        if self.bg_color_active is None:
            self.bg_color_active = style.bg[gtk.STATE_ACTIVE]
        if self.bg_color_insensitive is None:
            self.bg_color_insensitive = style.bg[gtk.STATE_INSENSITIVE]
        if self.base_color_normal is None:
            self.base_color_normal = style.base[gtk.STATE_NORMAL]
        if self.base_color_insensitive is None:
            self.base_color_insensitive = style.base[gtk.STATE_INSENSITIVE]
        if self.fg_color_normal is None:
            self.fg_color_normal = style.fg[gtk.STATE_NORMAL]
        if self.fg_color_insensitive is None:
            self.fg_color_insensitive = style.fg[gtk.STATE_INSENSITIVE]
        if self.text_color_normal is None:
            self.text_color_normal = style.text[gtk.STATE_NORMAL]

        if COLORS.get(name):
            bg_color = colormap.alloc_color(COLORS.get(name, 'white'))
            fg_color = gtk.gdk.color_parse("black")
            widget.modify_bg(gtk.STATE_ACTIVE, bg_color)
            widget.modify_base(gtk.STATE_NORMAL, bg_color)
            widget.modify_fg(gtk.STATE_NORMAL, fg_color)
            widget.modify_text(gtk.STATE_NORMAL, fg_color)
            widget.modify_text(gtk.STATE_INSENSITIVE, fg_color)
        elif name == 'readonly':
            widget.modify_bg(gtk.STATE_ACTIVE, self.bg_color_insensitive)
            widget.modify_base(gtk.STATE_NORMAL, self.base_color_insensitive)
            widget.modify_fg(gtk.STATE_NORMAL, self.fg_color_insensitive)
            widget.modify_text(gtk.STATE_NORMAL, self.text_color_normal)
            widget.modify_text(gtk.STATE_INSENSITIVE, self.text_color_normal)
        else:
            widget.modify_bg(gtk.STATE_ACTIVE, self.bg_color_active)
            widget.modify_base(gtk.STATE_NORMAL, self.base_color_normal)
            widget.modify_fg(gtk.STATE_NORMAL, self.fg_color_normal)
            widget.modify_text(gtk.STATE_NORMAL, self.text_color_normal)
            widget.modify_text(gtk.STATE_INSENSITIVE, self.text_color_normal)

    def invisible_set(self, value):
        widget = self._invisible_widget()
        if value and value != '0':
            self.visible = False
            widget.hide()
        else:
            self.visible = True
            widget.show()

    def display_value(self):
        return self._view.modelfield.get_client(self._view.model)

    def _menu_open(self, obj, event):
        if event.button == 3:
            menu = gtk.Menu()
            for stock_id, callback, sensitivity in self._menu_entries:
                if stock_id:
                    item = gtk.ImageMenuItem(stock_id)
                    if callback:
                        item.connect("activate", callback)
                    item.set_sensitive(sensitivity)
                else:
                    item = gtk.SeparatorMenuItem()
                item.show()
                menu.append(item)
            menu.popup(None, None, None, event.button, event.time)
            return True

    def _populate_popup(self, widget, menu):
        menu_entries = []
        menu_entries.append((None, None, None))
        menu_entries += self._menu_entries
        for stock_id, callback, sensitivity in menu_entries:
            if stock_id:
                item = gtk.ImageMenuItem(stock_id)
                if callback:
                    item.connect("activate", callback)
                item.set_sensitive(sensitivity)
            else:
                item = gtk.SeparatorMenuItem()
            item.show()
            menu.append(item)
        return True

    def _focus_in(self):
        pass

    def _focus_out(self):
        if not self._view.modelfield:
            return False
        if not self.visible:
            return False
        self.set_value(self._view.model, self._view.modelfield)

    def display(self, model, modelfield):
        if not modelfield:
            self._readonly_set(self.attrs.get('readonly', False))
            return
        self._readonly_set(modelfield.get_state_attrs(model).\
                get('readonly', False))
        if modelfield.get_state_attrs(model).get('readonly', False):
            self.color_set('readonly')
        elif not modelfield.get_state_attrs(model).get('valid', True):
            self.color_set('invalid')
        elif modelfield.get_state_attrs(model).get('required', False):
            self.color_set('required')
        else:
            self.color_set('normal')
        self.invisible_set(modelfield.get_state_attrs(model).\
                get('invisible', False))

    def set_value(self, model, model_field):
        pass

    def cancel(self):
        pass
