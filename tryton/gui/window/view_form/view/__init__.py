# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from tryton.common import node_attributes


class View(object):
    view_type = None
    widget = None
    mnemonic_widget = None
    view_id = None
    modified = None
    editable = None
    children_field = None
    scroll = None

    def __init__(self, screen, xml):
        self.screen = screen
        self.fields = {}
        self.attributes = node_attributes(xml)
        screen.set_on_write(self.attributes.get('on_write'))

    def set_value(self):
        raise NotImplementedError

    def get_fields(self):
        raise NotImplementedError

    @property
    def selected_records(self):
        return []

    def get_buttons(self):
        raise NotImplementedError

    @staticmethod
    def parse(screen, xml, children_field):
        from .list import ViewTree
        from .form import ViewForm
        from .graph import ViewGraph
        from .calendar_ import ViewCalendar

        root, = xml.childNodes
        tagname = root.tagName
        if tagname == 'tree':
            return ViewTree(screen, root, children_field)
        elif tagname == 'form':
            return ViewForm(screen, root)
        elif tagname == 'graph':
            return ViewGraph(screen, root)
        elif tagname == 'calendar':
            return ViewCalendar(screen, root)
