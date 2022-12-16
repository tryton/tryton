# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import gettext
from contextlib import contextmanager

from gi.repository import Gtk, Gdk

from tryton.common import IconFactory
from tryton.common.htmltextbuffer import (
    serialize, deserialize,
    setup_tags, register_foreground, remove_tags,
    FAMILIES, SIZE2SCALE, MIME, use_serialize_func)

_ = gettext.gettext
SIZES = sorted(SIZE2SCALE.keys())


def register_format(textview):
    buffer_ = textview.get_buffer()
    setup_tags(buffer_)
    buffer_.register_serialize_format(str(MIME), serialize, None)
    buffer_.register_deserialize_format(str(MIME), deserialize, None)


def set_content(textview, content):
    with disable_text_style(textview):
        buffer_ = textview.get_buffer()
        start = buffer_.get_start_iter()
        end = buffer_.get_end_iter()
        buffer_.delete(start, end)
        if use_serialize_func:
            buffer_.deserialize(buffer_, MIME, start, content)
        else:
            deserialize(
                buffer_, buffer_, start, content,
                buffer_.deserialize_get_can_create_tags(MIME), None)


def get_content(textview):
    buffer_ = textview.get_buffer()
    start = buffer_.get_start_iter()
    end = buffer_.get_end_iter()
    if use_serialize_func:
        return buffer_.serialize(buffer_, MIME, start, end)
    else:
        return serialize(buffer_, buffer_, start, end, None)


def add_toolbar(textview):
    toolbar = Gtk.Toolbar()

    tag_widgets = {}
    colors = {}

    for icon, label in [
            ('bold', _("Bold")),
            ('italic', _("Italic")),
            ('underline', _("Underline")),
            ]:
        button = Gtk.ToggleToolButton()
        button.set_icon_widget(IconFactory.get_image(
                'tryton-format-%s' % icon,
                Gtk.IconSize.SMALL_TOOLBAR))
        button.set_label(label)
        button.connect('toggled', _toggle_props, icon, textview)
        toolbar.insert(button, -1)
        tag_widgets[icon] = button

    toolbar.insert(Gtk.SeparatorToolItem(), -1)

    for name, options, active in [
            ('family', FAMILIES, FAMILIES.index('normal')),
            ('size', SIZES, SIZES.index('4')),
            ]:
        combobox = Gtk.ComboBoxText()
        for option in options:
            combobox.append_text(option)
        combobox.set_active(active)
        combobox.set_focus_on_click(False)
        combobox.connect('changed', _change_props, name, textview)
        tool = Gtk.ToolItem()
        tool.add(combobox)
        toolbar.insert(tool, -1)
        tag_widgets[name] = combobox

    toolbar.insert(Gtk.SeparatorToolItem(), -1)

    button = None
    for name, label in [
            ('left', _("Align Left")),
            ('center', _("Align Center")),
            ('right', _("Align Right")),
            ('justify', _("Justify")),
            ]:
        icon = 'tryton-format-align-%s' % name
        button = Gtk.RadioToolButton.new_from_widget(button)
        button.set_icon_widget(IconFactory.get_image(
                icon, Gtk.IconSize.SMALL_TOOLBAR))
        button.set_active(icon == 'left')
        button.set_label(label)
        button.connect(
            'toggled', _toggle_justification, name, textview)
        toolbar.insert(button, -1)
        tag_widgets[name] = button

    toolbar.insert(Gtk.SeparatorToolItem(), -1)

    for icon, label in [
            ('foreground', _("Foreground Color")),
            # TODO ('background', _('Background')),
            ]:
        button = Gtk.ToolButton()
        if icon == 'foreground':
            button.set_icon_widget(IconFactory.get_image(
                    'tryton-format-color-text',
                    Gtk.IconSize.SMALL_TOOLBAR))
        button.set_label(label)
        button.connect('clicked', _toggle_color, icon, textview, colors)
        toolbar.insert(button, -1)
        tag_widgets[icon] = button

    buffer_ = textview.get_buffer()
    buffer_.connect_after(
        'insert-text', _insert_text_style, tag_widgets)
    textview.connect_after(
        'move-cursor',
        lambda *a: _detect_style(textview, tag_widgets, colors))
    textview.connect_after(
        'button-release-event',
        lambda *a: _detect_style(textview, tag_widgets, colors))

    return toolbar


@contextmanager
def disable_text_style(textview):
    buffer_ = textview.get_buffer()
    try:
        buffer_.handler_block_by_func(_insert_text_style)
    except TypeError:
        pass
    yield
    try:
        buffer_.handler_unblock_by_func(_insert_text_style)
    except TypeError:
        pass


def _toggle_props(toggle, name, textview):
    buffer_ = textview.get_buffer()
    try:
        start, end = buffer_.get_selection_bounds()
    except ValueError:
        return
    _apply_tool(buffer_, name, toggle, start, end)


def _change_props(combobox, name, textview):
    buffer_ = textview.get_buffer()
    try:
        start, end = buffer_.get_selection_bounds()
    except ValueError:
        return
    _apply_tool(buffer_, name, combobox, start, end)


def _toggle_justification(button, name, textview):
    buffer_ = textview.get_buffer()
    try:
        start, end = buffer_.get_selection_bounds()
    except ValueError:
        insert = buffer_.get_insert()
        start = buffer_.get_iter_at_mark(insert)
        end = start.copy()
    start.set_line_offset(0)
    if not end.ends_line():
        end.forward_to_line_end()
    _apply_tool(buffer_, name, button, start, end)


