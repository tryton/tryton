# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
__version__ = "5.0.40"
import sys

import gi
import pygtkcompat
import locale

pygtkcompat.enable()
pygtkcompat.enable_gtk(version='3.0')
try:
    pygtkcompat.enable_goocanvas()
except ValueError:
    pass
try:
    gi.require_version('GtkSpell', '3.0')
except ValueError:
    pass

from gi.repository import GdkPixbuf
_unset = object()

Gdk = sys.modules['gtk.gdk']
# XXX this prevents isinstance test
Gdk.PixbufLoader = GdkPixbuf.PixbufLoader.new

Gtk = sys.modules['gtk']
Gtk.widget_set_default_direction = Gtk.Widget.set_default_direction
Gtk.accel_map_add_entry = Gtk.AccelMap.add_entry
Gtk.accel_map_load = Gtk.AccelMap.load
Gtk.accel_map_save = Gtk.AccelMap.save

Gtk.PROGRESS_LEFT_TO_RIGHT = (Gtk.Orientation.HORIZONTAL, False)
Gtk.PROGRESS_RIGHT_TO_LEFT = (Gtk.Orientation.HORIZONTAL, True)
Gtk.PROGRESS_BOTTOM_TO_TOP = (Gtk.Orientation.VERTICAL, True)
Gtk.PROGRESS_TOP_TO_BOTTOM = (Gtk.Orientation.VERTICAL, False)

Gtk.CLIPBOARD_PRIMARY = Gdk.Atom.intern('PRIMARY', True)
Gtk.CLIPBOARD_CLIPBOARD = Gdk.Atom.intern('CLIPBOARD', True)

orig_tree_view_column_set_cell_data_func = (
    Gtk.TreeViewColumn.set_cell_data_func)


def set_cell_data_func(self, cell, func, user_data=_unset):
    def callback(*args):
        if args[-1] == _unset:
            args = args[:-1]
        return func(*args)
    orig_tree_view_column_set_cell_data_func(
        self, cell, callback, user_data)
Gtk.TreeViewColumn.set_cell_data_func = set_cell_data_func

Gtk.TreeViewColumn.get_cell_renderers = Gtk.TreeViewColumn.get_cells

orig_set_orientation = Gtk.ProgressBar.set_orientation


def set_orientation(self, orientation):
    orientation, inverted = orientation
    orig_set_orientation(self, orientation)
    self.set_inverted(inverted)
Gtk.ProgressBar.set_orientation = set_orientation

orig_set_orientation = Gtk.CellRendererProgress.set_orientation


def set_orientation(self, orientation):
    orientation, inverted = orientation
    orig_set_orientation(self, orientation)
    self.set_property('inverted', inverted)
Gtk.CellRendererProgress.set_orientation = set_orientation

orig_popup = Gtk.Menu.popup


def popup(self, parent_menu_shell, parent_menu_item, func, button,
        activate_time, data=None):
    if func:
        def position_func(menu, x, y, user_data=None):
            return func(menu, user_data)
    else:
        position_func = None
    orig_popup(self, parent_menu_shell, parent_menu_item,
        position_func, data, button, activate_time)
Gtk.Menu.popup = popup


def get_active_text(self):
    active = self.get_active()
    if active < 0:
        return None
    else:
        model = self.get_model()
        index = self.get_property('entry-text-column')
        return model[active][index]
Gtk.ComboBox.get_active_text = get_active_text

Gtk.GenericCellRenderer.__gobject_init__ = Gtk.GenericCellRenderer.__init__

from gi.repository import Pango


def make_attr_constructor(method):
    def constructor(value, start_index, end_index):
        attr = getattr(Pango, method)(value)
        attr.start_index = start_index
        if end_index >= 0:
            attr.end_index = end_index
        return attr
    return constructor


def make_attr_2_constructor(method):
    def constructor(one, two, start_index, end_index):
        attr = getattr(Pango, method)(one, two)
        attr.start_index = start_index
        if end_index >= 0:
            attr.end_index = end_index
        return attr
    return constructor


