#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import gtk
from tryton.gui.window.view_form.screen import Screen
from interface import WidgetInterface
import tryton.rpc as rpc
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.view_form.widget_search.form import _LIMIT
import tryton.common as common
import gettext

_ = gettext.gettext


class Many2Many(WidgetInterface):

    def __init__(self, window, parent, model, attrs=None):
        super(Many2Many, self).__init__(window, parent, model, attrs)

        self.widget = gtk.VBox(homogeneous=False, spacing=5)

        hbox = gtk.HBox(homogeneous=False, spacing=3)
        self.wid_text = gtk.Entry()
        self.wid_text.set_property('width_chars', 13)
        self.wid_text.connect('activate', self._sig_activate)
        self.wid_text.connect('button_press_event', self._menu_open)
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

        self.screen = Screen(attrs['relation'], self._window,
                view_type=['tree'], views_preload=attrs.get('views', {}))

        self.widget.pack_start(self.screen.widget, expand=True, fill=True)

        self.old = None

    def grab_focus(self):
        return self.wid_text.grab_focus()

    def destroy(self):
        self.screen.destroy()
        self.widget.destroy()
        del self.widget

    def _sig_add(self, *args):
        domain = self._view.modelfield.domain_get(self._view.model)
        context = self._view.modelfield.context_get(self._view.model)
        value = self.wid_text.get_text()

        try:
            ids = rpc.execute('object', 'execute',
                    self.attrs['relation'], 'name_search',
                    value, domain, 'ilike', context,
                    _LIMIT)
        except Exception, exception:
            common.process_exception(exception, self._window)
            return False
        ids = [x[0] for x in ids]
        if len(ids) != 1 or not value:
            win = WinSearch(self.attrs['relation'], sel_multi=True, ids=ids,
                    context=context, domain=domain, parent=self._window,
                    views_preload=self.attrs.get('views', {}))
            ids = win.run()

        res_id = None
        if ids:
            res_id = ids[0]
        self.screen.load(ids)
        self.screen.display(res_id=res_id)
        if self.screen.current_view:
            self.screen.current_view.set_cursor()
        self.wid_text.set_text('')
        self.set_value(self._view.model, self._view.modelfield)

    def _sig_remove(self, *args):
        self.screen.remove()
        self.screen.display()
        self.set_value(self._view.model, self._view.modelfield)

    def _sig_activate(self, *args):
        self._sig_add()
        self.wid_text.grab_focus()

    def _readonly_set(self, value):
        super(Many2Many, self)._readonly_set(value)
        self.wid_text.set_editable(not value)
        self.wid_text.set_sensitive(not value)
        self.wid_but_remove.set_sensitive(not value)
        self.wid_but_add.set_sensitive(not value)

    def display(self, model, model_field):
        super(Many2Many, self).display(model, model_field)
        ids = []
        if model_field:
            ids = model_field.get_client(model)
        if ids != self.old:
            self.screen.clear()
            self.screen.load(ids, set_cursor=False)
            self.old = ids
        self.screen.display()
        return True

    def set_value(self, model, model_field):
        model_field.set_client(model, [x.id for x in self.screen.models.models])

    def cancel(self):
        self.old = None
