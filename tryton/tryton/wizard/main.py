#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
import tryton.rpc as rpc
import tryton.common as common
import thread, time
from tryton.gui.window.view_form.screen import Screen
import os
import pango
from tryton.config import CONFIG

_ = gettext.gettext


class Dialog(object):
    "Dialog for wizard"

    def __init__(self, arch, fields, state, obj_name, parent,
            action='', size=(0, 0), context=None):
        self.parent = parent
        self.action = action
        self.states = []
        default = -1
        self.dia = gtk.Dialog(_('Wizard'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        self.dia.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        if hasattr(self.dia, 'set_deletable') and os.name != 'nt':
            self.dia.set_deletable(False)

        self.accel_group = gtk.AccelGroup()
        self.dia.add_accel_group(self.accel_group)

        for i in state:
            but = gtk.Button(i[1])
            but.show()
            if len(i) >= 3:
                icon = gtk.Image()
                icon.set_from_stock(i[2], gtk.ICON_SIZE_BUTTON)
                but.set_image(icon)
            self.dia.add_action_widget(but, len(self.states))
            if len(i) >= 4 and i[3]:
                if default < 0:
                    default = len(self.states)
                    but.set_flags(gtk.CAN_DEFAULT)
                    but.add_accelerator('clicked', self.accel_group,
                            gtk.keysyms.Return, gtk.gdk.CONTROL_MASK,
                            gtk.ACCEL_VISIBLE)
                    self.dia.set_default_response(default)
            self.states.append(i[0])

        val = {}
        for i in fields:
            if 'value' in fields[i]:
                val[i] = fields[i]['value']

        self.screen = Screen(obj_name, self.dia, view_type=[], context=context)
        self.screen.add_view(arch, fields, display=True)

        title = gtk.Label()
        title.set_use_markup(True)
        title.modify_font(pango.FontDescription("14"))
        title.set_label('<b>' + self.screen.current_view.title + '</b>')
        title.set_padding(20, 3)
        title.set_alignment(0.0, 0.5)
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

        self.dia.vbox.pack_start(eb, expand=False, fill=True, padding=3)

        self.dia.vbox.pack_start(self.screen.widget, True, True)

        width, height = self.screen.screen_container.size_get()
        parent_width, parent_height = parent.get_size()
        dia_width, dia_height = self.dia.get_size()
        self.widget_width = max(min(parent_width - 20,
            max(dia_width, width + 20)), size[0])
        self.widget_height = max(min(parent_height - 60,
            height + dia_height + 20), size[1])
        self.dia.set_default_size(self.widget_width,
                self.widget_height)
        self.screen.widget.show()
        self.dia.set_title(self.screen.current_view.title)
        self.dia.show()
        self.screen.new(default=False)
        self.screen.current_record.set_default(val)
        self.screen.current_view.set_cursor()

    def run(self, datas=None):
        if datas is None:
            datas = {}
        while True:
            res = self.dia.run()
            self.screen.current_view.set_value()
            if self.screen.current_record.validate() \
                    or (res<0) or (self.states[res]=='end'):
                break
            self.screen.display()

        if CONFIG['client.save_width_height']:
            width, height = self.dia.get_size()
            if (width, height) != (self.widget_width, self.widget_height):
                try:
                    rpc.execute('model', 'ir.action.wizard_size', 'set_size',
                            self.action, self.screen.model_name, width, height,
                            rpc.CONTEXT)
                except Exception:
                    pass

        if res < len(self.states) and res >= 0:
            datas.update(self.screen.get())
            self.dia.hide()
            self.parent.present()
            return self.states[res], datas
        else:
            self.dia.hide()
            self.parent.present()
            return False

    def destroy(self):
        self.dia.destroy()

    def message_info(self, message, color='red'):
        if message:
            self.info_label.set_label(message)
            self.eb_info.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(
                COLOR_SCHEMES.get(color, 'white')))
            self.eb_info.show_all()
        else:
            self.info_label.set_label('')
            self.eb_info.hide()


class Wizard(object):

    @staticmethod
    def execute(action, datas, parent, state='init',
            direct_print=False, email_print=False, email=None,
            context=None):
        from tryton.action import Action
        if not 'form' in datas:
            datas['form'] = {}
        args = ('wizard', action, 'create', rpc.CONTEXT)
        try:
            wiz_id = rpc.execute(*args)
        except Exception, exception:
            wiz_id = common.process_exception(exception, parent, *args)
            if not wiz_id:
                return
        dia = None
        res = {}
        while state != 'end':
            ctx = context.copy()
            ctx.update(rpc.CONTEXT)
            ctx['active_id'] = datas.get('id')
            ctx['active_ids'] = datas.get('ids')
            rpcprogress = common.RPCProgress('execute', ('wizard',
                action, 'execute', wiz_id, datas, state, ctx), parent)
            try:
                res = rpcprogress.run()
                exception = None
            except Exception, exception:
                common.process_exception(exception, parent)
                # Continue by running previous result except if access to
                # wizard is denied
                if exception.args[0] == 'AccessDenied':
                    break
            if not res:
                if dia:
                    res = {'type': 'form'}
                else:
                    break
            else:
                if dia and not exception:
                    dia.destroy()
                    dia = None

            if 'datas' in res:
                datas['form'] = res['datas']
            elif res['type'] == 'form':
                datas['form'] = {}
            if res['type'] == 'form':
                if not dia:
                    dia = Dialog(res['arch'], res['fields'], res['state'],
                            res['object'], parent, action=action,
                            size=res['size'], context=ctx)
                    dia.screen.current_record.set(datas['form'])
                res2 = dia.run(datas['form'])
                if not res2:
                    break
                state, new_data = res2

                for data in new_data:
                    if new_data[data] is None:
                        del new_data[data]
                datas['form'].update(new_data)
                del new_data
            elif res['type'] == 'action':
                Action._exec_action(res['action'], dia or parent, datas,
                        context=ctx)
                state = res['state']
            elif res['type'] == 'print':
                datas['report_id'] = res.get('report_id', False)
                if res.get('get_id_from_action', False):
                    backup_ids = datas['ids']
                    datas['ids'] = datas['form']['ids']
                    Action.exec_report(res['report'], datas, dia or parent,
                            direct_print=direct_print, email_print=email_print,
                            email=email, context=ctx)
                    datas['ids'] = backup_ids
                else:
                    Action.exec_report(res['report'], datas, dia or parent,
                            direct_print=direct_print, email_print=email_print,
                            email=email, context=ctx)
                state = res['state']
            elif res['type'] == 'state':
                state = res['state']
        if dia:
            dia.destroy()
            dia = None
        try:
            rpc.execute('wizard', action, 'delete', wiz_id, rpc.CONTEXT)
            #XXX to remove when company displayed in status bar
            rpc.context_reload()
        except Exception:
            pass
