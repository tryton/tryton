#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import tryton.rpc as rpc
from tryton.common import COLORS, process_exception, message
from tryton.config import TRYTON_ICON
from tryton.gui.window.view_form.view.form_gtk.preference \
        import WidgetFieldPreference
import gettext

_ = gettext.gettext

def field_pref_set(field, name, model_name, value, client_value, dependance,
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
    for val, widget in widgets.iteritems():
        if widget.get_active():
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
        args = ('model', 'ir.default', method, model_name, field, clause,
                value, user, rpc.CONTEXT)
        try:
            rpc.execute(*args)
        except Exception, exception:
            process_exception(exception, window, *args)
        return True
    return False


class WidgetInterface(object):

    def __init__(self, field_name, model_name, window, attrs=None):
        self.field_name = field_name
        self.model_name = model_name
        self.window = window
        self.view = None # Filled by ViewForm
        self.attrs = attrs or {}
        for attr_name in ('readonly', 'invisible'):
            if attr_name in self.attrs:
                self.attrs[attr_name] = bool(int(self.attrs[attr_name]))
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
        self.colors = {}
        self.visible = True
        self.color_name = None

    def __get_record(self):
        if self.view:
            return self.view.screen.current_record

    record = property(__get_record)

    def __get_field(self):
        if self.record:
            return self.record.group.fields[self.field_name]

    field = property(__get_field)

    def destroy(self):
        pass

    def _menu_sig_default_get(self):
        if self.field.get_state_attrs(self.record).get('readonly', False):
            return False
        model_name = self.field.parent.model_name
        args = ('model', model_name, 'default_get', [self.attrs['name']],
                rpc.CONTEXT)
        try:
            res = rpc.execute(*args)
        except Exception, exception:
            process_exception(exception, self.window, *args)
        self.field.set_default(self.record,
                res.get(self.attrs['name'], False), modified=True)
        self.display(self.record, self.field)

    def _menu_sig_default_set(self, reset=False):
        deps = []
        for wname, wviews in self.view.widgets.iteritems():
            for wview in wviews:
                if wview.field.attrs.get('change_default', False):
                    wvalue = wview.field.get(self.record)
                    name = wview.field.attrs.get('string', wname)
                    value = wview.field.get_client(self.record)
                    deps.append((wname, name, wvalue, value))
        if not self.field.validate(self.record):
            message(_('Invalid field!'), parent=self.window)
            return
        value = self.field.get_default(self.record)
        client_value = self.display_value()
        model_name = self.field.parent.model_name
        field_pref_set(self.field_name,
                self.attrs.get('string', self.field_name), model_name,
                value, client_value, deps, self.window, reset=reset)

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
        self.color_name = name
        widget = self._color_widget()

        if not self.colors:
            style = widget.get_style()
            self.colors = {
                'bg_color_active': style.bg[gtk.STATE_ACTIVE],
                'bg_color_insensitive': style.bg[gtk.STATE_INSENSITIVE],
                'base_color_normal': style.base[gtk.STATE_NORMAL],
                'base_color_insensitive': style.base[gtk.STATE_INSENSITIVE],
                'fg_color_normal': style.fg[gtk.STATE_NORMAL],
                'fg_color_insensitive': style.fg[gtk.STATE_INSENSITIVE],
                'text_color_normal': style.text[gtk.STATE_NORMAL],
            }

        if COLORS.get(name):
            colormap = widget.get_colormap()
            bg_color = colormap.alloc_color(COLORS.get(name, 'white'))
            fg_color = gtk.gdk.color_parse("black")
            widget.modify_bg(gtk.STATE_ACTIVE, bg_color)
            widget.modify_base(gtk.STATE_NORMAL, bg_color)
            widget.modify_fg(gtk.STATE_NORMAL, fg_color)
            widget.modify_text(gtk.STATE_NORMAL, fg_color)
            widget.modify_text(gtk.STATE_INSENSITIVE, fg_color)
        elif name == 'readonly':
            widget.modify_bg(gtk.STATE_ACTIVE,
                    self.colors['bg_color_insensitive'])
            widget.modify_base(gtk.STATE_NORMAL,
                    self.colors['base_color_insensitive'])
            widget.modify_fg(gtk.STATE_NORMAL,
                    self.colors['fg_color_insensitive'])
            widget.modify_text(gtk.STATE_NORMAL,
                    self.colors['text_color_normal'])
            widget.modify_text(gtk.STATE_INSENSITIVE,
                    self.colors['text_color_normal'])
        else:
            widget.modify_bg(gtk.STATE_ACTIVE,
                    self.colors['bg_color_active'])
            widget.modify_base(gtk.STATE_NORMAL,
                    self.colors['base_color_normal'])
            widget.modify_fg(gtk.STATE_NORMAL,
                    self.colors['fg_color_normal'])
            widget.modify_text(gtk.STATE_NORMAL,
                    self.colors['text_color_normal'])
            widget.modify_text(gtk.STATE_INSENSITIVE,
                    self.colors['text_color_normal'])

    def invisible_set(self, value):
        widget = self._invisible_widget()
        if value and value != '0':
            self.visible = False
            widget.hide()
        else:
            self.visible = True
            widget.show()

    def display_value(self):
        return self.field.get_client(self.record)

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
        if not self.field:
            return False
        if not self.visible:
            return False
        self.set_value(self.record, self.field)

    def display(self, record, field):
        if not field:
            self._readonly_set(self.attrs.get('readonly', False))
            self.invisible_set(self.attrs.get('invisible', False))
            return
        self._readonly_set(self.attrs.get('readonly',
            field.get_state_attrs(record).get('readonly', False)))
        if self.attrs.get('readonly',
                field.get_state_attrs(record).get('readonly', False)):
            self.color_set('readonly')
        elif not field.get_state_attrs(record).get('valid', True):
            self.color_set('invalid')
        elif field.get_state_attrs(record).get('required', False):
            self.color_set('required')
        else:
            self.color_set('normal')
        self.invisible_set(self.attrs.get('invisible',
            field.get_state_attrs(record).get('invisible', False)))

    def set_value(self, record, field):
        pass

    def cancel(self):
        pass
