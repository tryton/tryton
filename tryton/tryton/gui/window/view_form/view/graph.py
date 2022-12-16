# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys

import gtk
import gettext

from . import View
from tryton.common import node_attributes, get_toplevel_window, message
from tryton.config import TRYTON_ICON
from .graph_gtk.bar import VerticalBar, HorizontalBar
from .graph_gtk.line import Line
from .graph_gtk.pie import Pie

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
        dia = gtk.Dialog(_('Save As'), parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                gtk.STOCK_OK, gtk.RESPONSE_OK))
        dia.set_icon(TRYTON_ICON)
        dia.set_has_separator(True)
        dia.set_default_response(gtk.RESPONSE_OK)

        dia.vbox.set_spacing(5)
        dia.vbox.set_homogeneous(False)

        title = gtk.Label('<b>' + _('Image Size') + '</b>')
        title.set_alignment(0.0, 0.5)
        title.set_use_markup(True)
        dia.vbox.pack_start(title)

        table = gtk.Table(2, 2)
        table.set_col_spacings(3)
        table.set_row_spacings(3)
        table.set_border_width(1)
        table.attach(gtk.Label(_('Width:')), 0, 1, 0, 1, yoptions=False,
                xoptions=gtk.FILL)
        spinwidth = gtk.SpinButton(gtk.Adjustment(400.0,
                0.0, sys.maxint, 1.0, 10.0))
        spinwidth.set_numeric(True)
        spinwidth.set_activates_default(True)
        table.attach(spinwidth, 1, 2, 0, 1, yoptions=False, xoptions=gtk.FILL)
        table.attach(gtk.Label(_('Height:')), 0, 1, 1, 2, yoptions=False,
                xoptions=gtk.FILL)
        spinheight = gtk.SpinButton(gtk.Adjustment(200.0,
                0.0, sys.maxint, 1.0, 10.0))
        spinheight.set_numeric(True)
        spinheight.set_activates_default(True)
        table.attach(spinheight, 1, 2, 1, 2, yoptions=False, xoptions=gtk.FILL)
        dia.vbox.pack_start(table)

        filechooser = gtk.FileChooserWidget(gtk.FILE_CHOOSER_ACTION_SAVE, None)
        filter = gtk.FileFilter()
        filter.set_name(_('PNG image (*.png)'))
        filter.add_mime_type('image/png')
        filter.add_pattern('*.png')
        filechooser.add_filter(filter)
        dia.vbox.pack_start(filechooser)

        dia.show_all()

        while True:
            response = dia.run()
            width = spinwidth.get_value_as_int()
            height = spinheight.get_value_as_int()
            filename = filechooser.get_filename()
            if response == gtk.RESPONSE_OK:
                if width and height and filename:
                    if not filename.endswith('.png'):
                        filename = filename + '.png'
                    try:
                        self.widgets['root'].export_png(
                            filename, width, height)
                        break
                    except MemoryError:
                        message(_('Image size too large!'), dia,
                                gtk.MESSAGE_ERROR)
            else:
                break
        parent.present()
        dia.destroy()

    def button_press(self, widget, event):
        if event.button == 3:
            menu = gtk.Menu()
            item = gtk.ImageMenuItem(_('Save As...'))
            img = gtk.Image()
            img.set_from_stock('tryton-save-as', gtk.ICON_SIZE_MENU)
            item.set_image(img)
            item.connect('activate', self.save)
            item.show()
            menu.append(item)
            menu.popup(None, None, None, event.button, event.time)
            return True
        elif event.button == 1:
            self.widgets['root'].action()
