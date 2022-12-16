/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View.Calendar = Sao.class_(Sao.View, {
        init: function(screen, xml) {
            Sao.View.Graph._super.init.call(this, screen, xml);
            this.view_type = 'calendar';
            this.el = jQuery('<div/>', {
                'class': 'calendar'
            });
            // TODO
            Sao.common.warning.run(
                    Sao.i18n.gettext('Calendar view not yet implemented'),
                    Sao.i18n.gettext('Warning'));
        },
        display: function() {
            return jQuery.when();
        }
    });

}());
