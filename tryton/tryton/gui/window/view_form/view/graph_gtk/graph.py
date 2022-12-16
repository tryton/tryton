# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# This code is inspired by the pycha project
# (http://www.lorenzogil.com/projects/pycha/)
import datetime
import locale
import math
from dateutil.relativedelta import relativedelta
from functools import reduce

import cairo
from gi.repository import Gdk, Gtk

import tryton.rpc as rpc
from tryton.action import Action
from tryton.common import hex2rgb, generateColorscheme, COLOR_SCHEMES
from tryton.gui.window import Window
from tryton.pyson import PYSONDecoder


class Popup(object):

    def __init__(self, widget):
        self.win = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.win.set_name('gtk-tooltips')
        self.win.set_resizable(False)
        self.win.set_border_width(1)
        self.win.set_transient_for(widget.props.window)
        self.label = Gtk.Label()
        self.win.add(self.label)
        self.win.connect('enter-notify-event', self.enter)

    def set_text(self, text):
        self.label.set_text(text)

    def set_position(self, widget, x, y):
        origin = widget.props.window.get_origin()
        allocation = widget.get_allocation()
        width, height = allocation.width, allocation.height
        popup_width, popup_height = self.win.get_size()
        if x < popup_width // 2:
            x = popup_width // 2
        if x > width - popup_width // 2:
            x = width - popup_width // 2
        pos_x = origin.x + x - popup_width // 2
        if pos_x < 0:
            pos_x = 0
        if y < popup_height + 5:
            y = popup_height + 5
        if y > height:
            y = height
        pos_y = origin.y + y - popup_height - 5
        if pos_y < 0:
            pos_y = 0
        self.win.move(int(pos_x), int(pos_y))

    def show(self):
        self.win.show_all()

    def hide(self):
        self.win.hide()

    def destroy(self):
        self.win.destroy()

    def enter(self, widget, event):
        self.win.hide()


