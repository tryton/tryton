#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import pango
import gettext
from tryton.signal_event import SignalEvent
import tryton.rpc as rpc
import tryton.common as common
from tryton.gui.window.view_form.screen import Screen
from tryton.gui import Main
from tryton.exceptions import TrytonServerError
from tryton.config import CONFIG
from tryton.gui.window.nomodal import NoModal
_ = gettext.gettext


class Wizard(object):

    def __init__(self, name=False):
        super(Wizard, self).__init__()
        self.widget = gtk.VBox(spacing=3)
        self.toolbar_box = None
        self.widget.show()
        self.name = name or ''
        self.model = ''
        self.action = None
        self.datas = None
        self.state = 'init'
        self.direct_print = False
        self.email_print = False
        self.email = False
        self.context = None
        self.states = {}
        self.response2state = {}
        self.__processing = False
        self.__waiting_response = False

    def run(self, action, datas, state='init', direct_print=False,
            email_print=False, email=None, context=None):
        self.action = action
        self.datas = datas
        self.state = state
        self.direct_print = direct_print
        self.email_print = email_print
        self.email = email
        self.context = context
        if not 'form' in datas:
            datas['form'] = {}
        args = ('wizard', action, 'create', rpc.CONTEXT)
        try:
            self.wiz_id = rpc.execute(*args)
        except TrytonServerError, exception:
            self.wiz_id = common.process_exception(exception, *args)
            if not self.wiz_id:
                return
        self.process()

    def process(self):
        from tryton.action import Action
        res = {}
        if self.__processing or self.__waiting_response:
            return
        try:
            self.__processing = True
            while self.state != 'end':
                ctx = self.context.copy()
                ctx.update(rpc.CONTEXT)
                ctx['active_id'] = self.datas.get('id')
                ctx['active_ids'] = self.datas.get('ids')
                rpcprogress = common.RPCProgress('execute', ('wizard',
                        self.action, 'execute', self.wiz_id, self.datas,
                        self.state, ctx))
                try:
                    res = rpcprogress.run()
                except TrytonServerError, exception:
                    common.process_exception(exception)
                    self.end()
                    break
                if not res:
                    self.end()
                    return

                if 'datas' in res:
                    self.datas['form'] = res['datas']
                elif res['type'] == 'form':
                    self.datas['form'] = {}
                if res['type'] == 'form':
                    self.clean()
                    self.update(res, res['state'], res['object'], context=ctx)
                    self.screen.current_record.set_default(self.datas['form'])
                    self.__waiting_response = True
                    break
                elif res['type'] == 'action':
                    self.state = res['state']
                    sensitive_widget = self.widget.get_toplevel()
                    if self.state == 'end':
                        self.end()
                    Action._exec_action(res['action'], self.datas, context=ctx)
                    if self.state == 'end' or (
                            res['action']['type'] == 'ir.action.wizard'
                            and not sensitive_widget.props.sensitive):
                        return
                elif res['type'] == 'print':
                    self.datas['report_id'] = res.get('report_id', False)
                    if res.get('get_id_from_action', False):
                        backup_ids = self.datas['ids']
                        self.datas['ids'] = self.datas['form']['ids']
                        Action.exec_report(res['report'], self.datas,
                            direct_print=self.direct_print,
                            email_print=self.email_print, email=self.email,
                            context=ctx)
                        self.datas['ids'] = backup_ids
                    else:
                        Action.exec_report(res['report'], self.datas,
                            direct_print=self.direct_print,
                            email_print=self.email_print, email=self.email,
                            context=ctx)
                    self.state = res['state']
                elif res['type'] == 'state':
                    self.state = res['state']

            if self.state == 'end':
                self.end()
        finally:
            self.__processing = False

    def destroy(self):
        if hasattr(self, 'screen'):
            self.screen.signal_unconnect(self)
            self.screen.destroy()
            del self.screen
        del self.widget

    def end(self):
        try:
            rpc.execute('wizard', self.action, 'delete', self.wiz_id,
                rpc.CONTEXT)
            if self.action == 'ir.module.module.config_wizard':
                rpc.context_reload()
        except TrytonServerError:
            pass

    def clean(self):
        for widget in self.widget.get_children():
            self.widget.remove(widget)
        self.states = {}

    def response(self, widget, response):
        self.__waiting_response = False
        state = self.response2state.get(response, 'end')
        self.screen.current_view.set_value()
        if not self.screen.current_record.validate() \
                and state != 'end':
            self.screen.display()
            return
        self.datas['form'].update(self.screen.get())
        self.state = state
        self.process()

    def _get_button(self, state):
        button = gtk.Button()
        button.set_use_underline(True)
        button.set_label('_' + state[1])
        if len(state) >= 3:
            common.ICONFACTORY.register_icon(state[2])
            icon = gtk.Image()
            icon.set_from_stock(state[2], gtk.ICON_SIZE_BUTTON)
            button.set_image(icon)
        self.states[state[0]] = button
        response = len(self.states)
        self.response2state[response] = state[0]
        button.show()
        return button

    def update(self, view, states, obj_name, context=None):
        self.model = obj_name

        for state in states:
            self._get_button(state)

        val = {}
        fields = view['fields']
        for i in fields:
            if 'value' in fields[i]:
                val[i] = fields[i]['value']

        self.screen = Screen(obj_name, mode=[], context=context)
        self.screen.add_view(view, display=True)
        self.screen.widget.show()

        title = gtk.Label()
        title.set_use_markup(True)
        title.modify_font(pango.FontDescription("14"))
        title.set_label('<b>' + self.screen.current_view.title + '</b>')
        title.set_padding(20, 4)
        title.set_alignment(0.0, 0.5)
        title.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#000000"))
        title.show()

        self.info_label = gtk.Label()
        self.info_label.set_padding(3, 3)
        self.info_label.set_alignment(1.0, 0.5)

        self.eb_info = gtk.EventBox()
        self.eb_info.add(self.info_label)
        self.eb_info.connect('button-release-event',
                lambda *a: self.message_info(''))

        vbox = gtk.VBox()
        vbox.pack_start(self.eb_info, expand=True, fill=True, padding=5)
        vbox.show()

        hbox = gtk.HBox()
        hbox.pack_start(title, expand=True, fill=True)
        hbox.pack_start(vbox, expand=False, fill=True, padding=20)
        hbox.show()

        frame = gtk.Frame()
        frame.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        frame.add(hbox)
        frame.show()

        eb = gtk.EventBox()
        eb.add(frame)
        eb.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#ffffff"))
        eb.show()

        self.widget.pack_start(eb, expand=False, fill=True, padding=3)

        if self.toolbar_box:
            self.widget.pack_start(self.toolbar_box, False, True)

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(self.screen.widget)
        viewport.show()
        self.scrolledwindow = gtk.ScrolledWindow()
        self.scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        self.scrolledwindow.add(viewport)
        self.scrolledwindow.show()

        self.widget.pack_start(self.scrolledwindow)

        self.screen.new(default=False)
        self.screen.current_record.set_default(val)
        self.screen.current_view.set_cursor()


