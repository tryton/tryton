# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# This code is inspired by the pycha project
# (http://www.lorenzogil.com/projects/pycha/)
import locale
import math
import datetime

import cairo

from graph import Graph
import tryton.common as common
import tryton.rpc as rpc


class Bar(Graph):

    def __init__(self, *args, **kwargs):
        super(Bar, self).__init__(*args, **kwargs)
        self.bars = []

    def drawGraph(self, cr, width, height):

        def drawBar(bar):
            cr.set_line_width(0.5)

            x = self.area.w * bar.x + self.area.x
            y = self.area.h * bar.y + self.area.y
            w = self.area.w * bar.w
            h = self.area.h * bar.h

            if w < 1 or h < 1:
                return  # don't draw too small

            self.drawRectangle(cr, x, y, w, h)
            r, g, b = self.colorScheme[bar.yname]
            if bar.highlight:
                r, g, b = common.highlight_rgb(r, g, b)
            cr.set_source(self.sourceRectangle(x, y, w, h, r, g, b))
            cr.fill_preserve()
            cr.stroke()

        cr.save()
        for bar in self.bars:
            drawBar(bar)
        cr.restore()

    def drawRectangle(self, cr, x, y, w, h):
        radius = 2.5
        cr.arc(x + radius, y + radius, radius, 0, 2 * math.pi)
        cr.arc(x + w - radius, y + radius, radius, 0, 2 * math.pi)
        cr.arc(x + w - radius, y + h - radius, radius, 0, 2 * math.pi)
        cr.arc(x + radius, y + h - radius, radius, 0, 2 * math.pi)
        cr.rectangle(x + radius, y, w - radius * 2, h)
        cr.rectangle(x, y + radius, w, h - radius * 2)

    def sourceRectangle(self, x, y, w, h, r, g, b):
        linear = cairo.LinearGradient((x + w) / 2, y, (x + w) / 2, y + h)
        linear.add_color_stop_rgb(0, 3.5 * r / 5.0, 3.5 * g / 5.0,
            3.5 * b / 5.0)
        linear.add_color_stop_rgb(1, r, g, b)
        return linear

    def motion(self, widget, event):
        super(Bar, self).motion(widget, event)

        if not getattr(self, 'area', None):
            return

        def intersect(bar, event):
            x = self.area.w * bar.x + self.area.x
            y = self.area.h * bar.y + self.area.y
            w = self.area.w * bar.w
            h = self.area.h * bar.h

            if x <= event.x <= x + w and y <= event.y <= y + h:
                return True
            return False

        highlight = False
        draw_bars = []
        yfields_timedelta = {x.get('key', x['name']): x.get('timedelta')
            for x in self.yfields if 'timedelta' in x}
        for bar in self.bars:
            if intersect(bar, event):
                if not bar.highlight:
                    bar.highlight = True
                    if bar.yname in yfields_timedelta:
                        converter = None
                        if yfields_timedelta[bar.yname]:
                            converter = rpc.CONTEXT.get(
                                yfields_timedelta[bar.yname])
                        label = common.timedelta.format(
                            datetime.timedelta(seconds=bar.yval), converter)
                    else:
                        label = locale.format('%.2f', bar.yval, True)
                    label += '\n'
                    label += str(self.labels[bar.xname])
                    self.popup.set_text(label)
                    draw_bars.append(bar)
            else:
                if bar.highlight:
                    bar.highlight = False
                    draw_bars.append(bar)
            if bar.highlight:
                highlight = True

        if highlight:
            self.popup.show()
        else:
            self.popup.hide()

        if draw_bars:
            minx = self.area.w + self.area.x
            miny = self.area.h + self.area.y
            maxx = maxy = 0.0
            for bar in draw_bars:
                x = self.area.w * bar.x + self.area.x
                y = self.area.h * bar.y + self.area.y
                minx = int(min(x, minx))
                miny = int(min(y, miny))
                maxx = int(max(x + self.area.w * bar.w, maxx))
                maxy = int(max(y + self.area.h * bar.h, maxy))
            self.queue_draw_area(minx - 1, miny - 1,
                    maxx - minx + 2, maxy - miny + 2)

    def action(self):
        super(Bar, self).action()
        for bar in self.bars:
            if bar.highlight:
                ids = self.ids[bar.xname]
                self.action_keyword(ids)