def make_attr_3_constructor(method):
    def constructor(one, two, three, start_index, end_index):
        attr = getattr(Pango, method)(one, two, three)
        attr.start_index = start_index
        if end_index >= 0:
            attr.end_index = end_index
        return attr
    return constructor


for method, name, constructor in [
        ('attr_language_new', 'AttrLanguage', make_attr_constructor),
        ('attr_family_new', 'AttrFamily', make_attr_constructor),
        ('attr_foreground_new', 'AttrForeground', make_attr_3_constructor),
        ('attr_background_new', 'AttrBackground', make_attr_3_constructor),
        ('attr_size_new', 'AttrSize', make_attr_constructor),
        ('attr_size_new_absolute', 'AttrSizeAbsolute',
            make_attr_constructor),
        ('attr_style_new', 'AttrStyle', make_attr_constructor),
        ('attr_weight_new', 'AttrWeight', make_attr_constructor),
        ('attr_variant_new', 'AttrVariant', make_attr_constructor),
        ('attr_stretch_new', 'AttrStretch', make_attr_constructor),
        ('attr_font_desc_new', 'AttrFontDesc', make_attr_constructor),
        ('attr_underline_new', 'AttrUnderline', make_attr_constructor),
        ('attr_underline_color_new', 'AttrUnderlineColor',
            make_attr_3_constructor),
        ('attr_strikethrough_new', 'AttrStrikethrough',
            make_attr_constructor),
        ('attr_strikethrough_color_new', 'AttrStrikethroughColor',
            make_attr_3_constructor),
        ('attr_rise_new', 'AttrRise', make_attr_constructor),
        ('attr_scale_new', 'AttrScale', make_attr_constructor),
        ('attr_fallback_new', 'AttrFallback', make_attr_constructor),
        ('attr_letter_spacing_new', 'AttrLetterSpacing',
            make_attr_constructor),
        ('attr_shape_new', 'AttrShape', make_attr_2_constructor),
        ]:
    if hasattr(Pango, method):
        setattr(Pango, name, constructor(method))


import gtk

if not hasattr(gtk, 'TreePath'):
    gtk.TreePath = tuple
if not hasattr(gtk, 'TargetEntry'):
    gtk.TargetEntry = lambda *a: a
    gtk.TargetEntry.new = lambda *a: a
if not hasattr(gtk, 'CLIPBOARD_PRIMARY'):
    gtk.CLIPBOARD_PRIMARY = 'PRIMARY'
    gtk.CLIPBOARD_CLIPBOARD = 'CLIPBOARD'


import gobject
try:
    # Import earlier otherwise there is a segmentation fault on MSYS2
    import goocalendar
except ImportError:
    pass
gobject.threads_init()

if not hasattr(gtk.gdk, 'lock'):
    class _Lock(object):
        __enter__ = gtk.gdk.threads_enter

        def __exit__(*ignored):
            gtk.gdk.threads_leave()

    gtk.gdk.lock = _Lock()

if sys.platform == 'win32':
    class Dialog(gtk.Dialog):

        def run(self):
            with gtk.gdk.lock:
                return super(Dialog, self).run()
    gtk.Dialog = Dialog

if not hasattr(locale, 'localize'):
    def localize(formatted, grouping=False, monetary=False):
        if '.' in formatted:
            seps = 0
            parts = formatted.split('.')
            if grouping:
                parts[0], seps = locale._group(parts[0], monetary=monetary)
            decimal_point = locale.localeconv()[
                monetary and 'mon_decimal_point' or 'decimal_point']
            formatted = decimal_point.join(parts)
            if seps:
                formatted = locale._strip_padding(formatted, seps)
        else:
            seps = 0
            if grouping:
                formatted, seps = locale._group(formatted, monetary=monetary)
            if seps:
                formatted = locale._strip_padding(formatted, seps)
        return formatted
    setattr(locale, 'localize', localize)
