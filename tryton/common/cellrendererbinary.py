# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gi.repository import Gtk, Gdk, GObject, Pango

from .common import IconFactory

BUTTON_BORDER = 2
BUTTON_SPACING = 1


class CellRendererBinary(Gtk.CellRenderer):
    __gproperties__ = {
        'visible': (GObject.TYPE_BOOLEAN, 'Visible', 'Visible', True,
            GObject.ParamFlags.READWRITE),
        'editable': (GObject.TYPE_BOOLEAN, 'Editable', 'Editable', False,
            GObject.ParamFlags.READWRITE),
        'size': (GObject.TYPE_STRING, 'Size', 'Size', '',
            GObject.ParamFlags.READWRITE),
        }
    __gsignals__ = {
        'select': (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
            (GObject.TYPE_STRING,)),
        'open': (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
            (GObject.TYPE_STRING,)),
        'save': (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
            (GObject.TYPE_STRING,)),
        'clear': (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE,
            (GObject.TYPE_STRING,)),
        }

    def __init__(self, use_filename):
        Gtk.CellRenderer.__init__(self)
        self.visible = True
        self.editable = False
        self.set_property('mode', Gtk.CellRendererMode.ACTIVATABLE)
        self.use_filename = use_filename
        self.images = {}
        for key, icon in (
                ('select', 'tryton-search'),
                ('open', 'tryton-open'),
                ('save', 'tryton-save'),
                ('clear', 'tryton-clear')):
            img_sensitive = IconFactory.get_pixbuf(
                icon, Gtk.IconSize.SMALL_TOOLBAR)
            img_insensitive = img_sensitive.copy()
            img_sensitive.saturate_and_pixelate(img_insensitive, 0, False)
            width = img_sensitive.get_width()
            height = img_sensitive.get_height()
            self.images[key] = (img_sensitive, img_insensitive, width, height)

    @property
    def buttons(self):
        buttons = []
        if self.size:
            if self.use_filename:
                buttons.append('open')
            buttons.append('save')
            buttons.append('clear')
        else:
            buttons.append('select')
        return buttons

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def button_width(self):
        return (sum(width for n, (_, _, width, _) in self.images.items()
                if n in self.buttons)
            + (2 * (BUTTON_BORDER + BUTTON_SPACING) * len(self.buttons))
            - 2 * BUTTON_SPACING)

    def do_get_size(self, widget, cell_area=None):
        if cell_area is None:
            return (0, 0, 30, 18)
        else:
            return (cell_area.x, cell_area.y,
                cell_area.width, cell_area.height)

    def do_activate(
            self, event, widget, path, background_area, cell_area, flags):
        if event is None:
            return
        button_width = self.button_width()

        for index, button_name in enumerate(self.buttons):
            _, _, pxbf_width, _ = self.images[button_name]
            if index == 0 and button_name == 'open':
                x_offset = 0
            else:
                x_offset = (cell_area.width - button_width
                    + (pxbf_width + (2 * BUTTON_BORDER) + BUTTON_SPACING)
                    * index)
            x_button = cell_area.x + x_offset
            if x_button < event.x < (x_button + pxbf_width
                    + (2 * BUTTON_BORDER)):
                break
        else:
            button_name = None
        if not self.visible or not button_name:
            return
        elif not self.editable and button_name in ('select', 'clear'):
            return
        elif not self.size and button_name in {'open', 'save'}:
            return
        self.emit(button_name, path)
        return True

    def do_render(self, cr, widget, background_area, cell_area, flags):
        if not self.visible:
            return

        button_width = self.button_width()

        state = self.get_state(widget, flags)

        context = widget.get_style_context()
        context.save()
        context.add_class('button')

        xpad, ypad = self.get_padding()
        x = cell_area.x + xpad
        y = cell_area.y + ypad
        w = cell_area.width - 2 * xpad
        h = cell_area.height - 2 * ypad

        padding = context.get_padding(state)
        layout = widget.create_pango_layout(self.size)
        lwidth = w - button_width - padding.left - padding.right
        if lwidth < 0:
            lwidth = 0
        layout.set_width(lwidth * Pango.SCALE)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
        layout.set_wrap(Pango.WrapMode.CHAR)
        layout.set_alignment(Pango.Alignment.RIGHT)

        if lwidth > 0:
            lw, lh = layout.get_size()  # Can not use get_pixel_extents
            lw /= Pango.SCALE
            lh /= Pango.SCALE

            lx = x + padding.left
            if self.buttons and self.buttons[0] == 'open':
                pxbf_width = self.images['open'][2]
                lx += pxbf_width + 2 * BUTTON_BORDER + BUTTON_SPACING
            ly = y + padding.top + 0.5 * (
                h - padding.top - padding.bottom - lh)

            Gtk.render_layout(context, cr, lx, ly, layout)

        for index, button_name in enumerate(self.buttons):
            pxbf_sens, pxbf_insens, pxbf_width, pxbf_height = \
                self.images[button_name]
            if (not self.editable and button_name in {'select', 'clear'}
                    or not self.size and button_name in {'open', 'save'}):
                pixbuf = pxbf_insens
            else:
                pixbuf = pxbf_sens

            if index == 0 and button_name == 'open':
                x_offset = 0
            else:
                x_offset = (w - button_width
                    + (pxbf_width + (2 * BUTTON_BORDER) + BUTTON_SPACING)
                    * index)
            if x_offset < 0:
                continue
            bx = cell_area.x + x_offset
            by = cell_area.y
            bw = pxbf_width + (2 * BUTTON_BORDER)

            Gtk.render_background(context, cr, bx, by, bw, h)
            Gtk.render_frame(context, cr, bx, by, bw, h)

            Gdk.cairo_set_source_pixbuf(
                cr, pixbuf, bx + BUTTON_BORDER, by + (h - pxbf_height) / 2)
            cr.paint()
        context.restore()


GObject.type_register(CellRendererBinary)
