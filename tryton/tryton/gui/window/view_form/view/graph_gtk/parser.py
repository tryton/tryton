#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from tryton.gui.window.view_form.view.interface import ParserInterface
import tryton.common as common
import gtk
from bar import VerticalBar, HorizontalBar
from line import Line
from pie import Pie
from tryton.config import TRYTON_ICON, CONFIG
import sys
import os
import gettext

_ = gettext.gettext

GRAPH_TYPE = {
    'vbar': VerticalBar,
    'hbar': HorizontalBar,
    'line': Line,
    'pie': Pie,
}


def save(widget, graph):
    parent = common.get_toplevel_window()
    dia = gtk.Dialog(_('Save As'), parent,
        gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
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
    filechooser.set_current_folder(CONFIG['client.default_path'])
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
        if filename:
            filename = filename.decode('utf-8')
            try:
                CONFIG['client.default_path'] = \
                    os.path.dirname(filename)
                CONFIG.save()
            except IOError:
                pass
        if response == gtk.RESPONSE_OK:
            if width and height and filename:
                if not filename.endswith('.png'):
                    filename = filename + '.png'
                try:
                    graph.export_png(filename, width, height)
                    break
                except MemoryError:
                    common.message(_('Image size too large!'), dia,
                            gtk.MESSAGE_ERROR)
        else:
            break
    parent.present()
    dia.destroy()
    return


def button_press(widget, event, graph):
    if event.button == 3:
        menu = gtk.Menu()
        item = gtk.ImageMenuItem(_('Save As...'))
        img = gtk.Image()
        img.set_from_stock('tryton-save-as', gtk.ICON_SIZE_MENU)
        item.set_image(img)
        item.connect('activate', save, graph)
        item.show()
        menu.append(item)
        menu.popup(None, None, None, event.button, event.time)
        return True
    elif event.button == 1:
        graph.action()


class ParserGraph(ParserInterface):

    def parse(self, model, root_node, fields):
        attrs = common.node_attributes(root_node)
        self.title = attrs.get('string', 'Unknown')
        xfield = None
        yfields = []

        for node in root_node.childNodes:
            if not node.nodeType == node.ELEMENT_NODE:
                continue

            if node.localName == 'x':
                for child in node.childNodes:
                    if not child.nodeType == child.ELEMENT_NODE:
                        continue
                    xfield = common.node_attributes(child)
                    if not xfield.get('string'):
                        xfield['string'] = fields[xfield['name']
                            ].attrs['string']
                    break
            elif node.localName == 'y':
                for child in node.childNodes:
                    if not child.nodeType == child.ELEMENT_NODE:
                        continue
                    yattrs = common.node_attributes(child)
                    if not yattrs.get('string') and yattrs['name'] != '#':
                        yattrs['string'] = fields[yattrs['name']
                            ].attrs['string']
                    yfields.append(yattrs)

        widget = GRAPH_TYPE[attrs.get('type', 'vbar')
            ](xfield, yfields, attrs, model)
        event = gtk.EventBox()
        event.add(widget)
        event.connect('button-press-event', button_press, widget)

        return event, {'root': widget}, [], '', [], None
