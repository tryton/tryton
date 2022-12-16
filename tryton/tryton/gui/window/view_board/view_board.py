#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'View board'

import xml.dom.minidom
from parser import ParserBoard
from tryton.gui.window.view_board.action import Action


class ViewBoard(object):
    'View board'

    def __init__(self, arch, context=None):
        self.context = context

        xml_dom = xml.dom.minidom.parseString(arch)
        parser = ParserBoard(context)
        for node in xml_dom.childNodes:
            if not node.nodeType == node.ELEMENT_NODE:
                continue
            self.widget, self.widgets = parser.parse(node)
            break
        self.actions = [x for x in self.widgets if isinstance(x, Action)]
        for action in self.actions:
            action.signal_connect(self, 'active-changed',
                    self._active_changed)
        self.widget.show_all()
        self._active_changed(None)

    def widget_get(self):
        return self.widget

    def reload(self):
        for widget in self.widgets:
            widget.display()

    def _active_changed(self, event_action, *args):
        for action in self.actions:
            if action == event_action:
                continue
            action.update_domain(self.actions)
