/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */

(function() {
    'use strict';

    var Translate = {};
    Translate.translate_view = function(data) {
        var model = data.model;
        Sao.Tab.create({
            model: 'ir.translation',
            domain: [['model', '=', model]],
            mode: ['tree', 'form'],
            name: Sao.i18n.gettext('Translate view'),
        });
    };
    Translate.get_plugins = function(model) {
        var access = Sao.common.MODELACCESS.get('ir.translation');
        if (access.read && access.write) {
            return [
                [Sao.i18n.gettext('Translate view'), Translate.translate_view],
            ];
        } else {
            return [];
        }
    };

    Sao.Plugins.push(Translate);
}());
