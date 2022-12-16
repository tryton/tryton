# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# This code is inspired by the pycha project
# (http://www.lorenzogil.com/projects/pycha/)
import math
import locale
import datetime

import cairo

from .graph import Graph, Area
import tryton.common as common
import tryton.rpc as rpc


class Pie(Graph):

    def _getDatasKeys(self):
        return list(self.datas.keys())

    def drawLegend(self, cr, width, height):
        pass

    def drawAxis(self, cr, width, height):
        cr.set_source_rgb(*common.hex2rgb('#000000'))

        for slice in self.slices:
            normalisedAngle = slice.normalisedAngle()

            labelx = self.centerx + \
                math.sin(normalisedAngle) * (self.radius + 10)
            labely = self.centery - \
                math.cos(normalisedAngle) * (self.radius + 10)

            label = '%s (%s%%)' % (self.labels[slice.xname],
                locale.localize('{:.2f}'.format(slice.fraction * 100)))
            extents = cr.text_extents(label)
            labelWidth = extents[2]
            labelHeight = extents[3]

            x = y = 0

            if normalisedAngle <= math.pi * 0.5:
                x = labelx
                y = labely - labelHeight
            elif math.pi / 2 < normalisedAngle <= math.pi:
                x = labelx
                y = labely
            elif math.pi < normalisedAngle <= math.pi * 1.5:
                x = labelx - labelWidth
                y = labely
            else:
                x = labelx - labelWidth
                y = labely - labelHeight

            cr.move_to(x, y)
            cr.show_text(label)

    def drawLines(self, cr, width, height):
        pass

    def updateArea(self, cr, width, height):
        width = width - self.leftPadding - self.rightPadding
        height = height - self.topPadding - self.bottomPadding
        self.area = Area(self.leftPadding, self.topPadding, width, height)

        self.centerx = self.area.x + self.area.w * 0.5
        self.centery = self.area.y + self.area.h * 0.5
        self.radius = min(self.area.w * 0.4, self.area.h * 0.4)

    def updateGraph(self):

        self.sum = 0.0
        for xkey in self.datas.keys():
            key = self.yfields[0].get('key', self.yfields[0]['name'])
            if self.datas[xkey][key] > 0:
                self.sum += self.datas[xkey][key]

        fraction = angle = 0.0

        self.slices = []
        for xkey in self.datas.keys():
            key = self.yfields[0].get('key', self.yfields[0]['name'])
            value = self.datas[xkey][key]
            if value > 0:
                angle += fraction
                fraction = value / self.sum
                slice = Slice(xkey, fraction, value, angle)
                self.slices.append(slice)

    def drawGraph(self, cr, width, height):
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        cr.save()
        for slice in self.slices:
            if slice.isBigEnough():
                if bool(int(self.yfields[0].get('fill', 1))):
                    color = self.colorScheme[slice.xname]
                    if slice.highlight:
                        color = common.highlight_rgb(*color)
                    cr.set_source_rgba(*color)
                    slice.draw(cr, self.centerx, self.centery, self.radius)
                    cr.fill()
                cr.set_source_rgb(*common.hex2rgb(
                        self.attrs.get('background', '#f5f5f5')))
                slice.draw(cr, self.centerx, self.centery, self.radius)
                cr.set_line_width(2)
                cr.stroke()
        cr.restore()

    def motion(self, widget, event):
        super(Pie, self).motion(widget, event)

        if not getattr(self, 'area', None):
            return

        d = (event.x - self.centerx) ** 2 + (event.y - self.centery) ** 2
        if d > self.radius ** 2:
            self.popup.hide()
            for slice in self.slices:
                if slice.highlight:
                    self.queue_draw()
                slice.highlight = False
            return

        self.popup.show()

        if event.y == self.centery:
            angle = math.pi / 2
        else:
            angle = math.atan((event.x - self.centerx)
                / (self.centery - event.y))
        if event.x >= self.centerx:
            if event.y <= self.centery:
                pass
            else:
                angle += math.pi
        else:
            if event.y < self.centery:
                angle += 2 * math.pi
            else:
                angle += math.pi

        for slice in self.slices:
            if slice.startAngle <= angle <= slice.endAngle:
                if not slice.highlight:
                    slice.highlight = True
                    if 'timedelta' in self.yfields[0]:
                        converter = self.yfields[0].get('timedelta')
                        if converter:
                            converter = rpc.CONTEXT.get(converter)
                        value = common.timedelta.format(
                            datetime.timedelta(
                                seconds=slice.fraction * self.sum),
                            converter)
                        sum = common.timedelta.format(
                            datetime.timedelta(seconds=self.sum), converter)
                    else:
                        value = locale.localize(
                            '{:.2f}'.format(slice.fraction * self.sum))
                        sum = locale.localize('{:.2f}'.format(self.sum))
                    label = '%s (%s%%)\n%s/%s' % (
                        self.labels[slice.xname],
                        locale.localize('{:.2f}'.format(slice.fraction * 100)),
                        value, sum)
                    self.popup.set_text(label)
                    self.queue_draw()
            else:
                if slice.highlight:
                    slice.highlight = False
                    self.queue_draw()

    def action(self):
        super(Pie, self).action()
        for slice in self.slices:
            if slice.highlight:
                ids = self.ids[slice.xname]
                self.action_keyword(ids)


class Slice(object):

    def __init__(self, xname, fraction, value, angle):
        self.xname = xname
        self.fraction = fraction
        self.value = value
        self.startAngle = 2 * angle * math.pi
        self.endAngle = 2 * (angle + fraction) * math.pi
        self.highlight = False

    def isBigEnough(self):
        return abs(self.startAngle - self.endAngle) > 0.001

    def draw(self, cr, centerx, centery, radius):
        cr.new_path()
        cr.move_to(centerx, centery)
        cr.arc(centerx, centery, radius,
            self.startAngle - (math.pi / 2),
            self.endAngle - (math.pi / 2))
        cr.line_to(centerx, centery)
        cr.close_path()

    def normalisedAngle(self):
        normalisedAngle = (self.startAngle + self.endAngle) / 2

        if normalisedAngle > 2 * math.pi:
            normalisedAngle -= 2 * math.pi
        elif normalisedAngle < 0:
            normalisedAngle += 2 * math.pi
        return normalisedAngle
