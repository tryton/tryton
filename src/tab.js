/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.Tab = Sao.class_(Object, {
        init: function() {
              }
    });

    Sao.Tab.counter = 0;

    Sao.Tab.create = function(attributes) {
        if (attributes.context === undefined) {
            attributes.context = {};
        }
        var tab;
        if (attributes.model) {
            tab = new Sao.Tab.Form(attributes.model, attributes);
        } else {
            tab = new Sao.Tab.Board(attributes);
        }
        jQuery('#tabs').tabs();
        tab.id = '#tab-' + Sao.Tab.counter++;
        jQuery('#tabs').tabs('add', tab.id, tab.name);
        jQuery('#tabs > ul li').last().append(jQuery('<a href="#">' +
                    '<span class="ui-icon ui-icon-circle-close"></span>' +
                    '</a>')
                .hover(
                    function() {
                        jQuery(this).css('cursor', 'pointer');
                    },
                    function() {
                        jQuery(this).css('cursor', 'default');
                    })
                .click(function() {
                    // TODO check modified
                    jQuery('#tabs').tabs('remove', tab.id);
                }));
        jQuery(tab.id).html(tab.el);
        jQuery('#tabs').tabs('select', tab.id);
    };

    Sao.Tab.Form = Sao.class_(Sao.Tab, {
        init: function(model_name, attributes) {
            Sao.Tab.Form._super.init.call(this);
            var screen = new Sao.Screen(model_name, attributes);
            this.screen = screen;
            this.attributes = jQuery.extend({}, attributes);
            this.name = attributes.name; // XXX use screen current view title
            var el = jQuery('<div/>', {
                'class': 'form'
            });
            this.el = el;
            this.screen.load_next_view().done(function() {
                el.html(screen.el);
            }).done(function() {
                screen.search_filter().done(function() {
                    screen.display();
                });
            });
        }
    });
}());
