# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext

from tryton.gui.window.view_form.view.form import Container, FormXMLViewParser
from tryton.common import node_attributes
from .action import Action

_ = gettext.gettext


class BoardXMLViewParser(FormXMLViewParser):

    def _parse_board(self, node, attributes):
        container_attributes = node_attributes(node)
        container = Container.constructor(
            int(container_attributes.get('col', 4)),
            container_attributes.get('homogeneous', False))
        self.view.widget = container.container
        self.parse_child(node, container)
        assert not self._containers

    def _parse_action(self, node, attributes):
        attributes.setdefault('yexpand', True)
        attributes.setdefault('yfill', True)
        action = Action(attributes, self.view.context)
        action.signal_connect(
            self.view, 'active-changed', self.view._active_changed)
        self.view.actions.append(action)
        self.container.add(action.widget, attributes)


class ViewBoard(object):
    'View board'
    widget = None
    xml_parser = BoardXMLViewParser

    def __init__(self, xml, context=None):
        self.context = context
        self.actions = []
        self.state_widgets = []
        self.xml_parser(self, None, {}).parse(xml)
        self.widget.show_all()
        self._active_changed(None)

    def widget_get(self):
        return self.widget

    def reload(self):
        for action in self.actions:
            action.display()
        for state_widget in self.state_widgets:
            state_widget.state_set(None)

    def _active_changed(self, event_action, *args):
        for action in self.actions:
            if action == event_action:
                continue
            action.update_domain(self.actions)
