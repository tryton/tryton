# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys

import gettext

from gi.repository import Gtk

from . import View
from .graph_gtk.bar import VerticalBar, HorizontalBar
from .graph_gtk.line import Line
from .graph_gtk.pie import Pie
from tryton.common import file_selection, IconFactory
from tryton.common import node_attributes, get_toplevel_window, message
from tryton.common.underline import set_underline
from tryton.config import TRYTON_ICON
from tryton.gui import Main

_ = gettext.gettext


class ViewGraph(View):

    def __init__(self, screen, xml):
        super(ViewGraph, self).__init__(screen, xml)
        self.view_type = 'graph'
        self.widgets = {}
        self.widget = self.parse(xml)

    def parse(self, node):
        xfield = None
        yfields = []

        for node in node.childNodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue
            if node.tagName == 'x':
                for child in node.childNodes:
                    if not child.nodeType == child.ELEMENT_NODE:
                        continue
                    xfield = node_attributes(child)
                    field = self.screen.group.fields[xfield['name']]
                    if not xfield.get('string'):
                        xfield['string'] = field.attrs['string']
            elif node.tagName == 'y':
                for child in node.childNodes:
                    if not child.nodeType == child.ELEMENT_NODE:
                        continue
                    yattrs = node_attributes(child)
                    if not yattrs.get('string') and yattrs['name'] != '#':
                        field = self.screen.group.fields[yattrs['name']]
                        yattrs['string'] = field.attrs['string']
                    yfields.append(yattrs)

        Widget = self.get_widget(self.attributes.get('type', 'vbar'))
        widget = Widget(self, xfield, yfields)
        self.widgets['root'] = widget
        event = Gtk.EventBox()
        event.add(widget)
        event.connect('button-press-event', self.button_press)
        return event

    WIDGETS = {
        'vbar': VerticalBar,
        'hbar': HorizontalBar,
        'line': Line,
        'pie': Pie,
        }

    @classmethod
    def get_widget(cls, name):
        return cls.WIDGETS[name]

    def __getitem__(self, name):
        return None

    def destroy(self):
        self.widget.destroy()
        self.widgets['root'].destroy()
        self.widgets.clear()

    def set_value(self):
        pass

    def reset(self):
        pass

    def display(self):
        self.widgets['root'].display(self.screen.group)
        return True

    def set_cursor(self, new=False, reset_view=True):
        pass

    def get_fields(self):
        return []

    def get_buttons(self):
        return []

    def save(self, widget):
        parent = get_toplevel_window()
        dia = Gtk.Dialog(
            title=_('Image Size'), transient_for=parent, modal=True,
            destroy_with_parent=True)
        Main().add_window(dia)
        cancel_button = dia.add_button(
            set_underline(_("Cancel")), Gtk.ResponseType.CANCEL)
        cancel_button.set_image(IconFactory.get_image(
                'tryton-cancel', Gtk.IconSize.BUTTON))
        cancel_button.set_always_show_image(True)
        ok_button = dia.add_button(
            set_underline(_("OK")), Gtk.ResponseType.OK)
        ok_button.set_image(IconFactory.get_image(
                'tryton-ok', Gtk.IconSize.BUTTON))
        ok_button.set_always_show_image(True)
        dia.set_icon(TRYTON_ICON)
        dia.set_default_response(Gtk.ResponseType.OK)

        hbox = Gtk.HBox(spacing=3)
        dia.vbox.pack_start(hbox, expand=False, fill=True, padding=0)

        hbox.pack_start(
            Gtk.Label(label=_('Width:')), expand=False, fill=True, padding=0)
        spinwidth = Gtk.SpinButton()
        spinwidth.configure(Gtk.Adjustment(
                value=400.0, lower=0.0, upper=sys.maxsize,
                step_increment=1.0, page_increment=10.0),
            climb_rate=1, digits=0)
        spinwidth.set_numeric(True)
        spinwidth.set_activates_default(True)
        hbox.pack_start(spinwidth, expand=True, fill=True, padding=0)

        hbox.pack_start(
            Gtk.Label(label=_('Height:')), expand=False, fill=True, padding=0)
        spinheight = Gtk.SpinButton()
        spinheight.configure(Gtk.Adjustment(
                value=200.0, lower=0.0, upper=sys.maxsize,
                step_increment=1.0, page_increment=10.0),
            climb_rate=1, digits=0)
        spinheight.set_numeric(True)
        spinheight.set_activates_default(True)
        hbox.pack_start(spinheight, expand=True, fill=True, padding=0)
        dia.show_all()

        filter = Gtk.FileFilter()
        filter.set_name(_('PNG image (*.png)'))
        filter.add_mime_type('image/png')
        filter.add_pattern('*.png')

        while True:
            response = dia.run()
            width = spinwidth.get_value_as_int()
            height = spinheight.get_value_as_int()
            if response == Gtk.ResponseType.OK:
                filename = file_selection(
                    _('Save As'),
                    action=Gtk.FileChooserAction.SAVE,
                    preview=False,
                    filters=[filter])
                if width and height and filename:
                    if not filename.endswith('.png'):
                        filename = filename + '.png'
                    try:
                        self.widgets['root'].export_png(
                            filename, width, height)
                        break
                    except MemoryError:
                        message(
                            _('Image size too large.'), dia,
                            Gtk.MessageType.ERROR)
            else:
                break
        parent.present()
        dia.destroy()

    def button_press(self, widget, event):
        if event.button == 3:
            menu = Gtk.Menu()
            item = Gtk.MenuItem(label=_('Save As...'))
            item.connect('activate', self.save)
            item.show()
            menu.append(item)
            if hasattr(menu, 'popup_at_pointer'):
                menu.popup_at_pointer(event)
            else:
                menu.popup(None, None, None, event.button, event.time)
            return True
        elif event.button == 1:
            self.widgets['root'].action()
