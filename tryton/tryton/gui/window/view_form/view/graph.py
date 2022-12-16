#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from interface import ParserView


class ViewGraph(ParserView):

    def __init__(self, screen, widget, children=None, state_widgets=None,
            notebooks=None, cursor_widget=None, children_field=None):
        super(ViewGraph, self).__init__(screen, widget, children,
            state_widgets, notebooks, cursor_widget, children_field)
        self.view_type = 'graph'
        self.widgets = children
        self.editable = False

    def __getitem__(self, name):
        return None

    def destroy(self):
        self.widget.destroy()
        for widget in self.widgets.keys():
            self.widgets[widget].destroy()
            del self.widgets[widget]

    def set_value(self):
        pass

    def reset(self):
        pass

    def display(self):
        for widget in self.widgets.itervalues():
            widget.display(self.screen.group)
        return True

    def set_cursor(self, new=False, reset_view=True):
        pass

    def get_fields(self):
        return []
