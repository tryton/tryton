#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
from tryton.common import TRYTON_ICON, COLOR_SCHEMES
from interface import WidgetInterface
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.view_form.model.group import ModelRecordGroup
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.view_form.widget_search.form import _LIMIT
import tryton.common as common
import tryton.rpc as rpc
import pango

_ = gettext.gettext

def _create_menu(self, attrs):
    hbox = gtk.HBox(homogeneous=False, spacing=0)
    menubar = gtk.MenuBar()
    if hasattr(menubar, 'set_pack_direction') and \
            hasattr(menubar, 'set_child_pack_direction'):
        menubar.set_pack_direction(gtk.PACK_DIRECTION_LTR)
        menubar.set_child_pack_direction(gtk.PACK_DIRECTION_LTR)

    menuitem_title = gtk.ImageMenuItem(stock_id='tryton-preferences')

    menu_title = gtk.Menu()
    menuitem_set_to_default = gtk.MenuItem(_('Set to default value'), True)
    menuitem_set_to_default.connect('activate',
            lambda *x: self._menu_sig_default_get())
    menu_title.add(menuitem_set_to_default)
    menuitem_set_default = gtk.MenuItem(_('Set as default'), True)
    menuitem_set_default.connect('activate',
            lambda *x: self._menu_sig_default_set())
    menu_title.add(menuitem_set_default)
    menuitem_reset_default = gtk.MenuItem(_('Reset default'), True)
    menuitem_reset_default.connect('activate',
            lambda *x: self._menu_sig_default_set(reset=True))
    menu_title.add(menuitem_reset_default)
    menuitem_title.set_submenu(menu_title)

    menubar.add(menuitem_title)
    hbox.pack_start(menubar, expand=True, fill=True)

    tooltips = common.Tooltips()

    if attrs.get('add_remove'):

        self.wid_text = gtk.Entry()
        self.wid_text.set_property('width_chars', 13)
        self.wid_text.connect('activate', self._sig_activate)
        hbox.pack_start(self.wid_text, expand=True, fill=True)

        self.but_add = gtk.Button()
        tooltips.set_tip(self.but_add, _('Add'))
        self.but_add.connect('clicked', self._sig_add)
        img_add = gtk.Image()
        img_add.set_from_stock('tryton-list-add', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_add.set_alignment(0.5, 0.5)
        self.but_add.add(img_add)
        self.but_add.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(self.but_add, expand=False, fill=False)

        self.but_remove = gtk.Button()
        tooltips.set_tip(self.but_remove, _('Remove'))
        self.but_remove.connect('clicked', self._sig_remove, True)
        img_remove = gtk.Image()
        img_remove.set_from_stock('tryton-list-remove', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_remove.set_alignment(0.5, 0.5)
        self.but_remove.add(img_remove)
        self.but_remove.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(self.but_remove, expand=False, fill=False)

        hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

    self.but_new = gtk.Button()
    tooltips.set_tip(self.but_new, _('Create a new record'))
    self.but_new.connect('clicked', self._sig_new)
    img_new = gtk.Image()
    img_new.set_from_stock('tryton-new', gtk.ICON_SIZE_SMALL_TOOLBAR)
    img_new.set_alignment(0.5, 0.5)
    self.but_new.add(img_new)
    self.but_new.set_relief(gtk.RELIEF_NONE)
    hbox.pack_start(self.but_new, expand=False, fill=False)

    self.but_open = gtk.Button()
    tooltips.set_tip(self.but_open, _('Edit selected record'))
    self.but_open.connect('clicked', self._sig_edit)
    img_open = gtk.Image()
    img_open.set_from_stock('tryton-open', gtk.ICON_SIZE_SMALL_TOOLBAR)
    img_open.set_alignment(0.5, 0.5)
    self.but_open.add(img_open)
    self.but_open.set_relief(gtk.RELIEF_NONE)
    hbox.pack_start(self.but_open, expand=False, fill=False)

    self.but_del = gtk.Button()
    tooltips.set_tip(self.but_del, _('Delete selected record'))
    self.but_del.connect('clicked', self._sig_remove)
    img_del = gtk.Image()
    img_del.set_from_stock('tryton-delete', gtk.ICON_SIZE_SMALL_TOOLBAR)
    img_del.set_alignment(0.5, 0.5)
    self.but_del.add(img_del)
    self.but_del.set_relief(gtk.RELIEF_NONE)
    hbox.pack_start(self.but_del, expand=False, fill=False)

    hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

    but_pre = gtk.Button()
    tooltips.set_tip(but_pre, _('Previous'))
    but_pre.connect('clicked', self._sig_previous)
    img_pre = gtk.Image()
    img_pre.set_from_stock('tryton-go-previous', gtk.ICON_SIZE_SMALL_TOOLBAR)
    img_pre.set_alignment(0.5, 0.5)
    but_pre.add(img_pre)
    but_pre.set_relief(gtk.RELIEF_NONE)
    hbox.pack_start(but_pre, expand=False, fill=False)

    self.label = gtk.Label('(0,0)')
    hbox.pack_start(self.label, expand=False, fill=False)

    but_next = gtk.Button()
    tooltips.set_tip(but_next, _('Next'))
    but_next.connect('clicked', self._sig_next)
    img_next = gtk.Image()
    img_next.set_from_stock('tryton-go-next', gtk.ICON_SIZE_SMALL_TOOLBAR)
    img_next.set_alignment(0.5, 0.5)
    but_next.add(img_next)
    but_next.set_relief(gtk.RELIEF_NONE)
    hbox.pack_start(but_next, expand=False, fill=False)

    hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

    but_switch = gtk.Button()
    tooltips.set_tip(but_switch, _('Switch'))
    but_switch.connect('clicked', self.switch_view)
    img_switch = gtk.Image()
    img_switch.set_from_stock('tryton-fullscreen', gtk.ICON_SIZE_SMALL_TOOLBAR)
    img_switch.set_alignment(0.5, 0.5)
    but_switch.add(img_switch)
    but_switch.set_relief(gtk.RELIEF_NONE)
    hbox.pack_start(but_switch, expand=False, fill=False)

    if attrs.get('add_remove'):
        hbox.set_focus_chain([self.wid_text])
    else:
        hbox.set_focus_chain([])

    tooltips.enable()

    return hbox, menuitem_title


class Dialog(object):

    def __init__(self, model_name, parent, model=None, attrs=None,
            model_ctx=None, window=None, default_get_ctx=None, readonly=False,
            domain=None):

        if attrs is None:
            attrs = {}
        if model_ctx is None:
            model_ctx = {}
        if default_get_ctx is None:
            default_get_ctx = {}

        self.attrs = attrs
        self.model_name = model_name
        self.parent=parent
        self.model_ctx = model_ctx
        self.default_get_ctx = default_get_ctx

        self.dia = gtk.Dialog(_('Link'), window,
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT)
        self.dia.connect('close', self._sig_close)
        self.window = window
        self.dia.set_property('default-width', 760)
        self.dia.set_property('default-height', 500)
        self.dia.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.dia.set_icon(TRYTON_ICON)
        self.dia.set_has_separator(False)

        self.accel_group = gtk.AccelGroup()
        self.dia.add_accel_group(self.accel_group)

        self.but_cancel = None
        if not model:
            icon_cancel = gtk.STOCK_CANCEL
            self.but_cancel = self.dia.add_button(icon_cancel,
                    gtk.RESPONSE_CANCEL)

        self.but_ok = self.dia.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.but_ok.add_accelerator('clicked', self.accel_group,
                gtk.keysyms.Return, gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

        self.dia.set_default_response(gtk.RESPONSE_OK)

        self.default_get_ctx = default_get_ctx

        menuitem_title = None
        if isinstance(model, ModelRecordGroup):
            hbox, menuitem_title = _create_menu(self, attrs)
            self.dia.vbox.pack_start(hbox, expand=False, fill=True)
        self.dia.show()

        self.screen = Screen(model_name, self.dia, view_type=[], parent=parent,
                parent_name=attrs.get('relation_field', ''),
                exclude_field=attrs.get('relation_field', None), readonly=readonly,
                domain=domain)
        self.screen.models._context.update(model_ctx)
        modified = False
        if not model:
            model = self.screen.new(context=default_get_ctx)
            modified = True
        if isinstance(model, ModelRecordGroup):
            self.screen.tree_saves = False
            self.screen.add_view_id(False, 'tree', display=True,
                    context=default_get_ctx)
            self.screen.add_view_id(False, 'form', display=False,
                    context=default_get_ctx)
            self.screen.signal_connect(self, 'record-message', self._sig_label)
            self.screen.widget.connect('key_press_event', self.on_keypress)
            self.screen.models_set(model)
        else:
            self.screen.models.model_add(model, modified=modified)
            self.screen.current_model = model
            if ('views' in attrs) and ('form' in attrs['views']):
                arch = attrs['views']['form']['arch']
                fields = attrs['views']['form']['fields']
                if attrs.get('relation_field', False) \
                        and attrs['relation_field'] in fields:
                    del fields[attrs['relation_field']]
                self.screen.add_view(arch, fields, display=True,
                        context=default_get_ctx)
            else:
                self.screen.add_view_id(False, 'form', display=True,
                        context=default_get_ctx)

        name = self.screen.current_view.title
        self.dia.set_title(name)
        if menuitem_title:
            menuitem_title.get_child().set_text(name)

        title = gtk.Label()
        title.set_use_markup(True)
        title.modify_font(pango.FontDescription("12"))
        title.set_label('<b>' + name + '</b>')
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

        self.dia.vbox.pack_start(eb, expand=False, fill=True, padding=3)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_placement(gtk.CORNER_TOP_LEFT)
        scroll.set_shadow_type(gtk.SHADOW_NONE)
        scroll.show()
        self.dia.vbox.pack_start(scroll, expand=True, fill=True)

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.show()
        scroll.add(viewport)

        self.screen.widget.show()
        viewport.add(self.screen.widget)

        width, height = self.screen.screen_container.size_get()
        viewport.set_size_request(width, height + 30)
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
        if self.attrs.get('add_remove') \
                and event.keyval == gtk.keysyms.F3 \
                and self.but_add.get_property('sensitive'):
            self._sig_add()
            return False
        if ((event.keyval in (gtk.keysyms.N, gtk.keysyms.n) \
                and event.state & gtk.gdk.CONTROL_MASK) \
                or event.keyval == gtk.keysyms.F3) \
                and self.but_new.get_property('sensitive'):
            self._sig_new(widget)
            return False
        if event.keyval == gtk.keysyms.F2:
            self._sig_edit(widget)
            return False
        if (event.keyval in (gtk.keysyms.L, gtk.keysyms.l) \
                and event.state & gtk.gdk.CONTROL_MASK):
            self.switch_view(widget)
            return False

    def switch_view(self, widget):
        self.screen.switch_view()

    def _sig_new(self, widget):
        if (self.screen.current_view.view_type == 'form') \
                or self.screen.editable_get():
            self.screen.new(context=self.default_get_ctx)
            self.screen.current_view.widget.set_sensitive(True)
        else:
            dia = Dialog(self.model_name, parent=self.parent,
                    attrs=self.attrs, model_ctx=self.model_ctx,
                    default_get_ctx=self.default_get_ctx,
                    window=self.window)
            res = True
            while res:
                res, value = dia.run()
                if res:
                    self.screen.models.model_add(value)
                    value.signal('record-changed', value.parent)
                    self.screen.display()
                    dia.new()
            dia.destroy()

    def _sig_edit(self, widget=None):
        if self.screen.current_model:
            dia = Dialog(self.model_name, parent=self.parent,
                    model=self.screen.current_model, attrs=self.attrs,
                    window=self.window)
            res, value = dia.run()
            dia.destroy()

    def _sig_next(self, widget):
        self.screen.display_next()

    def _sig_previous(self, widget):
        self.screen.display_prev()

    def _sig_remove(self, widget, remove=False):
        self.screen.remove(remove=remove)

    def _sig_activate(self, *args):
        self._sig_add()
        self.wid_text.grab_focus()

    def _sig_add(self, *args):
        domain = []
        context = rpc.CONTEXT.copy()

        try:
            if self.wid_text.get_text():
                dom = [('rec_name', 'ilike',
                        '%' + self.wid_text.get_text() + '%'), domain]
            else:
                dom = domain
            ids = rpc.execute('model', self.attrs['relation'],
                    'search', dom, 0, _LIMIT, None, context)
        except Exception, exception:
            common.process_exception(exception, self._window)
            return False
        if len(ids) != 1:
            win = WinSearch(self.attrs['relation'], sel_multi=True, ids=ids,
                    context=context, domain=domain, parent=self._window,
                    views_preload=self.attrs.get('views', {}))
            ids = win.run()

        res_id = None
        if ids:
            res_id = ids[0]
        self.screen.load(ids, modified=True)
        self.screen.display(res_id=res_id)
        if self.screen.current_view:
            self.screen.current_view.set_cursor()
        self.wid_text.set_text('')

    def _sig_label(self, screen, signal_data):
        name = '_'
        if signal_data[0] >= 0:
            name = str(signal_data[0] + 1)
        line = '(%s/%s)' % (name, signal_data[1])
        self.label.set_text(line)

    def _menu_sig_default_get(self):
        pass

    def _menu_sig_default_set(self, reset=False):
        pass

    def new(self):
        model = self.screen.new(context=self.default_get_ctx)
        self.screen.models.model_add(model)
        return True

    def run(self):
        end = False
        while not end:
            res = self.dia.run()
            self.screen.current_view.set_value()
            end = (res != gtk.RESPONSE_OK) \
                    or (not self.screen.current_model \
                        or self.screen.current_model.validate())
            if not end:
                self.screen.current_view.set_cursor()
                self.screen.display()
            if self.but_cancel:
                self.but_cancel.set_label(gtk.STOCK_CLOSE)

        if res == gtk.RESPONSE_OK:
            model = self.screen.current_model
            return (True, model)
        return (False, None)

    def _sig_close(self, widget):
        if self.screen.current_view:
            self.screen.current_view.set_value()
        if not self.but_cancel \
                and self.screen.current_model \
                and not self.screen.current_model.validate():
            if self.screen.current_view:
                self.screen.current_view.set_cursor()
            self.screen.display()
            widget.emit_stop_by_name('close')

    def destroy(self):
        self.screen.signal_unconnect(self)
        self.window.present()
        self.dia.destroy()
        self.screen.destroy()


class One2Many(WidgetInterface):

    def __init__(self, window, parent, model, attrs=None):
        super(One2Many, self).__init__(window, parent, model, attrs)

        self.widget = gtk.VBox(homogeneous=False, spacing=5)

        hbox, menuitem_title = _create_menu(self, attrs)

        self.widget.pack_start(hbox, expand=False, fill=True)

        self.screen = Screen(attrs['relation'], self._window,
                view_type=attrs.get('mode','tree,form').split(','),
                parent=self.parent, parent_name=attrs.get('relation_field', ''),
                views_preload=attrs.get('views', {}),
                tree_saves=attrs.get('saves', False), create_new=True,
                row_activate=self._on_activate,
                default_get=attrs.get('default_get', {}),
                exclude_field=attrs.get('relation_field', None))
        self.screen.signal_connect(self, 'record-message', self._sig_label)
        menuitem_title.get_child().set_text(attrs.get('string', ''))

        self.widget.pack_start(self.screen.widget, expand=True, fill=True)

        self.screen.widget.connect('key_press_event', self.on_keypress)

    def grab_focus(self):
        return self.screen.widget.grab_focus()

    def on_keypress(self, widget, event):
        if self.attrs.get('add_remove') \
                and event.keyval == gtk.keysyms.F3 \
                and self.but_add.get_property('sensitive'):
            self._sig_add()
            return False
        if ((event.keyval == gtk.keysyms.N \
                    and event.state & gtk.gdk.CONTROL_MASK \
                    and event.state & gtk.gdk.SHIFT_MASK) \
                or event.keyval == gtk.keysyms.F3) \
                and self.but_new.get_property('sensitive'):
            self._sig_new(widget)
            return False
        if event.keyval == gtk.keysyms.F2:
            self._sig_edit(widget)
            return False

    def destroy(self):
        self.screen.destroy()

    def _on_activate(self):
        self._sig_edit()

    def switch_view(self, widget):
        self.screen.switch_view()

    def _readonly_set(self, value):
        self.but_new.set_sensitive(not value)
        self.but_del.set_sensitive(not value)
        if self.attrs.get('add_remove'):
            self.wid_text.set_sensitive(not value)
            self.but_add.set_sensitive(not value)
            self.but_remove.set_sensitive(not value)

    def _sig_new(self, widget):
        self._view.view_form.set_value()
        ctx = self._view.model.expr_eval(self.screen.default_get)
        ctx.update(self._view.model.expr_eval('dict(%s)' % \
                self.attrs.get('context', '')))
        sequence = None
        idx = -1
        if self.screen.current_view.view_type == 'tree':
            sequence = self.screen.current_view.widget_tree.sequence
            select_ids = self.screen.sel_ids_get()
            if select_ids:
                model = self.screen.models.get_by_id(select_ids[0])
                idx = self.screen.models.models.index(model)
        if (self.screen.current_view.view_type == 'form') \
                or self.screen.editable_get():
            self.screen.new(context=ctx)
            self.screen.current_view.widget.set_sensitive(True)
        else:
            readonly = False
            domain = []
            if self._view.modelfield and self._view.model:
                modelfield = self._view.modelfield
                model = self._view.model
                readonly = modelfield.get_state_attrs(model
                        ).get('readonly', False)
                domain = modelfield.domain_get(self._view.model)
            dia = Dialog(self.attrs['relation'], parent=self._view.model,
                    attrs=self.attrs,
                    model_ctx=self.screen.models._context,
                    default_get_ctx=ctx, window=self._window,
                    readonly=readonly, domain=domain)
            res = True
            while res:
                res, value = dia.run()
                if res:
                    if idx >= 0:
                        idx += 1
                    self.screen.models.model_add(value, position=idx)
                    value.signal('record-changed', value.parent)
                    self.screen.display_next()
                    dia.new()
            dia.destroy()
        if sequence:
            self.screen.models.set_sequence(field=sequence)

    def _sig_edit(self, widget=None):
        self._view.view_form.set_value()
        if self.screen.current_model:
            readonly = False
            domain = []
            if self._view.modelfield and self._view.model:
                modelfield = self._view.modelfield
                model = self._view.model
                readonly = modelfield.get_state_attrs(model
                        ).get('readonly', False)
                domain = modelfield.domain_get(self._view.model)
            dia = Dialog(self.attrs['relation'], parent=self._view.model,
                    model=self.screen.current_model, attrs=self.attrs,
                    window=self._window, readonly=readonly, domain=domain,
                    model_ctx=self.screen.models.context)
            res, value = dia.run()
            dia.destroy()

    def _sig_next(self, widget):
        self.screen.display_next()

    def _sig_previous(self, widget):
        self.screen.display_prev()

    def _sig_remove(self, widget, remove=False):
        self.screen.remove(remove=remove)

    def _sig_activate(self, *args):
        self._sig_add()
        self.wid_text.grab_focus()

    def _sig_add(self, *args):
        self._view.view_form.set_value()
        domain = self._view.modelfield.domain_get(self._view.model)
        context = rpc.CONTEXT.copy()
        context.update(self._view.modelfield.context_get(self._view.model))
        domain = domain[:]
        domain.extend(self._view.model.expr_eval(self.attrs.get('add_remove'),
            context))
        removed_ids = self._view.modelfield.get_removed_ids(self._view.model)

        try:
            if self.wid_text.get_text():
                dom = [('rec_name', 'ilike', '%' + self.wid_text.get_text() + '%'),
                    ['OR', domain, ('id', 'in', removed_ids)]]
            else:
                dom = ['OR', domain, ('id', 'in', removed_ids)]
            ids = rpc.execute('model', self.attrs['relation'],
                    'search', dom, 0, _LIMIT, None, context)
        except Exception, exception:
            common.process_exception(exception, self._window)
            return False
        if len(ids) != 1:
            win = WinSearch(self.attrs['relation'], sel_multi=True, ids=ids,
                    context=context, domain=domain, parent=self._window,
                    views_preload=self.attrs.get('views', {}))
            ids = win.run()

        res_id = None
        if ids:
            res_id = ids[0]
        self.screen.load(ids, modified=True)
        self.screen.display(res_id=res_id)
        if self.screen.current_view:
            self.screen.current_view.set_cursor()
        self.wid_text.set_text('')

    def _sig_label(self, screen, signal_data):
        name = '_'
        if signal_data[0] >= 0:
            name = str(signal_data[0] + 1)
        line = '(%s/%s)' % (name, signal_data[1])
        self.label.set_text(line)

    def display(self, model, model_field):
        if not model_field:
            self.screen.current_model = None
            self.screen.display()
            return False
        super(One2Many, self).display(model, model_field)
        new_models = model_field.get_client(model)
        if self.screen.models != new_models:
            self.screen.models_set(new_models)
            if (self.screen.current_view.view_type == 'tree') \
                    and self.screen.editable_get():
                self.screen.current_model = None
            readonly = False
            domain = []
            if self._view.modelfield and self._view.model:
                modelfield = self._view.modelfield
                model = self._view.model
                readonly = modelfield.get_state_attrs(model
                        ).get('readonly', False)
                domain = modelfield.domain_get(self._view.model)
            if self.screen.domain != domain:
                self.screen.domain = domain
            self.screen.models.readonly = readonly
        self.screen.display()
        return True

    def display_value(self):
        return '<' + self.attrs.get('string', '') + '>'

    def set_value(self, model, model_field):
        self.screen.current_view.set_value()
        if self.screen.is_modified():
            model.modified = True
            model.modified_fields.setdefault(model_field.name)
        return True
