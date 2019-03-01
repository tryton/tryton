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
        get record() {
            return this.screen.current_record;
        },
        set record(value) {
            this.screen.current_record = value;
        },
        get group() {
            return this.screen.group;
        },
        set_value: function() {
        },
        get_fields: function() {
            return Object.keys(this.fields);
        },
        get selected_records() {
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
}());
