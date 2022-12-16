#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gettext
import copy
import tryton.rpc as rpc
from tryton.action import Action
from tryton.gui.window.view_form.view.interface import ParserInterface
import tryton.common as common
from tryton.config import CONFIG, TRYTON_ICON
from tryton.gui.main import Main
import logging
from tryton.exceptions import TrytonServerError

_ = gettext.gettext


class Button(object):

    def __init__(self, attrs=None):
        super(Button, self).__init__()
        self.attrs = attrs or {}
        self.widget = gtk.Button()
        text = attrs.get('string', _('Unknown'))
        if '_' not in text:
            text = '_' + text
        self.widget.set_use_underline(True)
        self.widget.set_label(text)
        if attrs.get('icon', False):
            try:
                stock = attrs['icon']
                common.ICONFACTORY.register_icon(stock)
                icon = gtk.Image()
                icon.set_from_stock(stock, gtk.ICON_SIZE_SMALL_TOOLBAR)
                self.widget.set_image(icon)
            except KeyError:
                log = logging.getLogger('common')
                log.warning(_('Wrong icon for the button!'))
        self.widget.connect('clicked', self.button_clicked)
        self.form = None #fill later by ViewForm

    def button_clicked(self, widget):
        if not self.form:
            return
        record = self.form.screen.current_record
        obj_id = self.form.screen.save_current()
        if obj_id:
            if not self.attrs.get('confirm', False) or \
                    common.sur(self.attrs['confirm']):
                button_type = self.attrs.get('type', 'workflow')
                ctx = rpc.CONTEXT.copy()
                ctx.update(record.context_get())
                if button_type == 'workflow':
                    args = ('model', self.form.screen.model_name,
                            'workflow_trigger_validate', obj_id,
                            self.attrs['name'], ctx)
                    try:
                        rpc.execute(*args)
                    except TrytonServerError, exception:
                        common.process_exception(exception, *args)
                elif button_type == 'object':
                    args = ('model', self.form.screen.model_name, self.attrs['name'],
                            [obj_id], ctx)
                    try:
                        rpc.execute(*args)
                    except TrytonServerError, exception:
                        common.process_exception(exception, *args)
                elif button_type == 'action':
                    action_id = None
                    args = ('model', 'ir.action', 'get_action_id',
                            int(self.attrs['name']), ctx)
                    try:
                        action_id = rpc.execute(*args)
                    except TrytonServerError, exception:
                        action_id = common.process_exception(exception, *args)
                    if action_id:
                        Action.execute(action_id, {
                            'model': self.form.screen.model_name,
                            'id': obj_id,
                            'ids': [obj_id],
                            }, context=ctx)
                else:
                    raise Exception('Unallowed button type')
                self.form.screen.reload(written=True)
        else:
            self.form.screen.display()

    def state_set(self, record):
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}),
                    check_load=False)
        else:
            state_changes = {}
        if state_changes.get('invisible', False):
            self.widget.hide()
        else:
            self.widget.show()
        self.widget.set_sensitive(not state_changes.get('readonly', False))
        if 'icon' in state_changes:
            stock = state_changes['icon']
            if stock:
                common.ICONFACTORY.register_icon(stock)
                icon = gtk.Image()
                icon.set_from_stock(stock, gtk.ICON_SIZE_SMALL_TOOLBAR)
                self.widget.set_image(icon)
            else:
                self.widget.set_image(gtk.Image())


class Label(gtk.Label):

    def __init__(self, str=None, attrs=None):
        super(Label, self).__init__(str=str)
        self.attrs = attrs or {}

    def state_set(self, record):
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}),
                    check_load=False)
        else:
            state_changes = {}
        if state_changes.get('invisible', self.attrs.get('invisible')):
            self.hide()
        else:
            self.show()


