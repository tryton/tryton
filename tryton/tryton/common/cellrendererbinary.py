# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk
import gobject
import pango

BUTTON_BORDER = 10
BUTTON_SPACING = 2


class CellRendererBinary(gtk.GenericCellRenderer):
    __gproperties__ = {
        'visible': (gobject.TYPE_BOOLEAN, 'Visible', 'Visible', True,
            gobject.PARAM_READWRITE),
        'editable': (gobject.TYPE_BOOLEAN, 'Editable', 'Editable', False,
            gobject.PARAM_READWRITE),
        'size': (gobject.TYPE_STRING, 'Size', 'Size', '',
            gobject.PARAM_READWRITE),
    }
    __gsignals__ = {
        'select': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)),
        'open': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)),
        'save': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)),
        'clear': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)),
    }

    def __init__(self, use_filename):
        self.__gobject_init__()
        self.visible = True
        self.editable = False
        self.set_property('mode', gtk.CELL_RENDERER_MODE_EDITABLE)
        self.use_filename = use_filename
        if use_filename:
            self.buttons = ('select', 'open', 'save', 'clear')
        else:
            self.buttons = ('select', 'save', 'clear')
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

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def button_width(self):
        return (sum(width for _, _, width, _ in self.images.itervalues())
            + (2 * (BUTTON_BORDER + BUTTON_SPACING) * len(self.buttons))
            - 2 * BUTTON_SPACING)

    def on_get_size(self, widget, cell_area=None):
        if cell_area is None:
            return (0, 0, 30, 18)
        else:
            return (cell_area.x, cell_area.y,
                cell_area.width, cell_area.height)

    def on_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        if event is None:
            return
        button_width = self.button_width()

        for index, button_name in enumerate(self.buttons):
            _, _, pxbf_width, _ = self.images[button_name]
            x_offset = (cell_area.width - button_width
                + (pxbf_width + (2 * BUTTON_BORDER) + BUTTON_SPACING) * index)
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

    def on_render(self, window, widget, background_area, cell_area,
            expose_area, flags):
        if not self.visible:
            return
        # Handle Pixmap window as pygtk failed
        if type(window) == gtk.gdk.Pixmap:
            return

        button_width = self.button_width()

        # display size
        layout = widget.create_pango_layout(self.size)
        layout.set_font_description(widget.style.font_desc)
        w, h = layout.get_size()
        x = int(cell_area.x + cell_area.width - button_width - w / pango.SCALE
            - BUTTON_SPACING)
        y = int(cell_area.y + (cell_area.height - h / pango.SCALE) / 2)
        layout.set_width(((cell_area.width / 2) - 2) * pango.SCALE)
        state = gtk.STATE_NORMAL
        if flags & gtk.CELL_RENDERER_SELECTED:
            state = gtk.STATE_ACTIVE
        if x >= cell_area.x:
            widget.style.paint_layout(window, state, True, expose_area,
                widget, "cellrendererbinary", x, y, layout)

        # display buttons
        for index, button_name in enumerate(self.buttons):
            state = gtk.STATE_NORMAL
            shadow = gtk.SHADOW_OUT
            pxbf_sens, pxbf_insens, pxbf_width, pxbf_height = \
                self.images[button_name]
            if (self.clicking == button_name
                    and flags & gtk.CELL_RENDERER_SELECTED):
                state = gtk.STATE_ACTIVE
                shadow = gtk.SHADOW_IN
            if (not self.editable and button_name in ('select', 'clear')
                    or not self.size and button_name in ('open', 'save')):
                state = gtk.STATE_INSENSITIVE
                pixbuf = pxbf_insens
            else:
                pixbuf = pxbf_sens
            x_offset = (cell_area.width - button_width
                + (pxbf_width + (2 * BUTTON_BORDER) + BUTTON_SPACING) * index)
            if x_offset < 0:
                continue
            widget.style.paint_box(window, state, shadow,
                None, widget, "button", cell_area.x + x_offset, cell_area.y,
                pxbf_width + (2 * BUTTON_BORDER), cell_area.height)
            window.draw_pixbuf(widget.style.black_gc,
                pixbuf, 0, 0,
                cell_area.x + x_offset + BUTTON_BORDER,
                cell_area.y + (cell_area.height - pxbf_height) / 2)

gobject.type_register(CellRendererBinary)
