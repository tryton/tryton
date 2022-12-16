#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
from tryton.common import COLORS


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
                'text_color_insensitive': style.text[gtk.STATE_INSENSITIVE],
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
            self._readonly_set(self.attrs.get('readonly', True))
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