class VBox(gtk.VBox):

    def __init__(self, homogeneous=False, spacing=0, attrs=None):
        super(VBox, self).__init__(homogeneous, spacing)
        self.attrs = attrs or {}

    def state_set(self, record):
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}),
                    check_load=False)
        else:
            state_changes = {}
        if state_changes.get('invisible', self.attrs.get('invisible')):
            self.hide()
        else:
            self.show()


class Image(gtk.Image):

    def __init__(self, attrs=None):
        super(Image, self).__init__()
        self.attrs = attrs or {}

    def state_set(self, record):
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}),
                    check_load=False)
        else:
            state_changes = {}
        if state_changes.get('invisible', self.attrs.get('invisible')):
            self.hide()
        else:
            self.show()
        state_changes = self.attrs.get('states', {})


class Frame(gtk.Frame):

    def __init__(self, label=None, attrs=None):
        if not label: # label must be None to have no label widget
            label = None
        super(Frame, self).__init__(label=label)
        self.attrs = attrs or {}
        if not label:
            self.set_shadow_type(gtk.SHADOW_NONE)
        self.set_border_width(0)

    def state_set(self, record):
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}),
                    check_load=False)
        else:
            state_changes = {}
        if state_changes.get('invisible', self.attrs.get('invisible')):
            self.hide()
        else:
            self.show()


class ScrolledWindow(gtk.ScrolledWindow):

    def __init__(self, hadjustment=None, vadjustment=None, attrs=None):
        super(ScrolledWindow, self).__init__(hadjustment=hadjustment,
                vadjustment=vadjustment)
        self.attrs = attrs or {}

    def state_set(self, record):
        if record:
            state_changes = record.expr_eval(self.attrs.get('states', {}),
                    check_load=False)
        else:
            state_changes = {}
        if state_changes.get('invisible', self.attrs.get('invisible')):
            self.hide()
        else:
            self.show()


class Alignment(gtk.Alignment):

    def __init__(self, widget, attrs):
        super(Alignment, self).__init__(
            float(attrs.get('xalign', 0.0)),
            float(attrs.get('yalign', 0.5)),
            abs(1 - float(attrs.get('xalign', 0.0))),
            abs(1 - float(attrs.get('yalign', 0.0))))
        self.add(widget)
        widget.connect('show', lambda *a: self.show())
        widget.connect('hide', lambda *a: self.hide())


class _container(object):
    def __init__(self, tooltips):
        self.cont = []
        self.col = []
        self.tooltips = tooltips
        self.trans_box = []

    def new(self, col=4):
        table = gtk.Table(1, col)
        table.set_homogeneous(False)
        table.set_col_spacings(0)
        table.set_row_spacings(0)
        table.set_border_width(0)
        self.cont.append( (table, 0, 0) )
        self.col.append( col )

    def get(self):
        return self.cont[-1][0]

    def pop(self):
        table = self.cont.pop()[0]
        self.col.pop()
        return table

    def newline(self):
        (table, width, height) = self.cont[-1]
        if width > 0:
            self.cont[-1] = (table, 0, height + 1)
        table.resize(height + 1, self.col[-1])

    def wid_add(self, widget, name='', yexpand=False, ypadding=2, rowspan=1,
            colspan=1, translate=False, fname=None, help_tip=False, yfill=False,
            xexpand=True, xfill=True, xpadding=3):
        (table, width, height) = self.cont[-1]
        if colspan > self.col[-1]:
            colspan = self.col[-1]
        if colspan + width > self.col[-1]:
            self.newline()
            (table, width, height) = self.cont[-1]
        yopt = False
        if yexpand:
            yopt = yopt | gtk.EXPAND
        if yfill:
            yopt = yopt | gtk.FILL
        xopt = False
        if xexpand:
            xopt = xopt | gtk.EXPAND
        if xfill:
            xopt = xopt | gtk.FILL
        if help_tip:
            self.tooltips.set_tip(widget, help_tip)
            self.tooltips.enable()
        if translate:
            button = gtk.Button()
            img = gtk.Image()
            img.set_from_stock('tryton-locale', gtk.ICON_SIZE_SMALL_TOOLBAR)
            button.set_image(img)
            button.set_relief(gtk.RELIEF_NONE)
            self.trans_box.append((button, name, fname, widget.get_children()[0]))
            widget.get_child().pack_start(button, fill=False, expand=False)
        widget.show_all()
        table.attach(widget, width, width + colspan,
                height, height + rowspan,
                yoptions=yopt, ypadding=ypadding,
                xoptions=xopt, xpadding=xpadding)
        self.cont[-1] = (table, width + colspan, height)
        wid_list = table.get_children()
        wid_list.reverse()
        table.set_focus_chain(wid_list)

    def empty_add(self, colspan=1):
        (table, width, height) = self.cont[-1]
        if colspan > self.col[-1]:
            colspan = self.col[-1]
        if colspan + width > self.col[-1]:
            self.newline()
            (table, width, height) = self.cont[-1]
        self.cont[-1] = (table, width + colspan, height)


