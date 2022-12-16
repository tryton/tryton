#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Parser'
import gtk
import gettext
from tryton.gui.window.view_form.view.form_gtk.parser import _container, VBox
import tryton.common as common
from action import Action
from tryton.config import CONFIG

_ = gettext.gettext


class ParserBoard(object):

    def __init__(self, context=None):
        self.title = None
        self.context = context

    def parse(self, root_node, notebook=None, paned=None, tooltips=None):
        widgets = []

        attrs = common.node_attributes(root_node)
        if not tooltips:
            tooltips = common.Tooltips()

        container = _container(tooltips)
        container.new(col=int(attrs.get('col', 4)))

        if not self.title:
            self.title = attrs.get('string', 'Unknown')

        for node in root_node.childNodes:
            if not node.nodeType == node.ELEMENT_NODE:
                continue
            attrs = common.node_attributes(node)
            yexpand = int(attrs.get('yexpand', 0))
            yfill = int(attrs.get('yfill', 0))
            xexpand = int(attrs.get('xexpand', 1))
            xfill = int(attrs.get('xfill', 1))
            colspan = int(attrs.get('colspan', 1))
            if node.localName == 'image':
                common.ICONFACTORY.register_icon(attrs['name'])
                icon = gtk.Image()
                icon.set_from_stock(attrs['name'], gtk.ICON_SIZE_DIALOG)
                container.wid_add(icon,
                    help_tip=attrs.get('help', False),
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill, ypadding=10,
                    xexpand=xexpand, xfill=xfill)
            elif node.localName == 'separator':
                text = attrs.get('string', '')
                vbox = VBox(attrs=attrs)
                if text:
                    label = gtk.Label(text)
                    label.set_use_markup(True)
                    label.set_alignment(float(attrs.get('align', 0.0)), 0.5)
                    vbox.pack_start(label)
                vbox.pack_start(gtk.HSeparator())
                container.wid_add(vbox,
                    help_tip=attrs.get('help', False),
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill, ypadding=10,
                    xexpand=xexpand, xfill=xfill)
            elif node.localName == 'label':
                text = attrs.get('string', '')
                if not text:
                    container.empty_add(int(attrs.get('colspan', 1)))
                    continue
                label = gtk.Label(text)
                label.set_use_markup(True)
                label.set_alignment(float(attrs.get('xalign', 1.0)),
                    float(attrs.get('yalign', 0.0)))
                label.set_angle(int(attrs.get('angle', 0)))
                xexpand = bool(attrs.get('xexpand', 0))
                container.wid_add(label,
                    help_tip=attrs.get('help', False),
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill,
                    xexpand=xexpand, xfill=xfill)
            elif node.localName == 'newline':
                container.newline()
            elif node.localName == 'notebook':
                notebook = gtk.Notebook()
                if CONFIG['client.form_tab'] == 'top':
                    pos = gtk.POS_TOP
                elif CONFIG['client.form_tab'] == 'left':
                    pos = gtk.POS_LEFT
                elif CONFIG['client.form_tab'] == 'right':
                    pos = gtk.POS_RIGHT
                elif CONFIG['client.form_tab'] == 'bottom':
                    pos = gtk.POS_BOTTOM
                notebook.set_tab_pos(pos)
                notebook.set_border_width(3)
                container.wid_add(notebook,
                    colspan=int(attrs.get('colspan', 4)),
                    yexpand=True, yfill=True)
                widget, new_widgets = self.parse(node, notebook,
                    tooltips=tooltips)
                widgets += new_widgets
            elif node.localName == 'page':
                if CONFIG['client.form_tab'] == 'left':
                    angle = 90
                elif CONFIG['client.form_tab'] == 'right':
                    angle = -90
                else:
                    angle = 0
                label = gtk.Label(attrs.get('string', _('No String Attr.')))
                label.set_angle(angle)
                widget, new_widgets = self.parse(node, notebook,
                    tooltips=tooltips)
                widgets += new_widgets
                notebook.append_page(widget, label)
            elif node.localName == 'group':
                widget, new_widgets = self.parse(node, tooltips=tooltips)
                widgets += new_widgets
                if attrs.get('string', None):
                    frame = gtk.Frame(attrs['string'])
                    frame.add(widget)
                else:
                    frame = widget
                container.wid_add(frame,
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill, ypadding=0,
                    xexpand=xexpand, xfill=xfill, xpadding=0)
            elif node.localName == 'hpaned':
                hpaned = gtk.HPaned()
                container.wid_add(hpaned, colspan=int(attrs.get('colspan', 4)),
                        yexpand=True, yfill=True)
                widget, new_widgets = self.parse(node, paned=hpaned,
                    tooltips=tooltips)
                widgets += new_widgets
                if 'position' in attrs:
                    hpaned.set_position(int(attrs['position']))
            elif node.localName == 'vpaned':
                vpaned = gtk.VPaned()
                container.wid_add(vpaned, colspan=int(attrs.get('colspan', 4)),
                        yexpand=True, yfill=True)
                widget, new_widgets = self.parse(node, paned=vpaned,
                    tooltips=tooltips)
                widgets += new_widgets
                if 'position' in attrs:
                    vpaned.set_position(int(attrs['position']))
            elif node.localName == 'child':
                widget, new_widgets = self.parse(node, paned=paned,
                    tooltips=tooltips)
                widgets += new_widgets
                if not paned.get_child1():
                    paned.pack1(widget, resize=True, shrink=True)
                elif not paned.get_child2():
                    paned.pack2(widget, resize=True, shrink=True)
            elif node.localName == 'action':
                widget_act = Action(attrs, self.context)
                widgets.append(widget_act)
                yexpand = bool(attrs.get('yexpand', 1))
                yfill = bool(attrs.get('yfill', 1))
                container.wid_add(widget_act.widget,
                    colspan=colspan,
                    yexpand=yexpand, yfill=yfill,
                    xexpand=xexpand, xfill=xfill)
        return container.pop(), widgets
