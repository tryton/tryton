#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import gtk
import gobject
import pango


class CellRendererButton(gtk.GenericCellRenderer):
    #TODO Add keyboard editing
    __gproperties__ = {
            "text": (gobject.TYPE_STRING, None, "Text",
                "Displayed text", gobject.PARAM_READWRITE),
    }

    __gsignals__ = {
            'clicked': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                (gobject.TYPE_STRING, )),
    }

    def __init__(self, text=""):
        self.__gobject_init__()
        self.text = text
        self.set_property('mode', gtk.CELL_RENDERER_MODE_EDITABLE)
        self.clicking = False

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def on_render(self, window, widget, background_area, cell_area,
            expose_area, flags):
        state = gtk.STATE_NORMAL
        shadow = gtk.SHADOW_OUT
        if self.clicking and flags & gtk.CELL_RENDERER_SELECTED:
            state = gtk.STATE_ACTIVE
            shadow = gtk.SHADOW_IN
        widget.style.paint_box(window, state, shadow,
                None, widget, "button",
                cell_area.x, cell_area.y,
                cell_area.width, cell_area.height)
        layout = widget.create_pango_layout('')
        layout.set_font_description(widget.style.font_desc)
        w, h = layout.get_size()
        x = cell_area.x
        y = int(cell_area.y + (cell_area.height - h / pango.SCALE) / 2)
        window.draw_layout(widget.style.text_gc[0], x, y, layout)

        layout = widget.create_pango_layout(self.text)
        layout.set_font_description(widget.style.font_desc)
        w, h = layout.get_size()
        x = int(cell_area.x + (cell_area.width - w / pango.SCALE) / 2)
        y = int(cell_area.y + (cell_area.height - h / pango.SCALE) / 2)
        window.draw_layout(widget.style.text_gc[0], x, y, layout)

    def on_get_size(self, widget, cell_area=None):
        if cell_area is None:
            return (0, 0, 30, 18)
        else:
            return (cell_area.x, cell_area.y, cell_area.width, cell_area.height)

    def on_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        if (event is None) or ((event.type == gtk.gdk.BUTTON_PRESS) \
                or (event.type == gtk.gdk.KEY_PRESS \
                    and event.keyval == gtk.keysyms.space)):
            self.clicking = True
            widget.queue_draw()
            gtk.main_iteration()
            self.emit("clicked", path)
            def timeout(self, widget):
                self.clicking = False
                widget.queue_draw()
            gobject.timeout_add(60, timeout, self, widget)

gobject.type_register(CellRendererButton)
