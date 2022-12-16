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

    def widget_class(widget, name, value):
        pass
else:
    def set_widget_style(widget, editable):
        pass

    def widget_class(widget, name, value):
        style_context = widget.get_style_context()
        if value:
            style_context.add_class(name)
        else:
            style_context.remove_class(name)
