#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from tryton.common import TRYTON_ICON, COLOR_SCHEMES
import tryton.common as common
from tryton.config import CONFIG
import gtk
import pango
import gettext
from tryton.gui.window.nomodal import NoModal
from tryton.common import RPCExecute, RPCException

_ = gettext.gettext


class WinForm(NoModal):
    "Form window"

    def __init__(self, screen, callback, view_type='form',
            new=False, many=False, domain=None, context=None,
            save_current=False):
        NoModal.__init__(self)
        self.screen = screen
        self.callback = callback
        self.domain = domain
        self.context = context
        self.save_current = save_current
        self.prev_view = self.screen.current_view
        self.screen.screen_container.alternate_view = True
        switch_new = False
        if view_type == 'form' and not self.screen.current_record:
            switch_new = True
        if view_type not in (x.view_type for x in self.screen.views) and \
                view_type not in self.screen.view_to_load:
            self.screen.add_view_id(False, view_type, display=True)
        else:
            self.screen.switch_view(view_type=view_type, context=context)
        if new and not switch_new:
            self.screen.new(context=self.context)
        self.win = gtk.Dialog(_('Link'), self.parent,
                gtk.DIALOG_DESTROY_WITH_PARENT)
        self.win.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.win.set_icon(TRYTON_ICON)
        self.win.set_has_separator(False)
        self.win.connect('response', self.response)

        self.accel_group = gtk.AccelGroup()
        self.win.add_accel_group(self.accel_group)

        self.but_cancel = None
        self.but_ok = None
        self.but_new = None
        if new:
            icon_cancel = gtk.STOCK_CANCEL
            self.but_cancel = self.win.add_button(icon_cancel,
                    gtk.RESPONSE_CANCEL)

        self.but_ok = self.win.add_button(gtk.STOCK_OK,
            gtk.RESPONSE_OK)
        if new and many:
            self.but_ok.add_accelerator('clicked',
                self.accel_group, gtk.keysyms.Return,
                gtk.gdk.CONTROL_MASK | gtk.gdk.SHIFT_MASK,
                gtk.ACCEL_VISIBLE)

            self.but_new = self.win.add_button(gtk.STOCK_NEW,
                gtk.RESPONSE_ACCEPT)
            self.but_new.add_accelerator('clicked', self.accel_group,
                gtk.keysyms.Return, gtk.gdk.CONTROL_MASK,
                gtk.ACCEL_VISIBLE)
            self.win.set_default_response(gtk.RESPONSE_ACCEPT)
        else:
            self.but_ok.add_accelerator('clicked', self.accel_group,
                gtk.keysyms.Return, gtk.gdk.CONTROL_MASK,
                gtk.ACCEL_VISIBLE)
            self.win.set_default_response(gtk.RESPONSE_OK)

        self.win.set_title(self.screen.current_view.title)

        title = gtk.Label()
        title.set_use_markup(True)
        title.modify_font(pango.FontDescription("12"))
        title.set_label('<b>' + self.screen.current_view.title + '</b>')
        title.set_padding(20, 3)
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

        self.win.vbox.pack_start(eb, expand=False, fill=True, padding=3)

        if view_type == 'tree':
            hbox = gtk.HBox(homogeneous=False, spacing=0)
            tooltips = common.Tooltips()

            if domain is not None:
                self.wid_text = gtk.Entry()
                self.wid_text.set_property('width_chars', 13)
                self.wid_text.connect('activate', self._sig_activate)
                self.wid_text.connect('focus-out-event', self._focus_out)
                hbox.pack_start(self.wid_text, expand=True, fill=True)

                self.but_add = gtk.Button()
                tooltips.set_tip(self.but_add, _('Add'))
                self.but_add.connect('clicked', self._sig_add)
                img_add = gtk.Image()
                img_add.set_from_stock('tryton-list-add',
                    gtk.ICON_SIZE_SMALL_TOOLBAR)
                img_add.set_alignment(0.5, 0.5)
                self.but_add.add(img_add)
                self.but_add.set_relief(gtk.RELIEF_NONE)
                hbox.pack_start(self.but_add, expand=False, fill=False)

                self.but_remove = gtk.Button()
                tooltips.set_tip(self.but_remove, _('Remove <Del>'))
                self.but_remove.connect('clicked', self._sig_remove, True)
                img_remove = gtk.Image()
                img_remove.set_from_stock('tryton-list-remove',
                    gtk.ICON_SIZE_SMALL_TOOLBAR)
                img_remove.set_alignment(0.5, 0.5)
                self.but_remove.add(img_remove)
                self.but_remove.set_relief(gtk.RELIEF_NONE)
                hbox.pack_start(self.but_remove, expand=False, fill=False)

                hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

            self.but_new = gtk.Button()
            tooltips.set_tip(self.but_new, _('Create a new record <F3>'))
            self.but_new.connect('clicked', self._sig_new)
            img_new = gtk.Image()
            img_new.set_from_stock('tryton-new', gtk.ICON_SIZE_SMALL_TOOLBAR)
            img_new.set_alignment(0.5, 0.5)
            self.but_new.add(img_new)
            self.but_new.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_new, expand=False, fill=False)

            self.but_del = gtk.Button()
            tooltips.set_tip(self.but_del, _('Delete selected record <Del>'))
            self.but_del.connect('clicked', self._sig_remove, False)
            img_del = gtk.Image()
            img_del.set_from_stock('tryton-delete',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            img_del.set_alignment(0.5, 0.5)
            self.but_del.add(img_del)
            self.but_del.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_del, expand=False, fill=False)

            self.but_undel = gtk.Button()
            tooltips.set_tip(self.but_undel,
                _('Undelete selected record <Ins>'))
            self.but_undel.connect('clicked', self._sig_undelete)
            img_undel = gtk.Image()
            img_undel.set_from_stock('tryton-undo',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            img_undel.set_alignment(0.5, 0.5)
            self.but_undel.add(img_undel)
            self.but_undel.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_undel, expand=False, fill=False)

            hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

            self.but_pre = gtk.Button()
            tooltips.set_tip(self.but_pre, _('Previous'))
            self.but_pre.connect('clicked', self._sig_previous)
            img_pre = gtk.Image()
            img_pre.set_from_stock('tryton-go-previous',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            img_pre.set_alignment(0.5, 0.5)
            self.but_pre.add(img_pre)
            self.but_pre.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_pre, expand=False, fill=False)

            self.label = gtk.Label('(0,0)')
            hbox.pack_start(self.label, expand=False, fill=False)

            self.but_next = gtk.Button()
            tooltips.set_tip(self.but_next, _('Next'))
            self.but_next.connect('clicked', self._sig_next)
            img_next = gtk.Image()
            img_next.set_from_stock('tryton-go-next',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            img_next.set_alignment(0.5, 0.5)
            self.but_next.add(img_next)
            self.but_next.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_next, expand=False, fill=False)

            hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

            but_switch = gtk.Button()
            tooltips.set_tip(but_switch, _('Switch'))
            but_switch.connect('clicked', self.switch_view)
            img_switch = gtk.Image()
            img_switch.set_from_stock('tryton-fullscreen',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            img_switch.set_alignment(0.5, 0.5)
            but_switch.add(img_switch)
            but_switch.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(but_switch, expand=False, fill=False)

            tooltips.enable()

            alignment = gtk.Alignment(1.0)
            alignment.add(hbox)
            alignment.show_all()

            self.win.vbox.pack_start(alignment, expand=False, fill=True)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_placement(gtk.CORNER_TOP_LEFT)
        scroll.set_shadow_type(gtk.SHADOW_NONE)
        scroll.show()
        self.win.vbox.pack_start(scroll, expand=True, fill=True)

        scroll.add(self.screen.screen_container.alternate_viewport)

        sensible_allocation = self.sensible_widget.get_allocation()
        self.win.set_default_size(int(sensible_allocation.width * 0.9),
            int(sensible_allocation.height * 0.9))

        if view_type == 'tree':
            self.screen.signal_connect(self, 'record-message', self._sig_label)
            self.screen.screen_container.alternate_viewport.connect(
                    'key-press-event', self.on_keypress)

        self.register()
        self.win.show()

        common.center_window(self.win, self.parent, self.sensible_widget)

        self.screen.display()
        self.screen.current_view.set_cursor()

    def message_info(self, message, color='red'):
        if message:
            self.info_label.set_label(message)
            self.eb_info.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse(
                COLOR_SCHEMES.get(color, 'white')))
            self.eb_info.show_all()
        else:
            self.info_label.set_label('')
            self.eb_info.hide()

    def on_keypress(self, widget, event):
        if (event.keyval == gtk.keysyms.F3) \
                and self.but_new.get_property('sensitive'):
            self._sig_new(widget)
            return False
        if event.keyval in (gtk.keysyms.Delete, gtk.keysyms.KP_Delete) \
                and widget == self.screen.screen_container.alternate_viewport:
            self._sig_remove(widget)
            return False

    def switch_view(self, widget):
        self.screen.switch_view()

    def _sig_new(self, widget):
        self.screen.new(context=self.context)
        self.screen.current_view.widget.set_sensitive(True)

    def _sig_next(self, widget):
        self.screen.display_next()

    def _sig_previous(self, widget):
        self.screen.display_prev()

    def _sig_remove(self, widget, remove=False):
        self.screen.remove(remove=remove)

    def _sig_undelete(self, button):
        self.screen.unremove()

    def _sig_activate(self, *args):
        self._sig_add()
        self.wid_text.grab_focus()

    def _focus_out(self, *args):
        if self.wid_text.get_text():
            self._sig_add()

    def _sig_add(self, *args):
        from tryton.gui.window.win_search import WinSearch
        domain = self.domain[:]
        model_name = self.screen.model_name

        try:
            if self.wid_text.get_text():
                dom = [('rec_name', 'ilike',
                        '%' + self.wid_text.get_text() + '%'), domain]
            else:
                dom = domain
            ids = RPCExecute('model', model_name, 'search', dom,
                    0, CONFIG['client.limit'], None, context=self.context)
        except RPCException:
            return False

        def callback(result):
            if result:
                ids = [x[0] for x in result]
                self.screen.load(ids, modified=True)
                self.screen.display(res_id=ids[0])
            self.screen.set_cursor()
            self.wid_text.set_text('')
        if len(ids) != 1:
            WinSearch(model_name, callback, sel_multi=True,
                ids=ids, context=self.context, domain=domain)
        else:
            callback([(i, None) for i in ids])

    def _sig_label(self, screen, signal_data):
        name = '_'
        if signal_data[0] >= 1:
            name = str(signal_data[0])
            self.but_del.set_sensitive(True)
            if self.domain is not None:
                self.but_remove.set_sensitive(True)
            if signal_data[0] < signal_data[1]:
                self.but_next.set_sensitive(True)
            else:
                self.but_next.set_sensitive(False)
            if signal_data[0] > 1:
                self.but_pre.set_sensitive(True)
            else:
                self.but_pre.set_sensitive(False)
            self.but_del.set_sensitive(True)
            self.but_undel.set_sensitive(True)
        else:
            self.but_del.set_sensitive(False)
            self.but_undel.set_sensitive(False)
            self.but_next.set_sensitive(False)
            self.but_pre.set_sensitive(False)
            if self.domain is not None:
                self.but_remove.set_sensitive(False)
        line = '(%s/%s)' % (name, signal_data[1])
        self.label.set_text(line)

    def response(self, win, response_id):
        validate = False
        cancel_responses = (gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT)
        self.screen.current_view.set_value()
        if (response_id not in cancel_responses
                and self.screen.current_record is not None):
            validate = self.screen.current_record.validate(
                self.screen.current_view.get_fields())
            if validate and self.save_current:
                if not self.screen.save_current():
                    validate = False
            if not validate:
                self.screen.set_cursor()
                self.screen.display()
                return
            if response_id == gtk.RESPONSE_ACCEPT:
                self.new()
                return
        if (self.but_cancel
                and self.screen.current_record
                and response_id in cancel_responses):
            self.screen.group.remove(self.screen.current_record, remove=True)
            result = False
        else:
            result = response_id not in cancel_responses
        self.callback(result)
        self.destroy()

    def new(self):
        self.screen.new(context=self.context)
        self.screen.current_view.display()
        self.screen.set_cursor(new=True)

    def destroy(self):
        self.screen.screen_container.alternate_view = False
        viewport = self.screen.screen_container.alternate_viewport
        if viewport.get_child():
            viewport.remove(viewport.get_child())
        self.screen.switch_view(view_type=self.prev_view.view_type)
        self.screen.signal_unconnect(self)
        self.win.destroy()
        NoModal.destroy(self)

    def show(self):
        self.win.show()
        common.center_window(self.win, self.parent, self.sensible_widget)

    def hide(self):
        self.win.hide()
