# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# This code is inspired by the pycha project
# (http://www.lorenzogil.com/projects/pycha/)
import locale
import math
import datetime

import cairo

from .graph import Graph
import tryton.common as common
import tryton.rpc as rpc


class Line(Graph):

    def updateGraph(self):

        yfield2attrs = {}
        for yfield in self.yfields:
            yfield2attrs[yfield.get('key', yfield['name'])] = yfield

        self.points = []
        i = 0
        keys = list(self.datas.keys())
        keys.sort()
        for xfield in keys:
            j = 0
            for yfield in self.datas[xfield]:
                xval = i
                yval = self.datas[xfield][yfield]

                x = (xval - self.minxval) * self.xscale
                y = 1.0 - (yval - self.minyval) * self.yscale

                if self.xrange == 0:
                    x = 1.0

                if (not bool(int(yfield2attrs[yfield].get('empty', 1)))
                        and yval == 0):
                    continue

                point = Point(x, y, xval, yval, xfield, yfield)
                if (0.0 <= point.x <= 1.0) and (0.0 <= point.y <= 1.0):
                    self.points.append(point)

                j += 1
            i += 1

    def drawGraph(self, cr, width, height):
        key2fill = {}
        key2interpolation = {}
        for yfield in self.yfields:
            key = yfield.get('key', yfield['name'])
            key2fill[key] = bool(int(yfield.get('fill', 0)))
            key2interpolation[key] = yfield.get('interpolation', 'linear')

        def preparePath(key):
            interpolation = key2interpolation[key]
            points = (p for p in self.points if p.yname == key)
            zero = 1.0 + self.minyval * self.yscale
            cr.new_path()

            cr.move_to(self.area.x, zero * self.area.h + self.area.y)
            if interpolation == 'linear':
                for point in points:
                    cr.line_to(point.x * self.area.w + self.area.x,
                        point.y * self.area.h + self.area.y)
            else:
                previous = Point(0, zero, None, None, None, None)

                def breakage(previous, point):
                    if interpolation == 'constant-center':
                        return previous.x + ((point.x - previous.x) / 2.0)
                    elif interpolation == 'constant-left':
                        return point.x
                    elif interpolation == 'constant-right':
                        return previous.x
                for point in points:
                    cr.line_to(
                        breakage(previous, point) * self.area.w + self.area.x,
                        previous.y * self.area.h + self.area.y)
                    cr.line_to(
                        breakage(previous, point) * self.area.w + self.area.x,
                        point.y * self.area.h + self.area.y)
                    cr.line_to(point.x * self.area.w + self.area.x,
                        point.y * self.area.h + self.area.y)
                    previous = point
                cr.line_to(breakage(previous,
                        Point(1, zero, None, None, None, None))
                    * self.area.w + self.area.x,
                    previous.y * self.area.h + self.area.y)
            cr.line_to(self.area.w + self.area.x,
                zero * self.area.h + self.area.y)
            cr.move_to(self.area.x, zero * self.area.h + self.area.y)

            if key2fill[key]:
                cr.close_path()
            else:
                cr.set_source_rgb(*self.colorScheme[key])
                cr.stroke()

        cr.save()
        cr.set_line_width(2)

        if self._getDatasKeys():
            transparency = 0.8 / len(self._getDatasKeys())
            for key in self._getDatasKeys():
                if key2fill[key]:
                    cr.save()

                    r, g, b = self.colorScheme[key]
                    preparePath(key)
                    cr.set_source_rgb(r, g, b)
                    cr.stroke_preserve()
                    cr.restore()

                    # Add soft transparency the area when line is filled
                    cr.set_source_rgba(r, g, b, transparency)
                    cr.fill()

                    # Add gradient top to bottom
                    linear = cairo.LinearGradient(
                        width / 2, 0, width / 2, height)
                    linear.add_color_stop_rgba(
                        0, r * 0.65, g * 0.65, b * 0.65, transparency)
                    linear.add_color_stop_rgba(1, r, g, b, 0.1)
                    cr.set_source(linear)
                    preparePath(key)
                    cr.fill()
                else:
                    preparePath(key)

        for point in self.points:
            cr.set_source_rgb(*self.colorScheme[point.yname])
            cr.move_to(point.x * self.area.w + self.area.x,
                    point.y * self.area.h + self.area.y)
            cr.arc(point.x * self.area.w + self.area.x,
                point.y * self.area.h + self.area.y,
                3, 0, 2 * math.pi)
            cr.fill()

        cr.restore()

    def drawLegend(self, cr, widht, height):
        super(Line, self).drawLegend(cr, widht, height)
        cr.save()
        for point in self.points:
            if point.highlight:
                cr.set_line_width(2)
                cr.set_source_rgb(*common.hex2rgb('#000000'))
                cr.move_to(point.x * self.area.w + self.area.x,
                        point.y * self.area.h + self.area.y)
                cr.arc(point.x * self.area.w + self.area.x,
                    point.y * self.area.h + self.area.y,
                    3, 0, 2 * math.pi)
                cr.stroke()
                cr.set_source_rgb(*common.highlight_rgb(
                        *self.colorScheme[point.yname]))
                cr.arc(point.x * self.area.w + self.area.x,
                    point.y * self.area.h + self.area.y,
                    3, 0, 2 * math.pi)
                cr.fill()
        cr.restore()

    def motion(self, widget, event):
        if not getattr(self, 'area', None):
            return

        nearest = None
        for point in self.points:
            x = point.x * self.area.w + self.area.x
            y = point.y * self.area.h + self.area.y

            square = (event.x - x) ** 2 + (event.y - y) ** 2

            if not nearest or square < nearest[1]:
                nearest = (point, square)

        dia = self.area.w ** 2 + self.area.h ** 2

        keys2txt = {}
        for yfield in self.yfields:
            keys2txt[yfield.get('key', yfield['name'])] = yfield['string']

        highlight = False
        draw_points = []
        yfields_timedelta = {x.get('key', x['name']): x.get('timedelta')
            for x in self.yfields if 'timedelta' in x}
        for point in self.points:
            if point == nearest[0] and nearest[1] < dia / 100:
                if not point.highlight:
                    point.highlight = True
                    label = keys2txt[point.yname]
                    label += '\n'
                    if point.yval in yfields_timedelta:
                        converter = None
                        if yfields_timedelta[point.yname]:
                            converter = rpc.CONTEXT.get(
                                yfields_timedelta[point.yname])
                        label += common.timedelta.format(point.yval, converter)
                    else:
                        label += locale.localize(
                            '{:.2f}'.format(point.yval), True)
                    label += '\n'
                    label += str(self.labels[point.xname])
                    self.popup.set_text(label)
                    draw_points.append(point)
            else:
                if point.highlight:
                    point.highlight = False
                    draw_points.append(point)
            if point.highlight:
                self.popup.set_position(self,
                        point.x * self.area.w + self.area.x,
                        point.y * self.area.h + self.area.y)
                highlight = True
        if highlight:
            self.popup.show()
        else:
            self.popup.hide()

        if draw_points:
            minx = self.area.w + self.area.x
            miny = self.area.h + self.area.y
            maxx = maxy = 0.0
            for point in draw_points:
                x = self.area.w * point.x + self.area.x
                y = self.area.h * point.y + self.area.y
                minx = min(x - 5, minx)
                miny = min(y - 5, miny)
                maxx = max(x + 5, maxx)
                maxy = max(y + 5, maxy)
            self.queue_draw_area(int(minx - 1), int(miny - 1),
                    int(maxx - minx + 1), int(maxy - miny + 1))

    def updateXY(self):
        super(Line, self).updateXY()
        if self.xrange != 0:
            self.xrange -= 1
            if self.xrange == 0:
                self.xscale = 1.0
            else:
                self.xscale = 1.0 / self.xrange

    def drawAxis(self, cr, width, height):
        super(Line, self).drawAxis(cr, width, height)
        self.drawLine(cr, 1.0, 0)

    def action(self):
        super(Line, self).action()
        for point in self.points:
            if point.highlight:
                ids = self.ids[point.xname]
                self.action_keyword(ids)

    def YLabels(self):
        ylabels = super(Line, self).YLabels()
        if all('timedelta' in f for f in self.yfields):
            converter = {f.get('timedelta') for f in self.yfields}
            if len(converter) == 1:
                converter = rpc.CONTEXT.get(converter.pop())
            return [
                (x[0], common.timedelta.format(
                        datetime.timedelta(seconds=locale.atof(x[1])),
                        converter))
                for x in ylabels]
        return ylabels


class Point(object):

    def __init__(self, x, y, xval, yval, xname, yname):
        self.x, self.y = x, y
        self.xval, self.yval = xval, yval
        self.xname = xname
        self.yname = yname
        self.highlight = False
