#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'View board'

from parser import ParserBoard
import xml.dom.minidom

class ViewBoard(object):
    'View board'

    def __init__(self, arch, window, context=None):
        self.window = window

        xml_dom = xml.dom.minidom.parseString(arch)
        parser = ParserBoard(window)
        for node in xml_dom.childNodes:
            if not node.nodeType == node.ELEMENT_NODE:
                continue
            self.widget, self.widgets = parser.parse(node)
            break
        self.widget.show_all()

    def widget_get(self):
        return self.widget

    def reload(self):
        for widget in self.widgets:
            widget.display()
