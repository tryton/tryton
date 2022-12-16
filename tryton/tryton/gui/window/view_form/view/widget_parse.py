#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from interface import ParserInterface
import form_gtk
import list_gtk
import graph_gtk
#import calendar_gtk
from form import ViewForm
from list import ViewList
from graph import ViewGraph
#from calendar import ViewCalendar
from tryton.exceptions import TrytonError

PARSERS = {
    'form': form_gtk.ParserForm,
    'tree': list_gtk.ParserTree,
    'graph': graph_gtk.ParserGraph,
    #'calendar': calendar_gtk.parser_calendar,
}

PARSERS2 = {
    'form': ViewForm,
    'tree': ViewList,
    'graph': ViewGraph,
    #'calendar': ViewCalendar,
}


class WidgetParse(ParserInterface):

    def parse(self, screen, root_node, fields, children_field=None):
        widget = None
        for node in root_node.childNodes:
            if not node.nodeType == node.ELEMENT_NODE:
                continue
            if node.localName in PARSERS:
                widget = PARSERS[node.localName](self.parent, self.attrs,
                    screen, children_field)
                (wid, child, state_widgets, on_write, notebooks,
                    cursor_widget) = widget.parse(screen.model_name, node,
                        fields)
                screen.set_on_write(on_write)
                res = PARSERS2[node.localName](screen, wid, child,
                    state_widgets, notebooks, cursor_widget, children_field)
                res.title = widget.title
                widget = res
                break
            else:
                raise TrytonError('Unknow view mode: %s' % node.localName)
        return widget
