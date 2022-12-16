# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import Gtk, GObject, Pango


class CellRendererButton(Gtk.CellRenderer):
    __gproperties__ = {
        "text": (GObject.TYPE_STRING, None, "Text",
            "Displayed text", GObject.ParamFlags.READWRITE),
        'visible': (GObject.TYPE_INT, 'Visible',
            'Visible', 0, 10, 0, GObject.ParamFlags.READWRITE),
        'sensitive': (GObject.TYPE_INT, 'Sensitive',
            'Sensitive', 0, 10, 0, GObject.ParamFlags.READWRITE),
        }

    __gsignals__ = {
        'clicked': (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
            (GObject.TYPE_STRING,)),
        }

    def __init__(self, text=""):
        Gtk.CellRenderer.__init__(self)
        self.text = text
        self.set_property('mode', Gtk.CellRendererMode.EDITABLE)
        self.visible = True
        self.sensitive = True

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_render(self, cr, widget, background_area, cell_area, flags):
        if not self.visible:
            return

        if not self.sensitive:
            state = Gtk.StateFlags.INSENSITIVE
        else:
            state = Gtk.StateFlags.NORMAL

        context = widget.get_style_context()
        context.save()
        context.add_class('text-button')
        context.set_state(state)

        xpad, ypad = self.get_padding()
        x = cell_area.x + xpad
        y = cell_area.y + ypad
        w = cell_area.width - 2 * xpad
        h = cell_area.height - 2 * ypad

        Gtk.render_background(context, cr, x, y, w, h)
        Gtk.render_frame(context, cr, x, y, w, h)

        padding = context.get_padding(state)
        layout = widget.create_pango_layout(self.text)
        layout.set_width((w - padding.left - padding.right) * Pango.SCALE)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        layout.set_wrap(Pango.WrapMode.CHAR)

        lw, lh = layout.get_size()  # Can not use get_pixel_extents
        lw /= Pango.SCALE
        lh /= Pango.SCALE
        if w < lw:
            x = x + padding.left
        else:
            x = x + padding.left + 0.5 * (
                w - padding.left - padding.right - lw)
        y = y + padding.top + 0.5 * (h - padding.top - padding.bottom - lh)

        Gtk.render_layout(context, cr, x, y, layout)
        context.restore()

    def do_get_size(self, widget, cell_area=None):
        if cell_area is None:
            return (0, 0, 30, 18)
        else:
            return (cell_area.x, cell_area.y,
                cell_area.width, cell_area.height)

    def do_start_editing(
            self, event, widget, path, background_area, cell_area, flags):
        if not self.visible or not self.sensitive:
            return
        self.emit("clicked", path)


GObject.type_register(CellRendererButton)
