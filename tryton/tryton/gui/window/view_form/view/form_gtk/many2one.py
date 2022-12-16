#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gobject
import gtk
import gettext
from interface import WidgetInterface
from tryton.common import TRYTON_ICON, COLOR_SCHEMES
import tryton.common as common
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm
import tryton.rpc as rpc
from tryton.action import Action
from tryton.config import CONFIG
from tryton.pyson import PYSONEncoder
from tryton.exceptions import TrytonServerError
import pango

_ = gettext.gettext


class Many2One(WidgetInterface):

    def __init__(self, field_name, model_name, attrs=None):
        super(Many2One, self).__init__(field_name, model_name, attrs=attrs)

        self.widget = gtk.HBox(spacing=0)
        self.widget.set_property('sensitive', True)

        self.wid_text = gtk.Entry()
        self.wid_text.set_property('width-chars', 13)
        self.wid_text.set_property('activates_default', True)
        self.wid_text.connect_after('key_press_event', self.sig_key_press)
        self.wid_text.connect('populate-popup', self._populate_popup)
        self.wid_text.connect('focus-in-event', lambda x, y: self._focus_in())
        self.wid_text.connect('focus-out-event', lambda x, y: self._focus_out())
        self.wid_text.connect_after('changed', self.sig_changed)
        self.changed = True
        self.wid_text.connect('activate', self.sig_activate)
        self.wid_text.connect_after('focus-out-event', self.sig_activate)
        self.focus_out = True
        self.widget.pack_start(self.wid_text, expand=True, fill=True)

        self.but_open = gtk.Button()
        img_find = gtk.Image()
        img_find.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_open.set_image(img_find)
        self.but_open.set_relief(gtk.RELIEF_NONE)
        self.but_open.connect('clicked', self.sig_edit)
        self.but_open.set_alignment(0.5, 0.5)
        self.widget.pack_start(self.but_open, expand=False, fill=False)

        self.but_new = gtk.Button()
        img_new = gtk.Image()
        img_new.set_from_stock('tryton-new', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.but_new.set_image(img_new)
        self.but_new.set_relief(gtk.RELIEF_NONE)
        self.but_new.connect('clicked', self.sig_new)
        self.but_new.set_alignment(0.5, 0.5)
        self.widget.pack_start(self.but_new, expand=False, fill=False)

        self.widget.set_focus_chain([self.wid_text])

        self.tooltips = common.Tooltips()
        self.tooltips.set_tip(self.but_new, _('Create a new record'))
        self.tooltips.set_tip(self.but_open, _('Open a record'))
        self.tooltips.enable()

        self._readonly = False

    def grab_focus(self):
        return self.wid_text.grab_focus()

    def _readonly_set(self, value):
        self._readonly = value
        self.wid_text.set_editable(not value)
        self.but_new.set_sensitive(not value)
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.wid_text])

    def _color_widget(self):
        return self.wid_text

    def sig_activate(self, widget=None, event=None, key_press=False):
        if not self.focus_out:
            return
        if not self.field:
            return
        self.changed = False
        value = self.field.get(self.record)

        self.focus_out = False
        if not value:
            if not key_press and not event and widget:
                widget.emit_stop_by_name('activate')
            if not self._readonly and (self.wid_text.get_text() or \
                    (self.field.get_state_attrs(
                        self.record)['required']) and key_press):
                domain = self.field.domain_get(self.record)
                context = rpc.CONTEXT.copy()
                context.update(self.field.context_get(self.record))
                self.wid_text.grab_focus()

                try:
                    if self.wid_text.get_text():
                        dom = [('rec_name', 'ilike',
                            '%' + self.wid_text.get_text() + '%'),
                            domain]
                    else:
                        dom = domain
                    ids = rpc.execute('model', self.attrs['relation'],
                            'search', dom, 0, CONFIG['client.limit'], None,
                            context)
                except TrytonServerError, exception:
                    self.focus_out = True
                    common.process_exception(exception)
                    self.changed = True
                    return
                if len(ids)==1:
                    self.field.set_client(self.record, ids[0],
                            force_change=True)
                    self.focus_out = True
                    self.display(self.record, self.field)
                    return
                def callback(ids):
                    if ids:
                        self.field.set_client(self.record, ids[0],
                                force_change=True)
                    self.focus_out = True
                    self.display(self.record, self.field)

                WinSearch(self.attrs['relation'], callback, sel_multi=False,
                    ids=ids, context=context, domain=domain,
                    views_preload=self.attrs.get('views', {}))
                return
        self.focus_out = True
        self.display(self.record, self.field)
        self.changed = True
        return

    def get_screen(self):
        domain = self.field.domain_get(self.record)
        context = self.field.context_get(self.record)
        return Screen(self.attrs['relation'], domain=domain, context=context,
            mode=['form'], views_preload=self.attrs.get('views', {}),
            readonly=self._readonly)

    def sig_new(self, *args):
        self.focus_out = False
        screen = self.get_screen()
        def callback(result):
            if result and screen.save_current():
                value = (screen.current_record.id,
                        screen.current_record.rec_name())
                self.field.set_client(self.record, value)
            self.focus_out = True
        WinForm(screen, callback, new=True)

    def sig_edit(self, widget):
        self.changed = False
        value = self.field.get(self.record)
        self.focus_out = False
        if value:
            screen = self.get_screen()
            screen.load([self.field.get(self.record)])
            def callback(result):
                if result and screen.save_current():
                    value = (screen.current_record.id,
                            screen.current_record.rec_name())
                    self.field.set_client(self.record, value,
                        force_change=True)
                elif result:
                    screen.display()
                    return WinForm(screen, callback)
                self.focus_out = True
                self.display(self.record, self.field)
                self.changed = True
            WinForm(screen, callback)
            return
        elif not self._readonly:
            domain = self.field.domain_get(self.record)
            context = rpc.CONTEXT.copy()
            context.update(self.field.context_get(self.record))
            self.wid_text.grab_focus()

            try:
                if self.wid_text.get_text():
                    dom = [('rec_name', 'ilike',
                        '%' + self.wid_text.get_text() + '%'),
                        domain]
                else:
                    dom = domain
                ids = rpc.execute('model', self.attrs['relation'],
                        'search', dom, 0, CONFIG['client.limit'], None,
                        context)
            except TrytonServerError, exception:
                self.focus_out = True
                common.process_exception(exception)
                self.changed = True
                return False
            if ids and len(ids)==1:
                self.field.set_client(self.record, ids[0],
                        force_change=True)
                self.focus_out = True
                self.display(self.record, self.field)
                return True

            def callback(ids):
                if ids:
                    self.field.set_client(self.record, ids[0],
                            force_change=True)
                self.focus_out = True
                self.display(self.record, self.field)
                self.changed = True
            WinSearch(self.attrs['relation'], callback, sel_multi=False,
                ids=ids, context=context, domain=domain,
                views_preload=self.attrs.get('views', {}))
            return
        self.focus_out = True
        self.display(self.record, self.field)
        self.changed = True

    def sig_key_press(self, widget, event, *args):
        editable = self.wid_text.get_editable()
        if event.keyval == gtk.keysyms.F3 and editable:
            self.sig_new(widget, event)
            return True
        elif event.keyval == gtk.keysyms.F2:
            self.sig_edit(widget)
            return True
        elif event.keyval in (gtk.keysyms.Tab, gtk.keysyms.Return) and editable:
            self.sig_activate(widget, event, key_press=True)
        return False

    def sig_changed(self, *args):
        if not self.changed:
            return False
        if self.field.get(self.record):
            self.field.set_client(self.record, False)
            self.display(self.record, self.field)
        return False

    def set_value(self, record, field):
        # Simulate a focus-out
        self.sig_activate()

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
        res = field.get_client(record) or ''
        self.wid_text.set_text(res)
        self.wid_text.set_position(len(res))
        if res and current_stock != 'tryton-open':
            img.set_from_stock('tryton-open', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.tooltips.set_tip(self.but_open, _('Open a record'))
        elif not res and current_stock != 'tryton-find':
            img.set_from_stock('tryton-find', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.tooltips.set_tip(self.but_open, _('Search a record'))
        self.changed = True

    def _populate_popup(self, widget, menu):
        value = self.field.get(self.record)
        args = ('model', 'ir.action.keyword', 'get_keyword',
                'form_relate', (self.attrs['relation'], -1), rpc.CONTEXT)
        try:
            relates = rpc.execute(*args)
        except TrytonServerError, exception:
            relates = common.process_exception(exception)
            if not relates:
                return False
        menu_entries = []
        menu_entries.append((None, None, None))
        menu_entries.append((None, None, None))
        menu_entries.append((_('Actions'),
            lambda x: self.click_and_action('form_action'),0))
        menu_entries.append((_('Reports'),
            lambda x: self.click_and_action('form_print'),0))
        menu_entries.append((None, None, None))
        for relate in relates:
            relate['string'] = relate['name']
            fct = lambda action: lambda x: self.click_and_relate(action)
            menu_entries.append(
                    ('... ' + relate['name'], fct(relate), 0))

        for stock_id, callback, sensitivity in menu_entries:
            if stock_id:
                item = gtk.ImageMenuItem(stock_id)
                if callback:
                    item.connect("activate", callback)
                item.set_sensitive(bool(sensitivity or value))
            else:
                item = gtk.SeparatorMenuItem()
            item.show()
            menu.append(item)
        return True

    def click_and_relate(self, action):
        data = {}
        context = {}
        act = action.copy()
        obj_id = self.field.get(self.record)
        if not obj_id:
            common.message(_('You must select a record to use the relation!'))
            return False
        screen = Screen(self.attrs['relation'])
        screen.load([obj_id])
        encoder = PYSONEncoder()
        act['domain'] = encoder.encode(screen.current_record.expr_eval(
            act.get('domain', []), check_load=False))
        act['context'] = encoder.encode(screen.current_record.expr_eval(
            act.get('context', {}), check_load=False))
        data['model'] = self.attrs['relation']
        data['id'] = obj_id
        data['ids'] = [obj_id]
        return Action._exec_action(act, data, context)

    def click_and_action(self, atype):
        obj_id = self.field.get(self.record)
        return Action.exec_keyword(atype, {
            'model': self.attrs['relation'],
            'id': obj_id or False,
            'ids': [obj_id],
            }, alwaysask=True)
