#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gobject
import pango

from date_widget import DateEntry


class CellRendererDate(gtk.GenericCellRenderer):
    __gproperties__ = {
            'text': (gobject.TYPE_STRING, None, 'Text',
                'Text', gobject.PARAM_READWRITE),
            'foreground': (gobject.TYPE_STRING, None, 'Foreground',
                'Foreground', gobject.PARAM_WRITABLE),
            'foreground-set': (gobject.TYPE_INT, 'Foreground Set',
                'Foreground Set', 0, 10, 0, gobject.PARAM_READWRITE),
            'background': (gobject.TYPE_STRING, None, 'Background',
                'Background', gobject.PARAM_WRITABLE),
            'background-set': (gobject.TYPE_INT, 'Background Set',
                'Background Set', 0, 10, 0, gobject.PARAM_READWRITE),
            'editable': (gobject.TYPE_INT, 'Editable',
                'Editable', 0, 10, 0, gobject.PARAM_READWRITE),
            'visible': (gobject.TYPE_INT, 'Visible',
                'Visible', 0, 10, 0, gobject.PARAM_READWRITE),
            'strikethrough': (gobject.TYPE_BOOLEAN, 'Strikethrough',
                'Strikethrough', False, gobject.PARAM_WRITABLE),
    }

    def __init__(self, format):
        self.__gobject_init__()
        self._renderer = gtk.CellRendererText()
        self.set_property("mode", self._renderer.get_property("mode"))

        self.format = format
        self.cmd = ''
        self.text = self._renderer.get_property('text')
        self.editable = self._renderer.get_property('editable')
        self.visible = True

    def set_sensitive(self, value):
        if hasattr(self._renderer, 'set_sensitive'):
            return self._renderer.set_sensitive(value)
        return self._renderer.set_property('sensitive', value)

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
        if pspec.name == 'visible':
            return
        self._renderer.set_property(pspec.name, value)
        self.set_property("mode", self._renderer.get_property("mode"))

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def on_get_size(self, widget, cell_area):
        return self._renderer.get_size(widget, cell_area)

    def on_render(self, window, widget, background_area, cell_area,
            expose_area, flags):
        if not self.visible:
            return
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
        if not self.visible:
            return
        return self._renderer.activate(event, widget, path, background_area,
                cell_area, flags)

    def on_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        if not self.visible:
            return
        editable = DateEntry(self.format)
        editable.set_property('shadow-type', gtk.SHADOW_NONE)

        colormap = editable.get_colormap()
        style = editable.get_style()
        if hasattr(self, 'background') \
                and getattr(self, 'background') != 'white':
            bg_color = colormap.alloc_color(getattr(self, 'background'))
            fg_color = gtk.gdk.color_parse("black")
            editable.modify_bg(gtk.STATE_ACTIVE, bg_color)
            editable.modify_base(gtk.STATE_NORMAL, bg_color)
            editable.modify_fg(gtk.STATE_NORMAL, fg_color)
            editable.modify_text(gtk.STATE_NORMAL, fg_color)
            editable.modify_text(gtk.STATE_INSENSITIVE, fg_color)
        else:
            editable.modify_bg(gtk.STATE_ACTIVE, style.bg[gtk.STATE_ACTIVE])
            editable.modify_base(gtk.STATE_NORMAL,
                style.base[gtk.STATE_NORMAL])
            editable.modify_fg(gtk.STATE_NORMAL, style.fg[gtk.STATE_NORMAL])
            editable.modify_text(gtk.STATE_NORMAL,
                style.text[gtk.STATE_NORMAL])
            editable.modify_text(gtk.STATE_INSENSITIVE,
                style.text[gtk.STATE_INSENSITIVE])

        if self.text:
            editable.set_text(self.text)
        else:
            editable.clear()
        editable.grab_focus()
        editable.show()
        return editable

gobject.type_register(CellRendererDate)
