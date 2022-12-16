/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
(function() {
    'use strict';

    Sao.View = Sao.class_(Object, {
        init: function(screen, xml) {
            this.screen = screen;
            this.view_type = null;
            this.el = null;
            this.view_id = null;
            this.fields = {};
            var attributes = xml.children()[0].attributes;
            this.attributes = {};
            for (var i = 0, len = attributes.length; i < len; i++) {
                var attribute = attributes[i];
                this.attributes[attribute.name] = attribute.value;
            }
            screen.set_on_write(this.attributes.on_write);
        },
        set_value: function() {
        },
        get_fields: function() {
            return Object.keys(this.fields);
        },
        selected_records: function() {
            return [];
        },
        get_buttons: function() {
            return [];
        }
    });

    Sao.View.idpath2path = function(tree, idpath) {
        var path = [];
        var child_path;
        if (!idpath) {
            return [];
        }
        for (var i = 0, len = tree.rows.length; i < len; i++) {
            if (tree.rows[i].record.id == idpath[0]) {
                path.push(i);
                child_path = Sao.View.idpath2path(tree.rows[i],
                        idpath.slice(1, idpath.length));
                path = path.concat(child_path);
                break;
            }
        }
        return path;
    };

    Sao.View.parse = function(screen, xml, children_field) {
        switch (xml.children().prop('tagName')) {
            case 'tree':
                return new Sao.View.Tree(screen, xml, children_field);
            case 'form':
                return new Sao.View.Form(screen, xml);
            case 'graph':
                return new Sao.View.Graph(screen, xml);
            case 'calendar':
                return new Sao.View.Calendar(screen, xml);
        }
    };

    Sao.View.resize = function(el) {
        // Let the browser compute the table size with the fixed layout
        // then set this size to the treeview to allow scroll on overflow
        // and set the table layout to auto to get the width from the content.
        if (!el) {
            el = jQuery(document);
        }
        el.find('.treeview').each(function() {
            var treeview = jQuery(this);
            treeview.css('width', '100%');
            treeview.children('.tree').css('table-layout', 'fixed');
        });
        el.find('.treeview').each(function() {
            var treeview = jQuery(this);
            if (treeview.width()) {
                treeview.css('width', treeview.width());
                treeview.children('.tree').css('table-layout', 'auto');
            }
        });
    };
    jQuery(window).resize(function() {
        Sao.View.resize();
    });

}());
