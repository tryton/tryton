#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gobject
import gettext
from interface import WidgetInterface
from many2one import Dialog
from tryton.gui.window.win_search import WinSearch
import tryton.rpc as rpc
from tryton.rpc import RPCProxy
import tryton.common as common
from tryton.gui.window.view_form.widget_search.form import _LIMIT

_ = gettext.gettext


class Reference(WidgetInterface):

    def __init__(self, window, parent, model, attrs=None):
        if attrs is None:
            attrs = {}
        super(Reference, self).__init__(window, parent, model, attrs)

        self.widget = gtk.HBox(spacing=0)

        self.widget_combo = gtk.ComboBoxEntry()
        child = self.widget_combo.get_child()
        child.set_editable(False)
        child.connect('changed',
                self.sig_changed_combo)
        child.connect('key_press_event', self.sig_key_pressed)
        self.widget_combo.set_size_request(int(attrs.get('widget_size', -1)), -1)
        self.widget.pack_start(self.widget_combo, expand=False, fill=True)

        self.widget.pack_start(gtk.Label('-'), expand=False, fill=False)

        self.wid_text = gtk.Entry()
        self.wid_text.set_property('width-chars', 13)
        self.wid_text.connect('key_press_event', self.sig_key_press)
        self.wid_text.connect('populate-popup', self._populate_popup)
        self.wid_text.connect_after('changed', self.sig_changed)
        self.changed = True
        self.wid_text.connect_after('activate', self.sig_activate)
        self.wid_text.connect_after('focus-out-event', self.sig_focus_out,
                True)
        self.focus_out = True
        self.widget.pack_start(self.wid_text, expand=True, fill=True)

        self.but_open = gtk.Button()
        img_find = gtk.Image()
        img_find.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_open = gtk.Image()
        img_open.set_from_stock('tryton-open', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_open.set_image(img_find)
        self.but_open.set_relief(gtk.RELIEF_NONE)
        self.but_open.connect('clicked', self.sig_activate)
        self.but_open.set_alignment(0.5, 0.5)
        self.widget.pack_start(self.but_open, padding=2, expand=False,
                fill=False)

        self.but_new = gtk.Button()
        img_new = gtk.Image()
        img_new.set_from_stock('tryton-new', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_new.set_image(img_new)
        self.but_new.set_relief(gtk.RELIEF_NONE)
        self.but_new.connect('clicked', self.sig_new)
        self.but_new.set_alignment(0.5, 0.5)
        self.widget.pack_start(self.but_new, expand=False, fill=False)

        self.widget.set_focus_chain([self.widget_combo, self.wid_text])

        tooltips = common.Tooltips()
        tooltips.set_tip(self.but_open, _('Search / Open a record'))
        tooltips.set_tip(self.but_new, _('Create a new record'))
        tooltips.enable()

        self._readonly = False
        self._selection = {}
        self._selection2 = {}
        selection = attrs.get('selection', [])
        if not isinstance(selection, (list, tuple)):
            try:
                selection = rpc.execute('model',
                        self.model, selection, rpc.CONTEXT)
            except Exception, exception:
                common.process_exception(exception, self._window)
                selection = []
        selection.sort(lambda x, y: cmp(x[1], y[1]))
        self.set_popdown(selection)

        self.last_key = (None, 0)
        self.key_catalog = {}

    def grab_focus(self):
        return self.widget_combo.grab_focus()

    def get_model(self):
        child = self.widget_combo.get_child()
        res = child.get_text()
        return self._selection.get(res, False)

    def set_popdown(self, selection):
        model = gtk.ListStore(gobject.TYPE_STRING)
        lst = []
        for (i, j) in selection:
            name = str(j)
            lst.append(name)
            self._selection[name] = i
            self._selection2[i] = name
        self.key_catalog = {}
        for name in lst:
            i = model.append()
            model.set(i, 0, name)
            if name:
                key = name[0].lower()
                self.key_catalog.setdefault(key, []).append(i)
        self.widget_combo.set_model(model)
        self.widget_combo.set_text_column(0)
        return lst

    def _readonly_set(self, value):
        self._readonly = value
        self.widget_combo.set_sensitive(not value)
        self.wid_text.set_editable(not value)
        self.but_new.set_sensitive(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.widget_combo, self.wid_text])

    def _color_widget(self):
        return self.wid_text

    def set_value(self, model, model_field):
        return

    def sig_activate(self, widget=None):
        self.sig_focus_out(widget, None)

    def sig_focus_out(self, widget, event, leave=False):
        if not self.focus_out:
            return
        child = self.widget_combo.get_child()
        self.changed = False
        value = self._view.modelfield.get_client(self._view.model)

        self.focus_out = False
        if not value:
            model, (obj_id, name) = self.get_model() or '', (0, '')
        else:
            try:
                model, (obj_id, name) = value
            except ValueError:
                self.focus_out = True
                return False
        if model and obj_id:
            if not leave:
                dia = Dialog(model, obj_id, attrs=self.attrs,
                        window=self._window)
                res, value = dia.run()
                if res:
                    self._view.modelfield.set_client(self._view.model,
                            (model, value), force_change=True)
                dia.destroy()
        elif model:
            if not self._readonly and ( self.wid_text.get_text() or not leave):
                domain = self._view.modelfield.domain_get(self._view.model)
                context = self._view.modelfield.context_get(self._view.model)

                try:
                    if self.wid_text.get_text():
                        dom = [('rec_name', 'ilike',
                                '%' + self.wid_text.get_text() + '%'),
                                domain]
                    else:
                        dom = domain
                    ids = rpc.execute('model', model,
                            'search', dom, 0, _LIMIT, None, context)
                except Exception, exception:
                    self.focus_out = True
                    self.changed = True
                    common.process_exception(exception, self._window)
                    return False
                if ids and len(ids) == 1:
                    self._view.modelfield.set_client(self._view.model,
                            (model, (ids[0], '')))
                    self.display(self._view.model, self._view.modelfield)
                    self.focus_out = True
                    self.changed = True
                    return True

                win = WinSearch(model, sel_multi=False, ids=ids, context=context,
                        domain=domain, parent=self._window)
                ids = win.run()
                if ids:
                    self._view.modelfield.set_client(self._view.model,
                            (model, (ids[0], '')))
        else:
            self._view.modelfield.set_client(self._view.model,
                    ('', (name, name)))
        self.focus_out = True
        self.changed = True
        self.display(self._view.model, self._view.modelfield)

    def sig_new(self, *args):
        model = self.get_model()
        if not model:
            return
        dia = Dialog(model, window=self._window)
        res, value = dia.run()
        if res:
            self._view.modelfield.set_client(self._view.model,
                    (model, value))
            self.display(self._view.model, self._view.modelfield)
        dia.destroy()

    def sig_key_press(self, widget, event):
        editable = self.wid_text.get_editable()
        if event.keyval == gtk.keysyms.F3 and editable:
            self.sig_new(widget, event)
            return True
        elif event.keyval == gtk.keysyms.F2:
            self.sig_focus_out(widget, event)
            return True
        elif event.keyval in (gtk.keysyms.Tab, gtk.keysyms.Return) and editable:
            if self._view.modelfield.get(self._view.model) or \
                    not self.wid_text.get_text():
                return False
            self.sig_focus_out(widget, event, leave=True)
            return True
        return False

    def sig_changed_combo(self, *args):
        if not self.changed:
            return
        self.wid_text.set_text('')
        self._view.modelfield.set_client(self._view.model,
                (self.get_model(), (0, '')))

    def sig_changed(self, *args):
        if not self.changed:
            return False
        val = self._view.modelfield.get_client(self._view.model)
        if not val:
            model, (obj_id, name) = '', (0, '')
        else:
            model, (obj_id, name) = val
        if self.get_model() and obj_id:
            self._view.modelfield.set_client(self._view.model,
                    (self.get_model(), (0, '')))
            self.display(self._view.model, self._view.modelfield)
        return False

    def display(self, model, model_field):
        child = self.widget_combo.get_child()
        self.changed = False
        if not model_field:
            child.set_text('')
            self.changed =True
            return False
        super(Reference, self).display(model, model_field)
        value = model_field.get_client(model)
        img = gtk.Image()
        if not value:
            model, (obj_id, name) = '', (0, '')
        else:
            model, (obj_id, name) = value
        if model:
            child.set_text(self._selection2[model])
            if not name and obj_id:
                try:
                    name = RPCProxy(model).read(obj_id, ['rec_name'],
                            rpc.CONTEXT)['rec_name']
                except Exception, exception:
                    common.process_exception(exception, self._window)
                    name = '???'
            self.wid_text.set_text(name)
            if obj_id:
                img.set_from_stock('tryton-open', gtk.ICON_SIZE_SMALL_TOOLBAR)
                self.but_open.set_image(img)
            else:
                img.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
                self.but_open.set_image(img)
        else:
            child.set_text('')
            self.wid_text.set_text(str(name))
            img.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.but_open.set_image(img)
        self.changed = True

    def display_value(self):
        return self.widget_combo.get_child().get_text() + ', ' + \
                self.wid_text.get_text()

    def sig_key_pressed(self, *args):
        key = args[1].string.lower()
        if self.last_key[0] == key:
            self.last_key[1] += 1
        else:
            self.last_key = [ key, 1 ]
        if not self.key_catalog.has_key(key):
            return
        self.widget_combo.set_active_iter(
                self.key_catalog[key][self.last_key[1] \
                        % len(self.key_catalog[key])])
