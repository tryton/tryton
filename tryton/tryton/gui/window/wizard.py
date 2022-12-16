# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import gettext

from gi.repository import Gdk, Gtk, Pango

from tryton.signal_event import SignalEvent
import tryton.common as common
from tryton.gui.window.view_form.screen import Screen
from tryton.gui import Main
from tryton.exceptions import TrytonServerError
from tryton.gui.window.nomodal import NoModal
from tryton.common.button import Button
from tryton.common import RPCExecute, RPCException, RPCContextReload
from tryton.common import TRYTON_ICON
from tryton.common.widget_style import widget_class
from .infobar import InfoBar
from .tabcontent import TabContent

_ = gettext.gettext
logger = logging.getLogger(__name__)


class Wizard(InfoBar):

    def __init__(self, name=''):
        super(Wizard, self).__init__()
        self.widget = Gtk.VBox(spacing=3)
        self.widget.show()
        self.name = name or _('Wizard')
        self.id = None
        self.ids = None
        self.action = None
        self.action_id = None
        self.direct_print = False
        self.email_print = False
        self.email = False
        self.context = None
        self.states = {}
        self.response2state = {}
        self.__processing = False
        self.__waiting_response = False
        self.session_id = None
        self.start_state = None
        self.end_state = None
        self.screen = None
        self.screen_state = None
        self.state = None

    def run(self, action, data, direct_print=False, email_print=False,
            email=None, context=None):
        self.action = action
        self.action_id = data.get('action_id')
        self.id = data.get('id')
        self.ids = data.get('ids')
        self.model = data.get('model')
        self.direct_print = direct_print
        self.email_print = email_print
        self.email = email
        self.context = context.copy() if context is not None else {}
        self.context['active_id'] = self.id
        self.context['active_ids'] = self.ids
        self.context['active_model'] = self.model
        self.context['action_id'] = self.action_id

        def callback(result):
            try:
                result = result()
            except RPCException:
                self.destroy()
                return
            self.session_id, self.start_state, self.end_state = result
            self.state = self.start_state
            self.process()
        RPCExecute('wizard', action, 'create', callback=callback)

    def process(self):
        from tryton.action import Action
        if self.__processing or self.__waiting_response:
            return
        self.__processing = True

        ctx = self.context.copy()
        if self.screen:
            data = {
                self.screen_state: self.screen.get_on_change_value(),
                }
        else:
            data = {}

        def callback(result):
            try:
                result = result()
            except RPCException as rpc_exception:
                if (not isinstance(rpc_exception.exception,
                        TrytonServerError)
                        or not self.screen):
                    self.state = self.end_state
                    self.end()
                self.__processing = False
                return

            if 'view' in result:
                self.clean()
                view = result['view']
                self.update(view['fields_view'], view['buttons'])

                self.screen.new(default=False)
                self.screen.current_record.set_default(view['defaults'])
                self.update_buttons(self.screen.current_record)
                self.screen.set_cursor()

                self.screen_state = view['state']
                self.__waiting_response = True
            else:
                self.state = self.end_state

            def execute_actions():
                for action in result.get('actions', []):
                    for k, v in [
                            ('direct_print', self.direct_print),
                            ('email_print', self.email_print),
                            ('email', self.email),
                            ]:
                        action[0].setdefault(k, v)
                    context = self.context.copy()
                    # Remove wizard keys added by run
                    del context['active_id']
                    del context['active_ids']
                    del context['active_model']
                    del context['action_id']
                    Action._exec_action(*action, context=context)

            if self.state == self.end_state:
                self.end(lambda *a: execute_actions())
            else:
                execute_actions()
            self.__processing = False

        RPCExecute('wizard', self.action, 'execute', self.session_id, data,
            self.state, context=ctx, callback=callback)

    def destroy(self, action=None):
        if self.screen:
            self.screen.destroy()

    def end(self, callback=None):
        def end_callback(action):
            self.destroy(action=action())
            if callback:
                callback()
        try:
            RPCExecute('wizard', self.action, 'delete', self.session_id,
                process_exception=False, callback=end_callback)
        except Exception:
            logger.warn(
                _("Unable to delete wizard %s") % self.session_id,
                exc_info=True)

    def clean(self):
        for widget in self.widget.get_children():
            self.widget.remove(widget)
        self.states = {}

    def response(self, widget, response):
        self.__waiting_response = False
        state = self.response2state.get(response, self.end_state)
        self.screen.current_view.set_value()
        if (not self.screen.current_record.validate()
                and state != self.end_state):
            self.screen.display(set_cursor=True)
            self.message_info(
                self.screen.invalid_message(), Gtk.MessageType.ERROR)
            return
        self.message_info()
        self.state = state
        self.process()

    def _get_button(self, definition):
        button = Button(definition)
        self.states[definition['state']] = button
        response = len(self.states)
        self.response2state[response] = definition['state']
        button.show()
        return button

    def _record_changed(self, screen, record):
        self.update_buttons(record)

    def update_buttons(self, record):
        for button in self.states.values():
            button.state_set(record)

    def update(self, view, buttons):
        tooltips = common.Tooltips()
        for button in buttons:
            self._get_button(button)

        self.screen = Screen(view['model'], mode=[], context=self.context)
        self.screen.add_view(view)
        self.screen.switch_view()
        self.screen.widget.show()
        self.screen.signal_connect(self, 'group-changed',
            self._record_changed)

        title = Gtk.Label(
            label=common.ellipsize(self.name, 80),
            halign=Gtk.Align.START, margin=5,
            ellipsize=Pango.EllipsizeMode.END)
        tooltips.set_tip(title, self.name)
        title.set_size_request(0, -1)  # Allow overflow
        title.show()

        hbox = Gtk.HBox()
        hbox.pack_start(title, expand=True, fill=True, padding=0)
        hbox.show()

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        widget_class(frame, 'wizard-title', True)
        frame.add(hbox)
        frame.show()

        self.widget.pack_start(frame, expand=False, fill=True, padding=3)

        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.NONE)
        viewport.add(self.screen.widget)
        viewport.show()
        self.scrolledwindow = Gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(Gtk.ShadowType.NONE)
        self.scrolledwindow.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolledwindow.add(viewport)
        self.scrolledwindow.show()

        self.widget.pack_start(
            self.scrolledwindow, expand=True, fill=True, padding=0)

        self.create_info_bar()
        self.widget.pack_start(
            self.info_bar, expand=False, fill=True, padding=0)