def _toggle_color(button, name, textview, colors):
    buffer_ = textview.get_buffer()
    insert = buffer_.get_insert()
    try:
        start, end = buffer_.get_selection_bounds()
    except ValueError:
        start = end = None
    else:
        # Use offset position to preserve across buffer_ modification
        start = start.get_offset()
        end = end.get_offset()

    dialog = Gtk.ColorChooserDialog(
        title=_('Select a color'),
        transient_for=textview.get_toplevel(),
        use_alpha=False)
    color = Gdk.RGBA()
    if name in colors:
        color.parse(colors[name])
        dialog.set_rgba(color)
    if dialog.run() == Gtk.ResponseType.OK:
        color = dialog.get_rgba()
        if start is not None and end is not None:
            start = buffer_.get_iter_at_offset(start)
            end = buffer_.get_iter_at_offset(end)
            tag = register_foreground(buffer_, color)
            remove_tags(buffer_, start, end, name)
            buffer_.apply_tag(tag, start, end)
    dialog.destroy()
    buffer_.place_cursor(buffer_.get_iter_at_mark(insert))


def _apply_tool(buffer_, name, tool, start, end):
    # First test RadioToolButton as they inherit from ToggleToolButton
    if isinstance(tool, Gtk.RadioToolButton):
        name = 'justification %s' % name
        if not tool.get_active():
            remove_tags(buffer_, start, end, name)
        else:
            remove_tags(buffer_, start, end, 'justification')
            buffer_.apply_tag_by_name(name, start, end)
    elif isinstance(tool, Gtk.ToggleToolButton):
        if tool.get_active():
            buffer_.apply_tag_by_name(name, start, end)
        else:
            buffer_.remove_tag_by_name(name, start, end)
    elif isinstance(tool, Gtk.ComboBoxText):
        value = tool.get_active_text()
        remove_tags(buffer_, start, end, name)
        name = '%s %s' % (name, value)
        buffer_.apply_tag_by_name(name, start, end)


def _insert_text_style(buffer_, iter_, text, length, tag_widgets):
    # Text is already inserted so iter_ points to the end
    start = iter_.copy()
    start.backward_chars(length)
    end = iter_.copy()
    # Apply tags activated from the toolbar
    for name, widget in tag_widgets.items():
        _apply_tool(buffer_, name, widget, start, end)


def _detect_style(textview, tag_widgets, colors):
    buffer_ = textview.get_buffer()
    try:
        start, end = buffer_.get_selection_bounds()
    except ValueError:
        start = end = buffer_.get_iter_at_mark(
            buffer_.get_insert())

    def toggle_button(name, values):
        try:
            value, = values
        except ValueError:
            value = False
        button = tag_widgets[name]
        button.handler_block_by_func(_toggle_props)
        button.set_active(value)
        button.handler_unblock_by_func(_toggle_props)

    def set_combobox(name, indexes):
        try:
            index, = indexes
        except ValueError:
            index = -1
        combobox = tag_widgets[name]
        combobox.handler_block_by_func(_change_props)
        combobox.set_active(index)
        combobox.handler_unblock_by_func(_change_props)

    def toggle_justification(names, value):
        if len(names) != 1:
            value = False
        for name in names:
            button = tag_widgets[name]
            button.handler_block_by_func(_toggle_justification)
            button.set_active(value)
            button.handler_unblock_by_func(_toggle_justification)

    bolds, italics, underlines = set(), set(), set()
    families, sizes, justifications = set(), set(), set()
    colors['foreground'] = 'black'

    iter_ = start.copy()
    while True:
        bold, italic, underline = False, False, False
        family = FAMILIES.index('normal')
        size = SIZES.index('4')
        justification = 'left'

        for tag in iter_.get_tags():
            if not tag.props.name:
                continue
            elif tag.props.name == 'bold':
                bold = True
            elif tag.props.name == 'italic':
                italic = True
            elif tag.props.name == 'underline':
                underline = True
            elif tag.props.name.startswith('family'):
                _, family = tag.props.name.split()
                family = FAMILIES.index(family)
            elif tag.props.name.startswith('size'):
                _, size = tag.props.name.split()
                size = SIZES.index(size)
            elif tag.props.name.startswith('justification'):
                _, justification = tag.props.name.split()
            elif tag.props.name.startswith('foreground'):
                _, colors['foreground'] = tag.props.name.split()
        bolds.add(bold)
        italics.add(italic)
        underlines.add(underline)
        families.add(family)
        sizes.add(size)
        justifications.add(justification)

        iter_.forward_char()
        if iter_.compare(end) > 0:
            iter_ = end
        if iter_.compare(end) == 0:
            break

    for name, values in [
            ('bold', bolds),
            ('italic', italics),
            ('underline', underlines)]:
        toggle_button(name, values)
    set_combobox('family', families)
    set_combobox('size', sizes)
    toggle_justification(justifications, True)


if __name__ == '__main__':
    win = Gtk.Window()
    box = Gtk.VBox()
    win.add(box)

    textview = Gtk.TextView()
    register_format(textview)
    toolbar = add_toolbar(textview)
    box.pack_start(toolbar, expand=False, fill=True, padding=0)
    box.pack_start(textview, expand=True, fill=True, padding=0)

    win.show_all()
    Gtk.main()
