# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import operator
import gettext

from gi.repository import Gtk

from . import View, XMLViewParser
from tryton.common.focus import (get_invisible_ancestor, find_focused_child,
    next_focus_widget, find_focusable_child, find_first_focus_widget)
from tryton.common import Tooltips, node_attributes, IconFactory, get_align
from tryton.common.underline import set_underline
from tryton.common.button import Button
from tryton.config import CONFIG
from .form_gtk.calendar_ import Date, Time, DateTime
from .form_gtk.document import Document
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
from .form_gtk.url import Email, URL, CallTo, SIP, HTML
from .form_gtk.image import Image as Image2
from .form_gtk.progressbar import ProgressBar
from .form_gtk.one2one import One2One
from .form_gtk.richtextbox import RichTextBox
from .form_gtk.dictionary import DictWidget
from .form_gtk.multiselection import MultiSelection
from .form_gtk.pyson import PYSON
from .form_gtk.state_widget import (Label, VBox, Image, Frame, ScrolledWindow,
    Notebook, Expander, Link)

_ = gettext.gettext


class _Container(object):

    def __init__(self, col=4, homogeneous=False):
        super().__init__()
        if col < 0:
            col = 0
        self.col = col
        self.tooltips = Tooltips()
        self.tooltips.enable()

    def add_row(self):
        raise NotImplementedError

    def add_col(self):
        raise NotImplementedError

    def add(self, widget, attributes):
        if widget and attributes.get('help'):
            self.tooltips.set_tip(widget, attributes['help'])

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


class Container(_Container):

    def __init__(self, col=4, homogeneous=False):
        super().__init__(col=col, homogeneous=homogeneous)
        self.container = Gtk.Grid(
            column_spacing=3, row_spacing=3,
            column_homogeneous=homogeneous, row_homogeneous=homogeneous,
            border_width=3)
        self.last = (0, 0)

    def add_row(self):
        height, width = self.last
        self.last = (height + 1, 0)

    def add_col(self):
        height, width = self.last
        self.last = (height, width + 1)

    def add(self, widget, attributes):
        super().add(widget, attributes)

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

        if widget:
            widget.set_vexpand(bool(attributes.get('yexpand')))
            widget.set_hexpand(bool(attributes.get('xexpand', True)))
            widget.show_all()
            self.container.attach(widget, width, height, colspan, 1)


class VContainer(_Container):
    def __init__(self, col=1, homogeneous=False):
        col = 1
        super().__init__(col=col, homogeneous=homogeneous)
        self.container = Gtk.VBox()
        self.container.set_homogeneous(homogeneous)

    def add_row(self):
        pass

    def add_col(self):
        pass

    def add(self, widget, attributes):
        super().add(widget, attributes)
        if widget:
            expand = bool(int(attributes.get('yexpand', False)))
            fill = bool(int(attributes.get('yfill', False)))
            self.container.pack_start(
                widget, expand=expand, fill=fill, padding=2)


class HContainer(_Container):
    def __init__(self, col=0, homogeneous=False):
        col = 0
        super().__init__(col=col, homogeneous=homogeneous)
        self.container = Gtk.HBox()
        self.container.set_homogeneous(homogeneous)

    def add_row(self):
        pass

    def add_col(self):
        pass

    def add(self, widget, attributes):
        super().add(widget, attributes)
        if widget:
            expand = bool(int(attributes.get('xexpand', True)))
            fill = bool(int(attributes.get('xfill', True)))
            self.container.pack_start(
                widget, expand=expand, fill=fill, padding=1)


