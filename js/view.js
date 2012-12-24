/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
'use strict';

Sao.View = Class(Object, {
    init: function(screen, xml) {
        this.screen = screen;
        this.view_type = null;
        this.el = null;
    }
});

Sao.View.parse = function(screen, xml, children_field) {
    switch (xml.children().prop('tagName')) {
        case 'tree':
            return new Sao.View.Tree(screen, xml, children_field);
    }
};

Sao.View.tree_column_get = function(type) {
    switch (type) {
        default:
            return Sao.View.Tree.CharColumn;
    }
};

Sao.View.Tree = Class(Sao.View, {
    init: function(screen, xml, children_field) {
        Sao.View.Tree._super.init.call(this, screen, xml);
        this.view_type = 'tree';
        this.el = $('<div/>', {
            'class': 'treeview'
        });
        this.expanded = {};
        this.children_field = children_field;

        // Columns
        this.columns = [];
        this.create_columns(screen.model, xml);

        // Table of records
        this.table = $('<table/>', {
            'class': 'tree'
        });
        this.el.append(this.table);
        var thead = $('<thead/>');
        this.table.append(thead);
        var tr = $('<tr/>');
        thead.append(tr);
        this.columns.forEach(function(column) {
            var th = $('<th/>', {
                'text': column.attributes['name']
            });
            tr.append(th);
        });
        this.tbody = $('<tbody/>');
        this.table.append(this.tbody);

        // Footer with pagination stuff
        var footer = $('<div/>', {
            'class': 'treefooter'
        });
        this.previous_button = $('<button/>').button({
            'disabled': true,
            'icons': {
                primary: 'ui-icon-triangle-1-w'
            },
            'text': false,
            'label': 'Previous' //TODO translation
        });
        footer.append(this.previous_button);
        this.pagination = $('<span/>', {
            text: '0 / 0'
        });
        footer.append(this.pagination);
        this.next_button = $('<button/>').button({
            'disabled': true,
            'icons': {
                primary: 'ui-icon-triangle-1-e'
            },
            'text': false,
            'label': 'Next' //TODO translation
        });
        this.pagination.append(this.next_button);
        this.el.append(footer);
    },
    create_columns: function(model, xml) {
        var self = this;
        xml.find('tree').children().each(function(pos, child) {
            if (child.tagName == 'field') {
                var attributes = {
                    'name': child.getAttribute('name'),
                    'readonly': child.getAttribute('readonly') == 1,
                    'widget': child.getAttribute('widget'),
                    'tree_invisible': child.getAttribute('tree_invisible') == 1,
                    'expand': child.getAttribute('expand') == 1,
                    'icon': child.getAttribute('icon'),
                    'sum': child.getAttribute('sum'),
                    'width': child.getAttribute('width'),
                    'orientation': child.getAttribute('orientation'),
                    'float_time': child.getAttribute('float_time'),
                    'pre_validate': child.getAttribute('pre_validate') == 1,
                    'completion': child.getAttribute('completion') == 1
                };
                var ColumnFactory = Sao.View.tree_column_get(
                    attributes['widget']);
                var column = new ColumnFactory(model, attributes);
            } else if (child.tagName == 'button') {
                var attributes = {
                    'help': child.getAttribute('help'),
                    'string': child.getAttribute('string'),
                    'confirm': child.getAttribute('confirm'),
                    'name': child.getAttribute('name')
                };
                var column = new Sao.View.Tree.ButtonColumn(attributes);
            }
            self.columns.push(column);
        });
    },
    display: function() {
        this.tbody.empty();
        var add_row = function(record, pos, group) {
            var tree_row = new Sao.View.Tree.Row(this, pos);
            tree_row.display(record);
        };
        this.screen.group.forEach(add_row.bind(this));
    }
});

Sao.View.Tree.Row = Class(Object, {
    init: function(tree, pos, parent) {
        this.tree = tree;
        this.children_field = tree.children_field;
        this.expander = null;
        this.expander_icon = null;
        if (parent) {
            var path = jQuery.extend([], parent.path.split('.'));
        } else
            var path = [];
        path.push(pos);
        this.path = path.join('.');
        this.el = $('<tr/>');
    },
    is_expanded: function() {
        return (this.path in this.tree.expanded);
    },
    display: function(record) {
        console.log(this.path);
        var depth = this.path.split('.').length;
        for (var i = 0; i < this.tree.columns.length; i++) {
            var td = $('<td/>');
            if ((i == 0) && this.children_field) {
                if (this.is_expanded()) {
                    var expanded = 'ui-icon-minus';
                } else
                    var expanded = 'ui-icon-plus';
                this.expander = $('<span/>', {
                    'class': 'expander'
                });
                this.expander.html('&nbsp;');
                // 16 == minimum width of icon
                this.expander.css('width', ((depth * 10) + 16) + 'px');
                this.expander.css('float', 'left');
                this.expander.click(this.toggle_row.bind(this));
                this.expander_icon = $('<i/>', {
                    'class': 'ui-icon ' + expanded
                });
                this.expander.append(this.expander_icon);
                this.expander_icon.css('float', 'right');
                td.append(this.expander);
            }
            var column = this.tree.columns[i];
            td.append(column.render(record));
            this.el.append(td);
        }
        this.tree.tbody.append(this.el);
        if (this.is_expanded()) {
            var add_row = function(record, pos, group) {
                var tree_row = new Sao.View.Tree.Row(this.tree, pos, this);
                tree_row.display(record);
            };
            add_row = add_row.bind(this);
            var children_field = this.children_field;
            console.log('Load children of ' + this.path);
            record.load(this.children_field).done(function() {
                var children = record.field_get_client(children_field);
                children.forEach(add_row);
            });
        }
    },
    toggle_row: function() {
        if (this.is_expanded()) {
            this.expander_icon.removeClass('ui-icon-minus');
            this.expander_icon.addClass('ui-icon-plus');
            delete this.tree.expanded[this.path];
        } else {
            this.expander_icon.removeClass('ui-icon-plus');
            this.expander_icon.addClass('ui-icon-minus');
            this.tree.expanded[this.path] = this;
        }
        this.tree.display();
    }
});

Sao.View.Tree.CharColumn = Class(Object, {
    init: function(model, attributes) {
        this.type = 'field';
        this.field = model.fields[attributes['name']];
        this.attributes = attributes;
    },
    render: function(record) {
        var cell = $('<span/>');
        var update_text = function() {
            cell.text(this.field.get_client(record));
        };
        record.load(this.attributes.name).done(update_text.bind(this));
        return cell;
    }
});

Sao.View.Tree.ButtonColumn = Class(Object, {
    init: function(attributes) {
        this.type = 'button';
        this.attributes = attributes;
    },
    render: function() {
        var button = $('<button/>', {
            'class': 'button',
            'label': this.attributes.string
        });
        return button;
    }
});
