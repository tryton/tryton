# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from io import BytesIO

import barcode
from barcode import PROVIDED_BARCODES as BARCODES
from barcode.writer import ImageWriter, SVGWriter

__all__ = ['BARCODES', 'generate_svg', 'generate_png']

BARCODES = set(BARCODES) | {'ean', 'isbn'}


def _generate(name, code, writer, **options):
    output = BytesIO()
    if name == 'ean':
        name = {
            14: 'ean14',
            13: 'ean13',
            12: 'upc',
            8: 'ean8',
            }[len(code)]
    elif name == 'isbn':
        name = {
            13: 'isbn13',
            10: 'isbn10',
            }[len(code)]
    Generator = barcode.get(name)
    Generator(code, writer=writer).write(output, options=options)
    return output


def generate_svg(
        name, code, width=0.2, height=15.0, border=6.5,
        font_size=10, text_distance=5.0,
        background='white', foreground='black'):
    writer = SVGWriter()
    options = dict(
        module_width=width,
        module_height=height,
        quiet_zone=border,
        font_size=font_size,
        text_distance=text_distance,
        background=background,
        foreground=foreground)
    return _generate(name, code, writer, **options)


def generate_png(
        name, code, width=2, height=150, border=6.5,
        font_size=10, text_distance=5.0,
        background='white', foreground='black'):
    dpi = 300
    width = width * 25.4 / dpi
    height = height * 25.4 / dpi
    writer = ImageWriter()
    options = dict(
        format='png',
        module_with=width,
        module_height=height,
        quiet_zone=border,
        font_size=font_size,
        text_distance=text_distance,
        background=background,
        foreground=foreground)
    return _generate(name, code, writer, **options)