class WizardForm(Wizard, TabContent, SignalEvent):
    "Wizard"

    def __init__(self, name=''):
        super(WizardForm, self).__init__(name=name)
        self.hbuttonbox = Gtk.HButtonBox()
        self.hbuttonbox.set_spacing(5)
        self.hbuttonbox.set_layout(Gtk.ButtonBoxStyle.END)
        self.hbuttonbox.show()
        self.dialogs = []

        self.handlers = {
            'but_close': self.sig_close
        }

    def clean(self):
        super(WizardForm, self).clean()
        for button in self.hbuttonbox.get_children():
            self.hbuttonbox.remove(button)

    def _get_button(self, state):
        button = super(WizardForm, self)._get_button(state)
        response = len(self.states)
        button.connect('clicked', self.response, response)
        self.hbuttonbox.pack_start(button, expand=True, fill=True, padding=0)
        return button

    def update(self, view, buttons):
        super(WizardForm, self).update(view, buttons)
        self.widget.pack_start(
            self.hbuttonbox, expand=False, fill=True, padding=0)

    def sig_close(self):
        if self.end_state in self.states:
            self.states[self.end_state].clicked()
        return self.state == self.end_state

    def destroy(self, action=None):
        super(WizardForm, self).destroy(action=action)
        if action == 'reload menu':
            RPCContextReload(Main().sig_win_menu)
        elif action == 'reload context':
            RPCContextReload()

    def end(self, callback=None):
        super(WizardForm, self).end(callback=callback)
        Main()._win_del(self.widget)

    def set_cursor(self):
        if self.screen:
            self.screen.set_cursor()


