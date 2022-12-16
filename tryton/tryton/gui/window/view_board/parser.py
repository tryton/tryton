#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
'Parser'
import gtk
from tryton.gui.window.view_form.view.form_gtk.parser import _container
import tryton.common as common
from action import Action
from tryton.config import CONFIG, TRYTON_ICON


class ParserBoard(object):

    def __init__(self, window):
        self.window = window
        self.title = None

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
            if node.localName == 'image':
                common.ICONFACTORY.register_icon(attrs['name'])
                icon = gtk.Image()
                icon.set_from_stock(attrs['name'], gtk.ICON_SIZE_DIALOG)
                container.wid_add(icon, colspan=int(attrs.get('colspan', 1)),
                        expand=int(attrs.get('expand',0)), ypadding=10,
                        help_tip=attrs.get('help', False),
                        fill=int(attrs.get('fill', 0)))
            elif node.localName == 'separator':
                text = attrs.get('string', '')
                if 'string' in attrs or 'name' in attrs:
                    if not text:
                        if 'name' in attrs and attrs['name'] in fields:
                            if 'states' in fields[attrs['name']]:
                                attrs['states'] = \
                                        fields[attrs['name']]['states']
                            text = fields[attrs['name']]['string']
                vbox = VBox(attrs=attrs)
                if text:
                    label = gtk.Label(text)
                    label.set_use_markup(True)
                    label.set_alignment(float(attrs.get('align', 0.0)), 0.5)
                    vbox.pack_start(label)
                vbox.pack_start(gtk.HSeparator())
                container.wid_add(vbox, colspan=int(attrs.get('colspan', 1)),
                        expand=int(attrs.get('expand', 0)),
                        ypadding=10, help_tip=attrs.get('help', False),
                        fill=int(attrs.get('fill', 0)))
            elif node.localName == 'label':
                text = attrs.get('string', '')
                if not text:
                    if 'name' in attrs and attrs['name'] in fields:
                        if 'states' in fields[attrs['name']]:
                            attrs['states'] = fields[attrs['name']]['states']
                        if gtk.widget_get_default_direction() == gtk.TEXT_DIR_RTL:
                            text = _(':') + fields[attrs['name']]['string']
                        else:
                            text = fields[attrs['name']]['string'] + _(':')
                        if 'align' not in attrs:
                            attrs['align'] = 1.0
                    else:
                        for node in node.childNodes:
                            if node.nodeType == node.TEXT_NODE:
                                text += node.data
                            else:
                                text += node.toxml()
                if not text:
                    container.empty_add(int(attrs.get('colspan', 1)))
                    continue
                label = gtk.Label(text)
                label.set_use_markup(True)
                if 'align' in attrs:
                    label.set_alignment(float(attrs['align'] or 0.0), 0.5)
                label.set_angle(int(attrs.get('angle', 0)))
                expand = False
                if 'expand' in attrs:
                    expand = bool(common.safe_eval(attrs['expand']))
                fill = False
                if 'fill' in attrs:
                    fill = bool(common.safe_eval(attrs['fill']))
                xexpand = False
                if 'xexpand' in attrs:
                    xexpand = bool(common.safe_eval(attrs['xexpand']))
                xfill = True
                if 'xfill' in attrs:
                    xfill = bool(common.safe_eval(attrs['xfill']))
                container.wid_add(label,
                        colspan=int(attrs.get('colspan', 1)),
                        expand=expand, help_tip=attrs.get('help', False),
                        fill=fill, xexpand=xexpand, xfill=xfill)
            elif node.localName == 'newline':
                container.newline()
            elif node.localName == 'notebook':
                notebook = gtk.Notebook()
                if attrs and 'tabpos' in attrs:
                    pos = {'up':gtk.POS_TOP,
                        'down':gtk.POS_BOTTOM,
                        'left':gtk.POS_LEFT,
                        'right':gtk.POS_RIGHT
                    }[attrs['tabpos']]
                else:
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
                container.wid_add(notebook, colspan=attrs.get('colspan', 3),
                        expand=True, fill=True)
                widget, new_widgets = self.parse(node, notebook, tooltips=tooltips)
                widgets += new_widgets
            elif node.localName == 'page':
                if CONFIG['client.form_tab'] == 'left':
                    angle = 90
                elif CONFIG['client.form_tab'] == 'right':
                    angle = -90
                else:
                    angle = 0
                label = gtk.Label(attrs.get('string','No String Attr.'))
                label.set_angle(angle)
                widget, new_widgets = self.parse(node, notebook, tooltips=tooltips)
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
                container.wid_add(frame, colspan=int(attrs.get('colspan', 1)),
                        expand=int(attrs.get('expand', 0)),
                        rowspan=int(attrs.get('rowspan', 1)), ypadding=0,
                        fill=int(attrs.get('fill', 1)))
            elif node.localName == 'hpaned':
                hpaned = gtk.HPaned()
                container.wid_add(hpaned, colspan=int(attrs.get('colspan', 4)),
                        expand=True, fill=True)
                widget, new_widgets = self.parse(node, paned=hpaned, tooltips=tooltips)
                widgets += new_widgets
                if 'position' in attrs:
                    hpaned.set_position(int(attrs['position']))
            elif node.localName == 'vpaned':
                vpaned = gtk.VPaned()
                container.wid_add(vpaned, colspan=int(attrs.get('colspan', 4)),
                        expand=True, fill=True)
                widget, new_widgets = self.parse(node, paned=vpaned, tooltips=tooltips)
                widgets += new_widgets
                if 'position' in attrs:
                    vpaned.set_position(int(attrs['position']))
            elif node.localName == 'child':
                widget, new_widgets = self.parse(node, paned=paned, tooltips=tooltips)
                widgets += new_widgets
                if not paned.get_child1():
                    paned.pack1(widget, resize=True, shrink=True)
                elif not paned.get_child2():
                    paned.pack2(widget, resize=True, shrink=True)
            elif node.localName == 'action':
                name = str(attrs['name'])
                widget_act = Action(self.window, attrs)
                widgets.append(widget_act)
                container.wid_add(widget_act.widget,
                        colspan=int(attrs.get('colspan', 1)),
                        expand=True, fill=True)
        return container.pop(), widgets
