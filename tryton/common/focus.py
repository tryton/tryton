# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from functools import cmp_to_key

import gtk


def get_invisible_ancestor(widget):
    if not widget.get_visible():
        return widget
    if not widget.props.parent:
        return None
    return get_invisible_ancestor(widget.props.parent)


def find_focused_child(widget):
    if widget.has_focus():
        return widget
    if not hasattr(widget, 'get_children'):
        return None
    for child in widget.get_children():
        focused_widget = find_focused_child(child)
        if focused_widget:
            return focused_widget


def tab_compare(a, b):
    text_direction = gtk.widget_get_default_direction()
    a_allocation = a.get_allocation()
    b_allocation = b.get_allocation()
    y1 = a_allocation.y + a_allocation.height // 2
    y2 = b_allocation.y + b_allocation.height // 2

    if y1 == y2:
        x1 = a_allocation.x + a_allocation.width // 2
        x2 = b_allocation.x + b_allocation.width // 2

        if text_direction == gtk.TEXT_DIR_RTL:
            return (x2 > x1) - (x2 < x1)
        else:
            return (x1 > x2) - (x1 < x2)
    else:
        return (y1 > y2) - (y1 < y2)


def get_focus_chain(widget):
    focus_chain = widget.get_focus_chain()
    # If the focus_chain is not defined on the widget then we will simply
    # search into all its children widgets
    return (focus_chain
        if focus_chain is not None
        else sorted(widget.get_children(), key=cmp_to_key(tab_compare)))


def find_focusable_child(widget):
    if not widget.get_visible():
        return None
    if widget.get_can_focus():
        return widget
    if not hasattr(widget, 'get_children'):
        return None
    for child in get_focus_chain(widget):
        focusable = find_focusable_child(child)
        if focusable:
            return focusable


def next_focus_widget(widget):
    if not widget.props.parent:
        return None
    focus_chain = widget.props.parent.get_focus_chain()
    if focus_chain is not None:
        idx = focus_chain.index(widget)
        focus_widget = None
        for widget in focus_chain[idx:] + focus_chain[:idx]:
            focus_widget = find_focusable_child(widget)
            if focus_widget:
                return focus_widget
        if not focus_widget:
            return next_focus_widget(widget.props.parent)
    else:
        focus_widget = find_focusable_child(widget.props.parent)
        if focus_widget:
            return focus_widget
        else:
            return next_focus_widget(widget.props.parent)


def find_first_focus_widget(ancestor, widgets):
    "Return the widget from widgets which should have first the focus"
    if len(widgets) == 1:
        return widgets[0]
    for child in get_focus_chain(ancestor):
        common = [w for w in widgets if w.is_ancestor(child)]
        if common:
            return find_first_focus_widget(child, common)
