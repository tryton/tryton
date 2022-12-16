# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import sys
from io import StringIO
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, unescape
from html.parser import HTMLParser

from gi.repository import Gtk, Gdk, Pango


def guess_decode(bytes, errors='strict'):
    for encoding in [sys.getfilesystemencoding(), 'utf-8', 'utf-16', 'utf-32']:
        try:
            return bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    else:
        return bytes.decode('ascii', errors=errors)


MIME = Gdk.Atom.intern('text/html', False)
# Disable serialize/deserialize registration function because it does not work
# on GTK-3, the "guint8 *data" is converted into a Gtk.TextIter
use_serialize_func = False


def _reverse_dict(dct):
    return {j: i for i, j in dct.items()}


SIZE2SCALE = {
    '1': 1 / (1.2 * 1.2 * 1.2),
    '2': 1 / (1.2 * 1.2),
    '3': 1 / 1.2,
    '4': 1,
    '5': 1.2,
    '6': 1.2 * 1.2,
    '7': 1.2 * 1.2 * 1.2,
    }
SCALE2SIZE = _reverse_dict(SIZE2SCALE)
ALIGN2JUSTIFICATION = {
    'left': Gtk.Justification.LEFT,
    'center': Gtk.Justification.CENTER,
    'right': Gtk.Justification.RIGHT,
    'justify': Gtk.Justification.FILL,
    }
JUSTIFICATION2ALIGN = _reverse_dict(ALIGN2JUSTIFICATION)
FAMILIES = ['normal', 'sans', 'serif', 'monospace']