class FormXMLViewParser(XMLViewParser):

    WIDGETS = {
        'biginteger': Integer,
        'binary': Binary,
        'boolean': CheckBox,
        'callto': CallTo,
        'char': Char,
        'date': Date,
        'datetime': DateTime,
        'dict': DictWidget,
        'document': Document,
        'email': Email,
        'float': Float,
        'html': HTML,
        'image': Image2,
        'integer': Integer,
        'many2many': Many2Many,
        'many2one': Many2One,
        'multiselection': MultiSelection,
        'numeric': Float,
        'one2many': One2Many,
        'one2one': One2One,
        'password': Password,
        'progressbar': ProgressBar,
        'pyson': PYSON,
        'reference': Reference,
        'richtext': RichTextBox,
        'selection': Selection,
        'sip': SIP,
        'text': TextBox,
        'time': Time,
        'timedelta': TimeDelta,
        'timestamp': DateTime,
        'url': URL,
        }

    def __init__(self, view, exclude_field, field_attrs):
        super().__init__(view, exclude_field, field_attrs)
        self._containers = []
        self._mnemonics = {}

    @property
    def container(self):
        if self._containers:
            return self._containers[-1]
        return None

    def _parse_form(self, node, attributes):
        container_attributes = node_attributes(node)
        container = Container.constructor(
            int(container_attributes.get('col', 4)),
            container_attributes.get('homogeneous', False))
        self.view.viewport.add(container.container)
        self.parse_child(node, container)
        assert not self._containers

    def parse_child(self, node, container=None):
        if container:
            self._containers.append(container)
        for child in node.childNodes:
            self.parse(child)
        if container:
            self._containers.pop()

    def _parse_field(self, node, attributes):
        name = attributes['name']
        if name and name == self.exclude_field:
            self.container.add(None, attributes)
            return

        widget = self.WIDGETS[attributes['widget']](self.view, attributes)
        self.view.widgets[name].append(widget)

        if widget.expand:
            attributes.setdefault('yexpand', True)
            attributes.setdefault('yfill', True)

        if attributes.get('height') or attributes.get('width'):
            widget.widget.set_size_request(
                int(attributes.get('width', -1)),
                int(attributes.get('height', -1)))

        widget.widget.set_halign(get_align(
                attributes.get('xalign', 0.5),
                bool(attributes.get('xexpand', True))))
        widget.widget.set_valign(get_align(
                attributes.get('yalign', 0.5),
                bool(attributes.get('yexpand'))))
        self.container.add(widget.widget, attributes)

        if name in self._mnemonics and widget.mnemonic_widget:
            label = self._mnemonics.pop(name)
            label.set_label(set_underline(label.get_label()))
            label.set_use_underline(True)
            label.set_mnemonic_widget(widget.mnemonic_widget)

    def _parse_button(self, node, attributes):
        button = Button(attributes)
        button.connect('clicked', self.view.button_clicked)
        self.view.state_widgets.append(button)
        self.container.add(button, attributes)

    def _parse_link(self, node, attributes):
        link = Link(attrs=attributes)
        self.view.state_widgets.append(link)
        self.container.add(link, attributes)

    def _parse_image(self, node, attributes):
        image = Image(attrs=attributes)
        self.view.state_widgets.append(image)
        self.container.add(image, attributes)

    def _parse_separator(self, node, attributes):
        name = attributes.get('name')
        if name and name == self.exclude_field:
            self.container.add(None, attributes)
            return
        vbox = VBox(attrs=attributes)
        if attributes.get('string'):
            label = Label(label=attributes['string'], attrs=attributes)
            label.set_halign(get_align(
                    attributes.get('xalign', 0.0),
                    bool(attributes.get('xexpand', True))))
            label.set_valign(get_align(
                    attributes.get('yalign', 0.5),
                    bool(attributes.get('yexpand', False))))
            vbox.pack_start(label, expand=True, fill=True, padding=0)
            self.view.state_widgets.append(label)
            if name:
                self._mnemonics[name] = label
        vbox.pack_start(Gtk.HSeparator(), expand=True, fill=True, padding=0)
        self.view.state_widgets.append(vbox)
        self.container.add(vbox, attributes)

    def _parse_label(self, node, attributes):
        name = attributes.get('name')
        if name and name == self.exclude_field:
            self.container.add(None, attributes)
            return
        if CONFIG['client.modepda']:
            attributes['xalign'] = 0.0

        attributes.setdefault('xexpand', 0)
        label = Label(label=attributes.get('string', ''), attrs=attributes)
        label.set_halign(get_align(
                attributes.get('xalign', 1.0),
                bool(attributes.get('xexpand'))))
        label.set_valign(get_align(
                attributes.get('yalign', 0.5),
                bool(attributes.get('yexpand'))))
        label.set_angle(int(attributes.get('angle', 0)))
        self.view.state_widgets.append(label)
        self.container.add(label, attributes)
        if name:
            self._mnemonics[name] = label

    def _parse_newline(self, node, attributes):
        self.container.add_row()

    def _parse_notebook(self, node, attributes):
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
            if not self.view.widget:
                # Not yet finish to parse
                return
            notebook.grab_focus()
            self.view.display()
            notebook.disconnect(handler_id)
        handler_id = notebook.connect('switch-page', switch)
        self.view.state_widgets.append(notebook)

        self.view.notebooks.append(notebook)
        self.container.add(notebook, attributes)
        self.parse_child(node, notebook)

    def _parse_page(self, node, attributes):
        tab_box = Gtk.HBox(spacing=3)
        if 'name' in attributes and attributes['name'] == self.exclude_field:
            return
        label = Gtk.Label(label=set_underline(attributes['string']))
        label.set_use_underline(True)

        if 'icon' in attributes:
            tab_box.pack_start(IconFactory.get_image(
                    attributes['icon'], Gtk.IconSize.SMALL_TOOLBAR),
                expand=True, fill=True, padding=0)
        tab_box.pack_start(label, expand=True, fill=True, padding=0)
        tab_box.show_all()

        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.NONE)
        scrolledwindow = ScrolledWindow(attrs=attributes)
        scrolledwindow.set_shadow_type(Gtk.ShadowType.NONE)
        scrolledwindow.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolledwindow.add(viewport)
        scrolledwindow.show_all()
        self.view.state_widgets.append(scrolledwindow)
        self.container.append_page(scrolledwindow, tab_box)
        container = Container.constructor(
            int(attributes.get('col', 4)),
            attributes.get('homogeneous', False))
        self.parse_child(node, container)
        viewport.add(container.container)

    def _parse_group(self, node, attributes):
        group = Container.constructor(
            int(attributes.get('col', 4)),
            attributes.get('homogeneous', False))
        self.parse_child(node, group)

        if 'name' in attributes and attributes['name'] == self.exclude_field:
            self.container.add(None, attributes)
            return

        can_expand = attributes.get('expandable')
        if can_expand:
            widget = Expander(label=attributes.get('string'), attrs=attributes)
            widget.add(group.container)
            widget.set_expanded(can_expand == '1')
            self.view.expandables.append(widget)
        else:
            widget = Frame(label=attributes.get('string'), attrs=attributes)
            widget.add(group.container)

        widget.set_halign(get_align(
                attributes.get('xalign', 0.5),
                bool(attributes.get('xexpand', True))))
        widget.set_valign(get_align(
                attributes.get('yalign', 0.5),
                bool(attributes.get('yexpand'))))
        self.view.state_widgets.append(widget)
        self.container.add(widget, attributes)

    def _parse_hpaned(self, node, attributes):
        self._parse_paned(node, attributes, Gtk.HPaned)

    def _parse_vpaned(self, node, attributes):
        self._parse_paned(node, attributes, Gtk.VPaned)

    def _parse_paned(self, node, attributes, Paned):
        attributes.setdefault('yexpand', True)
        attributes.setdefault('yfill', True)
        paned = Paned()
        if 'position' in attributes:
            paned.set_position(attributes['position'])
        self.container.add(paned, attributes)
        self.parse_child(node, paned)

    def _parse_child(self, node, attributes):
        paned = self.container
        container = Container.constructor(
            int(attributes.get('col', 4)),
            attributes.get('homogeneous', False))
        self.parse_child(node, container)
        if not paned.get_child1():
            pack = paned.pack1
        else:
            pack = paned.pack2
        pack(container.container, resize=True, shrink=True)