class ParserForm(ParserInterface):

    def __init__(self, parent=None, attrs=None, screen=None,
            children_field=None):
        super(ParserForm, self).__init__(parent=parent, attrs=attrs,
            screen=screen, children_field=children_field)
        self.widget_id = 0

    def parse(self, model_name, root_node, fields, notebook=None, paned=None,
            tooltips=None):
        dict_widget = {}
        button_list = []
        notebook_list = []
        attrs = common.node_attributes(root_node)
        on_write = attrs.get('on_write', '')
        if not tooltips:
            tooltips = common.Tooltips()
        container = _container(tooltips)
        if CONFIG['client.modepda']:
            container.new(col=1)
        else:
            container.new(col=int(attrs.get('col', 4)))
        cursor_widget = attrs.get('cursor')

        if not self.title:
            self.title = attrs.get('string', 'Unknown')

        for node in root_node.childNodes:
            if not node.nodeType == node.ELEMENT_NODE:
                continue
            attrs = common.node_attributes(node)
            if not cursor_widget:
                if attrs.get('name') and fields.get(attrs['name']) \
                        and attrs['name'] != self.screen.exclude_field:
                    cursor_widget = attrs.get('name')
            yexpand = int(attrs.get('yexpand', 0))
            yfill = int(attrs.get('yfill', 0))
            xexpand = int(attrs.get('xexpand', 1))
            xfill = int(attrs.get('xfill', 1))
            colspan = int(attrs.get('colspan', 1))
            if node.localName == 'image':
                common.ICONFACTORY.register_icon(attrs['name'])
                icon = Image(attrs)
                button_list.append(icon)
                icon.set_from_stock(attrs['name'], gtk.ICON_SIZE_DIALOG)
                container.wid_add(icon,
                    help_tip=attrs.get('help', False),
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill, ypadding=10,
                    xexpand=xexpand, xfill=xfill)
            elif node.localName == 'separator':
                text = attrs.get('string', '')
                if 'name' in attrs:
                    for attr_name in ('states', 'invisible'):
                        if attr_name not in attrs and attrs['name'] in fields:
                            if attr_name in fields[attrs['name']].attrs:
                                attrs[attr_name] = fields[attrs['name']
                                        ].attrs[attr_name]
                    if not text:
                        text = fields[attrs['name']].attrs['string']
                vbox = VBox(attrs=attrs)
                button_list.append(vbox)
                if text:
                    label = gtk.Label(text)
                    label.set_use_markup(True)
                    label.set_alignment(float(attrs.get('xalign', 0.0)), 0.5)
                    vbox.pack_start(label)
                vbox.pack_start(gtk.HSeparator())
                container.wid_add(vbox,
                    help_tip=attrs.get('help', False),
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill, ypadding=10,
                    xexpand=xexpand, xfill=xfill)
            elif node.localName == 'label':
                text = attrs.get('string', '')
                if 'name' in attrs and attrs['name'] in fields:
                    if attrs['name'] == self.screen.exclude_field:
                        container.empty_add(int(attrs.get('colspan', 1)))
                        continue
                    for attr_name in ('states', 'invisible'):
                        if attr_name not in attrs \
                                and attr_name in fields[attrs['name']].attrs:
                            attrs[attr_name] = fields[attrs['name']
                                    ].attrs[attr_name]
                    if not text:
                        if gtk.widget_get_default_direction() == \
                                gtk.TEXT_DIR_RTL:
                            text = _(':') + \
                                    fields[attrs['name']].attrs['string']
                        else:
                            text = fields[attrs['name']].attrs['string'] + \
                                    _(':')
                    if 'xalign' not in attrs:
                        attrs['xalign'] = 1.0
                elif not text:
                    for node in node.childNodes:
                        if node.nodeType == node.TEXT_NODE:
                            text += node.data
                        else:
                            text += node.toxml()
                if not text:
                    container.empty_add(int(attrs.get('colspan', 1)))
                    continue
                label = Label(text, attrs)
                button_list.append(label)
                label.set_use_markup(True)
                if CONFIG['client.modepda']:
                    attrs['xalign'] = 0.0
                label.set_alignment(float(attrs.get('xalign', 1.0)),
                    float(attrs.get('yalign', 0.0)))
                label.set_angle(int(attrs.get('angle', 0)))
                xexpand = bool(attrs.get('xexpand', 0))
                container.wid_add(label,
                    help_tip=attrs.get('help', False),
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill,
                    xexpand=xexpand, xfill=xfill)

            elif node.localName == 'newline':
                container.newline()

            elif node.localName == 'button':
                button = Button(attrs)
                button_list.append(button)
                container.wid_add(button.widget,
                    help_tip=attrs.get('help', False),
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill,
                    xexpand=xexpand, xfill=xfill)

            elif node.localName == 'notebook':
                notebook = gtk.Notebook()
                notebook.set_scrollable(True)
                notebook_list.append(notebook)
                if CONFIG['client.form_tab'] == 'top':
                    pos = gtk.POS_TOP
                elif CONFIG['client.form_tab'] == 'left':
                    pos = gtk.POS_LEFT
                elif CONFIG['client.form_tab'] == 'right':
                    pos = gtk.POS_RIGHT
                elif CONFIG['client.form_tab'] == 'bottom':
                    pos = gtk.POS_BOTTOM
                notebook.set_tab_pos(pos)
                notebook.set_border_width(3)
                colspan = int(attrs.get('colspan', 4))
                yexpand = bool(attrs.get('yexpand', 1))
                yfill = bool(attrs.get('yfill', 1))
                container.wid_add(notebook,
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill,
                    xexpand=xexpand, xfill=xfill)
                widget, widgets, buttons, spam, notebook_list2, cursor_widget2 = \
                        self.parse(model_name, node, fields, notebook,
                                tooltips=tooltips)
                if not cursor_widget:
                    cursor_widget = cursor_widget2
                notebook_list.extend(notebook_list2)
                button_list += buttons
                for widget_name, widgets in widgets.items():
                    dict_widget.setdefault(widget_name, [])
                    dict_widget[widget_name].extend(widgets)

            elif node.localName == 'page':
                if CONFIG['client.form_tab'] == 'left':
                    angle = 90
                    tab_box  = gtk.VBox(spacing=3)
                    image_pos, image_rotate = ('end',
                        gtk.gdk.PIXBUF_ROTATE_COUNTERCLOCKWISE)
                elif CONFIG['client.form_tab'] == 'right':
                    angle = -90
                    tab_box = gtk.VBox(spacing=3)
                    image_pos, image_rotate = ('start',
                        gtk.gdk.PIXBUF_ROTATE_CLOCKWISE)
                else:
                    angle = 0
                    tab_box = gtk.HBox(spacing=3)
                    image_pos, image_rotate = ('start',
                        gtk.gdk.PIXBUF_ROTATE_NONE)
                text = attrs.get('string', '')
                if 'name' in attrs and attrs['name'] in fields:
                    if attrs['name'] == self.screen.exclude_field:
                        continue
                    for attr_name in ('states', 'invisible'):
                        if attr_name in fields[attrs['name']].attrs:
                            attrs[attr_name] = \
                                    fields[attrs['name']].attrs[attr_name]
                    if not text:
                        text = fields[attrs['name']].attrs['string']
                if not text:
                    text = _('No String Attr.')
                if '_' not in text:
                    text = '_' + text
                tab_label = gtk.Label(text)
                tab_label.set_angle(angle)
                tab_label.set_use_underline(True)
                tab_box.pack_start(tab_label)
                if 'icon' in attrs:
                    common.ICONFACTORY.register_icon(attrs['icon'])
                    pixbuf = tab_box.render_icon(attrs['icon'],
                        gtk.ICON_SIZE_SMALL_TOOLBAR)
                    pixbuf = pixbuf.rotate_simple(image_rotate)
                    icon = gtk.Image()
                    icon.set_from_pixbuf(pixbuf)
                    if image_pos == 'end':
                        tab_box.pack_end(icon)
                    else:
                        tab_box.pack_start(icon)
                tab_box.show_all()
                widget, widgets, buttons, spam, notebook_list2, cursor_widget2 = \
                        self.parse(model_name, node, fields, notebook,
                                tooltips=tooltips)
                if not cursor_widget:
                    cursor_widget = cursor_widget2
                notebook_list.extend(notebook_list2)
                button_list += buttons
                for widget_name, widgets in widgets.iteritems():
                    dict_widget.setdefault(widget_name, [])
                    dict_widget[widget_name].extend(widgets)

                viewport = gtk.Viewport()
                viewport.set_shadow_type(gtk.SHADOW_NONE)
                viewport.add(widget)
                viewport.show()
                scrolledwindow = ScrolledWindow(attrs=attrs)
                scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
                scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                        gtk.POLICY_AUTOMATIC)
                scrolledwindow.add(viewport)

                button_list.append(scrolledwindow)
                notebook.append_page(scrolledwindow, tab_box)

            elif node.localName == 'field':
                name = str(attrs['name'])
                if name == self.screen.exclude_field:
                    container.empty_add(int(attrs.get('colspan', 1)))
                    continue
                if name not in fields:
                    container.empty_add(int(attrs.get('colspan', 1)))
                    log = logging.getLogger('view')
                    log.error('Unknown field "%s"' % str(name))
                    continue
                ftype = attrs.get('widget', fields[name].attrs['type'])
                if not ftype in WIDGETS_TYPE:
                    container.empty_add(int(attrs.get('colspan', 1)))
                    continue
                for attr_name in ('relation', 'domain', 'selection',
                        'relation_field', 'string', 'views', 'invisible',
                        'add_remove', 'sort', 'context', 'size', 'filename',
                        'autocomplete'):
                    if attr_name in fields[name].attrs and \
                            not attr_name in attrs:
                        attrs[attr_name] = fields[name].attrs[attr_name]

                widget_act = WIDGETS_TYPE[ftype][0](name, model_name, attrs)
                self.widget_id += 1
                widget_act.position = self.widget_id
                dict_widget.setdefault(name, [])
                dict_widget[name].append(widget_act)
                yexpand = bool(attrs.get('yexpand', WIDGETS_TYPE[ftype][2]))
                yfill = bool(attrs.get('yfill', WIDGETS_TYPE[ftype][3]))
                hlp = fields[name].attrs.get('help', attrs.get('help', False))
                if attrs.get('height', False) or attrs.get('width', False):
                    widget_act.widget.set_size_request(
                            int(attrs.get('width', -1)),
                            int(attrs.get('height', -1)))
                translate = False
                if ftype in ('char', 'text'):
                    translate = fields[name].attrs.get('translate', False)
                container.wid_add(Alignment(widget_act.widget, attrs),
                    fields[name].attrs['string'], fname=name,
                    help_tip=hlp,
                    translate=translate,
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill,
                    xexpand=xexpand, xfill=xfill)

            elif node.localName == 'group':
                widget, widgets, buttons, spam, notebook_list2, cursor_widget2 = \
                        self.parse(model_name, node, fields, tooltips=tooltips)
                if not cursor_widget:
                    cursor_widget = cursor_widget2
                notebook_list.extend(notebook_list2)
                for widget_name, widgets in widgets.iteritems():
                    dict_widget.setdefault(widget_name, [])
                    dict_widget[widget_name].extend(widgets)
                button_list += buttons
                text = ''
                if 'name' in attrs and attrs['name'] in fields:
                    if attrs['name'] == self.screen.exclude_field:
                        container.empty_add(int(attrs.get('colspan', 1)))
                        continue
                    for attr_name in ('states', 'invisible'):
                        if attr_name in fields[attrs['name']].attrs:
                            attrs[attr_name] = fields[attrs['name']
                                    ].attrs[attr_name]
                    text = fields[attrs['name']].attrs['string']
                if attrs.get('string'):
                    text = attrs['string']

                frame = Frame(text, attrs)
                frame.add(widget)
                button_list.append(frame)
                container.wid_add(frame,
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill, ypadding=0,
                    xexpand=xexpand, xfill=xfill,  xpadding=0)
            elif node.localName == 'hpaned':
                hpaned = gtk.HPaned()
                container.wid_add(hpaned, colspan=int(attrs.get('colspan', 4)),
                        yexpand=True, yfill=True)
                widget, widgets, buttons, spam, notebook_list2, cursor_widget2 = \
                        self.parse(model_name, node, fields, paned=hpaned,
                                tooltips=tooltips)
                if not cursor_widget:
                    cursor_widget = cursor_widget2
                notebook_list.extend(notebook_list2)
                button_list += buttons
                for widget_name, widgets in widgets.iteritems():
                    dict_widget.setdefault(widget_name, [])
                    dict_widget[widget_name].extend(widgets)
                if 'position' in attrs:
                    hpaned.set_position(int(attrs['position']))
            elif node.localName == 'vpaned':
                vpaned = gtk.VPaned()
                container.wid_add(vpaned, colspan=int(attrs.get('colspan', 4)),
                        yexpand=True, yfill=True)
                widget, widgets, buttons, spam, notebook_list, cursor_widget2 = \
                        self.parse(model_name, node, fields, paned=vpaned,
                                tooltips=tooltips)
                if not cursor_widget:
                    cursor_widget = cursor_widget2
                notebook_list.extend(notebook_list2)
                button_list += buttons
                for widget_name, widgets in widgets.iteritems():
                    dict_widget.setdefault(widget_name, [])
                    dict_widget[widget_name].extend(widgets)
                if 'position' in attrs:
                    vpaned.set_position(int(attrs['position']))
            elif node.localName == 'child':
                widget, widgets, buttons, spam, notebook_list2, cursor_widget2 = \
                        self.parse(model_name, node, fields, paned=paned,
                                tooltips=tooltips)
                if not cursor_widget:
                    cursor_widget = cursor_widget2
                notebook_list.extend(notebook_list2)
                button_list += buttons
                for widget_name, widgets in widgets.iteritems():
                    dict_widget.setdefault(widget_name, [])
                    dict_widget[widget_name].extend(widgets)
                if not paned.get_child1():
                    paned.pack1(widget, resize=True, shrink=True)
                elif not paned.get_child2():
                    paned.pack2(widget, resize=True, shrink=True)
        for (button, src, name, widget) in container.trans_box:
            button.connect('clicked', self.translate, model_name, name,
                    src, widget)
        return container.pop(), dict_widget, button_list, on_write, \
                notebook_list, cursor_widget

    def translate(self, widget, model_name, name, src, widget_entry):
        obj_id = self.screen.current_record.id
        if obj_id < 0:
            common.message(
                    _('You need to save the record before adding translations!'))
            return False

        obj_id = self.screen.current_record.save(force_reload=False)
        try:
            lang_ids = rpc.execute('model', 'ir.lang',
                    'search', [('translatable', '=', '1')],
                    rpc.CONTEXT)
        except TrytonServerError, exception:
            common.process_exception(exception)
            return False

        if not lang_ids:
            common.message(_('No other language available!'))
            return False
        try:
            lang_ids += rpc.execute('model', 'ir.lang',
                    'search', [('code', '=', 'en_US')],
                    rpc.CONTEXT)
            langs = rpc.execute('model', 'ir.lang',
                    'read', lang_ids, ['code', 'name'],
                    rpc.CONTEXT)
        except TrytonServerError, exception:
            common.process_exception(exception)
            return False

        code = rpc.CONTEXT.get('language', 'en_US')

        widget_entry = widget_entry.get_children()[0]
        if isinstance(widget_entry, gtk.ScrolledWindow):
            widget_entry = widget_entry.get_child()
        #widget accessor functions
        def value_get(widget):
            if isinstance(widget, gtk.Entry):
                return widget.get_text()
            elif isinstance(widget, gtk.TextView):
                buf = widget.get_buffer()
                iter_start = buf.get_start_iter()
                iter_end = buf.get_end_iter()
                return buf.get_text(iter_start, iter_end, False)
            else:
                return None

        def value_set(widget, value):
            if not value:
                value = ''
            if isinstance(widget, gtk.Entry):
                widget.set_text(value)
            elif isinstance(widget, gtk.TextView):
                buf = widget.get_buffer()
                buf.delete(buf.get_start_iter(), buf.get_end_iter())
                iter_start = buf.get_start_iter()
                buf.insert(iter_start, value)

        def widget_duplicate(widget):
            if isinstance(widget, gtk.Entry):
                entry = gtk.Entry()
                entry.set_property('activates_default', True)
                entry.set_max_length(widget.get_max_length())
                entry.set_width_chars(widget.get_width_chars())
                return entry, gtk.FILL
            elif isinstance(widget, gtk.TextView):
                textview = gtk.TextView()
                textview.set_wrap_mode(gtk.WRAP_WORD)
                scrolledwindow = gtk.ScrolledWindow()
                scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                        gtk.POLICY_ALWAYS)
                scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
                scrolledwindow.set_size_request(-1, 80)
                scrolledwindow.add(textview)
                textview.set_accepts_tab(False)
                return textview, gtk.FILL | gtk.EXPAND
            else:
                return None, False


        parent = common.get_toplevel_window()
        win = gtk.Dialog(_('Add Translation'),parent,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        win.set_has_separator(True)
        win.vbox.set_spacing(5)
        win.set_property('default-width', 600)
        win.set_property('default-height', 400)
        win.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        win.set_icon(TRYTON_ICON)

        accel_group = gtk.AccelGroup()
        win.add_accel_group(accel_group)

        but_cancel = win.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)

        but_ok = win.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        but_ok.add_accelerator('clicked', accel_group, gtk.keysyms.Return,
                gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

        vbox = gtk.VBox(spacing=5)

        entries_list = []
        table = gtk.Table(len(langs), 2)
        table.set_homogeneous(False)
        table.set_col_spacings(3)
        table.set_row_spacings(0)
        table.set_border_width(1)
        i = 0
        for lang in langs:
            context = copy.copy(rpc.CONTEXT)
            context['language'] = lang['code']
            try:
                val = rpc.execute('model', model_name,
                        'read', [obj_id], [name], context)
            except TrytonServerError, exception:
                common.process_exception(exception)
                return False
            val = val[0]
            if gtk.widget_get_default_direction() == gtk.TEXT_DIR_RTL:
                label = gtk.Label(_(':') + lang['name'])
            else:
                label = gtk.Label(lang['name'] + _(':'))
            label.set_alignment(1.0, 0.5)
            (entry, yoptions) = widget_duplicate(widget_entry)

            hbox = gtk.HBox(homogeneous=False)
            if code == lang['code']:
                value_set(entry, value_get(widget_entry))
            else:
                value_set(entry, val[name])

            entries_list.append((val['id'], lang['code'], entry))
            table.attach(label, 0, 1, i, i+1, yoptions=False, xoptions=gtk.FILL,
                    ypadding=2, xpadding=3)
            table.attach(entry, 1, 2, i, i+1, yoptions=yoptions,
                    ypadding=2, xpadding=3)
            i += 1

        vbox.pack_start(table)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(vbox)
        scrolledwindow = gtk.ScrolledWindow()
        scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                gtk.POLICY_AUTOMATIC)
        scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        scrolledwindow.add(viewport)
        win.vbox.add(scrolledwindow)
        win.show_all()

        data = []
        response = win.run()
        if response == gtk.RESPONSE_OK:
            to_save = [(x[0], x[1], value_get(x[2])) for x in entries_list]
            while to_save != []:
                new_val = {}
                new_val['id'], new_val['code'], new_val['value'] = \
                        to_save.pop()
                #update form field
                if new_val['code'] == code:
                    value_set(widget_entry, new_val['value'])
                context = copy.copy(rpc.CONTEXT)
                context['language'] = new_val['code']
                args = ('model', model_name, 'write', [obj_id],
                        {str(name):  new_val['value']}, context)
                try:
                    rpc.execute(*args)
                except TrytonServerError, exception:
                    common.process_exception(exception, *args)
        if response != gtk.RESPONSE_CANCEL:
            self.screen.current_record.reload()
        win.destroy()
        parent.present()
        return response != gtk.RESPONSE_CANCEL

