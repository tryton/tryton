#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from functools import wraps

from interface import ParserView


def goocalendar_required(func):
    "Decorator for goocalendar required"
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if 'goocalendar' not in self.children:
            return
        return func(self, *args, **kwargs)
    return wrapper


class ViewCalendar(ParserView):

    def __init__(self, screen, widget, children=None, buttons=None,
            notebooks=None, cursor_widget=None, children_field=None):
        super(ViewCalendar, self).__init__(screen, widget, children, buttons,
            notebooks, cursor_widget, children_field)
        self.view_type = 'calendar'
        self.editable = False

    def __getitem__(self, name):
        return None

    @goocalendar_required
    def destroy(self):
        self.widget.destroy()
        self.children['goocalendar'].destroy()

    @goocalendar_required
    def get_selected_date(self):
        return self.children['goocalendar'].selected_date

    @goocalendar_required
    def set_default_date(self, record, selected_date):
        self.children['goocalendar'].set_default_date(record, selected_date)

    def current_domain(self):
        if 'goocalendar' in self.children:
            return self.children['goocalendar'].current_domain()
        else:
            # No need to load any record as nothing will be shown
            return [('id', '=', -1)]

    def cancel(self):
        pass

    def set_value(self):
        pass

    def reset(self):
        pass

    @goocalendar_required
    def display(self):
        self.children['goocalendar'].display(self.screen.group)
        gtkcal = self.children['toolbar'].gtkcal
        if gtkcal and not gtkcal.is_drawable():
            import goocanvas
            # disable gtk.Calendar if it is not drawable anymore
            self.children['toolbar'].gtkcal_item.set_property('visibility',
                goocanvas.ITEM_INVISIBLE)
            self.children['toolbar'].current_page.set_active(False)

    def set_cursor(self, new=False, reset_view=True):
        pass

    def get_fields(self):
        return []
