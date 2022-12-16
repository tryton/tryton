# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import operator
import gtk
import gettext
from collections import defaultdict

from . import View
from tryton.common.focus import (get_invisible_ancestor, find_focused_child,
    next_focus_widget, find_focusable_child, find_first_focus_widget)
from tryton.common import Tooltips, node_attributes, IconFactory
from tryton.common.underline import set_underline
from tryton.common.button import Button
from tryton.config import CONFIG
from .form_gtk.calendar import Date, Time, DateTime
from .form_gtk.float import Float
from .form_gtk.integer import Integer
from .form_gtk.selection import Selection
from .form_gtk.char import Char, Password
from .form_gtk.timedelta import TimeDelta
from .form_gtk.checkbox import CheckBox
from .form_gtk.reference import Reference
from .form_gtk.binary import Binary
from .form_gtk.textbox import TextBox
from .form_gtk.one2many import One2Many
from .form_gtk.many2many import Many2Many
from .form_gtk.many2one import Many2One
from .form_gtk.url import Email, URL, CallTo, SIP
from .form_gtk.image import Image as Image2
from .form_gtk.progressbar import ProgressBar
from .form_gtk.one2one import One2One
from .form_gtk.richtextbox import RichTextBox
from .form_gtk.dictionary import DictWidget
from .form_gtk.multiselection import MultiSelection
from .form_gtk.pyson import PYSON
from .form_gtk.state_widget import (Label, VBox, Image, Frame, ScrolledWindow,
    Notebook, Alignment, Expander)

_ = gettext.gettext


class Container(object):

    @staticmethod
    def constructor(col=4, homogeneous=False):
        if CONFIG['client.modepda']:
            col = 1
        if col <= 0:
            return HContainer(col, homogeneous)
        elif col == 1:
            return VContainer(col, homogeneous)
        else:
            return Container(col, homogeneous)

    def __init__(self, col=4, homogeneous=False):
        if col < 0:
            col = 0
        self.col = col
        self.table = gtk.Table(1, col)
        self.table.set_homogeneous(homogeneous)
        self.table.set_col_spacings(0)
        self.table.set_row_spacings(0)
        self.table.set_border_width(0)
        self.last = (0, 0)
        self.tooltips = Tooltips()
        self.tooltips.enable()

    def add_row(self):
        height, width = self.last
        self.table.resize(height + 1, self.col or width)
        self.last = (height + 1, 0)

    def add_col(self):
        height, width = self.last
        self.table.resize(height or 1, width + 1)
        self.last = (height, width + 1)

    def add(self, widget, attributes):

        colspan = attributes.get('colspan', 1)
        if self.col > 0:
            height, width = self.last
            if colspan > self.col:
                colspan = self.col

            if width + colspan > self.col:
                self.add_row()
        else:
            self.add_col()
        height, width = self.last
        self.last = height, width + colspan

        if not widget:
            return

        yopt = 0
        if attributes.get('yexpand'):
            yopt = gtk.EXPAND
        if attributes.get('yfill'):
            if yopt:
                yopt |= gtk.FILL
            else:
                yopt = gtk.FILL

        xopt = 0
        if attributes.get('xexpand', True):
            xopt = gtk.EXPAND
        if attributes.get('xfill', True):
            if xopt:
                xopt |= gtk.FILL
            else:
                xopt = gtk.FILL

        if attributes.get('help'):
            self.tooltips.set_tip(widget, attributes['help'])

        widget.show_all()
        self.table.attach(widget,
            width, width + colspan,
            height, height + 1,
            yoptions=yopt, xoptions=xopt,
            ypadding=1, xpadding=2)


class VContainer(Container):
    def __init__(self, col=1, homogeneous=False):
        self.col = 1
        self.table = gtk.VBox()
        self.table.set_homogeneous(homogeneous)

    def add_row(self):
        pass

    def add_col(self):
        pass

    def add(self, widget, attributes):
        if not widget:
            return
        expand = bool(int(attributes.get('yexpand', False)))
        fill = bool(int(attributes.get('yfill', False)))
        self.table.pack_start(widget, expand=expand, fill=fill, padding=2)


class HContainer(Container):
    def __init__(self, col=0, homogeneous=False):
        self.col = 0
        self.table = gtk.HBox()
        self.table.set_homogeneous(homogeneous)

    def add_row(self):
        pass

    def add_col(self):
        pass

    def add(self, widget, attributes):
        if not widget:
            return
        expand = bool(int(attributes.get('xexpand', True)))
        fill = bool(int(attributes.get('xfill', True)))
        self.table.pack_start(widget, expand=expand, fill=fill, padding=1)