class WizardDialog(Wizard, NoModal):

    def __init__(self, name=''):
        Wizard.__init__(self, name=name)
        NoModal.__init__(self)
        self.dia = Gtk.Dialog(
            title=self.name, transient_for=self.parent,
            destroy_with_parent=True)
        Main().add_window(self.dia)
        self.dia.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.dia.set_icon(TRYTON_ICON)
        self.dia.set_deletable(False)
        self.dia.connect('delete-event', lambda *a: True)
        self.dia.connect('close', self.close)
        self.dia.connect('response', self.response)

        self.accel_group = Gtk.AccelGroup()
        self.dia.add_accel_group(self.accel_group)

        self._buttons = set()

        self.dia.vbox.pack_start(
            self.widget, expand=True, fill=True, padding=0)

        self.register()

    def clean(self):
        super(WizardDialog, self).clean()
        while self._buttons:
            button = self._buttons.pop()
            button.get_parent().remove(button)

    def _get_button(self, definition):
        button = super(WizardDialog, self)._get_button(definition)
        response = len(self.states)
        self.dia.add_action_widget(button, response)
        self._buttons.add(button)
        if definition['default']:
            button.add_accelerator(
                'clicked', self.accel_group, Gdk.KEY_Return,
                Gdk.ModifierType.CONTROL_MASK, Gtk.AccelFlags.VISIBLE)
            button.get_style_context().add_class(
                Gtk.STYLE_CLASS_SUGGESTED_ACTION)
            button.set_can_default(True)
            button.grab_default()
            self.dia.set_default_response(response)
        return button

    def update(self, view, buttons):
        super(WizardDialog, self).update(view, buttons)
        current_view = self.screen.current_view
        self.scrolledwindow.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        if current_view.scroll:
            current_view.scroll.set_policy(
                Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        self.show()
        self.scrolledwindow.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        if current_view.scroll:
            current_view.scroll.set_policy(
                Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    def destroy(self, action=None):
        super(WizardDialog, self).destroy(action=action)
        self.dia.destroy()
        NoModal.destroy(self)
        main = Main()
        if self.parent == main.window:
            current_form = main.get_page()
            if current_form:
                for dialog in current_form.dialogs:
                    dialog.show()
        if self.page.dialogs:
            dialog = self.page.dialogs[-1]
        else:
            dialog = self.page
        screen = getattr(dialog, 'screen', None)
        if self.sensible_widget == main.window:
            screen = main.menu_screen
        if screen:
            if (screen.current_record
                    and self.sensible_widget != main.window):
                if screen.model_name == self.model:
                    ids = self.ids
                else:
                    # Wizard run from a children record so reload parent record
                    ids = [screen.current_record.id]
                screen.reload(ids, written=True)
            if action:
                screen.client_action(action)

    def close(self, widget, event=None):
        widget.stop_emission_by_name('close')
        if self.end_state in self.states:
            self.states[self.end_state].clicked()
        return True

    def show(self):
        view = self.screen.current_view
        if view.view_type == 'form':
            expand = False
            for name in view.get_fields():
                for widget in view.widgets[name]:
                    if widget.expand:
                        expand = True
                        break
                if expand:
                    break
        else:
            expand = True
        if expand:
            width, height = self.default_size()
        else:
            width, height = -1, -1
        self.dia.set_default_size(max(200, width), height)
        width, height = self.dia.get_default_size()
        if width > 0 and height > 0:
            self.dia.resize(*self.dia.get_default_size())
        self.dia.show()

    def hide(self):
        self.dia.hide()
