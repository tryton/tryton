/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.common = {};

    Sao.common.selection = function(title, values, alwaysask) {
        if (alwaysask === undefined) {
            alwaysask = false;
        }
        if ((Object.keys(values).length == 1) && (!alwaysask)) {
            var prm = jQuery.Deferred();
            var key = Object.keys(values)[0];
            prm.resolve(values[key]);
            return prm;
        }
        // TODO
    };
}());
