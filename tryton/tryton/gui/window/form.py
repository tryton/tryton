#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Form"
import gettext
import gtk
import gobject
import locale
import tryton.rpc as rpc
from tryton.gui.window.view_form.screen import Screen
from tryton.action import Action
from tryton.config import CONFIG
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.preference import Preference
from tryton.gui.window.win_export import WinExport
from tryton.gui.window.win_import import WinImport
from tryton.gui.window.attachment import Attachment
from tryton.signal_event import SignalEvent
from tryton.common import TRYTON_ICON, message, sur, sur_3b, COLOR_SCHEMES
import tryton.common as common
import pango
from tryton.translate import date_format
from tryton.common import DT_FORMAT, DHM_FORMAT, HM_FORMAT

_ = gettext.gettext


class Form(SignalEvent):
    "Form"

    def __init__(self, model, window, res_id=False, domain=None, mode=None,
            view_ids=None, context=None, name=False, limit=None,
            auto_refresh=False, search_value=None):
        super(Form, self).__init__()

        if not mode:
            mode = ['tree', 'form']
        if domain is None:
            domain = []
        if view_ids is None:
            view_ids = []
        if context is None:
            context = {}

        self.model = model
        self.window = window
        self.domain = domain
        self.context = context

        self.widget = gtk.VBox(spacing=3)
        self.widget.show()

        self.screen = Screen(self.model, self.window, mode=mode,
                context=self.context, view_ids=view_ids, domain=domain,
                limit=limit, readonly=bool(auto_refresh),
                search_value=search_value)
        self.screen.signal_connect(self, 'record-message', self._record_message)
        self.screen.signal_connect(self, 'record-modified', self._record_modified)
        self.screen.signal_connect(self, 'attachment-count',
                self._attachment_count)
        self.screen.widget.show()

        if not name:
            self.name = self.screen.current_view.title
        else:
            self.name = name

        title = gtk.Label()
        title.set_use_markup(True)
        title.modify_font(pango.FontDescription("14"))
        title.set_label('<b>' + self.name + '</b>')
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

        self.status_label = gtk.Label()
        self.status_label.set_padding(5, 4)
        self.status_label.set_alignment(0.0, 0.5)
        self.status_label.show()

        hbox = gtk.HBox()
        hbox.pack_start(title, expand=True, fill=True)
        hbox.pack_start(vbox, expand=False, fill=True, padding=20)
        hbox.pack_start(self.status_label, expand=False, fill=True)
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

        self.toolbar_box = gtk.HBox()
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

        self.handlers = {
            'but_new': self.sig_new,
            'but_copy': self.sig_copy,
            'but_save': self.sig_save,
            'but_save_as': self.sig_save_as,
            'but_import': self.sig_import,
            'but_remove': self.sig_remove,
            'but_search': self.sig_search,
            'but_previous': self.sig_previous,
            'but_next': self.sig_next,
            'but_goto_id': self.sig_goto,
            'but_log': self.sig_logs,
            'but_print': self.sig_print,
            'but_reload': self.sig_reload,
            'but_action': self.sig_action,
            'but_switch': self.sig_switch,
            'but_attach': self.sig_attach,
            'but_close': self.sig_close,
        }
        if res_id not in (None, False):
            if isinstance(res_id, (int, long)):
                res_id = [res_id]
            self.screen.load(res_id)
        else:
            if self.screen.current_view.view_type == 'form':
                self.sig_new(None, autosave=False)
            if self.screen.current_view.view_type \
                    in ('tree', 'graph', 'calendar'):
                self.screen.search_filter()

        if auto_refresh and int(auto_refresh):
            gobject.timeout_add(int(auto_refresh) * 1000, self.sig_reload)

    def sig_goto(self, widget=None):
        if not self.modified_save():
            return
        win = gtk.Dialog(_('Go to ID'), self.window,
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OK, gtk.RESPONSE_OK))
        win.set_icon(TRYTON_ICON)
        win.set_has_separator(True)
        win.set_default_response(gtk.RESPONSE_OK)

        table = gtk.Table(2, 2)
        table.attach(gtk.Label(_('Go to ID:')), 1, 2, 0, 1, gtk.FILL)
        img = gtk.Image()
        img.set_from_stock('tryton-go-jump', gtk.ICON_SIZE_DIALOG)
        table.attach(img, 0, 1, 0, 2, gtk.FILL)

        entry = gtk.Entry()
        entry.set_property('activates_default', True)
        entry.set_max_length(0)
        entry.set_alignment(1.0)
        def sig_insert_text(widget, new_text, new_text_length, position):
            value = widget.get_text()
            position = widget.get_position()
            new_value = value[:position] + new_text + value[position:]
            try:
                locale.atoi(new_value)
            except Exception:
                widget.stop_emission('insert-text')
        entry.connect('insert_text', sig_insert_text)
        table.attach(entry, 1, 2, 1, 2)

        win.vbox.pack_start(table, expand=True, fill=True)
        win.show_all()

        response = win.run()
        if response == gtk.RESPONSE_OK:
            self.screen.display(locale.atoi(entry.get_text()), set_cursor=True)
        win.destroy()
        self.window.present()

    def destroy(self):
        if self.toolbar_box.get_children():
            toolbar = self.toolbar_box.get_children()[0]
            self.toolbar_box.remove(toolbar)
        self.screen.signal_unconnect(self)
        self.screen.destroy()
        self.screen = None
        self.widget = None
        #self.scrolledwindow.destroy()
        #self.scrolledwindow = None

    def sel_ids_get(self):
        return self.screen.sel_ids_get()

    def ids_get(self):
        return self.screen.ids_get()

    def id_get(self):
        return self.screen.id_get()

    def sig_attach(self, widget=None):
        obj_id = self.id_get()
        if obj_id >= 0 and obj_id is not False:
            win = Attachment(self.model, obj_id, self.window)
            win.run()
        else:
            self.message_info(_('No record selected!'))
        self.update_attachment_count(reload=True)
        return True

    def update_attachment_count(self, reload=False):
        record = self.screen.current_record
        if record:
            attachment_count = record.get_attachment_count(reload=reload)
        else:
            attachment_count = 0
        self.signal('attachment-count', attachment_count)

    def sig_switch(self, widget=None):
        if not self.modified_save():
            return
        self.screen.switch_view()

    def sig_logs(self, widget=None):
        obj_id = self.id_get()
        if obj_id < 0 or obj_id is False:
            self.message_info(_('You have to select one record!'))
            return False

        fields = [
            ('id', _('ID:')),
            ('create_uid.rec_name', _('Creation User:')),
            ('create_date', _('Creation Date:')),
            ('write_uid.rec_name', _('Latest Modification by:')),
            ('write_date', _('Latest Modification Date:')),
        ]

        ctx = self.context.copy()
        ctx.update(rpc.CONTEXT)
        args = ('model', self.model, 'read', [obj_id], [x[0] for x in fields],
                ctx)
        try:
            res = rpc.execute(*args)
        except Exception, exception:
            res = common.process_exception(exception, self.window, *args)
            if not res:
                return
        message_str = ''
        for line in res:
            for (key, val) in fields:
                value = str(line.get(key, False) or '/')
                if line.get(key, False) \
                        and key in ('create_date', 'write_date'):
                    display_format = date_format() + ' ' + HM_FORMAT
                    date = line[key]
                    if 'timezone' in rpc.CONTEXT:
                        try:
                            import pytz
                            lzone = pytz.timezone(rpc.CONTEXT['timezone'])
                            szone = pytz.timezone(rpc.TIMEZONE)
                            sdt = szone.localize(datetime, is_dst=True)
                            ldt = sdt.astimezone(lzone)
                            date = ldt
                        except Exception:
                            pass
                    value = common.datetime_strftime(date, display_format)
                message_str += val + ' ' + value +'\n'
        message_str += _('Model:') + ' ' + self.model
        message(message_str, self.window)
        return True

    def sig_remove(self, widget=None):
        if self.screen.current_view.view_type == 'form':
            msg = _('Are you sure to remove this record?')
        else:
            msg = _('Are you sure to remove those records?')
        if sur(msg, self.window):
            if not self.screen.remove(delete=True, force_remove=True):
                self.message_info(_('Records not removed!'))
            else:
                self.message_info(_('Records removed!'), 'green')

    def sig_import(self, widget=None):
        while(self.screen.view_to_load):
            self.screen.load_view_to_load()
        fields = {}
        for name, field in self.screen.group.fields.iteritems():
            fields[name] = field.attrs
        win = WinImport(self.model, self.window)
        win.run()

    def sig_save_as(self, widget=None):
        while self.screen.view_to_load:
            self.screen.load_view_to_load()
        fields = {}
        for name, field in self.screen.group.fields.iteritems():
            fields[name] = field.attrs
        win = WinExport(self.model, self.ids_get(), self.window,
                context=self.context)
        win.run()

    def sig_new(self, widget=None, autosave=True):
        if autosave:
            if not self.modified_save():
                return
        self.screen.new()
        self.message_info('')

    def sig_copy(self, widget=None):
        if not self.modified_save():
            return
        res_ids = self.sel_ids_get()
        ctx = self.context.copy()
        ctx.update(rpc.CONTEXT)
        args = ('model', self.model, 'copy', res_ids, {}, ctx)
        try:
            new_ids = rpc.execute(*args)
        except Exception, exception:
            new_ids = common.process_exception(exception, self.window, *args)
        if new_ids:
            self.screen.load(new_ids)
            self.message_info(_('Working now on the duplicated record(s)!'),
                    'green')

    def sig_save(self, widget=None):
        if self.screen.save_current():
            self.message_info(_('Record saved!'), 'green')
            return True
        else:
            self.message_info(_('Invalid form!'))
            return False

    def sig_previous(self, widget=None):
        if not self.modified_save():
            return
        self.screen.display_prev()
        self.message_info('')

    def sig_next(self, widget=None):
        if not self.modified_save():
            return
        self.screen.display_next()
        self.message_info('')

    def sig_reload(self, test_modified=True):
        if not hasattr(self, 'screen'):
            return False
        if test_modified and self.screen.modified():
            res = sur_3b(_('This record has been modified\n' \
                    'do you want to save it ?'), self.window)
            if res == 'ok':
                self.sig_save(None)
            elif res == 'ko':
                pass
            else:
                return False
        if self.screen.current_view.view_type == 'form':
            self.screen.cancel_current()
            self.screen.display()
        else:
            obj_id = self.id_get()
            self.screen.search_filter()
            for record in self.screen.group:
                if record.id == obj_id:
                    self.screen.current_record = record
                    self.screen.display(set_cursor=True)
                    break
        self.message_info('')
        return True

    def sig_action(self, keyword='form_action'):
        ids = self.ids_get()
        if self.screen.current_record:
            obj_id = self.screen.current_record.id
        else:
            obj_id = False
        if self.screen.current_view.view_type == 'form':
            obj_id = self.screen.save_current()
            if not obj_id:
                return False
            ids = [obj_id]
        if self.screen.current_view.view_type == 'tree':
            sel_ids = self.screen.current_view.sel_ids_get()
            if sel_ids:
                ids = sel_ids
        if len(ids):
            ctx = self.context.copy()
            if 'active_ids' in ctx:
                del ctx['active_ids']
            if 'active_id' in ctx:
                del ctx['active_id']
            res = Action.exec_keyword(keyword, self.window, {
                'model': self.screen.model_name,
                'id': obj_id or False,
                'ids': ids,
                }, context=ctx, alwaysask=True)
            if res:
                self.sig_reload(test_modified=False)
        else:
            self.message_info(_('No record selected!'))

    def sig_print(self):
        self.sig_action('form_print')

    def sig_search(self, widget=None):
        if not self.modified_save():
            return
        win = WinSearch(self.model, domain=self.domain,
                context=self.context, parent=self.window)
        res = win.run()
        if res:
            self.screen.clear()
            self.screen.load(res)

    def message_info(self, message, color='red'):
        if message:
            self.info_label.set_label(message)
            self.eb_info.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(
                COLOR_SCHEMES.get(color, 'white')))
            self.eb_info.show_all()
        else:
            self.info_label.set_label('')
            self.eb_info.hide()

    def _record_message(self, screen, signal_data):
        name = '_'
        if signal_data[0] >= 0:
            name = str(signal_data[0])
        msg = name + ' / ' + str(signal_data[1])
        if signal_data[1] < signal_data[2]:
            msg += _(' of ') + str(signal_data[2])
        self.status_label.set_text(msg)
        self.message_info('')

    def _record_modified(self, screen, signal_data):
        self.message_info('', color='white')

    def _attachment_count(self, screen, signal_data):
        self.signal('attachment-count', signal_data)

    def modified_save(self, reload=True):
        if self.screen.modified():
            value = sur_3b(
                    _('This record has been modified\n' \
                            'do you want to save it ?'),
                    self.window)
            if value == 'ok':
                return self.sig_save(None)
            elif value == 'ko':
                if reload:
                    self.sig_reload(test_modified=False)
                return True
            else:
                return False
        return True

    def sig_close(self):
        return self.modified_save(reload=False)