from calendar import Calendar, DateTime
from float import Float
from integer import Integer
from selection import Selection
from char import Char, Sha
from float_time import FloatTime
from checkbox import CheckBox
from reference import Reference
from binary import Binary
from textbox import TextBox
from one2many import One2Many
from many2many import Many2Many
from many2one import Many2One
from url import Email, URL, CallTo, SIP
from image import Image as Image2
from progressbar import ProgressBar
from one2one import One2One


WIDGETS_TYPE = {
    'date': (Calendar, 1, False, False),
    'datetime': (DateTime, 1, False, False),
    'float': (Float, 1, False, False),
    'numeric': (Float, 1, False, False),
    'integer': (Integer, 1, False, False),
    'biginteger': (Integer, 1, False, False),
    'selection': (Selection, 1, False, False),
    'char': (Char, 1, False, False),
    'sha': (Sha, 1, False, False),
    'float_time': (FloatTime, 1, False, False),
    'boolean': (CheckBox, 1, False, False),
    'reference': (Reference, 1, False, False),
    'binary': (Binary, 1, False, False),
    'text': (TextBox, 1, True, True),
    'one2many': (One2Many, 1, True, True),
    'many2many': (Many2Many, 1, True, True),
    'many2one': (Many2One, 1, False, False),
    'email' : (Email, 1, False, False),
    'url' : (URL, 1, False, False),
    'callto' : (CallTo, 1, False, False),
    'sip' : (SIP, 1, False, False),
    'image' : (Image2, 1, False, False),
    'progressbar': (ProgressBar, 1, False, False),
    'one2one': (One2One, 1, False, False),
}