class WizardForm(Wizard,SignalEvent):
    "Wizard"

    def __init__(self, name=False):
        super(WizardForm, self).__init__(name=name)
        self.toolbar_box = gtk.HBox()
        self.hbuttonbox = gtk.HButtonBox()
        self.hbuttonbox.set_spacing(5)
        self.hbuttonbox.set_layout(gtk.BUTTONBOX_END)
        self.hbuttonbox.show()
        self.widget.pack_start(self.toolbar_box, False, True)
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
        self.hbuttonbox.pack_start(button)
        return button

    def update(self, view, states, obj_name, context=None):
        super(WizardForm, self).update(view, states, obj_name, context=context)
        self.widget.pack_start(self.hbuttonbox, expand=False, fill=True)

    def sig_close(self):
        if 'end' in self.states:
            self.states['end'].clicked()
        return self.state == 'end'

    def destroy(self):
        if self.toolbar_box.get_children():
            toolbar = self.toolbar_box.get_children()[0]
            self.toolbar_box.remove(toolbar)
        super(WizardForm, self).destroy()

    def end(self):
        super(WizardForm, self).end()
        Main.get_main()._win_del(self.widget)


class WizardDialog(Wizard, NoModal):

    def __init__(self, name=False):
        if not name:
            name = _('Wizard')
        Wizard.__init__(self, name=name)
        NoModal.__init__(self)
        self.dia = gtk.Dialog(self.name, self.parent,
            gtk.DIALOG_DESTROY_WITH_PARENT)
        self.dia.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        if hasattr(self.dia, 'set_deletable'):
            self.dia.set_deletable(False)
        self.dia.connect('close', self.close)
        self.dia.connect('response', self.response)
        self.dia.connect('state-changed', self.state_changed)

        self.accel_group = gtk.AccelGroup()
        self.dia.add_accel_group(self.accel_group)

        self.dia.vbox.add(self.widget)

        self.register()

    def clean(self):
        super(WizardDialog, self).clean()
        hbuttonbox = self.dia.get_action_area()
        for button in hbuttonbox.get_children():
            hbuttonbox.remove(button)

    def _get_button(self, state):
        button = super(WizardDialog, self)._get_button(state)
        response = len(self.states)
        self.dia.add_action_widget(button, response)
        if len(state) >= 4 and state[3]:
            button.set_flags(gtk.CAN_DEFAULT)
            button.add_accelerator('clicked', self.accel_group,
                gtk.keysyms.Return, gtk.gdk.CONTROL_MASK,
                gtk.ACCEL_VISIBLE)
            self.dia.set_default_response(response)
        return button

    def update(self, view, states, obj_name, context=None):
        super(WizardDialog, self).update(view, states, obj_name, context=context)
        sensible_allocation = self.sensible_widget.get_allocation()
        self.dia.set_default_size(int(sensible_allocation.width * 0.9),
            int(sensible_allocation.height * 0.9))
        self.dia.show()
        common.center_window(self.dia, self.parent, self.sensible_widget)

    def destroy(self):
        self.dia.destroy()
        NoModal.destroy(self)
        main = Main.get_main()
        if self.parent == main.window:
            current_form = main.get_page()
            if current_form:
                for dialog in current_form.dialogs:
                    dialog.show()
        super(WizardDialog, self).destroy()
        if self.page.dialogs:
            dialog = self.page.dialogs[-1]
        else:
            dialog = self.page
        if hasattr(dialog, 'screen'):
            dialog.screen.reload(written=True)

    def end(self):
        super(WizardDialog, self).end()
        self.destroy()

    def close(self, widget, event=None):
        widget.emit_stop_by_name('close')
        return True

    def show(self):
        self.dia.show()

    def hide(self):
        self.dia.hide()

    def state_changed(self, widget, state):
        if self.dia.props.sensitive and state == gtk.STATE_INSENSITIVE:
            self.process()
