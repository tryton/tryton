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

def field_pref_set(field, name, model, value, dependance=None, window=None):
    dialog = WidgetFieldPreference(window)
    if dependance is None:
        dependance = []
    entry = dialog.entry_field_name
    entry.set_text(name)
    entry = dialog.entry_domain
    entry.set_text(model)
    entry = dialog.entry_default_value
    entry.set_text((value and str(value)) or _('<empty>'))

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
        ir_default = RPCProxy('ir.default')
        try:
            ir_default.set_default(model, field, clause, value, user,
                    rpc.CONTEXT)
        except Exception, exception:
            process_exception(exception, window)
            return False
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
        ]
        self.widget = None
        self.position = 0

    def destroy(self):
        pass

    def _menu_sig_default_get(self):
        if self._view.modelfield.get_state_attrs(self._view.model)\
                .get('readonly', False):
            return False
        model = self._view.modelfield.parent.resource
        try:
            res = rpc.execute('object', 'execute', model,
                    'default_get', [self.attrs['name']])
        except Exception, exception:
            process_exception(exception, self._window)
        self._view.modelfield.set(self._view.model,
                res.get(self.attrs['name'], False))
        self.display(self._view.model, self._view.modelfield)

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
        colour = colormap.alloc_color(COLORS.get(name,'white'))
        widget.modify_bg(gtk.STATE_ACTIVE, colour)
        widget.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("black"))
        widget.modify_base(gtk.STATE_NORMAL, colour)
        widget.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse("black"))
        widget.modify_text(gtk.STATE_INSENSITIVE, gtk.gdk.color_parse("black"))

    def invisible_set(self, value):
        widget = self._invisible_widget()
        if value and value != '0':
            widget.hide()
        else:
            widget.show()

    def _menu_sig_default_set(self):
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
        model = self._view.modelfield.parent.resource
        field_pref_set(self._view.widget_name,
                self.attrs.get('string', self._view.widget_name), model,
                value, deps, window=self._window)

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
