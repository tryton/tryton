#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Action'
import gtk
from tryton.gui.window.view_form.screen import Screen
import tryton.rpc as rpc
import time
import datetime
from tryton.gui.window.win_search import WinSearch
from tryton.action import Action as Action2
from tryton.gui.window.view_tree.view_tree import ViewTree
import tryton.common as common
import gettext
_LIMIT = 2000
_ = gettext.gettext


class Action(object):

    def __init__(self, window, attrs=None):
        self.act_id = int(attrs['name'])
        self._window = window
        self.screen = None
        self.tree = None

        try:
            self.action = rpc.execute('model', 'ir.action.act_window', 'read',
                    self.act_id, False, rpc.CONTEXT)
        except Exception, exception:
            common.process_exception(exception, self._window)
            raise

        view_ids = None
        self.action['view_mode'] = None
        if self.action.get('views', []):
            view_ids = [x[0] for x in self.action['views']]
            self.action['view_mode'] = [x[1] for x in self.action['views']]
        elif self.action.get('view_id', False):
            view_ids = [self.action['view_id'][0]]

        if 'view_mode' in attrs:
            self.action['view_mode'] = attrs['view_mode']

        self.action.setdefault('domain', '[]')
        self.context = {}
        self.context.update(common.safe_eval(self.action.get('context', '{}'),
            self.context.copy()))

        eval_ctx = self.context.copy()
        eval_ctx['datetime'] = datetime
        self.context.update(common.safe_eval(self.action.get('context', '{}'),
            eval_ctx))

        domain_ctx = self.context.copy()
        domain_ctx['time'] = time
        domain_ctx['datetime'] = datetime
        self.domain = common.safe_eval(self.action['domain'] or '[]',
                domain_ctx)


        self.widget = gtk.Frame()
        self.widget.set_border_width(5)

        hbox = gtk.HBox(homogeneous=False, spacing=5)
        self.widget.set_label_widget(hbox)
        self.widget.set_label_align(1, 0.5)

        self.title = gtk.Label()
        hbox.pack_start(self.title, expand=True, fill=True)

        tooltips = common.Tooltips()

        hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

        if self.action['view_type'] == 'form':
            eb_search = gtk.EventBox()
            tooltips.set_tip(eb_search, _('Search'))
            eb_search.set_events(gtk.gdk.BUTTON_PRESS)
            eb_search.connect('button_press_event', self._sig_search)
            img_search = gtk.Image()
            img_search.set_from_stock('tryton-find', gtk.ICON_SIZE_BUTTON)
            img_search.set_alignment(0.5, 0.5)
            eb_search.add(img_search)
            hbox.pack_start(eb_search, expand=False, fill=False)

        eb_open = gtk.EventBox()
        tooltips.set_tip(eb_open, _('Open'))
        eb_open.set_events(gtk.gdk.BUTTON_PRESS)
        eb_open.connect('button_press_event', self._sig_open)
        img_open = gtk.Image()
        img_open.set_from_stock('tryton-open', gtk.ICON_SIZE_BUTTON)
        img_open.set_alignment(0.5, 0.5)
        eb_open.add(img_open)
        hbox.pack_start(eb_open, expand=False, fill=False)

        hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

        if self.action['view_type'] == 'form':
            eb_previous = gtk.EventBox()
            tooltips.set_tip(eb_previous, _('Previous'))
            eb_previous.set_events(gtk.gdk.BUTTON_PRESS)
            eb_previous.connect('button_press_event', self._sig_previous)
            img_previous = gtk.Image()
            img_previous.set_from_stock('tryton-go-previous', gtk.ICON_SIZE_BUTTON)
            img_previous.set_alignment(0.5, 0.5)
            eb_previous.add(img_previous)
            hbox.pack_start(eb_previous, expand=False, fill=False)

            self.label = gtk.Label('(0,0)')
            hbox.pack_start(self.label, expand=False, fill=False)

            eb_next = gtk.EventBox()
            tooltips.set_tip(eb_next, _('Next'))
            eb_next.set_events(gtk.gdk.BUTTON_PRESS)
            eb_next.connect('button_press_event', self._sig_next)
            img_next = gtk.Image()
            img_next.set_from_stock('tryton-go-next', gtk.ICON_SIZE_BUTTON)
            img_next.set_alignment(0.5, 0.5)
            eb_next.add(img_next)
            hbox.pack_start(eb_next, expand=False, fill=False)

            hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

            eb_switch = gtk.EventBox()
            tooltips.set_tip(eb_switch, _('Switch'))
            eb_switch.set_events(gtk.gdk.BUTTON_PRESS)
            eb_switch.connect('button_press_event', self._sig_switch)
            img_switch = gtk.Image()
            img_switch.set_from_stock('tryton-fullscreen', gtk.ICON_SIZE_BUTTON)
            img_switch.set_alignment(0.5, 0.5)
            eb_switch.add(img_switch)
            hbox.pack_start(eb_switch, expand=False, fill=False)

        alignment = gtk.Alignment(0.5, 0.5, 1.0, 1.0)
        alignment.set_padding(8, 0, 0, 0)
        self.widget.add(alignment)

        self.widget.show_all()

        if self.action['view_type'] == 'form':
            self.screen = Screen(self.action['res_model'], self._window,
                    view_type=self.action['view_mode'], context=self.context,
                    view_ids=view_ids, domain=self.domain, readonly=True)
            alignment.add(self.screen.widget)
            self.title.set_text(attrs.get('string',
                self.screen.current_view.title))
            self.screen.signal_connect(self, 'record-message', self._sig_label)
        elif self.action['view_type'] == 'tree':
            ctx = {}
            ctx.update(rpc.CONTEXT)
            ctx.update(self.context)
            try:
                view_base = rpc.execute('model', 'ir.ui.view', 'read',
                        view_ids[0], ['model', 'type'], ctx)
            except Exception, exception:
                common.process_exception(exception, self._window)
                raise
            try:
                view = rpc.execute('model', view_base['model'],
                        'fields_view_get', view_ids[0], view_base['type'], ctx)
            except Exception, exception:
                common.process_exception(exception, self._window)
                raise
            self.tree = ViewTree(view, [], self._window, True,
                    context=ctx)
            alignment.add(self.tree.widget_get())
            self.title.set_text(attrs.get('string',
                self.tree.name))
            self.tree.view.connect('key_press_event', self.sig_key_press)
        self.widget.set_size_request(int(attrs.get('width',-1)),
                int(attrs.get('height', -1)))
        self.display()

    def _sig_switch(self, *args):
        self.screen.switch_view()

    def _sig_search(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            ctx = {}
            ctx.update(rpc.CONTEXT)
            ctx.update(self.context)
            win = WinSearch(self.action['res_model'], domain=self.domain,
                    context=ctx, parent=self._window)
            res = win.run()
            if res:
                self.screen.clear()
                self.screen.load(res)

    def _sig_open(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            try:
                action_id = rpc.execute('model', 'ir.action',
                        'get_action_id', self.act_id, rpc.CONTEXT)
            except Exception, exception:
                common.process_exception(exception, self._window)
            if action_id:
                Action2.execute(action_id, {}, self._window)

    def _sig_previous(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            self.screen.display_prev()

    def _sig_next(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            self.screen.display_next()

    def _sig_label(self, screen, signal_data):
        name = '_'
        if signal_data[0] >= 0:
            name = str(signal_data[0] + 1)
        line = '(%s/%s)' % (name, signal_data[1])
        self.label.set_text(line)

    def set_value(self, mode, model_field):
        self.screen.current_view.set_value()
        return True

    def display(self):
        try:
            res_ids = rpc.execute('model', self.action['res_model'], 'search',
                    self.domain, 0, self.action['limit'] or _LIMIT, None,
                    rpc.CONTEXT)
        except Exception, exception:
            common.process_exception(exception, self._window)
            return False
        if self.screen:
            self.screen.clear()
            self.screen.load(res_ids)
        elif self.tree:
            self.tree.ids = res_ids
            self.tree.reload()
        return True

    def sig_key_press(self, widget, event):
        if event.keyval == gtk.keysyms.Left:
            model, paths = self.tree.view.get_selection()\
                    .get_selected_rows()
            for path in paths:
                self.tree.view.collapse_row(path)
        elif event.keyval == gtk.keysyms.Right:
            model, paths = self.tree.view.get_selection()\
                    .get_selected_rows()
            for path in paths:
                self.tree.view.expand_row(path, False)
