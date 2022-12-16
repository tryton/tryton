#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Interfaces"


class ParserInterface(object):

    def __init__(self, parent=None, attrs=None, screen=None,
            children_field=None):
        self.parent = parent
        self.attrs = attrs
        self.title = None
        self.state_widgets = {}
        self.screen = screen
        self.children_field = children_field


class ParserView(object):

    def __init__(self, screen, widget, children=None, state_widgets=None,
            notebooks=None, cursor_widget=None, children_field=None):
        self.screen = screen
        self.widget = widget
        self.children = children
        if state_widgets is None:
            state_widgets = []
        self.state_widgets = state_widgets
        if notebooks is None:
            notebooks = []
        self.notebooks = notebooks
        self.cursor_widget = cursor_widget
        self.children_field = children_field

    def get_fields(self):
        return self.children.keys()

    @property
    def modified(self):
        return False
