/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
'use strict';

Sao.Tab = Class(Object, {
    init: function() {
          }
});

Sao.Tab.Form = Class(Sao.Tab, {
    init: function(model_name, attributes) {
              Sao.Tab.Form._super.init.call(this);
              this.screen = new Sao.Screen(model_name, attributes);
              this.attributes = jQuery.extend({}, attributes);
          }
});