class ViewForm(View):
    editable = True
    view_type = 'form'
    xml_parser = FormXMLViewParser

    def __init__(self, view_id, screen, xml):
        self.notebooks = []
        self.expandables = []

        vbox = Gtk.VBox()
        vp = Gtk.Viewport()
        vp.set_shadow_type(Gtk.ShadowType.NONE)
        self.scroll = scroll = Gtk.ScrolledWindow()
        scroll.add(vp)
        scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_placement(Gtk.CornerType.TOP_LEFT)
        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        viewport.add(scroll)
        vbox.pack_start(viewport, expand=True, fill=True, padding=0)

        self.widget = vbox
        self.viewport = vp

        super().__init__(view_id, screen, xml)

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
        record = self.record
        if record:
            for name, widgets in self.widgets.items():
                if name in record.group.fields:
                    for widget in widgets:
                        if (not focused_widget
                                or widget.widget.is_focus()
                                or (isinstance(widget.widget, Gtk.Container)
                                    and widget.widget.get_focus_child())):
                            widget.set_value()

    @property
    def selected_records(self):
        if self.record:
            return [self.record]
        return []

    @property
    def modified(self):
        return any(w.modified for widgets in self.widgets.values()
            for w in widgets)

    def get_buttons(self):
        return [b for b in self.state_widgets if isinstance(b, Button)]

    def reset(self):
        record = self.record
        if record:
            for name, widgets in self.widgets.items():
                field = record.group.fields.get(name)
                if field and 'invalid' in field.get_state_attrs(record):
                    for widget in widgets:
                        field.get_state_attrs(record)['invalid'] = False
                        widget.display()

    def display(self):
        record = self.record
        if record:
            # Force to set fields in record
            # Get first the lazy one from the view to reduce number of requests
            field_names = set()
            for name in self.widgets:
                field = record.group.fields[name]
                field_names.add(name)
                field_names.update(f for f in field.attrs.get('depends', [])
                    if (not f.startswith('_parent')
                        and f in record.group.fields))
            fields = []
            for name in field_names:
                field = record.group.fields[name]
                fields.append(
                    (name, field.attrs.get('loading', 'eager') == 'eager',
                        len(field.views)))
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
                widget.display()
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
                child = find_focusable_child(self.viewport)
                if child:
                    child.grab_focus()
        record = self.record
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
                    self.viewport, invalid_widgets)
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
