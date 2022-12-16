#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import gtk
import gobject
import pango


class CellRendererText(gtk.GenericCellRenderer):
    __gproperties__ = {
            'text': (gobject.TYPE_STRING, None, 'Text',
                'Text', gobject.PARAM_READWRITE),
            'foreground': (gobject.TYPE_STRING, None, 'Foreground',
                'Foreground', gobject.PARAM_READWRITE),
            'background': (gobject.TYPE_STRING, None, 'Background',
                'Background', gobject.PARAM_READWRITE),
            'editable': (gobject.TYPE_INT, 'Editable',
                'Editable', 0, 10, 0, gobject.PARAM_READWRITE),
            'xalign': (gobject.TYPE_FLOAT, 'XAlign',
                'XAlign', 0, 1, 0, gobject.PARAM_READWRITE),
    }

    def __init__(self):
        self.__gobject_init__()
        self._renderer = gtk.CellRendererText()
        self.set_property("mode", self._renderer.get_property("mode"))

        self.text = self._renderer.get_property('text')
        self.editable = self._renderer.get_property('editable')

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
        self._renderer.set_property(pspec.name, value)
        self.set_property("mode", self._renderer.get_property("mode"))

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def on_get_size(self, widget, cell_area):
        return self._renderer.get_size(widget, cell_area)

    def on_render(self, window, widget, background_area, cell_area,
            expose_area, flags):
        # Handle Pixmap window as pygtk failed
        if type(window) == gtk.gdk.Pixmap:
            layout = widget.create_pango_layout(self.text)
            layout.set_font_description(widget.style.font_desc)
            w, h = layout.get_size()
            xalign = self._renderer.get_property('xalign')
            x = int(cell_area.x + (cell_area.width - w / pango.SCALE) * xalign)
            y = int(cell_area.y + (cell_area.height - h / pango.SCALE) / 2)
            window.draw_layout(widget.style.text_gc[0], x, y, layout)
            return
        return self._renderer.render(window, widget, background_area,
                cell_area, expose_area, flags)

    def on_activate(self, event, widget, path, background_area, cell_area,
            flags):
        return self._renderer.activate(event, widget, path, background_area,
                cell_area, flags)

    def on_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        if not event:
            event = gtk.gdk.Event(gtk.keysyms.Tab)
        editable = gtk.Entry()
        editable.set_property('shadow-type', gtk.SHADOW_NONE)

        colormap = editable.get_colormap()
        if hasattr(self, 'background'):
            colour = colormap.alloc_color(getattr(self, 'background'))
        else:
            colour = colormap.alloc_color('white')
        editable.modify_bg(gtk.STATE_ACTIVE, colour)
        editable.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("black"))
        editable.modify_base(gtk.STATE_NORMAL, colour)
        editable.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse("black"))
        editable.modify_text(gtk.STATE_INSENSITIVE, gtk.gdk.color_parse("black"))

        editable.set_text(self.text)
        editable.grab_focus()
        editable.show()
        return editable

gobject.type_register(CellRendererText)
