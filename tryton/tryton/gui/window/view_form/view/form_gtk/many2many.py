#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
from tryton.gui.window.view_form.screen import Screen
from interface import WidgetInterface
import tryton.rpc as rpc
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm
from tryton.config import CONFIG
import tryton.common as common
import gettext

_ = gettext.gettext


class Many2Many(WidgetInterface):

    def __init__(self, field_name, model_name, window, attrs=None):
        super(Many2Many, self).__init__(field_name, model_name, window,
                attrs=attrs)

        self.widget = gtk.VBox(homogeneous=False, spacing=5)

        hbox = gtk.HBox(homogeneous=False, spacing=3)
        self.wid_text = gtk.Entry()
        self.wid_text.set_property('width_chars', 13)
        self.wid_text.connect('activate', self._sig_activate)
        hbox.pack_start(self.wid_text, expand=True, fill=True)

        hbox.pack_start(gtk.VSeparator(), padding=2, expand=False, fill=False)

        self.wid_but_add = gtk.Button()
        hbox_add = gtk.HBox()
        img_add = gtk.Image()
        img_add.set_from_stock('tryton-list-add', gtk.ICON_SIZE_BUTTON)
        hbox_add.pack_start(img_add)
        label_add = gtk.Label(_('Add'))
        hbox_add.pack_start(label_add)
        self.wid_but_add.add(hbox_add)
        self.wid_but_add.set_relief(gtk.RELIEF_HALF)
        self.wid_but_add.set_focus_on_click(True)
        self.wid_but_add.connect('clicked', self._sig_add)
        hbox.pack_start(self.wid_but_add, padding=3, expand=False, fill=False)

        self.wid_but_remove = gtk.Button()
        hbox_remove = gtk.HBox()
        img_remove = gtk.Image()
        img_remove.set_from_stock('tryton-list-remove', gtk.ICON_SIZE_BUTTON)
        hbox_remove.pack_start(img_remove)
        label_remove = gtk.Label(_('Remove'))
        hbox_remove.pack_start(label_remove)
        self.wid_but_remove.add(hbox_remove)
        self.wid_but_remove.set_relief(gtk.RELIEF_HALF)
        self.wid_but_remove.set_focus_on_click(True)
        self.wid_but_remove.connect('clicked', self._sig_remove)
        hbox.pack_start(self.wid_but_remove, expand=False, fill=False)

        self.widget.pack_start(hbox, expand=False, fill=False)

        hbox.set_focus_chain([self.wid_text])

        self.screen = Screen(attrs['relation'], self.window,
                mode=['tree'], views_preload=attrs.get('views', {}),
                row_activate=self._on_activate)

        if not isinstance(self.screen.window, gtk.Dialog):
            self.screen.widget.set_size_request(0, 0)
        self.widget.pack_start(self.screen.widget, expand=True, fill=True)

        self.screen.widget.connect('key_press_event', self.on_keypress)
        self.wid_text.connect('key_press_event', self.on_keypress)

    def _color_widget(self):
        if hasattr(self.screen.current_view, 'widget_tree'):
            return self.screen.current_view.widget_tree
        return super(Many2Many, self)._color_widget()

    def grab_focus(self):
        return self.wid_text.grab_focus()

    def on_keypress(self, widget, event):
        if event.keyval == gtk.keysyms.F3:
            self._sig_add()
            return False
        if event.keyval == gtk.keysyms.F2 \
                and widget == self.screen.widget:
            self._sig_edit()
        if event.keyval in (gtk.keysyms.Delete, gtk.keysyms.KP_Delete) \
                and widget == self.screen.widget:
            self._sig_remove()
            return False

    def destroy(self):
        self.screen.destroy()
        self.widget.destroy()
        del self.widget

    def color_set(self, name):
        super(Many2Many, self).color_set(name)
        widget = self._color_widget()
        # if the style to apply is different from readonly then insensitive
        # cellrenderers should use the default insensitive color
        if name != 'readonly':
            widget.modify_text(gtk.STATE_INSENSITIVE,
                    self.colors['text_color_insensitive'])

    def _sig_add(self, *args):
        domain = self.field.domain_get(self.record)
        context = self.field.context_get(self.record)
        value = self.wid_text.get_text()

        try:
            if value:
                dom = [('rec_name', 'ilike', '%' + value + '%'), domain]
            else:
                dom = domain
            ids = rpc.execute('model', self.attrs['relation'], 'search',
                    dom , 0, CONFIG['client.limit'], None, context)
        except Exception, exception:
            common.process_exception(exception, self.window)
            return False
        if len(ids) != 1 or not value:
            win = WinSearch(self.attrs['relation'], sel_multi=True, ids=ids,
                context=context, domain=domain,
                parent=self.widget.get_toplevel(),
                views_preload=self.attrs.get('views', {}))
            ids = win.run()

        res_id = None
        if ids:
            res_id = ids[0]
        self.screen.load(ids, modified=True)
        self.screen.display(res_id=res_id)
        if self.screen.current_view:
            self.screen.current_view.set_cursor()
        self.wid_text.set_text('')

    def _sig_remove(self, *args):
        self.screen.remove(remove=True)

    def _sig_activate(self, *args):
        self._sig_add()
        self.wid_text.grab_focus()

    def _on_activate(self):
        self._sig_edit()

    def _sig_edit(self):
        if self.screen.current_record:
            win = WinForm(self.screen, self.widget.get_toplevel())
            if win.run():
                self.screen.current_record.save()
            else:
                self.screen.current_record.cancel()
            win.destroy()

    def _readonly_set(self, value):
        super(Many2Many, self)._readonly_set(value)
        self.wid_text.set_editable(not value)
        self.wid_text.set_sensitive(not value)
        self.wid_but_remove.set_sensitive(not value)
        self.wid_but_add.set_sensitive(not value)

    def display(self, record, field):
        super(Many2Many, self).display(record, field)
        if field is None:
            self.screen.new_group()
            self.screen.current_record = None
            self.screen.parent = True
            self.screen.display()
            return False
        new_group = field.get_client(record)
        if id(self.screen.group) != id(new_group):
            self.screen.group = new_group
        self.screen.display()
        return True

    def display_value(self):
        ids = self.field.get_default(self.record)
        try:
            result = rpc.execute('model', self.attrs['relation'], 'read',
                    ids, ['rec_name'], rpc.CONTEXT)
        except Exception:
            return str(ids)
        return ', '.join(x['rec_name'] for x in result)

    def set_value(self, record, field):
        self.screen.current_view.set_value()
        return True
