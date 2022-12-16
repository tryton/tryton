#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Interfaces"


class ParserInterface(object):

    def __init__(self, window, parent=None, attrs=None, screen=None):
        self.window = window
        self.parent = parent
        self.attrs = attrs
        self.title = None
        self.buttons = {}
        self.screen = screen


class ParserView(object):

    def __init__(self, window, screen, widget, children=None, buttons=None,
            toolbar=None, notebooks=None, cursor_widget=None):
        self.window = window
        self.screen = screen
        self.widget = widget
        self.children = children
        if buttons is None:
            buttons = []
        self.buttons = buttons
        self.toolbar = toolbar
        if notebooks is None:
            notebooks = []
        self.notebooks = notebooks
        self.cursor_widget = cursor_widget
