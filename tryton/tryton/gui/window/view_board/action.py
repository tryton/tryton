# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
'Action'
import gettext

from gi.repository import GLib, Gtk

from tryton.gui.window.view_form.screen import Screen
import tryton.rpc as rpc
import tryton.common as common
from tryton.config import CONFIG
from tryton.pyson import PYSONDecoder
from tryton.signal_event import SignalEvent
from tryton.gui.window.win_form import WinForm
from tryton.common import RPCExecute, RPCException
from tryton.action import Action as GenericAction
_ = gettext.gettext


class Action(SignalEvent):

    def __init__(self, attrs=None, context=None):
        if context is None:
            context = {}
        super(Action, self).__init__()
        self.name = attrs['name']

        try:
            self.action = RPCExecute('model', 'ir.action.act_window', 'get',
                self.name)
        except RPCException:
            raise

        view_ids = []
        view_mode = None
        if self.action.get('views', []):
            view_ids = [x[0] for x in self.action['views']]
            view_mode = [x[1] for x in self.action['views']]
        elif self.action.get('view_id', False):
            view_ids = [self.action['view_id'][0]]

        self.action.setdefault('pyson_domain', '[]')
        ctx = {}
        ctx.update(rpc.CONTEXT)
        ctx['_user'] = rpc._USER
        decoder = PYSONDecoder(ctx)
        action_ctx = context.copy()
        action_ctx.update(
            decoder.decode(self.action.get('pyson_context') or '{}'))
        ctx.update(action_ctx)

        ctx['context'] = ctx
        decoder = PYSONDecoder(ctx)
        self.domain = decoder.decode(self.action['pyson_domain'])
        order = decoder.decode(self.action['pyson_order'])
        search_value = decoder.decode(
            self.action['pyson_search_value'] or '[]')
        tab_domain = [(n, decoder.decode(d), c)
            for n, d, c in self.action['domains']]

        limit = self.action.get('limit')
        if limit is None:
            limit = CONFIG['client.limit']

        self.context = ctx
        self.domain = []
        self.update_domain([])

        self.widget = Gtk.Frame()
        self.widget.set_border_width(0)

        vbox = Gtk.VBox(homogeneous=False, spacing=3)
        self.widget.add(vbox)

        self.title = Gtk.Label()
        self.widget.set_label_widget(self.title)
        self.widget.set_label_align(0.0, 0.5)
        self.widget.show_all()

        self.screen = Screen(self.action['res_model'],
            view_ids=view_ids,
            domain=self.domain,
            context=action_ctx,
            order=order,
            mode=view_mode,
            limit=limit,
            search_value=search_value,
            tab_domain=tab_domain,
            context_model=self.action['context_model'],
            context_domain=self.action['context_domain'],
            row_activate=self.row_activate)
        vbox.pack_start(
            self.screen.widget, expand=True, fill=True, padding=0)
        self.screen.signal_connect(self, 'record-message',
            self._active_changed)

        if attrs.get('string'):
            self.title.set_text(attrs['string'])
        else:
            self.title.set_text(self.action['name'])

        self.widget.set_size_request(int(attrs.get('width', -1)),
                int(attrs.get('height', -1)))

        self.screen.search_filter()

    def row_activate(self):
        if not self.screen.current_record:
            return

        if (self.screen.current_view.view_type == 'tree'
                and int(self.screen.current_view.attributes.get(
                        'keyword_open', 0))):
            GenericAction.exec_keyword('tree_open', {
                    'model': self.screen.model_name,
                    'id': (self.screen.current_record.id
                        if self.screen.current_record else None),
                    'ids': [r.id for r in self.screen.selected_records],
                    }, context=self.screen.group._context.copy(),
                warning=False)
        else:
            def callback(result):
                if result:
                    self.screen.current_record.save()
                else:
                    self.screen.current_record.cancel()
            WinForm(self.screen, callback, title=self.title.get_text())

    def set_value(self, mode, model_field):
        self.screen.current_view.set_value()
        return True

    def display(self):
        self.screen.search_filter(self.screen.screen_container.get_text())

    def _active_changed(self, *args):
        self.signal('active-changed')

    def _get_active(self):
        if self.screen and self.screen.current_record:
            return common.EvalEnvironment(self.screen.current_record)

    active = property(_get_active)

    def update_domain(self, actions):
        domain_ctx = self.context.copy()
        domain_ctx['context'] = domain_ctx
        domain_ctx['_user'] = rpc._USER
        for action in actions:
            if action.active:
                domain_ctx[action.name] = action.active
        new_domain = PYSONDecoder(domain_ctx).decode(
                self.action['pyson_domain'])
        if self.domain == new_domain:
            return
        del self.domain[:]
        self.domain.extend(new_domain)
        if hasattr(self, 'screen'):  # Catch early update
            # Using idle_add to prevent corruption of the event who triggered
            # the update.
            def display():
                if self.screen.widget.props.window:
                    self.display()
            GLib.idle_add(display)
