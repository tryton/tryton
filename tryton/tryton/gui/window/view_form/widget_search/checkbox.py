#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
from interface import Interface

_ = gettext.gettext


class CheckBox(Interface):

    def __init__(self, name, parent, attrs=None, context=None):
        super(CheckBox, self).__init__(name, parent, attrs=attrs,
                context=context)

        self.widget = gtk.combo_box_entry_new_text()
        self.widget.child.set_editable(True)
        self.widget.child.set_property('activates_default', True)
        self.widget.child.connect('key_press_event', self.sig_key_press)
        self.widget.set_focus_chain([self.widget.child])

        if self.name != 'active' or \
                not (self.name == 'active' \
                and self.context.get('active_test', True)):
            self.widget.append_text('')
            self.widget.child.set_text('')
        else:
            self.widget.child.set_text(_('Yes'))
        self.widget.append_text(_('Yes'))
        self.widget.append_text(_('No'))

        completion = gtk.EntryCompletion()
        #Only available in PyGTK 2.6 and above.
        if hasattr(completion, 'set_inline_selection'):
            completion.set_inline_selection(True)
        completion.set_model(self.widget.get_model())
        self.widget.child.set_completion(completion)
        completion.set_text_column(0)
        self.widget.show()

    def sig_key_press(self, widget, event):
        if event.type == gtk.gdk.KEY_PRESS \
                and event.state & gtk.gdk.CONTROL_MASK \
                and event.keyval == gtk.keysyms.space:
            self.widget.popup()

    def _value_get(self):
        val = self.widget.child.get_text()
        if not val \
                and self.name == 'active' \
                and self.context.get('active_test', True):
            val = _('Yes')
            self.widget.child.set_text(val)
        if val:
            return [(self.name, '=', int(val == _('Yes')))]
        self.widget.child.set_text('')
        return []

    def _value_set(self, value):
        if value == '':
            if self.name != 'active' or \
                    (self.name == 'active' \
                    and self.context.get('active_test', True)):
                self.widget.child.set_text('')
            else:
                self.widget.child.set_text(_('Yes'))
            return
        if value:
            self.widget.child.set_text(_('Yes'))
        else:
            self.widget.child.set_text(_('No'))

    value = property(_value_get, _value_set)

    def sig_activate(self, fct):
        self.widget.child.connect_after('activate', fct)
