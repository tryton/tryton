# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
import xml.dom.minidom

from gi.repository import Gtk

from tryton.gui.window.view_form.view.form import Container
from tryton.common import node_attributes, IconFactory, get_align
from .action import Action

_ = gettext.gettext


class ViewBoard(object):
    'View board'

    def __init__(self, arch, context=None):
        self.context = context
        self.actions = []

        xml_dom = xml.dom.minidom.parseString(arch)
        for node in xml_dom.childNodes:
            if node.nodeType == node.ELEMENT_NODE:
                break

        self.attributes = node_attributes(node)
        self.widget = self.parse(node).container
        self.widget.show_all()

        self._active_changed(None)

    def parse(self, node, container=None):
        if not container:
            node_attrs = node_attributes(node)
            container = Container(int(node_attrs.get('col', 4)))
        for node in node.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            node_attrs = node_attributes(node)
            for i_field in ('yexpand', 'yfill', 'xexpand', 'xfill', 'colspan',
                    'position'):
                if i_field in node_attrs:
                    node_attrs[i_field] = int(node_attrs[i_field])

            parser = getattr(self, '_parse_%s' % node.tagName)
            parser(node, container, node_attrs)
        return container

    def _parse_image(self, node, container, attributes):
        container.add(
            IconFactory.get_image(attributes['name'], Gtk.IconSize.DIALOG),
            attributes)

    def _parse_separator(self, node, container, attributes):
        vbox = Gtk.VBox()
        if attributes.get('string'):
            label = Gtk.Label(label=attributes['string'])
            label.set_halign(get_align(attributes.get('xalign', 0.0)))
            label.set_valign(get_align(attributes.get('yalign', 0.5)))
            vbox.pack_start(
                label, expand=True, fill=True, padding=0)
        vbox.pack_start(
            Gtk.HSeparator(), expand=True, fill=True, padding=0)
        container.add(vbox, attributes)

    def _parse_label(self, node, container, attributes):
        if not attributes.get('string'):
            container.add(None, attributes)
            return
        label = Gtk.Label(label=attributes['string'])
        label.set_halign(get_align(attributes.get('xalign', 0.0)))
        label.set_halign(get_align(attributes.get('yalign', 0.5)))
        label.set_angle(int(attributes.get('angle', 0)))
        attributes.setdefault('xexpand', 0)
        container.add(label, attributes)

    def _parse_newline(self, node, container, attributes):
        container.add_row()

    def _parse_notebook(self, node, container, attributes):
        attributes.setdefault('yexpand', True)
        attributes.setdefault('yfill', True)
        notebook = Gtk.Notebook()
        notebook.set_scrollable(True)
        container.add(notebook, attributes)
        self.parse(node, notebook)

    def _parse_page(self, node, notebook, attributes):
        tab_box = Gtk.HBox(spacing=3)
        if '_' not in attributes['string']:
            attributes['string'] = '_' + attributes['string']
        label = Gtk.Label(label=attributes['string'])
        label.set_use_underline(True)
        tab_box.pack_start(label, expand=True, fill=True, padding=0)

        if 'icon' in attributes:
            tab_box.pack_start(IconFactory.get_image(
                    attributes['icon'], Gtk.IconSize.SMALL_TOOLBAR),
                expand=True, fill=True, padding=0)
        tab_box.show_all()

        viewport = Gtk.Viewport()
        viewport.set_shadow_type(Gtk.ShadowType.NONE)
        scrolledwindow = Gtk.ScrolledWindow()
        scrolledwindow.set_shadow_type(Gtk.ShadowType.NONE)
        scrolledwindow.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolledwindow.add(viewport)
        scrolledwindow.show_all()
        notebook.append_page(scrolledwindow, tab_box)
        container = self.parse(node)
        viewport.add(container.container)

    def _parse_group(self, node, container, attributes):
        group = self.parse(node)
        homogeneous = bool(attributes.get('homogeneous', False))
        group.container.set_column_homogeneous(homogeneous)
        group.container.set_row_homogeneous(homogeneous)
        frame = Gtk.Frame()
        frame.set_label(attributes.get('string'))
        if not attributes.get('string'):
            frame.set_shadow_type(Gtk.ShadowType.NONE)
        frame.set_border_width(0)
        frame.add(group.container)
        container.add(frame, attributes)

    def _parse_paned(self, node, container, attributes, Paned):
        attributes.setdefault('yexpand', True)
        attributes.setdefault('yfill', True)
        paned = Paned()
        if 'position' in attributes:
            paned.set_position(attributes['position'])
        container.add(paned, attributes)
        self.parse(node, paned)

    def _parse_hpaned(self, node, container, attributes):
        self._parse_paned(node, container, attributes, Gtk.HPaned)

    def _parse_vpaned(self, node, container, attributes):
        self._parse_paned(node, container, attributes, Gtk.VPaned)

    def _parse_child(self, node, paned, attributes):
        container = self.parse(node)
        if not paned.get_child1():
            pack = paned.pack1
        else:
            pack = paned.pack2
        pack(container.container, resize=True, shrink=True)

    def _parse_action(self, node, container, attributes):
        attributes.setdefault('yexpand', True)
        attributes.setdefault('yfill', True)
        action = Action(attributes, self.context)
        action.signal_connect(self, 'active-changed', self._active_changed)
        self.actions.append(action)
        container.add(action.widget, attributes)

    def widget_get(self):
        return self.widget

    def reload(self):
        for action in self.actions:
            action.display()

    def _active_changed(self, event_action, *args):
        for action in self.actions:
            if action == event_action:
                continue
            action.update_domain(self.actions)
