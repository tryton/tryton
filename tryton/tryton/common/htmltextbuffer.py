# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from __future__ import division
from io import BytesIO
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, unescape
from HTMLParser import HTMLParser

import pango
import gtk
import chardet

MIME = 'text/html'
if hasattr(gtk.gdk, 'Atom'):
    MIME = gtk.gdk.Atom.intern(MIME, False)


def _reverse_dict(dct):
    return {j: i for i, j in dct.iteritems()}

SIZE2SCALE = {
    '1': pango.SCALE_XX_SMALL,
    '2': pango.SCALE_X_SMALL,
    '3': pango.SCALE_SMALL,
    '4': pango.SCALE_MEDIUM,
    '5': pango.SCALE_LARGE,
    '6': pango.SCALE_X_LARGE,
    '7': pango.SCALE_XX_LARGE,
    }
SCALE2SIZE = _reverse_dict(SIZE2SCALE)
ALIGN2JUSTIFICATION = {
    'left': gtk.JUSTIFY_LEFT,
    'center': gtk.JUSTIFY_CENTER,
    'right': gtk.JUSTIFY_RIGHT,
    'justify': gtk.JUSTIFY_FILL,
    }
JUSTIFICATION2ALIGN = _reverse_dict(ALIGN2JUSTIFICATION)
FAMILIES = ['normal', 'sans', 'serif', 'monospace']


def gdk_to_hex(gdk_color):
    "Convert color to 2 digit hex"
    colors = [gdk_color.red, gdk_color.green, gdk_color.blue]
    return "#" + "".join(["%02x" % (color / 256) for color in colors])


def _markup(text):
    return '<markup>%s</markup>' % text


def _strip_markup(text):
    return text[len(u'<markup>'):-len(u'</markup>')]


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
    markup_text = BytesIO(_markup(markup_text))
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
    if isinstance(markup_text, unicode):
        markup_text = markup_text.encode('utf-8')
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
    return _strip_markup(ET.tostring(root, encoding='utf-8', method=method))


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
    if not isinstance(text, unicode):
        encoding = chardet.detect(text)['encoding'] or 'utf-8'
        text = text.decode(encoding)
    text = text.encode('utf-8')
    text, tags = parse_markup(normalize_markup(text, method='xml'))
    offset = iter_.get_offset()
    content.insert(iter_, text)

    def sort_key(tag):
        start, end, element = tag
        return start, -end, element

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
    ('bold', {'weight': pango.WEIGHT_BOLD}),
    ('italic', {'style': pango.STYLE_ITALIC}),
    ('underline', {'underline': pango.UNDERLINE_SINGLE}),
    ]
_TAGS.extend([('family %s' % family, {'family': family})
        for family in FAMILIES])
_TAGS.extend([('size %s' % size, {'scale': scale})
        for size, scale in SIZE2SCALE.iteritems()])
_TAGS.extend([('justification %s' % align, {'justification': justification})
        for align, justification in ALIGN2JUSTIFICATION.iteritems()])


def register_foreground(text_buffer, color):
    name = 'foreground %s' % color
    tag_table = text_buffer.get_tag_table()
    tag = tag_table.lookup(name)
    if not tag:
        tag = text_buffer.create_tag(name, foreground_gdk=color)
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
        yield register_foreground(
            content, gtk.gdk.color_parse(element.attrib['color']))
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
    if texttag.props.weight_set and texttag.props.weight == pango.WEIGHT_BOLD:
        tags.append('b')
    if texttag.props.style_set and texttag.props.style == pango.STYLE_ITALIC:
        tags.append('i')
    if (texttag.props.underline_set
            and texttag.props.underline == pango.UNDERLINE_SINGLE):
        tags.append('u')
    if texttag.props.family_set and texttag.props.family:
        font['face'] = texttag.props.family
    if texttag.props.scale_set and texttag.props.scale != pango.SCALE_MEDIUM:
        font['size'] = SCALE2SIZE[texttag.props.scale]
    if (texttag.props.foreground_set
            and texttag.props.foreground_gdk != gtk.gdk.Color(0, 0, 0)):
        font['color'] = gdk_to_hex(texttag.props.foreground_gdk)
    # TODO style background-color
    if font:
        tags.append('font')

    if close:
        return ''.join('</%s>' % t for t in tags)
    return ''.join('<%s %s>' % (t, ' '.join('%s="%s"' % (a, v)
                for a, v in attrib.get(t, {}).iteritems()))
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
    html = u'''<b>Bold</b>
 <i>Italic</i>
 <u>Underline</u>
<div><br/></div>
<div align="center">Center</div>
<div><font face="sans" size="6">Sans6<font color="#ff0000">red</font></font></div>
<div align="center"> <b> <i><u>Title</u></i> </b></div>'''

    win = gtk.Window()
    win.set_title('HTMLTextBuffer')

    def cb(window, event):
        print text_buffer.serialize(
            text_buffer, MIME, text_buffer.get_start_iter(),
            text_buffer.get_end_iter())
        gtk.main_quit()
    win.connect('delete-event', cb)
    vbox = gtk.VBox()
    win.add(vbox)

    text_buffer = gtk.TextBuffer()
    text_view = gtk.TextView()
    text_view.set_buffer(text_buffer)
    vbox.pack_start(text_view)

    setup_tags(text_buffer)
    text_buffer.register_serialize_format(MIME, serialize, None)
    text_buffer.register_deserialize_format(MIME, deserialize, None)

    text_buffer.deserialize(
        text_buffer, MIME, text_buffer.get_start_iter(), html)

    result = text_buffer.serialize(
        text_buffer, MIME, text_buffer.get_start_iter(),
        text_buffer.get_end_iter())
    assert normalize_markup(html) == result

    win.show_all()
    gtk.main()
