# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject
import pango


class CellRendererButton(gtk.GenericCellRenderer):
    # TODO Add keyboard editing
    __gproperties__ = {
            "text": (gobject.TYPE_STRING, None, "Text",
                "Displayed text", gobject.ParamFlags.READWRITE),
            'visible': (gobject.TYPE_INT, 'Visible',
                'Visible', 0, 10, 0, gobject.ParamFlags.READWRITE),
            'sensitive': (gobject.TYPE_INT, 'Sensitive',
                'Sensitive', 0, 10, 0, gobject.ParamFlags.READWRITE),
    }

    __gsignals__ = {
            'clicked': (gobject.SignalFlags.RUN_LAST, gobject.TYPE_NONE,
                (gobject.TYPE_STRING, )),
    }

    def __init__(self, text=""):
        self.__gobject_init__()
        self.text = text
        self.set_property('mode', gtk.CELL_RENDERER_MODE_EDITABLE)
        self.clicking = False
        self.visible = True
        self.sensitive = True

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_render(self, cr, widget, background_area, cell_area, flags):
        if not self.visible:
            return

        state = gtk.StateFlags.NORMAL
        if self.clicking and flags & gtk.CELL_RENDERER_SELECTED:
            state = gtk.StateFlags.ACTIVE
        elif not self.sensitive:
            state = gtk.StateFlags.INSENSITIVE

        context = widget.get_style_context()
        context.save()
        context.add_class('button')
        context.set_state(state)

        xpad, ypad = self.get_padding()
        x = cell_area.x + xpad
        y = cell_area.y + ypad
        w = cell_area.width - 2 * xpad
        h = cell_area.height - 2 * ypad

        gtk.render_background(context, cr, x, y, w, h)
        gtk.render_frame(context, cr, x, y, w, h)

        padding = context.get_padding(state)
        layout = widget.create_pango_layout(self.text)
        layout.set_width((w - padding.left - padding.right) * pango.SCALE)
        layout.set_ellipsize(pango.ELLIPSIZE_END)
        layout.set_wrap(pango.WRAP_CHAR)

        lw, lh = layout.get_size()  # Can not use get_pixel_extents
        lw /= pango.SCALE
        lh /= pango.SCALE
        if w < lw:
            x = x + padding.left
        else:
            x = x + padding.left + 0.5 * (
                w - padding.left - padding.right - lw)
        y = y + padding.top + 0.5 * (h - padding.top - padding.bottom - lh)

        gtk.render_layout(context, cr, x, y, layout)
        context.restore()

    def on_get_size(self, widget, cell_area=None):
        if cell_area is None:
            return (0, 0, 30, 18)
        else:
            return (cell_area.x, cell_area.y,
                cell_area.width, cell_area.height)
    do_get_size = on_get_size

    def on_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        if not self.visible or not self.sensitive:
            return
        if (event is None) or ((event.type == gtk.gdk.BUTTON_PRESS)
                or (event.type == gtk.gdk.KEY_PRESS
                    and event.keyval == gtk.keysyms.space)):
            self.clicking = True
            widget.queue_draw()
            while gtk.events_pending():
                gtk.main_iteration()
            self.emit("clicked", path)

            def timeout(self, widget):
                self.clicking = False
                widget.queue_draw()
            gobject.timeout_add(60, timeout, self, widget)
    do_start_editing = on_start_editing

gobject.type_register(CellRendererButton)