def gdk_to_hex(gdk_color):
    "Convert color to 2 digit hex"
    colors = [gdk_color.red, gdk_color.green, gdk_color.blue]
    return "#" + "".join(["%02x" % (color // 256) for color in colors])


def _markup(text):
    return '<markup>%s</markup>' % text


def _strip_markup(text):
    return text[len('<markup>'):-len('</markup>')]


def _strip_newline(text):
    return ''.join(text.splitlines())


class MarkupHTMLParse(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.root = ET.Element('markup')
        self._tags = [self.root]
        self.head = False
        self.body = True

    def handle_starttag(self, tag, attrs):
        if tag in ['b', 'i', 'u', 'div', 'font']:
            el = ET.SubElement(self._tags[-1], tag)
            for key, value in attrs:
                el.set(key, value)
            self._tags.append(el)
        elif tag == 'br':
            ET.SubElement(self._tags[-1], tag)
        elif tag == 'head':
            self.head = True

    def handle_endtag(self, tag):
        if tag in ['b', 'i', 'u', 'div', 'font']:
            el = self._tags.pop()
            assert el.tag == tag
        elif tag == 'head':
            self.head = False
        elif tag == 'body':
            self.body = False

    def handle_data(self, data):
        if self.head or not self.body:
            return
        el = self._tags[-1]
        if len(el) == 0:
            if el.text is None:
                el.text = ''
            el.text += data
        else:
            child = el[-1]
            if child.tail is None:
                child.tail = ''
            child.tail += data


def parse_markup(markup_text):
    'Return plain text and a list of start, end TextTag'
    markup_text = StringIO(_markup(markup_text))
    plain_text = ''
    tag_stack = []
    tags = []
    for event, element in ET.iterparse(markup_text, events=['start', 'end']):
        if element.tag == 'markup':
            if event == 'start' and element.text:
                plain_text += unescape(element.text)
            if event == 'end' and element.tail:
                plain_text += unescape(element.tail)
            continue
        if event == 'start':
            tag_stack.append((element, len(plain_text)))
            if element.text:
                plain_text += unescape(element.text)
        elif event == 'end':
            if element.tag == 'div':
                plain_text += '\n'
            assert tag_stack[-1][0] == element
            _, start = tag_stack.pop()
            end = len(plain_text)
            tags.append((start, end, element))
            if element.tail:
                plain_text += unescape(element.tail)
    return plain_text, tags


def normalize_markup(markup_text, method='html'):
    parser = MarkupHTMLParse()
    parser.feed(_strip_newline(markup_text))
    root = parser.root
    parent_map = {c: p for p in root.iter() for c in p}

    def order(em):
        "Re-order alphabetically tags"
        if (len(em) == 1
                and not em.text
                and em.tag not in ['div', 'markup']):
            child, = em
            if ((em.tag > child.tag or child.tag == 'div')
                    and not child.tail):
                em.tag, child.tag = child.tag, em.tag
                em.attrib, child.attrib = child.attrib, em.attrib
                if em in parent_map:
                    order(parent_map[em])

    # Add missing div for the first line
    if len(root) > 0 and root[0].tag != 'div':
        div = ET.Element('div')
        for em in list(root):
            if em.tag != 'div':
                root.remove(em)
                div.append(em)
            else:
                break
        root.insert(0, div)

    for em in root.iter():
        while em.text is None and len(em) == 1:
            dup, = em
            if dup.tag == em.tag and dup.tail is None:
                em.attrib.update(dup.attrib)
                em.remove(dup)
                em.extend(dup)
                em.text = dup.text
            else:
                break
        order(em)

    # Add missing br to empty lines
    for em in root.findall('div'):
        if em.text is None and len(em) == 0:
            em.append(ET.Element('br'))
    # TODO order attributes
    return _strip_markup(
        ET.tostring(root, encoding='utf-8', method=method).decode('utf-8'))


def find_list_delta(old, new):
    added = [e for e in new if e not in old]
    removed = [e for e in reversed(old) if e not in new]
    return added, removed


def serialize(register, content, start, end, data):
    text = ''
    if start.compare(end) == 0:
        return text
    iter_ = start
    while True:
        # Loop over line per line to get a div per line
        tags = []
        active_tags = []

        end_line = iter_.copy()
        if not end_line.ends_line():
            end_line.forward_to_line_end()
        if end_line.compare(end) > 0:
            end_line = end

        # Open div of the line
        align = None
        for tag in iter_.get_tags():
            if tag.props.justification_set:
                align = JUSTIFICATION2ALIGN[tag.props.justification]
        if align:
            text += '<div align="%s">' % align
        else:
            text += '<div>'

        while True:
            new_tags = iter_.get_tags()

            added, removed = find_list_delta(tags, new_tags)

            for tag in removed:
                if tag not in active_tags:
                    continue

                # close all open tags after this one
                while active_tags:
                    atag = active_tags.pop()
                    text += _get_html(atag, close=True)
                    if atag == tag:
                        break
                    added.insert(0, atag)

            for tag in added:
                text += _get_html(tag)
                active_tags.append(tag)

            tags = new_tags

            old_iter = iter_.copy()

            # Move to next tag toggle
            while True:
                iter_.forward_char()
                if iter_.compare(end) == 0:
                    break
                if iter_.toggles_tag():
                    break
            # Might have moved too far
            if iter_.compare(end_line) > 0:
                iter_ = end_line

            text += escape(old_iter.get_text(iter_))

            if iter_.compare(end_line) == 0:
                break

        # close any open tags
        for tag in reversed(active_tags):
            text += _get_html(tag, close=True)

        # Close the div of the line
        text += '</div>'

        iter_.forward_char()
        if iter_.compare(end) >= 0:
            break

    return normalize_markup(text)


def deserialize(register, content, iter_, text, create_tags, data):
    if not isinstance(text, str):
        text = guess_decode(text, errors='replace')
    text, tags = parse_markup(normalize_markup(text, method='xml'))
    offset = iter_.get_offset()
    content.insert(iter_, text)

    def sort_key(tag):
        start, end, element = tag
        return start, -end, element.tag

    for start, end, element in sorted(tags, key=sort_key):
        for tag in _get_tags(content, element):
            istart = content.get_iter_at_offset(start + offset)
            iend = content.get_iter_at_offset(end + offset)
            content.apply_tag(tag, istart, iend)
    return True


def setup_tags(text_buffer):
    for name, props in reversed(_TAGS):
        text_buffer.create_tag(name, **props)


_TAGS = [
    ('bold', {'weight': Pango.Weight.BOLD}),
    ('italic', {'style': Pango.Style.ITALIC}),
    ('underline', {'underline': Pango.Underline.SINGLE}),
    ]
_TAGS.extend([('family %s' % family, {'family': family})
        for family in FAMILIES])
_TAGS.extend([('size %s' % size, {'scale': scale})
        for size, scale in SIZE2SCALE.items()])
_TAGS.extend([('justification %s' % align, {'justification': justification})
        for align, justification in ALIGN2JUSTIFICATION.items()])


def register_foreground(text_buffer, color):
    name = 'foreground %s' % color.to_string()
    tag_table = text_buffer.get_tag_table()
    tag = tag_table.lookup(name)
    if not tag:
        tag = text_buffer.create_tag(name, foreground_rgba=color)
    return tag


def _get_tags(content, element):
    'Return tag for the element'
    tag_table = content.get_tag_table()

    if element.tag == 'b':
        yield tag_table.lookup('bold')
    elif element.tag == 'i':
        yield tag_table.lookup('italic')
    elif element.tag == 'u':
        yield tag_table.lookup('underline')
    if 'face' in element.attrib:
        tag = tag_table.lookup('family %s' % element.attrib['face'])
        if tag:
            yield tag
    size = element.attrib.get('size')
    if size in SIZE2SCALE:
        yield tag_table.lookup('size %s' % size)
    if 'color' in element.attrib:
        color = Gdk.RGBA()
        color.parse(element.attrib['color'])
        yield register_foreground(content, color)
    align = element.attrib.get('align')
    if align in ALIGN2JUSTIFICATION:
        yield tag_table.lookup('justification %s' % align)
    # TODO style background-color


def _get_html(texttag, close=False, div_only=False):
    'Return the html tag'
    # div alignment is managed at line level
    tags = []
    attrib = {}
    font = attrib['font'] = {}
    if texttag.props.weight_set and texttag.props.weight == Pango.Weight.BOLD:
        tags.append('b')
    if texttag.props.style_set and texttag.props.style == Pango.Style.ITALIC:
        tags.append('i')
    if (texttag.props.underline_set
            and texttag.props.underline == Pango.Underline.SINGLE):
        tags.append('u')
    if texttag.props.family_set and texttag.props.family:
        font['face'] = texttag.props.family
    if texttag.props.scale_set and texttag.props.scale != 1:
        font['size'] = SCALE2SIZE[texttag.props.scale]
    if (texttag.props.foreground_set
            and texttag.props.foreground_gdk != Gdk.Color(0, 0, 0)):
        font['color'] = gdk_to_hex(texttag.props.foreground_gdk)
    # TODO style background-color
    if font:
        tags.append('font')

    if close:
        return ''.join('</%s>' % t for t in tags)
    return ''.join('<%s %s>' % (t, ' '.join('%s="%s"' % (a, v)
                for a, v in attrib.get(t, {}).items()))
        for t in tags)


def get_tags(content, start, end):
    'Get all tags'
    iter_ = start.copy()
    tags = set()
    while True:
        tags.update(iter_.get_tags())
        iter_.forward_char()
        if iter_.compare(end) > 0:
            iter_ = end
        if iter_.compare(end) == 0:
            break
    tags.update(iter_.get_tags())
    return tags


def remove_tags(content, start, end, *names):
    'Remove all tags starting by names'
    tags = get_tags(content, start, end)
    for tag in sorted(tags, key=lambda t: t.get_priority()):
        for name in names:
            if tag.props.name and tag.props.name.startswith(name):
                content.remove_tag(tag, start, end)


if __name__ == '__main__':
    html = '''<b>Bold</b>
 <i>Italic</i>
 <u>Underline</u>
<div><br/></div>
<div align="center">Center</div>
<div><font face="sans" size="6">Sans6<font color="#ff0000">red</font></font></div>
<div align="center"> <b> <i><u>Title</u></i> </b></div>'''

    win = Gtk.Window()
    win.set_title('HTMLTextBuffer')

    def cb(window, event):
        if use_serialize_func:
            print(text_buffer.serialize(
                text_buffer, MIME, text_buffer.get_start_iter(),
                text_buffer.get_end_iter()))
        else:
            print(serialize(
                text_buffer, text_buffer, text_buffer.get_start_iter(),
                text_buffer.get_end_iter(), None))
        Gtk.main_quit()
    win.connect('delete-event', cb)
    vbox = Gtk.VBox()
    win.add(vbox)

    text_buffer = Gtk.TextBuffer()
    text_view = Gtk.TextView()
    text_view.set_buffer(text_buffer)
    vbox.pack_start(text_view, expand=True, fill=True, padding=0)

    setup_tags(text_buffer)
    text_buffer.register_serialize_format(str(MIME), serialize, None)
    text_buffer.register_deserialize_format(str(MIME), deserialize, None)

    if use_serialize_func:
        text_buffer.deserialize(
            text_buffer, MIME, text_buffer.get_start_iter(), html)

        result = text_buffer.serialize(
            text_buffer, MIME, text_buffer.get_start_iter(),
            text_buffer.get_end_iter())
    else:
        deserialize(
            text_buffer, text_buffer, text_buffer.get_start_iter(),
            html, text_buffer.deserialize_get_can_create_tags(MIME),
            None)

        result = serialize(
            text_buffer, text_buffer, text_buffer.get_start_iter(),
            text_buffer.get_end_iter(), None)

    assert normalize_markup(html) == result, (normalize_markup(html), result)

    win.show_all()
    Gtk.main()