class Graph(Gtk.DrawingArea):
    'Graph'

    __gsignals__ = {"draw": "override"}

    def __init__(self, view, xfield, yfields):
        super(Graph, self).__init__()
        self.view = view
        self.xfield = xfield
        self.yfields = yfields
        self.datas = {}
        self.topPadding = 15
        self.bottomPadding = 15
        self.rightPadding = 30
        self.leftPadding = 30
        self.set_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect('motion-notify-event', self.motion)
        self.connect('leave-notify-event', self.leave)
        self.popup = Popup(self)

    @property
    def attrs(self):
        return self.view.attributes

    @property
    def model(self):
        return self.view.screen.model_name

    def destroy(self):
        self.popup.destroy()
        super(Graph, self).destroy()

    def motion(self, widget, event):
        self.popup.set_position(self, event.x, event.y)

    def leave(self, widget, event):
        self.popup.hide()

    def do_draw(self, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()

        self.updateArea(cr, width, height)
        self.drawBackground(cr, width, height)
        self.drawLines(cr, width, height)
        self.drawGraph(cr, width, height)
        self.drawAxis(cr, width, height)
        self.drawLegend(cr, width, height)

    def export_png(self, filename, width, height):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        cx = cairo.Context(surface)

        self.updateArea(cx, width, height)
        self.drawBackground(cx, width, height)
        self.drawLines(cx, width, height)
        self.drawGraph(cx, width, height)
        self.drawAxis(cx, width, height)
        self.drawLegend(cx, width, height)
        surface.write_to_png(filename)

        self.queue_draw()

    def action(self):
        self.popup.hide()

    def action_keyword(self, ids):
        if not ids:
            return
        ctx = self.group._context.copy()
        if 'active_ids' in ctx:
            del ctx['active_ids']
        if 'active_id' in ctx:
            del ctx['active_id']
        event = Gtk.get_current_event()
        allow_similar = False
        if (event.state & Gdk.ModifierType.CONTROL_MASK
                or event.state & Gdk.ModifierType.MOD1_MASK):
            allow_similar = True
        with Window(hide_current=True, allow_similar=allow_similar):
            return Action.exec_keyword('graph_open', {
                    'model': self.model,
                    'id': ids[0],
                    'ids': ids,
                    }, context=ctx, warning=False)

    def drawBackground(self, cr, width, height):
        # Fill the background
        cr.save()
        r, g, b = hex2rgb(self.attrs.get('background', '#d5d5d5'))
        linear = cairo.LinearGradient(width // 2, 0, width // 2, height)
        linear.add_color_stop_rgb(0, 1, 1, 1)
        linear.add_color_stop_rgb(1, r, g, b)
        cr.set_source(linear)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        cr.stroke()
        cr.restore()

    def drawGraph(self, cr, width, height):
        pass

    def YLabels(self):
        ylabels = []
        if self.yrange == 0.0:
            base = 1
        else:
            base = 10 ** int(math.log(self.yrange, 10))
        for i in range(int(self.yrange / base) + 1):
            val = int(self.minyval / base) * base + i * base
            h = (val - self.minyval) * self.yscale
            label = locale.localize('{:.2f}'.format(val), True)
            ylabels.append((h, label))
        return ylabels

    def XLabels(self):
        xlabels = []
        i = 0.0
        keys = list(self.datas.keys())
        keys.sort()
        for key in keys:
            if self.xrange == 0:
                w = 1.0
            else:
                w = i / self.xrange
            xlabels.append((w, str(self.labels[key])))
            i += 1
        return xlabels

    def drawAxis(self, cr, width, height):
        cr.set_source_rgb(*hex2rgb('#000000'))
        cr.set_line_width(0.5)

        # Y axis
        def drawYLabel(h, label):
            x = self.area.x
            y = self.area.y + self.area.h - h * self.area.h

            cr.new_path()
            cr.move_to(x, y)
            cr.line_to(x - 3.0, y)
            cr.close_path()
            cr.stroke()

            extends = cr.text_extents(label)
            labelWidth = extends[2]
            labelHeight = extends[3]
            if labelWidth <= self.area.x:
                cr.move_to(x - 3.0 - labelWidth - 5, y + labelHeight / 2.0)
                cr.show_text(label)

        for h, label in self.YLabels():
            drawYLabel(h, label)
        cr.new_path()
        cr.move_to(self.area.x, self.area.y)
        cr.line_to(self.area.x, self.area.y + self.area.h)
        cr.close_path()
        cr.stroke()

        # X axis
        def drawXLabel(w, label):
            x = self.area.x + w * self.area.w
            y = self.area.y + self.area.h

            cr.new_path()
            cr.move_to(x, y)
            cr.line_to(x, y + 3.0)
            cr.close_path()
            cr.stroke()

            extends = cr.text_extents(label)
            labelWidth = extends[2]
            labelHeight = extends[3]
            if labelWidth <= self.xscale * self.area.w:
                cr.move_to(x - labelWidth / 2.0, y + labelHeight + 5)
                cr.show_text(label)

        for w, label in self.XLabels():
            drawXLabel(w, label)
        cr.new_path()
        cr.move_to(self.area.x, self.area.y + self.area.h)
        cr.line_to(self.area.x + self.area.w, self.area.y + self.area.h)
        cr.close_path()
        cr.stroke()

    def drawLines(self, cr, width, height):
        for h, label in self.YLabels():
            self.drawLine(cr, 0, h)

    def drawLine(self, cr, x, y):
        if x:
            x1 = x2 = self.area.x + x * self.area.w
            y1 = self.area.y
            y2 = y1 + self.area.h
        else:
            y1 = y2 = self.area.y + self.area.h - y * self.area.h
            x1 = self.area.x
            x2 = x1 + self.area.w

        cr.save()
        cr.set_source_rgb(*hex2rgb('#A0A0A0'))
        cr.set_line_width(0.3)
        cr.new_path()
        cr.set_dash([5.0, 4.0])
        cr.move_to(x1, y1)
        cr.line_to(x2, y2)
        cr.close_path()
        cr.stroke()
        cr.restore()

    def drawLegend(self, cr, width, height):
        if not int(self.attrs.get('legend', 1)):
            return

        padding = 4
        bullet = 15
        width = 0
        height = padding
        keys = self._getDatasKeys()
        if not keys:
            return
        keys2txt = {}
        for yfield in self.yfields:
            keys2txt[yfield.get('key', yfield['name'])] = yfield['string']
        for key in keys:
            extents = cr.text_extents(keys2txt[key])
            width = max(extents[2], width)
            height += max(extents[3], bullet) + padding
        width = padding + bullet + padding + width + padding

        pos_x, pos_y = self._getLegendPosition(width, height)

        cr.save()
        cr.rectangle(pos_x, pos_y, width, height)
        cr.set_source_rgba(1, 1, 1, 0.8)
        cr.fill_preserve()
        cr.set_line_width(0.5)
        cr.set_source_rgb(*hex2rgb('#000000'))
        cr.stroke()

        def drawKey(key, x, y, text_height):
            cr.rectangle(x, y, bullet, bullet)
            cr.set_source_rgb(*self.colorScheme[key])
            cr.fill_preserve()
            cr.set_source_rgb(0, 0, 0)
            cr.stroke()
            cr.move_to(x + bullet + padding,
                    y + bullet / 2.0 + text_height / 2.0)
            cr.show_text(keys2txt[key])

        cr.set_line_width(0.5)
        x = pos_x + padding
        y = pos_y + padding
        for key in keys:
            extents = cr.text_extents(keys2txt[key])
            drawKey(key, x, y, extents[3])
            y += max(extents[3], bullet) + padding

        cr.restore()

    def _getLegendPosition(self, width, height):
        return self.area.x + self.area.w * 0.05, \
            self.area.y + self.area.h * 0.05

    def display(self, group):
        self.updateDatas(group)
        self.setColorScheme()
        self.updateXY()
        self.updateGraph()
        self.queue_draw()

    def updateDatas(self, group):
        self.datas = {}
        self.labels = {}
        self.ids = {}
        self.group = group
        minx = None
        maxx = None
        for model in group:
            x = model[self.xfield['name']].get(model)
            if not minx:
                minx = x
            if not maxx:
                maxx = x
            if minx is None and maxx is None:
                if isinstance(x, datetime.datetime):
                    minx, maxx = datetime.datetime.min, datetime.datetime.max
                elif isinstance(x, datetime.date):
                    minx, maxx = datetime.date.min, datetime.date.max
                elif isinstance(x, datetime.timedelta):
                    minx, maxx = datetime.timedelta.min, datetime.timedelta.max
            try:
                minx = min(minx, x)
                maxx = max(maxx, x)
            except TypeError:
                continue
            self.labels[x] = model[self.xfield['name']].get_client(model)
            self.ids.setdefault(x, [])
            self.ids[x].append(model.id)
            self.datas.setdefault(x, {})
            for yfield in self.yfields:
                key = yfield.get('key', yfield['name'])
                if yfield.get('domain'):
                    context = rpc.CONTEXT.copy()
                    context['context'] = context.copy()
                    context['_user'] = rpc._USER
                    for field in model.group.fields:
                        context[field] = model[field].get(model)
                    if not PYSONDecoder(context).decode(yfield['domain']):
                        continue
                self.datas[x].setdefault(key, 0.0)
                if yfield['name'] == '#':
                    self.datas[x][key] += 1
                else:
                    value = model[yfield['name']].get(model)
                    if isinstance(value, datetime.timedelta):
                        value = value.total_seconds()
                    self.datas[x][key] += float(value or 0)
        date_format = self.view.screen.context.get('date_format', '%x')
        datetime_format = date_format + ' %X'
        if isinstance(minx, datetime.datetime):
            date = minx
            while date <= maxx:
                self.labels[date] = date.strftime(datetime_format)
                self.datas.setdefault(date, {})
                for yfield in self.yfields:
                    self.datas[date].setdefault(
                            yfield.get('key', yfield['name']), 0.0)
                date += relativedelta(days=1)
        elif isinstance(minx, datetime.date):
            date = minx
            while date <= maxx:
                self.labels[date] = date.strftime(date_format)
                self.datas.setdefault(date, {})
                for yfield in self.yfields:
                    self.datas[date].setdefault(
                            yfield.get('key', yfield['name']), 0.0)
                date += relativedelta(days=1)

    def updateArea(self, cr, width, height):
        maxylabel = ''
        for value, label in self.YLabels():
            if len(maxylabel) < len(label):
                maxylabel = label
        extends = cr.text_extents(maxylabel)
        yLabelWidth = extends[2]

        maxxlabel = ''
        for value, label in self.XLabels():
            if len(maxxlabel) < len(label):
                maxxlabel = label
        extends = cr.text_extents(maxxlabel)
        xLabelHeight = extends[3]

        if yLabelWidth > width / 3.0:
            yLabelWidth = 0
        width = width - self.leftPadding - yLabelWidth - self.rightPadding
        height = height - self.topPadding - self.bottomPadding - xLabelHeight
        self.area = Area(self.leftPadding + yLabelWidth, self.topPadding,
            width, height)

    def updateXY(self):
        self.maxxval = len(self.datas)
        self.minxval = 0.0

        self.xrange = self.maxxval - self.minxval
        if self.xrange == 0:
            self.xscale = 1.0
        else:
            self.xscale = 1.0 / self.xrange

        if not list(self.datas.values()):
            self.maxyval = 0.0
            self.minyval = 0.0
        else:
            self.maxyval = max([reduce(lambda x, y: max(x, y), x.values())
                    for x in self.datas.values()])
            self.minyval = min([reduce(lambda x, y: min(x, y), x.values())
                    for x in self.datas.values()])
        if self.minyval > 0:
            self.minyval = 0.0

        self.yrange = self.maxyval - self.minyval
        if self.yrange == 0:
            self.yscale = 1.0
        else:
            self.yscale = 1.0 / self.yrange

    def updateGraph(self):
        pass

    def setColorScheme(self):
        keys = self._getDatasKeys()
        color = self.attrs.get('color', 'blue')
        r, g, b = hex2rgb(COLOR_SCHEMES.get(color, color))
        maxcolor = max(max(r, g), b)
        self.colorScheme = generateColorscheme(color, keys,
                maxcolor / (len(keys) or 1))
        for yfield in self.yfields:
            if yfield.get('color'):
                self.colorScheme[yfield.get('key', yfield['name'])] = hex2rgb(
                        COLOR_SCHEMES.get(yfield['color'], yfield['color']))

    def _getDatasKeys(self):
        return [x.get('key', x['name']) for x in self.yfields]


class Area(object):

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
