# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
__version__ = "5.2.8"
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_foreign('cairo')
try:
    gi.require_version('GtkSpell', '3.0')
except ValueError:
    pass

try:
    # Import earlier otherwise there is a segmentation fault on MSYS2
    import goocalendar
except ImportError:
    pass