class ViewForm(View):
    editable = True

    def __init__(self, screen, xml):
        super(ViewForm, self).__init__(screen, xml)
        self.view_type = 'form'
        self.widgets = defaultdict(list)
        self.state_widgets = []
        self.notebooks = []
        self.expandables = []

        container = self.parse(xml)

        vbox = gtk.VBox()
        vp = gtk.Viewport()
        vp.set_shadow_type(gtk.SHADOW_NONE)
        vp.add(container.table)
        self.scroll = scroll = gtk.ScrolledWindow()
        scroll.add(vp)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_placement(gtk.CORNER_TOP_LEFT)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        viewport.add(scroll)
        vbox.pack_start(viewport, expand=True, fill=True)

        self.widget = vbox
        self._viewport = vp

    def parse(self, node, container=None):
        if not container:
            node_attrs = node_attributes(node)
            container = Container.constructor(
                int(node_attrs.get('col', 4)),
                node_attrs.get('homogeneous', False))
        mnemonics = {}
        for node in node.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            node_attrs = node_attributes(node)
            for b_field in ('readonly', 'homogeneous'):
                if b_field in node_attrs:
                    node_attrs[b_field] = bool(int(node_attrs[b_field]))
            for i_field in ('yexpand', 'yfill', 'xexpand', 'xfill', 'colspan',
                    'position'):
                if i_field in node_attrs:
                    node_attrs[i_field] = int(node_attrs[i_field])

            parser = getattr(self, '_parse_%s' % node.tagName)
            widget = parser(node, container, node_attrs)
            if not widget:
                continue
            name = node_attrs.get('name')
            if node.tagName == 'label' and name:
                mnemonics[name] = widget
            if node.tagName == 'field':
                if name in mnemonics and widget.mnemonic_widget:
                    label = mnemonics.pop(name)
                    label.set_label(set_underline(label.get_label()))
                    label.set_use_underline(True)
                    label.set_mnemonic_widget(widget.mnemonic_widget)
        return container

    def _parse_image(self, node, container, attributes):
        image = Image(attrs=attributes)
        self.state_widgets.append(image)
        container.add(image, attributes)

    def _parse_separator(self, node, container, attributes):
        if 'name' in attributes:
            field = self.screen.group.fields[attributes['name']]
            for attr in ('states', 'string'):
                if attr not in attributes and attr in field.attrs:
                    attributes[attr] = field.attrs[attr]
        vbox = VBox(attrs=attributes)
        if attributes.get('string'):
            label = Label(attributes['string'], attrs=attributes)
            label.set_alignment(float(attributes.get('xalign', 0.0)),
                float(attributes.get('yalign', 0.5)))
            vbox.pack_start(label)
            self.state_widgets.append(label)
        vbox.pack_start(gtk.HSeparator())
        self.state_widgets.append(vbox)
        container.add(vbox, attributes)

    def _parse_label(self, node, container, attributes):
        if 'name' in attributes:
            field = self.screen.group.fields[attributes['name']]
            if attributes['name'] == self.screen.exclude_field:
                container.add(None, attributes)
                return
            if 'states' not in attributes and 'states' in field.attrs:
                attributes['states'] = field.attrs['states']
            if 'string' not in attributes:
                attributes['string'] = field.attrs['string'] + _(':')
        if CONFIG['client.modepda']:
            attributes['xalign'] = 0.0

        label = Label(attributes.get('string', ''), attrs=attributes)
        label.set_alignment(float(attributes.get('xalign', 1.0)),
            float(attributes.get('yalign', 0.5)))
        label.set_angle(int(attributes.get('angle', 0)))
        attributes.setdefault('xexpand', 0)
        self.state_widgets.append(label)
        container.add(label, attributes)
        return label

    def _parse_newline(self, node, container, attributes):
        container.add_row()

    def _parse_button(self, node, container, attributes):
        button = Button(attributes)
        button.connect('clicked', self.button_clicked)
        self.state_widgets.append(button)
        container.add(button, attributes)

    def _parse_notebook(self, node, container, attributes):
        attributes.setdefault('yexpand', True)
        attributes.setdefault('yfill', True)
        attributes.setdefault('colspan', 4)
        notebook = Notebook(attrs=attributes)
        notebook.set_scrollable(True)
        notebook.set_border_width(3)
        if attributes.get('height') or attributes.get('width'):
            notebook.set_size_request(
                int(attributes.get('width', -1)),
                int(attributes.get('height', -1)))

        # Force to display the first time it switches on a page
        # This avoids glitch in position of widgets
        def switch(notebook, page, page_num):
            if not self.widget:
                # Not yet finish to parse
                return
            notebook.grab_focus()
            self.display()
            notebook.disconnect(handler_id)
        handler_id = notebook.connect('switch-page', switch)
        self.state_widgets.append(notebook)

        self.notebooks.append(notebook)
        container.add(notebook, attributes)
        self.parse(node, notebook)

    def _parse_page(self, node, notebook, attributes):
        tab_box = gtk.HBox(spacing=3)
        if 'name' in attributes:
            field = self.screen.group.fields[attributes['name']]
            if attributes['name'] == self.screen.exclude_field:
                return
            for attr in ('states', 'string'):
                if attr not in attributes and attr in field.attrs:
                    attributes[attr] = field.attrs[attr]
        label = gtk.Label(set_underline(attributes['string']))
        label.set_use_underline(True)

        if 'icon' in attributes:
            tab_box.pack_start(IconFactory.get_image(
                    attributes['icon'], gtk.ICON_SIZE_SMALL_TOOLBAR))
        tab_box.pack_start(label)
        tab_box.show_all()

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        scrolledwindow = ScrolledWindow(attrs=attributes)
        scrolledwindow.set_shadow_type(gtk.SHADOW_NONE)
        scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolledwindow.add(viewport)
        scrolledwindow.show_all()
        self.state_widgets.append(scrolledwindow)
        notebook.append_page(scrolledwindow, tab_box)
        container = self.parse(node)
        viewport.add(container.table)

    def _parse_field(self, node, container, attributes):
        name = attributes['name']
        field = self.screen.group.fields[name]

        if (name not in self.screen.group.fields
                or name == self.screen.exclude_field):
            container.add(None, attributes)
            return

        if 'widget' not in attributes:
            attributes['widget'] = field.attrs['type']

        for i_field in ('width', 'height'):
            if i_field in attributes:
                attributes[i_field] = int(attributes[i_field])

        for attr in ('relation', 'domain', 'selection',
                'relation_field', 'string', 'help', 'views',
                'add_remove', 'sort', 'context', 'size', 'filename',
                'autocomplete', 'translate', 'create', 'delete',
                'selection_change_with', 'schema_model'):
            if attr in field.attrs and attr not in attributes:
                attributes[attr] = field.attrs[attr]

        Widget = self.get_widget(attributes['widget'])
        widget = Widget(self, attributes)
        self.widgets[name].append(widget)

        if Widget.expand:
            attributes.setdefault('yexpand', True)
            attributes.setdefault('yfill', True)

        if attributes.get('height') or attributes.get('width'):
            widget.widget.set_size_request(
                int(attributes.get('width', -1)),
                int(attributes.get('height', -1)))
        container.add(Alignment(widget.widget, attributes), attributes)
        return widget

    def _parse_group(self, node, container, attributes):
        group = self.parse(node)
        if 'name' in attributes:
            field = self.screen.group.fields[attributes['name']]
            if attributes['name'] == self.screen.exclude_field:
                container.add(None, attributes)
                return
            for attr in ('states', 'string'):
                if attr not in attributes and attr in field.attrs:
                    attributes[attr] = field.attrs[attr]

        can_expand = attributes.get('expandable')
        if can_expand:
            widget = Expander(attributes.get('string'), attrs=attributes)
            widget.add(group.table)
            widget.set_expanded(can_expand == '1')
            self.expandables.append(widget)
        else:
            widget = Frame(attributes.get('string'), attrs=attributes)
            widget.add(group.table)

        self.state_widgets.append(widget)
        container.add(widget, attributes)

    def _parse_paned(self, node, container, attributes, Paned):
        attributes.setdefault('yexpand', True)
        attributes.setdefault('yfill', True)
        paned = Paned()
        if 'position' in attributes:
            paned.set_position(attributes['position'])
        container.add(paned, attributes)
        self.parse(node, paned)

    def _parse_hpaned(self, node, container, attributes):
        self._parse_paned(node, container, attributes, gtk.HPaned)

    def _parse_vpaned(self, node, container, attributes):
        self._parse_paned(node, container, attributes, gtk.VPaned)

    def _parse_child(self, node, paned, attributes):
        container = self.parse(node)
        if not paned.get_child1():
            pack = paned.pack1
        else:
            pack = paned.pack2
        pack(container.table, resize=True, shrink=True)

    WIDGETS = {
        'date': Date,
        'datetime': DateTime,
        'time': Time,
        'timestamp': DateTime,
        'float': Float,
        'numeric': Float,
        'integer': Integer,
        'biginteger': Integer,
        'selection': Selection,
        'char': Char,
        'password': Password,
        'timedelta': TimeDelta,
        'boolean': CheckBox,
        'reference': Reference,
        'binary': Binary,
        'text': TextBox,
        'one2many': One2Many,
        'many2many': Many2Many,
        'many2one': Many2One,
        'email': Email,
        'url': URL,
        'callto': CallTo,
        'sip': SIP,
        'image': Image2,
        'progressbar': ProgressBar,
        'one2one': One2One,
        'richtext': RichTextBox,
        'dict': DictWidget,
        'multiselection': MultiSelection,
        'pyson': PYSON,
        }

    @classmethod
    def get_widget(cls, name):
        return cls.WIDGETS[name]

    def get_fields(self):
        return list(self.widgets.keys())

    def __getitem__(self, name):
        return self.widgets[name][0]

    def destroy(self):
        for widget_name in list(self.widgets.keys()):
            for widget in self.widgets[widget_name]:
                widget.destroy()
        self.widget.destroy()

    def set_value(self, focused_widget=False):
        record = self.screen.current_record
        if record:
            for name, widgets in self.widgets.items():
                if name in record.group.fields:
                    field = record.group.fields[name]
                    for widget in widgets:
                        if (not focused_widget
                                or widget.widget.is_focus()
                                or (isinstance(widget.widget, gtk.Container)
                                    and widget.widget.get_focus_child())):
                            widget.set_value(record, field)

    @property
    def selected_records(self):
        if self.screen.current_record:
            return [self.screen.current_record]
        return []

    @property
    def modified(self):
        return any(w.modified for widgets in self.widgets.values()
            for w in widgets)

    def get_buttons(self):
        return [b for b in self.state_widgets if isinstance(b, Button)]

    def reset(self):
        record = self.screen.current_record
        if record:
            for name, widgets in self.widgets.items():
                field = record.group.fields.get(name)
                if field and 'invalid' in field.get_state_attrs(record):
                    for widget in widgets:
                        field.get_state_attrs(record)['invalid'] = False
                        widget.display(record, field)

    def display(self):
        record = self.screen.current_record
        if record:
            # Force to set fields in record
            # Get first the lazy one from the view to reduce number of requests
            fields = ((name, record.group.fields[name])
                for name in self.widgets)
            fields = (
                (name,
                    field.attrs.get('loading', 'eager') == 'eager',
                    len(field.views))
                for name, field in fields)
            fields = sorted(fields, key=operator.itemgetter(1, 2))
            for field, _, _ in fields:
                record[field].get(record)
        focused_widget = find_focused_child(self.widget)
        for name, widgets in self.widgets.items():
            field = None
            if record:
                field = record.group.fields.get(name)
            if field:
                field.state_set(record)
            for widget in widgets:
                widget.display(record, field)
        for widget in self.state_widgets:
            widget.state_set(record)
        if focused_widget:
            invisible_ancestor = get_invisible_ancestor(focused_widget)
            if invisible_ancestor:
                new_focused_widget = next_focus_widget(invisible_ancestor)
                if new_focused_widget:
                    new_focused_widget.grab_focus()
        return True

    def set_cursor(self, new=False, reset_view=True):
        focus_widget = None
        if reset_view or not self.widget.has_focus():
            if reset_view:
                for notebook in self.notebooks:
                    notebook.set_current_page(0)
            if self.attributes.get('cursor') in self.widgets:
                focus_widget = find_focusable_child(self.widgets[
                        self.attributes['cursor']][0].widget)
            else:
                child = find_focusable_child(self._viewport)
                if child:
                    child.grab_focus()
        record = self.screen.current_record
        if record:
            invalid_widgets = []
            for name in record.invalid_fields:
                widgets = self.widgets.get(name, [])
                for widget in widgets:
                    invalid_widget = find_focusable_child(widget.widget)
                    if invalid_widget:
                        invalid_widgets.append(invalid_widget)
            if invalid_widgets:
                focus_widget = find_first_focus_widget(
                    self._viewport, invalid_widgets)
        if focus_widget:
            for notebook in self.notebooks:
                for i in range(notebook.get_n_pages()):
                    child = notebook.get_nth_page(i)
                    if focus_widget.is_ancestor(child):
                        notebook.set_current_page(i)
            for group in self.expandables:
                if focus_widget.is_ancestor(group):
                    group.set_expanded(True)
            focus_widget.grab_focus()

    def button_clicked(self, widget):
        widget.handler_block_by_func(self.button_clicked)
        try:
            self.screen.button(widget.attrs)
        finally:
            widget.handler_unblock_by_func(self.button_clicked)
