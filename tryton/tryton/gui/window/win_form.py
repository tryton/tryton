# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from tryton.common import TRYTON_ICON
import tryton.common as common
import gtk
import pango
import gettext

from .infobar import InfoBar
from tryton.common.domain_parser import quote
from tryton.common.underline import set_underline
from tryton.gui import Main
from tryton.gui.window.nomodal import NoModal

_ = gettext.gettext


class WinForm(NoModal, InfoBar):
    "Form window"

    def __init__(self, screen, callback, view_type='form',
            new=False, many=0, domain=None, context=None,
            save_current=False, title='', rec_name=None):
        tooltips = common.Tooltips()
        NoModal.__init__(self)
        self.screen = screen
        self.callback = callback
        self.many = many
        self.domain = domain
        self.context = context
        self.save_current = save_current
        self.title = title
        self.prev_view = self.screen.current_view
        self.screen.screen_container.alternate_view = True
        self.screen.switch_view(view_type=view_type)
        if self.screen.current_view.view_type != view_type:
            self.destroy()
            return
        if new:
            self.screen.new(rec_name=rec_name)
        self.win = gtk.Dialog(_('Link'), self.parent,
                gtk.DIALOG_DESTROY_WITH_PARENT)
        Main().add_window(self.win)
        self.win.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.win.set_icon(TRYTON_ICON)
        self.win.set_deletable(False)
        self.win.connect('delete-event', lambda *a: True)
        self.win.connect('close', self.close)
        self.win.connect('response', self.response)

        allocation = self.parent.get_allocation()
        width, height, = allocation.width, allocation.height
        if self.parent != self.sensible_widget:
            width = max(width - 150, 0)
            height = max(height - 150, 0)
        self.win.set_default_size(width, height)

        self.accel_group = gtk.AccelGroup()
        self.win.add_accel_group(self.accel_group)

        readonly = self.screen.readonly or self.screen.group.readonly

        self.but_ok = None
        self.but_new = None

        self._initial_value = None
        if view_type == 'form':
            if new:
                label, icon = _("Delete"), 'tryton-delete'
            else:
                label, icon = _("Cancel"), 'tryton-cancel'
                record = self.screen.current_record
                self._initial_value = record.get_on_change_value()
                if record.parent and record.parent_name in record.group.fields:
                    parent_field = record.group.fields[record.parent_name]
                    self._initial_value[record.parent_name] = (
                        parent_field.get_eval(record))
            self.but_cancel = self.win.add_button(
                set_underline(label), gtk.RESPONSE_CANCEL)
            self.but_cancel.set_image(common.IconFactory.get_image(
                    icon, gtk.ICON_SIZE_BUTTON))
            self.but_cancel.set_always_show_image(True)

        if new and self.many:
            self.but_new = self.win.add_button(
                set_underline(_("New")), gtk.RESPONSE_ACCEPT)
            self.but_new.set_image(common.IconFactory.get_image(
                    'tryton-create', gtk.ICON_SIZE_BUTTON))
            self.but_new.set_always_show_image(True)
            self.but_new.set_accel_path('<tryton>/Form/New', self.accel_group)

        if self.save_current:
            self.but_ok = gtk.Button(_('_Save'), use_underline=True)
            self.but_ok.set_image(common.IconFactory.get_image(
                    'tryton-save', gtk.ICON_SIZE_BUTTON))
            self.but_ok.set_always_show_image(True)
            self.but_ok.set_accel_path('<tryton>/Form/Save', self.accel_group)
            self.but_ok.set_can_default(True)
            self.but_ok.show()
            self.win.add_action_widget(self.but_ok, gtk.RESPONSE_OK)
            if not new:
                self.but_ok.props.sensitive = False
        else:
            self.but_ok = self.win.add_button(
                set_underline(_("OK")), gtk.RESPONSE_OK)
            self.but_ok.set_image(common.IconFactory.get_image(
                    'tryton-ok', gtk.ICON_SIZE_BUTTON))
            self.but_ok.set_always_show_image(True)
        self.but_ok.add_accelerator('clicked', self.accel_group,
            gtk.keysyms.Return, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        self.win.set_default_response(gtk.RESPONSE_OK)

        self.win.set_title(self.title)

        title = gtk.Label()
        title.modify_font(pango.FontDescription("bold 12"))
        title.set_label(common.ellipsize(self.title, 80))
        tooltips.set_tip(title, self.title)
        title.set_padding(20, 3)
        title.set_alignment(0.0, 0.5)
        title.set_size_request(0, -1)  # Allow overflow
        title.set_max_width_chars(1)
        title.set_ellipsize(pango.ELLIPSIZE_END)
        title.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#000000"))
        title.show()

        hbox = gtk.HBox()
        hbox.pack_start(title, expand=True, fill=True)
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
            access = common.MODELACCESS[screen.model_name]

            but_switch = gtk.Button()
            tooltips.set_tip(but_switch, _('Switch'))
            but_switch.connect('clicked', self.switch_view)
            but_switch.add(common.IconFactory.get_image(
                    'tryton-switch', gtk.ICON_SIZE_SMALL_TOOLBAR))
            but_switch.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(but_switch, expand=False, fill=False)

            self.but_pre = gtk.Button()
            tooltips.set_tip(self.but_pre, _('Previous'))
            self.but_pre.connect('clicked', self._sig_previous)
            self.but_pre.add(common.IconFactory.get_image(
                    'tryton-back', gtk.ICON_SIZE_SMALL_TOOLBAR))
            self.but_pre.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_pre, expand=False, fill=False)

            self.label = gtk.Label('(0,0)')
            hbox.pack_start(self.label, expand=False, fill=False)

            self.but_next = gtk.Button()
            tooltips.set_tip(self.but_next, _('Next'))
            self.but_next.connect('clicked', self._sig_next)
            self.but_next.add(common.IconFactory.get_image(
                    'tryton-forward', gtk.ICON_SIZE_SMALL_TOOLBAR))
            self.but_next.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_next, expand=False, fill=False)

            hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

            if domain is not None:
                self.wid_text = gtk.Entry()
                self.wid_text.set_property('width_chars', 13)
                self.wid_text.connect('activate', self._sig_activate)
                self.wid_text.connect('focus-out-event', self._focus_out)
                hbox.pack_start(self.wid_text, expand=True, fill=True)

                self.but_add = gtk.Button()
                tooltips.set_tip(self.but_add, _('Add'))
                self.but_add.connect('clicked', self._sig_add)
                self.but_add.add(common.IconFactory.get_image(
                        'tryton-add', gtk.ICON_SIZE_SMALL_TOOLBAR))
                self.but_add.set_relief(gtk.RELIEF_NONE)
                hbox.pack_start(self.but_add, expand=False, fill=False)
                if not access['read'] or readonly:
                    self.but_add.set_sensitive(False)

                self.but_remove = gtk.Button()
                tooltips.set_tip(self.but_remove, _('Remove <Del>'))
                self.but_remove.connect('clicked', self._sig_remove, True)
                self.but_remove.add(common.IconFactory.get_image(
                        'tryton-remove', gtk.ICON_SIZE_SMALL_TOOLBAR))
                self.but_remove.set_relief(gtk.RELIEF_NONE)
                hbox.pack_start(self.but_remove, expand=False, fill=False)
                if not access['read'] or readonly:
                    self.but_remove.set_sensitive(False)

                hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

            self.but_new = gtk.Button()
            tooltips.set_tip(self.but_new, _('Create a new record <F3>'))
            self.but_new.connect('clicked', self._sig_new)
            self.but_new.add(common.IconFactory.get_image(
                    'tryton-create', gtk.ICON_SIZE_SMALL_TOOLBAR))
            self.but_new.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_new, expand=False, fill=False)
            if not access['create'] or readonly:
                self.but_new.set_sensitive(False)

            self.but_del = gtk.Button()
            tooltips.set_tip(self.but_del, _('Delete selected record <Del>'))
            self.but_del.connect('clicked', self._sig_remove, False)
            self.but_del.add(common.IconFactory.get_image(
                    'tryton-delete', gtk.ICON_SIZE_SMALL_TOOLBAR))
            self.but_del.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_del, expand=False, fill=False)
            if not access['delete'] or readonly:
                self.but_del.set_sensitive(False)

            self.but_undel = gtk.Button()
            tooltips.set_tip(self.but_undel,
                _('Undelete selected record <Ins>'))
            self.but_undel.connect('clicked', self._sig_undelete)
            self.but_undel.add(common.IconFactory.get_image(
                    'tryton-undo', gtk.ICON_SIZE_SMALL_TOOLBAR))
            self.but_undel.set_relief(gtk.RELIEF_NONE)
            hbox.pack_start(self.but_undel, expand=False, fill=False)
            if not access['delete'] or readonly:
                self.but_undel.set_sensitive(False)

            but_switch.props.sensitive = screen.number_of_views > 1

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

        self.create_info_bar()
        self.win.vbox.pack_start(self.info_bar, False, True)

        if view_type == 'tree':
            self.screen.signal_connect(self, 'record-message', self._sig_label)
            self.screen.screen_container.alternate_viewport.connect(
                    'key-press-event', self.on_keypress)

        if self.save_current and not new:
            self.screen.signal_connect(self, 'record-message',
                self.activate_save)
            self.screen.signal_connect(self, 'record-modified',
                self.activate_save)

        self.register()
        self.show()

        self.screen.display()
        self.screen.current_view.set_cursor()

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
        self.screen.new()
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
        value = self.wid_text.get_text()

        def callback(result):
            if result:
                ids = [x[0] for x in result]
                self.screen.load(ids, modified=True)
                self.screen.display(res_id=ids[0])
            self.screen.set_cursor()
            self.wid_text.set_text('')

        win = WinSearch(model_name, callback, sel_multi=True,
            context=self.context, domain=domain)
        win.screen.search_filter(quote(value))
        win.show()

    def _sig_label(self, screen, signal_data):
        name = '_'
        access = common.MODELACCESS[screen.model_name]
        readonly = screen.group.readonly
        if signal_data[0] >= 1:
            name = str(signal_data[0])
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
            if access['delete'] and not readonly:
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

    def activate_save(self, *args):
        modified = self.screen.modified()
        # Keep sensible as change could have been trigger by a Many2One edition
        sensitive = modified or self.but_ok.props.sensitive
        self.but_ok.props.sensitive = sensitive
        self.win.set_default_response(
            gtk.RESPONSE_OK if sensitive else gtk.RESPONSE_CANCEL)

    def close(self, widget):
        widget.emit_stop_by_name('close')
        self.response(self.win, gtk.RESPONSE_CANCEL)
        return True

    def response(self, win, response_id):
        validate = False
        cancel_responses = (gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT)
        self.screen.current_view.set_value()
        readonly = self.screen.group.readonly
        if (response_id not in cancel_responses
                and not readonly
                and self.screen.current_record is not None):
            validate = self.screen.current_record.validate(
                self.screen.current_view.get_fields())
            if validate and self.screen.pre_validate:
                validate = self.screen.current_record.pre_validate()
            if validate and self.save_current:
                if not self.screen.save_current():
                    validate = False
            elif validate and self.screen.current_view.view_type == 'form':
                view = self.screen.current_view
                for widgets in view.widgets.values():
                    for widget in widgets:
                        if (hasattr(widget, 'screen')
                                and widget.screen.pre_validate):
                            record = widget.screen.current_record
                            if record:
                                validate = record.pre_validate()
            if not validate:
                self.message_info(self.screen.invalid_message(),
                    gtk.MESSAGE_ERROR)
                self.screen.set_cursor()
                self.screen.display()
                return
            self.message_info()
            if response_id == gtk.RESPONSE_ACCEPT:
                self.new()
                return
        if (self.screen.current_record
                and not readonly
                and response_id in cancel_responses):
            record = self.screen.current_record
            added = 'id' in record.modified_fields
            if (self.screen.current_record.id < 0
                    or self.save_current):
                self.screen.cancel_current(self._initial_value)
            elif record.modified:
                record.cancel()
                record.reload()
                record.signal('record-changed')
            if added:
                record.modified_fields.setdefault('id')
            result = False
        else:
            result = response_id not in cancel_responses
        self.callback(result)
        self.destroy()

    def new(self):
        self.screen.new()
        self._initial_value = None
        self.screen.current_view.display()
        self.screen.set_cursor(new=True)
        self.many -= 1
        if self.many == 0:
            self.but_new.set_sensitive(False)
            self.win.set_default_response(gtk.RESPONSE_OK)

    def destroy(self):
        self.screen.screen_container.alternate_view = False
        viewport = self.screen.screen_container.alternate_viewport
        if viewport and viewport.get_parent():
            viewport.get_parent().remove(viewport)
        self.screen.switch_view(view_type=self.prev_view.view_type)
        self.screen.signal_unconnect(self)
        if getattr(self, 'win', None):
            self.win.destroy()
        NoModal.destroy(self)

    def show(self):
        self.win.show()

    def hide(self):
        self.win.hide()
