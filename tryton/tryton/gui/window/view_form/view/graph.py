# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys

import gtk
import gettext

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
        event = gtk.EventBox()
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
        dia = gtk.Dialog(_('Image Size'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        Main().add_window(dia)
        cancel_button = dia.add_button(
            set_underline(_("Cancel")), gtk.RESPONSE_CANCEL)
        cancel_button.set_image(IconFactory.get_image(
                'tryton-cancel', gtk.ICON_SIZE_BUTTON))
        cancel_button.set_always_show_image(True)
        ok_button = dia.add_button(
            set_underline(_("OK")), gtk.RESPONSE_OK)
        ok_button.set_image(IconFactory.get_image(
                'tryton-ok', gtk.ICON_SIZE_BUTTON))
        ok_button.set_always_show_image(True)
        dia.set_icon(TRYTON_ICON)
        dia.set_default_response(gtk.RESPONSE_OK)

        hbox = gtk.HBox(spacing=3)
        dia.vbox.pack_start(hbox, False, True)

        hbox.pack_start(gtk.Label(_('Width:')), False, True)
        spinwidth = gtk.SpinButton()
        spinwidth.configure(gtk.Adjustment(400.0, 0.0, sys.maxsize, 1.0, 10.0),
            climb_rate=1, digits=0)
        spinwidth.set_numeric(True)
        spinwidth.set_activates_default(True)
        hbox.pack_start(spinwidth, True, True)

        hbox.pack_start(gtk.Label(_('Height:')), False, True)
        spinheight = gtk.SpinButton()
        spinheight.configure(gtk.Adjustment(
                200.0, 0.0, sys.maxsize, 1.0, 10.0),
            climb_rate=1, digits=0)
        spinheight.set_numeric(True)
        spinheight.set_activates_default(True)
        hbox.pack_start(spinheight, True, True)
        dia.show_all()

        filter = gtk.FileFilter()
        filter.set_name(_('PNG image (*.png)'))
        filter.add_mime_type('image/png')
        filter.add_pattern('*.png')

        while True:
            response = dia.run()
            width = spinwidth.get_value_as_int()
            height = spinheight.get_value_as_int()
            if response == gtk.RESPONSE_OK:
                filename = file_selection(_('Save As'),
                    action=gtk.FILE_CHOOSER_ACTION_SAVE,
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
                        message(_('Image size too large.'), dia,
                                gtk.MESSAGE_ERROR)
            else:
                break
        parent.present()
        dia.destroy()

    def button_press(self, widget, event):
        if event.button == 3:
            menu = gtk.Menu()
            item = gtk.ImageMenuItem(_('Save As...'))
            item.set_image(IconFactory.get_image(
                    'tryton-save-as', gtk.ICON_SIZE_MENU))
            item.connect('activate', self.save)
            item.show()
            menu.append(item)
            menu.popup(None, None, None, event.button, event.time)
            return True
        elif event.button == 1:
            self.widgets['root'].action()
