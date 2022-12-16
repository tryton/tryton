# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import gtk
import pango
import re
from gettext import gettext as _
from .textbox import TextBox
from tryton.common import get_toplevel_window


def formalize_text_markup(text):
    '''This function formalize the text markup for editing and save data'''
    # Formalize <span> tag
    i = 0
    stack = []
    occurrence = 0
    span_open = "<span (.+?)='(.+?)'>"
    while i < len(text):
        data = re.match(span_open, text[i:])
        if data:
            occurrence += 1
            if not stack or occurrence == 1:
                stack.append([data.start() + i, data.end() + i, occurrence])
            else:
                stack[-1][1] = data.end() + i
                stack[-1][2] = occurrence
            i += data.end()
        else:
            occurrence = 0
            i += 1
        if stack:
            span_close = '</span>' * stack[-1][2]
            data = re.search('^' + span_close, text[i:])
            if data and stack[-1][2] > 1:
                span = stack.pop()
                text = re.sub(span_close, text[:i] + '</span>', text[i:], 1)
                text = text[:span[0]] + re.sub('><span', '',
                    text[span[0]:span[1]]) + text[span[1]:]
                i += data.end()
    # Special character
    text = re.sub('<\x08', '</b', text)
    # Formalize <p> tag
    lines = text.split('\n')
    align = "left"
    for i in range(len(lines)):
        while True:
            data = re.search("<p( align='(?P<val>[a-z]{4,6})')?>", lines[i])
            if data and data.group('val'):
                align = data.group('val')
                lines[i] = re.sub("<p( align='[a-z]{4,6}')?>", '', lines[i], 1)
            else:
                break
        actual_align = "<p align='%s'>" % align
        if re.search("</p>", lines[i]):
            align = 'left'
        lines[i] = re.sub('</p>', '', lines[i])
        # If not exists any line add paragraph
        if not re.search('^$', lines[i]):
            lines[i] = actual_align + lines[i] + "</p>"
    return '\n'.join(lines)


