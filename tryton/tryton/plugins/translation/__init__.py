#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from tryton.gui.window import Window
import gettext

_ = gettext.gettext


def translate_view(datas):
    model = datas['model']
    Window.create(False, 'ir.translation', res_id=False,
            domain=[('model', '=', model)],
            mode=['tree', 'form'])


def get_plugins(model):
    return [
        (_('Translate view'), translate_view),
    ]
