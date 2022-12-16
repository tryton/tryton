#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import pango
from tryton.signal_event import SignalEvent
import tryton.rpc as rpc
import tryton.common as common
from tryton.gui.window.view_form.screen import Screen
from tryton.gui import Main


class Wizard(SignalEvent):
    "Wizard"

    def __init__(self, window, name=False):
        super(Wizard, self).__init__()
        self.window = window
        self.widget = gtk.VBox(spacing=3)
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

        self.handlers = {
            'but_close': self.sig_close
        }

    def sig_close(self):
        if 'end' in self.states:
            self.states['end'].clicked()
        return self.state == 'end'

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
        args = ('wizard', action, 'create')
        try:
            self.wiz_id = rpc.execute(*args)
        except Exception, exception:
            self.wiz_id = common.process_exception(exception, self.window, *args)
            if not self.wiz_id:
                return
        self.process()

    def process(self):
        from tryton.action import Action
        while self.state != 'end':
            ctx = self.context.copy()
            ctx.update(rpc.CONTEXT)
            ctx['active_id'] = self.datas.get('id')
            ctx['active_ids'] = self.datas.get('ids')
            rpcprogress = common.RPCProgress('execute', ('wizard',
                self.action, 'execute', self.wiz_id, self.datas, self.state, ctx),
                self.window)
            try:
                res = rpcprogress.run()
            except Exception, exception:
                common.process_exception(exception, self.window)
                self.end()
                return
            if not res:
                self.end()
                return
            self.clean()

            if 'datas' in res:
                self.datas['form'] = res['datas']
            elif res['type'] == 'form':
                self.datas['form'] = {}
            if res['type'] == 'form':
                self.update(res['arch'], res['fields'], res['state'],
                            res['object'], context=ctx)
                self.screen.current_model.set(self.datas['form'])
                break
            elif res['type'] == 'action':
                self.state = res['state']
                if self.state == 'end':
                    self.end()
                Action._exec_action(res['action'], self.window, self.datas,
                        context=ctx)
                if self.state == 'end':
                    return
            elif res['type'] == 'print':
                self.datas['report_id'] = res.get('report_id', False)
                if res.get('get_id_from_action', False):
                    backup_ids = datas['ids']
                    self.datas['ids'] = self.datas['form']['ids']
                    Action.exec_report(res['report'], self.datas, self.window,
                            direct_print=self.direct_print,
                            email_print=self.email_print, email=self.email,
                            context=ctx)
                    self.datas['ids'] = backup_ids
                else:
                    Action.exec_report(res['report'], self.datas, self.window,
                            direct_print=self.direct_print,
                            email_print=self.email_print, email=self.email,
                            context=ctx)
                self.state = res['state']
            elif res['type'] == 'state':
                self.state = res['state']

        if self.state == 'end':
            self.end()

    def destroy(self):
        if hasattr(self, 'screen'):
            self.screen.signal_unconnect(self)
            self.screen.destroy()
            del self.screen
        del self.widget

    def end(self):
        try:
            rpc.execute('wizard', self.action, 'delete', self.wiz_id)
            #XXX to remove when company displayed in status bar
            rpc.context_reload()
        except:
            pass
        Main.get_main()._win_del(self.widget)

    def clean(self):
        for widget in self.widget.get_children():
            self.widget.remove(widget)
        self.states = {}

    def sig_clicked(self, widget, state):
        self.screen.current_view.set_value()
        if not self.screen.current_model.validate() \
                and state != 'end':
            self.screen.display()
            return
        self.datas['form'].update(self.screen.get())
        self.state = state
        self.process()

    def update(self, arch, fields, state, obj_name, context=None):
        self.model = obj_name

        hbuttonbox = gtk.HButtonBox()
        hbuttonbox.set_spacing(5)
        hbuttonbox.set_layout(gtk.BUTTONBOX_END)
        hbuttonbox.show()
        for i in state:
            but = gtk.Button()
            but.set_use_underline(True)
            but.set_label('_' + i[1])
            but.show()
            but.connect('clicked', self.sig_clicked, i[0])
            self.states[i[0]] = but
            if len(i) >= 3:
                icon = gtk.Image()
                icon.set_from_stock(i[2], gtk.ICON_SIZE_BUTTON)
                but.set_image(icon)
            hbuttonbox.pack_start(but)

        val = {}
        for i in fields:
            if 'value' in fields[i]:
                val[i] = fields[i]['value']

        self.screen = Screen(obj_name, self.window, view_type=[],
                context=context)
        self.screen.add_view_custom(arch, fields, display=True)
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

        self.widget.pack_start(hbuttonbox, expand=False, fill=True)

        self.screen.new(default=False)
        self.screen.current_model.set(val)
        self.screen.current_view.set_cursor()
