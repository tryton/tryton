#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gobject
import gettext
from interface import WidgetInterface
import tryton.common as common
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm
from tryton.config import CONFIG
from tryton.common.popup_menu import populate
from tryton.common import RPCExecute, RPCException

_ = gettext.gettext


class Many2One(WidgetInterface):

    def __init__(self, field_name, model_name, attrs=None):
        super(Many2One, self).__init__(field_name, model_name, attrs=attrs)

        self.widget = gtk.HBox(spacing=0)
        self.widget.set_property('sensitive', True)

        self.wid_text = gtk.Entry()
        self.wid_text.set_property('width-chars', 13)
        self.wid_text.set_property('activates_default', True)
        self.wid_text.connect('key-press-event', self.send_modified)
        self.wid_text.connect_after('key_press_event', self.sig_key_press)
        self.wid_text.connect('populate-popup', self._populate_popup)
        self.wid_text.connect('focus-in-event', lambda x, y: self._focus_in())
        self.wid_text.connect('focus-out-event',
            lambda x, y: self._focus_out())
        self.wid_text.connect_after('changed', self.sig_changed)
        self.changed = True
        self.wid_text.connect('activate', self.sig_activate)
        self.wid_text.connect_after('focus-out-event', self.sig_activate)
        self.focus_out = True

        self.but_open = gtk.Button()
        img_find = gtk.Image()
        img_find.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_open.set_image(img_find)
        self.but_open.set_relief(gtk.RELIEF_NONE)
        self.but_open.connect('clicked', self.sig_edit)
        self.but_open.set_alignment(0.5, 0.5)

        self.but_new = gtk.Button()
        img_new = gtk.Image()
        img_new.set_from_stock('tryton-new', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_new.set_image(img_new)
        self.but_new.set_relief(gtk.RELIEF_NONE)
        self.but_new.connect('clicked', self.sig_new)
        self.but_new.set_alignment(0.5, 0.5)

        self.widget.pack_end(self.but_new, expand=False, fill=False)
        self.widget.pack_end(self.but_open, expand=False, fill=False)
        self.widget.pack_end(self.wid_text, expand=True, fill=True)

        self.widget.set_focus_chain([self.wid_text])

        self.tooltips = common.Tooltips()
        self.tooltips.set_tip(self.but_new, _('Create a new record <F3>'))
        self.tooltips.set_tip(self.but_open, _('Open a record <F2>'))
        self.tooltips.enable()

        self._readonly = False

    def grab_focus(self):
        return self.wid_text.grab_focus()

    def get_model(self):
        return self.attrs['relation']

    def _readonly_set(self, value):
        self._readonly = value
        self.wid_text.set_editable(not value)
        self.but_new.set_sensitive(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.wid_text])

    @property
    def modified(self):
        if self.record and self.field:
            value = self.wid_text.get_text()
            return self.field.get_client(self.record) != value
        return False

    def _color_widget(self):
        return self.wid_text

    @staticmethod
    def has_target(value):
        return value is not None

    @staticmethod
    def value_from_id(id_, str_=None):
        if str_ is None:
            str_ = ''
        return id_, str_

    @staticmethod
    def id_from_value(value):
        return value

    def sig_activate(self, widget, event=None, key_press=False):
        if not self.focus_out or not self.field:
            return
        self.changed = False
        value = self.field.get(self.record)
        model = self.get_model()

        self.focus_out = False
        if model and not self.has_target(value):
            if not key_press and not event:
                widget.emit_stop_by_name('activate')
            if (not self._readonly
                    and (self.wid_text.get_text()
                        or (self.field.get_state_attrs(
                                self.record)['required'])
                            and key_press)):
                domain = self.field.domain_get(self.record)
                context = self.field.context_get(self.record)
                self.wid_text.grab_focus()

                try:
                    if self.wid_text.get_text():
                        dom = [('rec_name', 'ilike',
                            '%' + self.wid_text.get_text() + '%'),
                            domain]
                    else:
                        dom = domain
                    ids = RPCExecute('model', model, 'search', dom, 0,
                        CONFIG['client.limit'], None, context=context)
                except RPCException:
                    self.focus_out = True
                    self.changed = True
                    return
                if len(ids) == 1:
                    self.field.set_client(self.record,
                        self.value_from_id(ids[0]), force_change=True)
                    self.focus_out = True
                    self.display(self.record, self.field)
                    self.changed = True
                    return

                def callback(result):
                    if result:
                        self.field.set_client(self.record,
                            self.value_from_id(*result[0]), force_change=True)
                    self.focus_out = True
                    self.display(self.record, self.field)
                    self.changed = True

                WinSearch(model, callback, sel_multi=False,
                    ids=ids, context=context, domain=domain,
                    view_ids=self.attrs.get('view_ids', '').split(','),
                    views_preload=self.attrs.get('views', {}))
                return
        self.focus_out = True
        self.display(self.record, self.field)
        self.changed = True
        return

    def get_screen(self):
        domain = self.field.domain_get(self.record)
        context = self.field.context_get(self.record)
        return Screen(self.get_model(), domain=domain, context=context,
            mode=['form'], view_ids=self.attrs.get('view_ids', '').split(','),
            views_preload=self.attrs.get('views', {}), readonly=self._readonly)

    def sig_new(self, *args):
        self.focus_out = False
        screen = self.get_screen()

        def callback(result):
            if result:
                self.field.set_client(self.record,
                    self.value_from_id(screen.current_record.id,
                        screen.current_record.rec_name()))
                self.display(self.record, self.field)
            self.focus_out = True
        WinForm(screen, callback, new=True, save_current=True)

    def sig_edit(self, widget):
        if not self.focus_out or not self.field:
            return
        self.changed = False
        value = self.field.get(self.record)
        model = self.get_model()

        self.focus_out = False
        if model and self.has_target(value):
            screen = self.get_screen()
            screen.load([self.id_from_value(self.field.get(self.record))])

            def callback(result):
                if result:
                    self.field.set_client(self.record,
                        self.value_from_id(screen.current_record.id,
                            screen.current_record.rec_name()),
                        force_change=True)
                self.focus_out = True
                self.display(self.record, self.field)
                self.changed = True
            WinForm(screen, callback, save_current=True)
            return
        elif model and not self._readonly:
            domain = self.field.domain_get(self.record)
            context = self.field.context_get(self.record)
            self.wid_text.grab_focus()

            try:
                if self.wid_text.get_text():
                    dom = [('rec_name', 'ilike',
                        '%' + self.wid_text.get_text() + '%'),
                        domain]
                else:
                    dom = domain
                ids = RPCExecute('model', model, 'search', dom, 0,
                    CONFIG['client.limit'], None, context=context)
            except RPCException:
                self.focus_out = True
                self.changed = True
                return False
            if len(ids) == 1:
                self.field.set_client(self.record, self.value_from_id(ids[0]),
                    force_change=True)
                self.focus_out = True
                self.display(self.record, self.field)
                return True

            def callback(result):
                if result:
                    self.field.set_client(self.record,
                        self.value_from_id(*result[0]), force_change=True)
                self.focus_out = True
                self.display(self.record, self.field)
                self.changed = True
            WinSearch(model, callback, sel_multi=False,
                ids=ids, context=context, domain=domain,
                view_ids=self.attrs.get('view_ids', '').split(','),
                views_preload=self.attrs.get('views', {}))
            return
        self.focus_out = True
        self.display(self.record, self.field)
        self.changed = True
        return

    def sig_key_press(self, widget, event, *args):
        editable = self.wid_text.get_editable()
        if event.keyval == gtk.keysyms.F3 and editable:
            self.sig_new(widget, event)
            return True
        elif event.keyval == gtk.keysyms.F2:
            self.sig_edit(widget)
            return True
        elif (event.keyval in (gtk.keysyms.Tab, gtk.keysyms.Return)
                and editable):
            self.sig_activate(widget, event, key_press=True)
        return False

    def sig_changed(self, *args):
        if not self.changed:
            return False
        value = self.field.get(self.record)
        if self.has_target(value):
            def clean():
                self.field.set_client(self.record,
                    self.value_from_id(None, ''))
                self.display(self.record, self.field)
            gobject.idle_add(clean)
        return False

    def set_value(self, record, field):
        pass  # No update of the model, the model is updated in real time !

    def set_text(self, value):
        if not value:
            value = ''
        self.wid_text.set_text(value)
        self.wid_text.set_position(len(value))

    def display(self, record, field):
        self.changed = False
        super(Many2One, self).display(record, field)
        if not field:
            self.wid_text.set_text('')
            self.wid_text.set_position(0)
            self.changed = True
            return False
        img = self.but_open.get_image()
        current_stock = img.get_stock()[0]
        self.set_text(field.get_client(record))
        value = field.get(record)
        if self.has_target(value) and current_stock != 'tryton-open':
            img.set_from_stock('tryton-open', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.tooltips.set_tip(self.but_open, _('Open a record <F2>'))
        elif not self.has_target(value) and current_stock != 'tryton-find':
            img.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.tooltips.set_tip(self.but_open, _('Search a record <F2>'))
        self.changed = True

    def _populate_popup(self, widget, menu):
        value = self.field.get(self.record)
        if self.has_target(value):
            populate(menu, self.get_model(), self.id_from_value(value))
        return True
