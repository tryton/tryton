/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
'use strict';

Sao.View = Class(Object, {
    init: function(screen, xml) {
              this.view_type = null;
              this.el = null;
          }
});

Sao.View.parse = function(screen, xml) {
    switch (xml.children().prop('tagName')) {
        case 'tree':
            return new Sao.View.Tree(screen, xml);
    }
};

Sao.View.Tree = Class(Sao.View, {
    init: function(screen, xml) {
              Sao.View.Tree._super.init.call(this, screen, xml);
              this.view_type = 'tree';
              this.el = $('<div/>', {
                  'class': 'treeview'
              });
          }
});
