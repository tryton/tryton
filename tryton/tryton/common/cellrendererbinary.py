# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject
import pango

BUTTON_BORDER = 2
BUTTON_SPACING = 1


class CellRendererBinary(gtk.GenericCellRenderer):
    __gproperties__ = {
        'visible': (gobject.TYPE_BOOLEAN, 'Visible', 'Visible', True,
            gobject.ParamFlags.READWRITE),
        'editable': (gobject.TYPE_BOOLEAN, 'Editable', 'Editable', False,
            gobject.ParamFlags.READWRITE),
        'size': (gobject.TYPE_STRING, 'Size', 'Size', '',
            gobject.ParamFlags.READWRITE),
    }
    __gsignals__ = {
        'select': (gobject.SignalFlags.RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)),
        'open': (gobject.SignalFlags.RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)),
        'save': (gobject.SignalFlags.RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)),
        'clear': (gobject.SignalFlags.RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)),
    }

    def __init__(self, use_filename):
        self.__gobject_init__()
        self.visible = True
        self.editable = False
        self.set_property('mode', gtk.CELL_RENDERER_MODE_EDITABLE)
        self.use_filename = use_filename
        self.clicking = ''
        self.images = {}
        widget = gtk.Button()
        for key, stock_name in (
                ('select', 'tryton-find'),
                ('open', 'tryton-open'),
                ('save', 'tryton-save-as'),
                ('clear', 'tryton-clear')):
            # hack to get gtk.gdk.Image from stock icon
            img_sensitive = widget.render_icon(stock_name,
                gtk.ICON_SIZE_SMALL_TOOLBAR)
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
        return (sum(width for n, (_, _, width, _) in self.images.iteritems()
                if n in self.buttons)
            + (2 * (BUTTON_BORDER + BUTTON_SPACING) * len(self.buttons))
            - 2 * BUTTON_SPACING)

    def on_get_size(self, widget, cell_area=None):
        if cell_area is None:
            return (0, 0, 30, 18)
        else:
            return (cell_area.x, cell_area.y,
                cell_area.width, cell_area.height)
    do_get_size = on_get_size

    def on_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
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
        if not self.editable and button_name in ('select', 'clear'):
            return
        if not self.size and button_name == 'save':
            return
        if event.type == gtk.gdk.BUTTON_PRESS:
            self.clicking = button_name
            self.emit(button_name, path)

            def timeout(self, widget):
                self.clicking = ''
                widget.queue_draw()
            gobject.timeout_add(60, timeout, self, widget)
    do_start_editing = on_start_editing

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
        layout.set_width(lwidth * pango.SCALE)
        layout.set_ellipsize(pango.ELLIPSIZE_END)
        layout.set_wrap(pango.WRAP_CHAR)
        layout.set_alignment(pango.ALIGN_RIGHT)

        if lwidth > 0:
            lw, lh = layout.get_size()  # Can not use get_pixel_extents
            lw /= pango.SCALE
            lh /= pango.SCALE

            lx = x + padding.left
            if self.buttons and self.buttons[0] == 'open':
                pxbf_width = self.images['open'][2]
                lx += pxbf_width + 2 * BUTTON_BORDER + BUTTON_SPACING
            ly = y + padding.top + 0.5 * (
                h - padding.top - padding.bottom - lh)

            gtk.render_layout(context, cr, lx, ly, layout)

        for index, button_name in enumerate(self.buttons):
            pxbf_sens, pxbf_insens, pxbf_width, pxbf_height = \
                self.images[button_name]
            state = gtk.StateFlags.NORMAL
            if (self.clicking == button_name
                    and flags & gtk.CELL_RENDERER_SELECTED):
                state = gtk.StateFlags.ACTIVE
            if (not self.editable and button_name in {'select', 'clear'}
                    or not self.size and button_name in {'open', 'save'}):
                state = gtk.StateFlags.INSENSITIVE
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

            gtk.render_background(context, cr, bx, by, bw, h)
            gtk.render_frame(context, cr, bx, by, bw, h)

            gtk.gdk.cairo_set_source_pixbuf(
                cr, pixbuf, bx + BUTTON_BORDER, by + (h - pxbf_height) / 2)
            cr.paint()
        context.restore()


gobject.type_register(CellRendererBinary)
