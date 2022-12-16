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
from tryton.gui.window.view_form.widget_search.form import _LIMIT
from tryton.pyson import PYSONEncoder
import pango

_ = gettext.gettext


class Many2One(WidgetInterface):

    def __init__(self, field_name, model_name, window, attrs=None):
        super(Many2One, self).__init__(field_name, model_name, window,
                attrs=attrs)

        self.widget = gtk.HBox(spacing=0)
        self.widget.set_property('sensitive', True)
        self.widget.connect('focus-in-event', lambda x, y: self._focus_in())
        self.widget.connect('focus-out-event', lambda x, y: self._focus_out())

        self.wid_text = gtk.Entry()
        self.wid_text.set_property('width-chars', 13)
        self.wid_text.set_property('activates_default', True)
        self.wid_text.connect_after('key_press_event', self.sig_key_press)
        self.wid_text.connect('populate-popup', self._populate_popup)
        self.wid_text.connect_after('changed', self.sig_changed)
        self.changed = True
        self.wid_text.connect('activate', self.sig_activate)
        self.wid_text.connect_after('focus-out-event',
                        self.sig_activate)
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

        self.completion = gtk.EntryCompletion()
        self.liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        if attrs.get('completion', False):
            try:
                result = rpc.execute('model', self.attrs['relation'],
                        'search_read', [], 0, None, None, rpc.CONTEXT,
                        ['rec_name'])
                names = [(x['id'], x['rec_name']) for x in result]
            except Exception, exception:
                common.process_exception(exception, self.window)
                names = []
            if names:
                self.load_completion(names)

    def grab_focus(self):
        return self.wid_text.grab_focus()

    def load_completion(self, names):
        self.completion.set_match_func(self.match_func, None)
        self.completion.connect("match-selected", self.on_completion_match)
        self.wid_text.set_completion(self.completion)
        self.completion.set_model(self.liststore)
        self.completion.set_text_column(1)
        for object_id, name in names:
            self.liststore.append([object_id, name])

    def match_func(self, completion, key_string, iter, data):
        model = self.completion.get_model()
        modelstr = model[iter][1].lower()
        return modelstr.startswith(key_string)

    def on_completion_match(self, completion, model, iter):
        self.field.set_client(self.record, int(model[iter][0]))
        self.display(self.record, self.field)
        return True

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
                            'search', dom, 0, _LIMIT, None, context)
                except Exception, exception:
                    self.focus_out = True
                    common.process_exception(exception, self.window)
                    self.changed = True
                    return False
                if len(ids)==1:
                    self.field.set_client(self.record, ids[0],
                            force_change=True)
                    self.focus_out = True
                    self.display(self.record, self.field)
                    return True

                win = WinSearch(self.attrs['relation'], sel_multi=False,
                        ids=ids, context=context, domain=domain,
                        parent=self.window,
                        views_preload=self.attrs.get('views', {}))
                ids = win.run()
                if ids:
                    self.field.set_client(self.record, ids[0],
                            force_change=True)
                    self.focus_out = True
                    self.display(self.record, self.field)
                    return True
                else:
                    self.focus_out = True
                    self.display(self.record, self.field)
                    return False
        self.focus_out = True
        self.display(self.record, self.field)
        self.changed = True
        return True

    def get_screen(self):
        domain = self.field.domain_get(self.record)
        context = self.field.context_get(self.record)
        return Screen(self.attrs['relation'], self.window, domain=domain,
                context=context, view_type=['form'],
                views_preload=self.attrs.get('views', {}))

    def sig_new(self, *args):
        self.focus_out = False
        screen = self.get_screen()
        win = WinForm(screen, self.window, new=True)
        while win.run():
            if screen.save_current():
                value = (screen.current_record.id,
                        screen.current_record.rec_name())
                self.field.set_client(self.record, value)
                break
            else:
                screen.display()
        win.destroy()
        self.focus_out = True

    def sig_edit(self, widget):
        self.changed = False
        value = self.field.get(self.record)
        self.focus_out = False
        if value:
            screen = self.get_screen()
            screen.load([self.field.get(self.record)])
            win = WinForm(screen, self.window)
            while win.run():
                if screen.save_current():
                    value = (screen.current_record.id,
                            screen.current_record.rec_name())
                    self.field.set_client(self.record, value, force_change=True)
                    break
                else:
                    screen.display()
            win.destroy()
        else:
            if not self._readonly:
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
                            'search', dom, 0, _LIMIT, None, context)
                except Exception, exception:
                    self.focus_out = True
                    common.process_exception(exception, self.window)
                    self.changed = True
                    return False
                if ids and len(ids)==1:
                    self.field.set_client(self.record, ids[0],
                            force_change=True)
                    self.focus_out = True
                    self.display(self.record, self.field)
                    return True

                win = WinSearch(self.attrs['relation'], sel_multi=False,
                        ids=ids, context=context,
                        domain=domain, parent=self.window,
                        views_preload=self.attrs.get('views', {}))
                ids = win.run()
                if ids:
                    self.field.set_client(self.record, ids[0],
                            force_change=True)
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
            return not self.sig_activate(widget, event, key_press=True)
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
            self.changed = True
            return False
        img = self.but_open.get_image()
        current_stock = img.get_stock()[0]
        res = field.get_client(record)
        self.wid_text.set_text((res and str(res)) or '')
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
                'form_relate', (self.attrs['relation'], 0), rpc.CONTEXT)
        try:
            relates = rpc.execute(*args)
        except Exception, exception:
            relates = common.process_exception(exception, self.window)
            if not relates:
                return False
        menu_entries = []
        menu_entries.append((None, None, None))
        menu_entries += self._menu_entries
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
            common.message(_('You must select a record to use the relation!'),
                    self.window)
            return False
        screen = Screen(self.attrs['relation'], self.window)
        screen.load([obj_id])
        encoder = PYSONEncoder()
        act['domain'] = encoder.encode(screen.current_record.expr_eval(
            act.get('domain', []), check_load=False))
        act['context'] = encoder.encode(screen.current_record.expr_eval(
            act.get('context', {}), check_load=False))
        data['model'] = self.attrs['relation']
        data['id'] = obj_id
        data['ids'] = [obj_id]
        return Action._exec_action(act, self.window, data, context)

    def click_and_action(self, atype):
        obj_id = self.field.get(self.record)
        return Action.exec_keyword(atype, self.window, {
            'model': self.attrs['relation'],
            'id': obj_id or False,
            'ids': [obj_id],
            }, alwaysask=True)