class VerticalBar(Bar):
    'Vertical Bar Graph'

    def updateGraph(self):

        barWidth = self.xscale * 0.9
        barMargin = self.xscale * (1.0 - 0.9) / 2

        self.bars = []
        i = 0
        keys = self.datas.keys()
        keys.sort()
        for xfield in keys:
            j = 0
            barWidthForSet = barWidth / len(self.datas[xfield])
            for yfield in self._getDatasKeys():
                xval = i
                yval = self.datas[xfield][yfield]

                x = (xval - self.minxval) * self.xscale + \
                    barMargin + (j * barWidthForSet)
                y = 1.0 - (yval - self.minyval) * self.yscale
                w = barWidthForSet
                h = yval * self.yscale

                if h < 0:
                    h = abs(h)
                    y -= h

                rect = Rect(x, y, w, h, xval, yval, xfield, yfield)
                if (0.0 <= rect.x <= 1.0) and (0.0 <= rect.y <= 1.0):
                    self.bars.append(rect)

                j += 1
            i += 1

    def XLabels(self):
        xlabels = super(VerticalBar, self).XLabels()
        return [(x[0] + (self.xscale / 2), x[1]) for x in xlabels]

    def YLabels(self):
        ylabels = super(VerticalBar, self).YLabels()
        if all('timedelta' in f for f in self.yfields):
            converter = {f.get('timedelta') for f in self.yfields}
            if len(converter) == 1:
                converter = rpc.CONTEXT.get(converter.pop())
            else:
                converter = None
            return [
                (x[0], common.timedelta.format(
                        datetime.timedelta(seconds=locale.atof(x[1])),
                        converter))
                for x in ylabels]
        return ylabels


class HorizontalBar(Bar):
    'Horizontal Bar Graph'

    def updateGraph(self):

        barWidth = self.xscale * 0.9
        barMargin = self.xscale * (1.0 - 0.9) / 2

        self.bars = []
        i = 0
        keys = self.datas.keys()
        keys.sort()
        for xfield in keys:
            j = 0
            barWidthForSet = barWidth / len(self.datas[xfield])
            for yfield in self._getDatasKeys():
                xval = i
                yval = self.datas[xfield][yfield]

                x = - self.minyval * self.yscale
                y = (xval - self.minxval) * self.xscale + \
                    barMargin + (j * barWidthForSet)
                w = yval * self.yscale
                h = barWidthForSet

                if w < 0:
                    w = abs(w)
                    x -= w

                rect = Rect(x, y, w, h, xval, yval, xfield, yfield)
                if (0.0 <= rect.x <= 1.0) and (0.0 <= rect.y <= 1.0):
                    self.bars.append(rect)

                j += 1
            i += 1

    def YLabels(self):
        xlabels = super(HorizontalBar, self).XLabels()
        return [(1 - (x[0] + (self.xscale / 2)), x[1]) for x in xlabels]

    def XLabels(self):
        ylabels = super(HorizontalBar, self).YLabels()
        if all('timedelta' in f for f in self.yfields):
            converter = {f.get('timedelta') for f in self.yfields}
            if len(converter) == 1:
                converter = rpc.CONTEXT.get(converter.pop())
            else:
                converter = None
            return [
                (x[0], common.timedelta.format(
                        datetime.timedelta(seconds=locale.atof(x[1])),
                        converter))
                for x in ylabels]
        return [(x[0], x[1]) for x in ylabels]

    def _getLegendPosition(self, width, height):
        return self.area.x + self.area.w * 0.95 - width, \
            self.area.y + self.area.h * 0.05

    def drawLines(self, cr, width, height):
        for w, label in self.XLabels():
            self.drawLine(cr, w, 0)


class Rect(object):

    def __init__(self, x, y, w, h, xval, yval, xname, yname):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.xval, self.yval = xval, yval
        self.yname = yname
        self.xname = xname
        self.highlight = False
