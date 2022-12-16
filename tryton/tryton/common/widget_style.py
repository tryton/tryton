# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gtk

gtk_version = getattr(gtk, 'get_major_version', lambda: 2)()

if gtk_version == 2:
    def set_widget_style(widget, editable):
        style = widget.__class__().get_style()
        if editable:
            widget.modify_fg(gtk.STATE_NORMAL, style.fg[gtk.STATE_NORMAL])
            widget.modify_base(gtk.STATE_NORMAL, style.base[gtk.STATE_NORMAL])
            widget.modify_bg(gtk.STATE_NORMAL, style.bg[gtk.STATE_NORMAL])
        else:
            widget.modify_fg(gtk.STATE_NORMAL, style.fg[gtk.STATE_INSENSITIVE])
            widget.modify_base(
                gtk.STATE_NORMAL, style.base[gtk.STATE_INSENSITIVE])
            widget.modify_bg(gtk.STATE_NORMAL, style.bg[gtk.STATE_INSENSITIVE])
else:
    def set_widget_style(widget, editable):
        # TODO
        pass