class RichTextBox(TextBox):
    '''Implements a rich text editor as widget to Tryton Client'''

    def __init__(self, view, attrs):
        super(RichTextBox, self).__init__(view, attrs)
        self.table_tag = gtk.TextTagTable()
        self.text_buffer = gtk.TextBuffer(self.table_tag)
        self.textview.set_buffer(self.text_buffer)
        self.textview.connect_after('move-cursor', self.detect_style)
        self.textview.connect('button-release-event', self.detect_style)
        self.focus_out = True

        tags = ('bold', 'italic', 'underline', 'font_family', 'size', 'left',
            'center', 'right', 'fill', 'foreground', 'background', 'markup')
        # Build all buttons
        self.tools = {}
        for tag in tags[:3]:
            self.tools[tag] = gtk.ToggleToolButton('gtk-%s' % tag)
        self.sizes = map(str, range(6, 33))
        fonts = self.textview.get_pango_context().list_families()
        self.families = sorted([font.get_name() for font in fonts])
        for tag, values in zip(tags[3:5], (self.families, self.sizes)):
            self.tools[tag] = gtk.ToolItem()
            box = gtk.combo_box_new_text()
            for value in values:
                box.append_text(value)
            box.set_focus_on_click(False)
            self.tools[tag].add(box)
        group = None
        for tag in tags[5:9]:
            self.tools[tag] = gtk.RadioToolButton(group,
                'gtk-justify-%s' % tag)
            if not group:
                group = self.tools[tag]
        for tag in tags[9:11]:
            self.tools[tag] = gtk.ToolButton('tryton-text-%s' % tag)
        self.tools['markup'] = gtk.ToggleToolButton('tryton-text-markup')
        # Set properties to each button
        tag_values = (
            ('bold', 'weight', pango.WEIGHT_BOLD),
            ('italic', 'style', pango.STYLE_ITALIC),
            ('underline', 'underline', pango.UNDERLINE_SINGLE),
            ('left', 'justification', gtk.JUSTIFY_LEFT),
            ('center', 'justification', gtk.JUSTIFY_CENTER),
            ('right', 'justification', gtk.JUSTIFY_RIGHT),
            ('fill', 'justification', gtk.JUSTIFY_FILL),
            )
        self.text_tags = {}
        for tag, name, prop in tag_values:
            self.text_tags[tag] = gtk.TextTag(tag)
            self.text_tags[tag].set_property(name, prop)
            self.table_tag.add(self.text_tags[tag])
        self.font_props = {
            'font_family': {},
            'size': {},
            'foreground': {},
            'background': {},
            }
        font_desc = self.textview.get_pango_context().get_font_description()
        self.current_font_prop = {
            'foreground': gtk.gdk.Color('#000'),
            'background': gtk.gdk.Color('#fff'),
            'font_family': font_desc.get_family(),
            'size': str(font_desc.get_size() / pango.SCALE),
            'justify': 'left',
            }
        self.tools['size'].child.set_active(self.sizes.index(
            self.current_font_prop['size']))
        font_family = self.current_font_prop['font_family']
        if font_family in self.families:
            self.tools['font_family'].child.set_active(self.families.index(
                    font_family))
        self.start_tags = {}
        self.end_tags = {}
        # Connect events
        self.tool_ids = {}
        for tag in tags[:3]:
            self.tool_ids[tag] = self.tools[tag].connect('toggled',
                self.action_style_font, self.text_tags[tag], tag)
        for tag in tags[3:5]:
            self.tool_ids[tag] = self.tools[tag].child.connect('changed',
                self.action_prop_font, tag)
        for tag in tags[5:9]:
            self.tool_ids[tag] = self.tools[tag].connect('toggled',
                self.action_justification, tag)
        for tag in tags[9:11]:
            self.tool_ids[tag] = self.tools[tag].connect('clicked',
                self.action_prop_font, tag)
        self.tool_ids['markup'] = self.tools['markup'].connect('toggled',
            self.edit_text_markup)
        self.insert_text_id = self.text_buffer.connect_after('insert-text',
            self.persist_style)
        # Tooltip text
        self.tools['bold'].set_tooltip_text(_('Change text to bold'))
        self.tools['italic'].set_tooltip_text(_('Change text to italic'))
        self.tools['underline'].set_tooltip_text(_('Change text to underline'))
        self.tools['font_family'].set_tooltip_text(_('Choose font-family'))
        self.tools['size'].set_tooltip_text(_('Choose font-size'))
        self.tools['left'].set_tooltip_text(_('Justify of line to the left'))
        self.tools['center'].set_tooltip_text(
            _('Justify of line to the center'))
        self.tools['right'].set_tooltip_text(_('Justify of line to the right'))
        self.tools['fill'].set_tooltip_text(
            _('Justify of line to fill window'))
        self.tools['foreground'].set_tooltip_text(
            _('Change the foreground text'))
        self.tools['background'].set_tooltip_text(
            _('Change the background text'))
        self.tools['markup'].set_tooltip_text(_('Change the markup text view'))
        # Packing widgets
        self.tool_bar = gtk.Toolbar()

        self.tool_bar.set_style(gtk.TOOLBAR_ICONS)
        for tag in tags:
            self.tool_bar.insert(self.tools[tag], -1)
        separator = gtk.SeparatorToolItem
        for local in (3, 6, 11, 14):
            self.tool_bar.insert(separator(), local)
        self.widget.pack_start(self.tool_bar, False)

    def get_value_markup(self):
        if self.tools['markup'].get_active():
            return self.get_value()
        else:
            return self.parser_to_text_markup(self.text_buffer)

    @property
    def modified(self):
        if self.record and self.field:
            return (formalize_text_markup(self.field.get_client(self.record) or
                    '') != self.get_value_markup())
        return False

    def set_value(self, record, field):
        # Popup for font_family and size should not trigger set_value from
        # Form.leave otherwise the selection is lost
        for tag in ('font_family', 'size'):
            tool = self.tools[tag]
            if (hasattr(tool.child.props, 'popup_shown')
                    and tool.child.props.popup_shown):
                return
        if self.modified:
            field.set_client(record, self.get_value_markup())

    def set_buffer(self, value):
        self.text_buffer.handler_block(self.insert_text_id)
        if self.tools['markup'].get_active():
            super(RichTextBox, self).set_buffer(value)
        else:
            text_buffer, deserial = self.parser_from_text_markup(value)
            self.text_buffer.deserialize(self.text_buffer, deserial,
                self.text_buffer.get_start_iter(),
                text_buffer.serialize(text_buffer,
                    "application/x-gtk-text-buffer-rich-text",
                    text_buffer.get_start_iter(), text_buffer.get_end_iter()))
        self.text_buffer.handler_unblock(self.insert_text_id)

    def _focus_out(self):
        if not self.focus_out:
            return
        # Popup for font_family and size should not trigger focus_out
        # otherwise the selection is lost
        for tag in ('font_family', 'size'):
            tool = self.tools[tag]
            if (hasattr(tool.child.props, 'popup_shown')
                    and tool.child.props.popup_shown):
                return
        super(RichTextBox, self)._focus_out()

    def _readonly_set(self, value):
        super(RichTextBox, self)._readonly_set(value)
        self.tool_bar.set_sensitive(not value)
        if value and self.tools['markup'].get_active():
            self.tools['markup'].set_active(False)

    def edit_text_markup(self, widget):
        '''on/off all buttons and call the appropriate parser'''
        tags = [tag for tag in self.tools if tag != 'markup']
        if widget.get_active():
            for tag in tags:
                self.tools[tag].set_sensitive(False)
            text = self.parser_to_text_markup(self.text_buffer)
            self.start_tags.clear()
            self.end_tags.clear()
        else:
            for tag in tags:
                self.tools[tag].set_sensitive(True)
            text = self.text_buffer.get_text(self.text_buffer.get_start_iter(),
                self.text_buffer.get_end_iter()).decode('utf-8')
        self.set_buffer(text)

    def parser_to_text_markup(self, buffer_):
        '''Parser from rich text view to text markup'''
        text_buffer = gtk.TextBuffer(self.table_tag)
        deserial = text_buffer.register_deserialize_tagset()
        text_buffer.deserialize(text_buffer, deserial,
            text_buffer.get_start_iter(), buffer_.serialize(
                buffer_, "application/x-gtk-text-buffer-rich-text",
                buffer_.get_start_iter(), buffer_.get_end_iter()))
        locks = {'bold': False, 'italic': False, 'underline': False,
            'left': False, 'right': False, 'center': False, 'fill': False}
        for prop in self.font_props:
            for tag_name in self.font_props[prop]:
                locks["%s %s" % (prop, tag_name)] = False
        imark = text_buffer.get_start_iter()
        while True:
            begin_mark = text_buffer.create_mark(None, imark, False)
            end_mark = text_buffer.create_mark(None, imark, True)
            for tag in ('bold', 'italic', 'underline'):
                imark = text_buffer.get_iter_at_mark(begin_mark)
                if imark.begins_tag(self.text_tags[tag]) and not locks[tag]:
                    text_buffer.insert(imark, "<%s>" % tag[0])
                    locks[tag] = True
                imark = text_buffer.get_iter_at_mark(end_mark)
                if imark.ends_tag(self.text_tags[tag]) and locks[tag]:
                    text_buffer.insert(imark, "</%s>" % tag[0])
                    locks[tag] = False
            for tag in ('left', 'right', 'center', 'fill'):
                imark = text_buffer.get_iter_at_mark(begin_mark)
                if imark.begins_tag(self.text_tags[tag]) and not locks[tag]:
                    text_buffer.insert(imark, "<p align='%s'>" % tag)
                    locks[tag] = True
                imark = text_buffer.get_iter_at_mark(end_mark)
                if imark.ends_tag(self.text_tags[tag]) and locks[tag]:
                    text_buffer.insert(imark, "</p>")
                    locks[tag] = False
            for tag in ('font_family', 'size', 'foreground', 'background'):
                for name, prop in self.font_props[tag].items():
                    imark = text_buffer.get_iter_at_mark(end_mark)
                    if (imark.begins_tag(prop)
                            and not locks['%s %s' % (tag, name)]):
                        locks['%s %s' % (tag, name)] = True
                        text_buffer.insert(imark,
                            "<span %s='%s'>" % (tag, name))
                    imark = text_buffer.get_iter_at_mark(end_mark)
                    if imark.ends_tag(prop) and locks['%s %s' % (tag, name)]:
                        locks['%s %s' % (tag, name)] = False
                        text_buffer.insert(imark, "</span>")
            imark = text_buffer.get_iter_at_mark(end_mark)
            if not imark.forward_to_tag_toggle(None):
                break
        text = text_buffer.get_text(text_buffer.get_start_iter(),
            text_buffer.get_end_iter()).decode('utf-8')
        return formalize_text_markup(text)

    def parser_from_text_markup(self, text):
        '''Parser from text markup to rich text view'''
        text_buffer = gtk.TextBuffer(self.table_tag)
        text_buffer.set_text(text)
        tags = []
        open_re = '<(?P<tag>\w{1,4})(?P<attrs> .+?)?>'
        create_mark = lambda pos: text_buffer.create_mark(None,
            text_buffer.get_iter_at_offset(pos), True)
        tag_names = {'b': 'bold', 'i': 'italic', 'u': 'underline',
            'p': 'justify', 'size': 'size', 'font_family': 'font_family',
            'foreground': 'foreground', 'background': 'background'}
        while re.search(open_re, text):
            data_open = re.search(open_re, text)
            tag = data_open.group('tag')
            attributes = data_open.group('attrs')
            text = re.sub(open_re, '', text, 1)
            text_buffer.delete(text_buffer.get_iter_at_offset(
                data_open.start()), text_buffer.get_iter_at_offset(
                    data_open.end()))
            close_re = '</%s>' % tag
            data_close = re.search(close_re, text)
            if data_close:
                text = re.sub(close_re, '', text, 1)
                text_buffer.delete(text_buffer.get_iter_at_offset(
                    data_close.start()), text_buffer.get_iter_at_offset(
                        data_close.end()))
                start = create_mark(data_open.start())
                end = create_mark(data_close.start())
                if tag in ('b', 'i', 'u'):
                    tags.append((start, end, tag_names[tag], None))
                elif tag == 'p':
                    val = re.search("align='(\w{,6})'", attributes)
                    if val:
                        tags.append((start, end, tag_names[tag], val.group(1)))
                elif tag == 'span':
                    attrs_re = " ([\w_]{4,11})='(.+?)'"
                    while re.search(attrs_re, attributes):
                        data = re.search(attrs_re, attributes)
                        att, val = data.group(1), data.group(2)
                        attributes = re.sub(attrs_re, '', attributes, 1)
                        tags.append((start, end, tag_names[att], val))
        for start, end, tag, value in tags:
            start = text_buffer.get_iter_at_mark(start)
            end = text_buffer.get_iter_at_mark(end)
            if tag in ('bold', 'italic', 'underline'):
                text_buffer.apply_tag(self.text_tags[tag], start, end)
            elif tag in ('font_family', 'size', 'foreground', 'background'):
                text_buffer.apply_tag(self.gen_tag(value, tag), start, end)
            else:  # tag <p>
                line = text_buffer.get_iter_at_line(start.get_line())
                text_buffer.apply_tag_by_name(value, line, end)
        self.text_buffer.set_text('')
        deserial = self.text_buffer.register_deserialize_tagset()
        return text_buffer, deserial

    def gen_tag(self, val, tag):
        '''
        Generates tags according tag values (foreground, background,
        font-family, font-size)
        '''
        key = "%s %s" % (tag, val)
        prop = {'foreground': 'foreground', 'background': 'background',
                'font_family': 'family', 'size': 'size-points'}
        try:
            self.font_props[tag][str(val)]
        except KeyError:
            self.font_props[tag][str(val)] = gtk.TextTag(key)
            try:
                self.font_props[tag][str(val)].set_property(prop[tag], val)
            except TypeError:
                self.font_props[tag][str(val)].set_property(prop[tag],
                    int(val))
            self.table_tag.add(self.font_props[tag][str(val)])
        return self.font_props[tag][str(val)]

    def detect_style(self, *args):
        '''
        Detect the styles of text when cursor is clicked in differents parts of
        text area
        '''
        local = self.text_buffer.get_iter_at_mark(
            self.text_buffer.get_insert())
        local.backward_char()
        current_tags = local.get_tags()
        locks = {'bold': False, 'italic': False, 'underline': False}
        font_desc = self.textview.get_pango_context().get_font_description()
        font_name = font_desc.get_family()
        size_name = str(font_desc.get_size() / pango.SCALE)
        justify, justify_type = True, 'left'
        for tag in current_tags:
            if tag.get_property('weight-set'):
                locks['bold'] = True
            elif tag.get_property('style-set'):
                locks['italic'] = True
            elif tag.get_property('underline-set'):
                locks['underline'] = True
            elif tag.get_property('family-set'):
                font_name = tag.get_property('family')
            elif tag.get_property('size-set'):
                size_name = str(int(tag.get_property('size-points')))
            elif tag.get_property('justification'):
                justify = True
                justify_type = tag.get_property('justification').value_nick
        for tag in ('bold', 'italic', 'underline'):
            self.tools[tag].handler_block(self.tool_ids[tag])
            self.tools[tag].set_active(locks[tag])
            self.tools[tag].handler_unblock(self.tool_ids[tag])
        for tag, attr, name in (('font_family', self.families, font_name),
        ('size', self.sizes, size_name)):
            self.tools[tag].child.handler_block(self.tool_ids[tag])
            self.tools[tag].child.set_active(attr.index(name))
            self.tools[tag].child.handler_unblock(self.tool_ids[tag])
        if justify_type != self.current_font_prop['justify']:
            tags = ('left', 'center', 'right', 'fill')
            for tag in tags:
                self.tools[tag].handler_block(self.tool_ids[tag])
            self.tools[justify_type].set_active(justify)
            for tag in tags:
                self.tools[tag].handler_unblock(self.tool_ids[tag])
            self.current_font_prop['justify'] = justify_type

    def persist_style(self, *args):
        '''Persistence of style when it is insert some text'''
        for tag in self.start_tags:
            start = self.text_buffer.get_iter_at_mark(self.start_tags[tag])
            end = self.text_buffer.get_iter_at_mark(self.end_tags[tag])
            justify_tags = ('left', 'center', 'right', 'fill')
            if tag in ('bold', 'italic', 'underline'):
                self.text_buffer.apply_tag_by_name(tag, start, end)
            elif tag in ('foreground', 'background', 'font_family', 'size'):
                self.text_buffer.apply_tag(self.gen_tag(
                    self.current_font_prop[tag], tag), start, end)
            elif tag in justify_tags:
                self.text_buffer.apply_tag_by_name(tag, start, end)

    def action_style_font(self, widget, texttag, tag):
        '''
        Apply style to text (selected or not) tag (bold, italic, underline)
        widget (button was clicked) texttag (correct tag in this method)
        '''
        if widget.get_active():
            if self.text_buffer.get_selection_bounds():
                start, end = self.text_buffer.get_selection_bounds()
                self.text_buffer.apply_tag(texttag, start, end)
            else:
                mark = self.text_buffer.get_iter_at_mark(
                    self.text_buffer.get_insert())
                start = self.text_buffer.create_mark(None, mark, True)
                end = self.text_buffer.create_mark(None, mark, False)
                self.start_tags[tag] = start
                self.end_tags[tag] = end
        else:
            if self.text_buffer.get_selection_bounds():
                start, end = self.text_buffer.get_selection_bounds()
                self.text_buffer.remove_tag_by_name(tag, start, end)
            else:
                if tag in self.start_tags:
                    del(self.start_tags[tag], self.end_tags[tag])

    def action_justification(self, widget, tag):
        '''Justify text of different tags (left, right, center, fill)'''
        if self.text_buffer.get_selection_bounds():
            start, end = self.text_buffer.get_selection_bounds()
            line = start.get_line()
            iter_line = self.text_buffer.get_iter_at_line(line)
            if not end.ends_line():
                end.forward_to_line_end()
            self.text_buffer.apply_tag_by_name(tag, iter_line, end)
        else:
            mark = self.text_buffer.get_iter_at_mark(
                self.text_buffer.get_insert())
            start = self.text_buffer.create_mark(None, mark, True)
            end = self.text_buffer.get_iter_at_mark(start)
            if not end.ends_line():
                end.forward_to_line_end()
            line = end.get_line()
            iter_line = self.text_buffer.get_iter_at_line(line)
        if widget.get_active():
            self.start_tags[tag] = self.text_buffer.create_mark(None,
                iter_line, True)
            self.end_tags[tag] = self.text_buffer.create_mark(None, end, False)
            self.text_buffer.apply_tag_by_name(tag, iter_line, end)
        else:
            self.text_buffer.remove_tag_by_name(tag, iter_line, end)
            if tag in self.start_tags:
                del(self.start_tags[tag], self.end_tags[tag])
        self.current_font_prop['justify'] = tag

    def action_prop_font(self, widget, tag):
        '''
        Apply style to text (selected or not) tag (color foreground, color
        background, font-family and font-size)
        '''
        content = None
        if tag in ['foreground', 'background']:
            # Deactivate focus_out to not lose selection
            self.focus_out = False
            labels = {
                'foreground': _('Select a foreground color'),
                'background': _('Select a background color'),
                }
            dialog = gtk.ColorSelectionDialog(labels[tag])
            dialog.set_transient_for(get_toplevel_window())
            dialog.set_resizable(False)
            dialog.colorsel.set_has_palette(True)
            dialog.colorsel.set_current_color(self.current_font_prop[tag])
            res = dialog.run()
            if res == gtk.RESPONSE_OK:
                content = dialog.colorsel.get_current_color()
                self.current_font_prop[tag] = content
            dialog.destroy()
            self.focus_out = True
        else:
            content = self.tools[tag].child.get_active_text()
            font = self.current_font_prop[tag]
            self.current_font_prop[tag] = content
        bounds = self.text_buffer.get_selection_bounds()
        if bounds:
            start, end = bounds
            if tag in ('font_family', 'size'):
                self.text_buffer.remove_tag(
                    self.gen_tag(font, tag), start, end)
            self.text_buffer.apply_tag(self.gen_tag(content, tag), start, end)
        else:
            mark = self.text_buffer.get_iter_at_mark(
                self.text_buffer.get_insert())
            start = self.text_buffer.create_mark(None, mark, True)
            end = self.text_buffer.create_mark(None, mark, False)
            self.start_tags[tag] = start
            self.end_tags[tag] = end
