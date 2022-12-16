# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from gettext import gettext as _

import gtk

from .textbox import TextBox
from tryton.common import get_toplevel_window
from tryton.common.htmltextbuffer import (serialize, deserialize,
    setup_tags, normalize_markup, remove_tags, register_foreground,
    FAMILIES, SIZE2SCALE, MIME)
from tryton.config import CONFIG

SIZES = sorted(SIZE2SCALE.keys())
# Disable serialize/deserialize registration function because it does not work
# on GTK-3, the "guint8 *data" is converted into a Gtk.TextIter
_use_serialize_func = False


class RichTextBox(TextBox):

    def __init__(self, view, attrs):
        super(RichTextBox, self).__init__(view, attrs)
        self.text_buffer = gtk.TextBuffer()
        setup_tags(self.text_buffer)
        self.text_buffer.register_serialize_format(
            str(MIME), serialize, None)
        self.text_buffer.register_deserialize_format(
            str(MIME), deserialize, None)
        self.text_buffer.connect_after('insert-text', self.insert_text_style)
        self.textview.set_buffer(self.text_buffer)
        self.textview.connect_after('move-cursor', self.detect_style)
        self.textview.connect('button-release-event', self.detect_style)

        self.toolbar = None
        self.tag_widgets = {}
        self.tags = {}
        self.colors = {}
        if int(self.attrs.get('toolbar', 1)):
            self.toolbar = self.get_toolbar()

    def get_toolbar(self):
        toolbar = gtk.Toolbar()
        toolbar.set_style({
                'default': False,
                'both': gtk.TOOLBAR_BOTH,
                'text': gtk.TOOLBAR_TEXT,
                'icons': gtk.TOOLBAR_ICONS}[CONFIG['client.toolbar']])

        self.widget.pack_start(toolbar, expand=False, fill=True)

        for icon in ['bold', 'italic', 'underline']:
            button = gtk.ToggleToolButton('gtk-%s' % icon)
            button.connect('toggled', self.toggle_props, icon)
            toolbar.insert(button, -1)
            self.tag_widgets[icon] = button

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        for name, options, active in [
                ('family', FAMILIES, FAMILIES.index('normal')),
                ('size', SIZES, SIZES.index('4')),
                ]:
            try:
                combobox = gtk.ComboBoxText()
            except AttributeError:
                combobox = gtk.combo_box_new_text()
            for option in options:
                combobox.append_text(option)
            combobox.set_active(active)
            combobox.set_focus_on_click(False)
            combobox.connect('changed', self.change_props, name)
            tool = gtk.ToolItem()
            tool.add(combobox)
            toolbar.insert(tool, -1)
            self.tag_widgets[name] = combobox

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        button = None
        for icon in ['left', 'center', 'right', 'fill']:
            name = icon
            if icon == 'fill':
                name = 'justify'
            stock_id = 'gtk-justify-%s' % icon
            if hasattr(gtk.RadioToolButton, 'new_with_stock_from_widget'):
                button = gtk.RadioToolButton.new_with_stock_from_widget(
                    button, stock_id)
            else:
                button = gtk.RadioToolButton(button, stock_id)
            button.set_active(icon == 'left')
            button.connect('toggled', self.toggle_justification, name)
            toolbar.insert(button, -1)
            self.tag_widgets[name] = button

        toolbar.insert(gtk.SeparatorToolItem(), -1)

        for icon, label in [
                ('foreground', _('Foreground')),
                # TODO ('background', _('Background')),
                ]:
            button = gtk.ToolButton('tryton-text-%s' % icon)
            button.set_label(label)
            button.connect('clicked', self.toggle_color, icon)
            toolbar.insert(button, -1)
            self.tag_widgets[icon] = button

        return toolbar

    def get_value(self):
        start = self.text_buffer.get_start_iter()
        end = self.text_buffer.get_end_iter()
        if _use_serialize_func:
            return self.text_buffer.serialize(
                self.text_buffer, MIME, start, end)
        else:
            return serialize(
                self.text_buffer, self.text_buffer, start, end, None)

    @property
    def modified(self):
        if self.record and self.field:
            value = normalize_markup(self.field.get_client(self.record) or '')
            return value != self.get_value()
        return False

    def set_buffer(self, value):
        self.text_buffer.handler_block_by_func(self.insert_text_style)
        start = self.text_buffer.get_start_iter()
        end = self.text_buffer.get_end_iter()
        self.text_buffer.delete(start, end)
        if _use_serialize_func:
            self.text_buffer.deserialize(self.text_buffer, MIME, start, value)
        else:
            deserialize(
                self.text_buffer, self.text_buffer, start, value,
                self.text_buffer.deserialize_get_can_create_tags(MIME), None)
        self.text_buffer.handler_unblock_by_func(self.insert_text_style)

    def _readonly_set(self, value):
        super(RichTextBox, self)._readonly_set(value)
        if self.toolbar:
            self.toolbar.set_sensitive(not value)

    def detect_style(self, *args):
        try:
            start, end = self.text_buffer.get_selection_bounds()
        except ValueError:
            start = end = self.text_buffer.get_iter_at_mark(
                self.text_buffer.get_insert())

        def toggle_button(name, values):
            try:
                value, = values
            except ValueError:
                value = False
            button = self.tag_widgets[name]
            button.handler_block_by_func(self.toggle_props)
            button.set_active(value)
            button.handler_unblock_by_func(self.toggle_props)

        def set_combobox(name, indexes):
            try:
                index, = indexes
            except ValueError:
                index = -1
            combobox = self.tag_widgets[name]
            combobox.handler_block_by_func(self.change_props)
            combobox.set_active(index)
            combobox.handler_unblock_by_func(self.change_props)

        def toggle_justification(names, value):
            if len(names) != 1:
                value = False
            for name in names:
                button = self.tag_widgets[name]
                button.handler_block_by_func(self.toggle_justification)
                button.set_active(value)
                button.handler_unblock_by_func(self.toggle_justification)

        bolds, italics, underlines = set(), set(), set()
        families, sizes, justifications = set(), set(), set()

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

    def insert_text_style(self, text_buffer, iter_, text, length):
        # Text is already inserted so iter_ point to the end
        start = iter_.copy()
        start.backward_chars(length)
        end = iter_.copy()
        # Apply tags activated from toolbar
        for name, widget in self.tag_widgets.iteritems():
            self._apply_tool(name, widget, start, end)

    def _apply_tool(self, name, tool, start, end):
        # First test RadioToolButton as they inherit from ToggleToolButton
        if isinstance(tool, gtk.RadioToolButton):
            name = 'justification %s' % name
            if not tool.get_active():
                remove_tags(self.text_buffer, start, end, name)
            else:
                remove_tags(self.text_buffer, start, end, 'justification')
                self.text_buffer.apply_tag_by_name(name, start, end)
        elif isinstance(tool, gtk.ToggleToolButton):
            if tool.get_active():
                self.text_buffer.apply_tag_by_name(name, start, end)
            else:
                self.text_buffer.remove_tag_by_name(name, start, end)
        elif isinstance(tool, gtk.ComboBox):
            value = tool.get_active_text()
            remove_tags(self.text_buffer, start, end, name)
            name = '%s %s' % (name, value)
            self.text_buffer.apply_tag_by_name(name, start, end)

    def toggle_props(self, toggle, name):
        try:
            start, end = self.text_buffer.get_selection_bounds()
        except ValueError:
            return
        self._apply_tool(name, toggle, start, end)

    def change_props(self, combobox, name):
        try:
            start, end = self.text_buffer.get_selection_bounds()
        except ValueError:
            return
        self._apply_tool(name, combobox, start, end)

    def toggle_justification(self, button, name):
        try:
            start, end = self.text_buffer.get_selection_bounds()
        except ValueError:
            insert = self.text_buffer.get_insert()
            start = self.text_buffer.get_iter_at_mark(insert)
            end = start.copy()
        start.set_line_offset(0)
        if not end.ends_line():
            end.forward_to_line_end()
        self._apply_tool(name, button, start, end)

    def toggle_color(self, button, name):
        insert = self.text_buffer.get_insert()
        try:
            start, end = self.text_buffer.get_selection_bounds()
        except ValueError:
            start = end = None
        else:
            # Use offset position to preserve across buffer modification
            start = start.get_offset()
            end = end.get_offset()

        dialog = gtk.ColorSelectionDialog(_('Select a color'))
        dialog.set_transient_for(get_toplevel_window())
        colorsel = dialog.get_color_selection()
        colorsel.set_has_palette(True)
        color = self.colors.get(name)
        if color:
            colorsel.set_current_color(color)
        if dialog.run() == gtk.RESPONSE_OK:
            color = colorsel.get_current_color()
            self.colors[name] = color
            if start is not None and end is not None:
                start = self.text_buffer.get_iter_at_offset(start)
                end = self.text_buffer.get_iter_at_offset(end)
                tag = register_foreground(self.text_buffer, color)
                remove_tags(self.text_buffer, start, end, name)
                self.text_buffer.apply_tag(tag, start, end)
        dialog.destroy()
        self.text_buffer.place_cursor(
            self.text_buffer.get_iter_at_mark(insert))
