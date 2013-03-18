#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
from interface import WidgetInterface
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm
from tryton.config import CONFIG
import tryton.common as common
from tryton.common import RPCExecute, RPCException

_ = gettext.gettext


class One2Many(WidgetInterface):

    def __init__(self, field_name, model_name, attrs=None):
        super(One2Many, self).__init__(field_name, model_name, attrs=attrs)

        self.widget = gtk.VBox(homogeneous=False, spacing=2)
        self._readonly = True
        self._position = 0
        self._length = 0

        hbox = gtk.HBox(homogeneous=False, spacing=0)
        hbox.set_border_width(2)

        label = gtk.Label(attrs.get('string', ''))
        label.set_alignment(0.0, 0.5)
        hbox.pack_start(label, expand=True, fill=True)

        hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

        tooltips = common.Tooltips()

        self.focus_out = True
        if attrs.get('add_remove'):

            self.wid_text = gtk.Entry()
            self.wid_text.set_property('width_chars', 13)
            self.wid_text.connect('activate', self._sig_activate)
            self.wid_text.connect('focus-out-event', self._focus_out)
            hbox.pack_start(self.wid_text, expand=True, fill=True)

            self.but_add = gtk.Button()
            tooltips.set_tip(self.but_add, _('Add'))
            self.but_add.connect('clicked', self._sig_add)
            self.but_add.connect('enter-notify-event', self.enter)
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
            self.but_remove.connect('enter-notify-event', self.enter)
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
        self.but_new.connect('enter-notify-event', self.enter)
        img_new = gtk.Image()
        img_new.set_from_stock('tryton-new', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_new.set_alignment(0.5, 0.5)
        self.but_new.add(img_new)
        self.but_new.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(self.but_new, expand=False, fill=False)

        self.but_open = gtk.Button()
        tooltips.set_tip(self.but_open, _('Edit selected record <F2>'))
        self.but_open.connect('clicked', self._sig_edit)
        self.but_open.connect('enter-notify-event', self.enter)
        img_open = gtk.Image()
        img_open.set_from_stock('tryton-open', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_open.set_alignment(0.5, 0.5)
        self.but_open.add(img_open)
        self.but_open.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(self.but_open, expand=False, fill=False)

        self.but_del = gtk.Button()
        tooltips.set_tip(self.but_del, _('Delete selected record <Del>'))
        self.but_del.connect('clicked', self._sig_remove, False)
        self.but_del.connect('enter-notify-event', self.enter)
        img_del = gtk.Image()
        img_del.set_from_stock('tryton-delete', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_del.set_alignment(0.5, 0.5)
        self.but_del.add(img_del)
        self.but_del.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(self.but_del, expand=False, fill=False)

        self.but_undel = gtk.Button()
        tooltips.set_tip(self.but_undel, _('Undelete selected record <Ins>'))
        self.but_undel.connect('clicked', self._sig_undelete)
        self.but_undel.connect('enter-notify-event', self.enter)
        img_undel = gtk.Image()
        img_undel.set_from_stock('tryton-undo', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_undel.set_alignment(0.5, 0.5)
        self.but_undel.add(img_undel)
        self.but_undel.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(self.but_undel, expand=False, fill=False)

        hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

        self.but_pre = gtk.Button()
        tooltips.set_tip(self.but_pre, _('Previous'))
        self.but_pre.connect('clicked', self._sig_previous)
        self.but_pre.connect('enter-notify-event', self.enter)
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
        self.but_next.connect('enter-notify-event', self.enter)
        img_next = gtk.Image()
        img_next.set_from_stock('tryton-go-next', gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_next.set_alignment(0.5, 0.5)
        self.but_next.add(img_next)
        self.but_next.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(self.but_next, expand=False, fill=False)

        hbox.pack_start(gtk.VSeparator(), expand=False, fill=True)

        but_switch = gtk.Button()
        tooltips.set_tip(but_switch, _('Switch'))
        but_switch.connect('clicked', self.switch_view)
        but_switch.connect('enter-notify-event', self.enter)
        img_switch = gtk.Image()
        img_switch.set_from_stock('tryton-fullscreen',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        img_switch.set_alignment(0.5, 0.5)
        but_switch.add(img_switch)
        but_switch.set_relief(gtk.RELIEF_NONE)
        hbox.pack_start(but_switch, expand=False, fill=False)

        if attrs.get('add_remove'):
            hbox.set_focus_chain([self.wid_text])
        else:
            hbox.set_focus_chain([])

        tooltips.enable()

        frame = gtk.Frame()
        frame.add(hbox)
        frame.set_shadow_type(gtk.SHADOW_OUT)
        self.widget.pack_start(frame, expand=False, fill=True)

        self.screen = Screen(attrs['relation'],
            mode=attrs.get('mode', 'tree,form').split(','),
            view_ids=attrs.get('view_ids', '').split(','),
            views_preload=attrs.get('views', {}),
            row_activate=self._on_activate,
            exclude_field=attrs.get('relation_field', None))
        self.screen.pre_validate = bool(int(attrs.get('pre_validate', 0)))
        self.screen.signal_connect(self, 'record-message', self._sig_label)

        self.widget.pack_start(self.screen.widget, expand=True, fill=True)

        self.screen.widget.connect('key_press_event', self.on_keypress)
        if self.attrs.get('add_remove'):
            self.wid_text.connect('key_press_event', self.on_keypress)

        but_switch.props.sensitive = self.screen.number_of_views > 1

    def _color_widget(self):
        if hasattr(self.screen.current_view, 'widget_tree'):
            return self.screen.current_view.widget_tree
        return super(One2Many, self)._color_widget()

    def grab_focus(self):
        return self.screen.widget.grab_focus()

    def on_keypress(self, widget, event):
        if (event.keyval == gtk.keysyms.F3) \
                and self.but_new.get_property('sensitive'):
            self._sig_new(widget)
            return False
        if event.keyval == gtk.keysyms.F2 \
                and widget == self.screen.widget:
            self._sig_edit(widget)
            return False
        if (event.keyval in (gtk.keysyms.Delete, gtk.keysyms.KP_Delete)
                and widget == self.screen.widget
                and self.but_del.get_property('sensitive')):
            self._sig_remove(widget)
            return False
        if event.keyval == gtk.keysyms.Insert and widget == self.screen.widget:
            self._sig_undelete(widget)
            return False

    def destroy(self):
        self.screen.destroy()

    def _on_activate(self):
        self._sig_edit()

    def switch_view(self, widget):
        self.screen.switch_view()
        self.color_set(self.color_name)

    @property
    def modified(self):
        return self.screen.current_view.modified

    def color_set(self, name):
        super(One2Many, self).color_set(name)
        widget = self._color_widget()
        # if the style to apply is different from readonly then insensitive
        # cellrenderers should use the default insensitive color
        if name != 'readonly':
            widget.modify_text(gtk.STATE_INSENSITIVE,
                    self.colors['text_color_insensitive'])

    def _readonly_set(self, value):
        self._readonly = value
        self._set_button_sensitive()

    def _set_button_sensitive(self):
        access = common.MODELACCESS[self.screen.model_name]
        if self.record and self.field:
            field_size = self.record.expr_eval(self.attrs.get('size'))
            o2m_size = len(self.field.get_eval(self.record))
            size_limit = (field_size is not None
                and o2m_size >= field_size >= 0)
        else:
            size_limit = False

        self.but_new.set_sensitive(bool(
                not self._readonly
                and self.attrs.get('create', True)
                and not size_limit
                and access['create']))
        self.but_del.set_sensitive(bool(
                not self._readonly
                and self.attrs.get('delete', True)
                and self._position
                and access['delete']))
        self.but_undel.set_sensitive(bool(
                not self._readonly
                and not size_limit
                and self._position))
        self.but_open.set_sensitive(bool(
                self._position
                and access['read']))
        self.but_next.set_sensitive(bool(
                self._position
                and self._position < self._length))
        self.but_pre.set_sensitive(bool(
                self._position
                and self._position > 1))
        if self.attrs.get('add_remove'):
            self.wid_text.set_sensitive(not self._readonly)
            self.but_add.set_sensitive(bool(
                    not self._readonly
                    and not size_limit
                    and access['write']
                    and access['read']))
            self.but_remove.set_sensitive(bool(
                    not self._readonly
                    and self._position
                    and access['write']
                    and access['read']))

    def _validate(self):
        self.view.set_value()
        record = self.screen.current_record
        if record:
            fields = self.screen.current_view.get_fields()
            if not record.validate(fields):
                self.screen.display()
                return False
            if self.screen.pre_validate and not record.pre_validate():
                return False
        return True

    def _sig_new(self, widget):
        if not common.MODELACCESS[self.screen.model_name]['create']:
            return
        if not self._validate():
            return
        ctx = {}
        ctx.update(self.field.context_get(self.record))
        sequence = None
        if self.screen.current_view.view_type == 'tree':
            sequence = self.screen.current_view.widget_tree.sequence

        def update_sequence():
            if sequence:
                self.screen.group.set_sequence(field=sequence)

        if (self.screen.current_view.view_type == 'form') \
                or self.screen.editable_get():
            self.screen.new(context=ctx)
            self.screen.current_view.widget.set_sensitive(True)
            update_sequence()
        else:
            field_size = self.record.expr_eval(self.attrs.get('size')) or -1
            field_size -= len(self.field.get_eval(self.record)) + 1
            WinForm(self.screen, lambda a: update_sequence(), new=True,
                many=field_size, context=ctx)

    def _sig_edit(self, widget=None):
        if not common.MODELACCESS[self.screen.model_name]['read']:
            return
        if not self._validate():
            return
        record = self.screen.current_record
        if record:
            WinForm(self.screen, lambda a: None)

    def _sig_next(self, widget):
        if not self._validate():
            return
        self.screen.display_next()

    def _sig_previous(self, widget):
        if not self._validate():
            return
        self.screen.display_prev()

    def _sig_remove(self, widget, remove=False):
        access = common.MODELACCESS[self.screen.model_name]
        if remove:
            if not access['write'] or not access['read']:
                return
        else:
            if not access['delete']:
                return
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
        if not self.focus_out:
            return
        access = common.MODELACCESS[self.screen.model_name]
        if not access['write'] or not access['read']:
            return
        self.view.set_value()
        domain = self.field.domain_get(self.record)
        context = self.field.context_get(self.record)
        domain = domain[:]
        domain.extend(self.record.expr_eval(self.attrs.get('add_remove')))
        removed_ids = self.field.get_removed_ids(self.record)

        self.focus_out = False
        try:
            if self.wid_text.get_text():
                dom = [('rec_name', 'ilike',
                        '%' + self.wid_text.get_text() + '%'),
                    ['OR', domain, ('id', 'in', removed_ids)]]
            else:
                dom = ['OR', domain, ('id', 'in', removed_ids)]
            ids = RPCExecute('model', self.attrs['relation'], 'search', dom,
                    0, CONFIG['client.limit'], None, context=context)
        except RPCException:
            self.focus_out = True
            return False

        sequence = None
        if self.screen.current_view.view_type == 'tree':
            sequence = self.screen.current_view.widget_tree.sequence

        def callback(result):
            self.focus_out = True
            if result:
                ids = [x[0] for x in result]
                self.screen.load(ids, modified=True)
                self.screen.display(res_id=ids[0])
                if sequence:
                    self.screen.group.set_sequence(field=sequence)
            self.screen.set_cursor()
            self.wid_text.set_text('')

        if len(ids) != 1:
            WinSearch(self.attrs['relation'], callback, sel_multi=True,
                ids=ids, context=context, domain=domain,
                view_ids=self.attrs.get('view_ids', '').split(','),
                views_preload=self.attrs.get('views', {}),
                new=self.but_new.get_property('sensitive'))
        else:
            callback([(i, None) for i in ids])

    def _sig_label(self, screen, signal_data):
        self._position = signal_data[0]
        self._length = signal_data[1]
        if self._position >= 1:
            name = str(self._position)
        else:
            name = '_'
        line = '(%s/%s)' % (name, self._length)
        self.label.set_text(line)
        self._set_button_sensitive()

    def display(self, record, field):
        super(One2Many, self).display(record, field)

        self._set_button_sensitive()

        if field is None:
            self.screen.new_group()
            self.screen.current_record = None
            self.screen.parent = True
            self.screen.display()
            return False
        new_group = field.get_client(record)

        if id(self.screen.group) != id(new_group):
            self.screen.group = new_group
            if (self.screen.current_view.view_type == 'tree') \
                    and self.screen.editable_get():
                self.screen.current_record = None
            readonly = False
            domain = []
            if record:
                readonly = field.get_state_attrs(record).get('readonly', False)
                domain = field.domain_get(record)
            if self.screen.domain != domain:
                self.screen.domain = domain
            if not self.screen.group.readonly and readonly:
                self.screen.group.readonly = readonly
        self.screen.display()
        return True

    def set_value(self, record, field):
        self.screen.save_tree_state()
        self.screen.current_view.set_value()
        if self.screen.modified():  # TODO check if required
            record.modified_fields.setdefault(field.name)
            record.signal('record-modified')
        return True
