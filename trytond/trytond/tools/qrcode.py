# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from io import BytesIO

import qrcode
from qrcode.image.pil import PilImage
from qrcode.image.svg import SvgImage
from webcolors import name_to_rgb

__all__ = ['generate_svg', 'generate_png']


def _generate(
        code, image_factory, error_correction, box_size, border, **options):
    output = BytesIO()
    qr = qrcode.QRCode(
        image_factory=image_factory,
        error_correction=error_correction,
        box_size=box_size, border=border)
    qr.add_data(code)
    qr.make_image(**options).save(output)
    return output


def _error_correction(value):
    return getattr(qrcode, f'ERROR_CORRECT_{value.upper()}')


def generate_svg(
        code, box_size=10, border=4, error_correction='M',
        background='white', foreground='black'):

    class FactoryImage(SvgImage):
        pass
    setattr(FactoryImage, 'background', background)
    return _generate(
        code, box_size=box_size, border=border,
        error_correction=_error_correction(error_correction),
        image_factory=SvgImage)


def generate_png(
        code, box_size=10, border=4, error_correction='M',
        background='white', foreground='black'):
    background = name_to_rgb(background)
    foreground = name_to_rgb(foreground)
    return _generate(
        code, box_size=box_size, border=border,
        error_correction=_error_correction(error_correction),
        back_color=background, fill_color=foreground,
        image_factory=PilImage)
