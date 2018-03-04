# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.


def widget_class(widget, name, value):
    style_context = widget.get_style_context()
    if value:
        style_context.add_class(name)
    else:
        style_context.remove_class(name)
