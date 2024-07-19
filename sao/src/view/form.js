/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */

/* eslint-disable no-with */
// Must be defined in non strict context otherwise is invalid
function eval_pyson(value){
    with (Sao.PYSON.eval) {
        // Add parenthesis to parse as object instead of statement
        return eval('(' + value + ')');
    }
}
/* eslint-enable no-with */

(function() {
    'use strict';

    Sao.View.FormXMLViewParser = Sao.class_(Sao.View.XMLViewParser, {
        init: function(view, exclude_field, field_attrs) {
            Sao.View.FormXMLViewParser._super.init.call(
                this, view, exclude_field, field_attrs);
            this._containers = [];
            this._mnemonics = {};
        },
        get container() {
            if (this._containers.length > 0) {
                return this._containers[this._containers.length - 1];
            }
            return null;
        },
        _parse_form: function(node, attributes) {
            var container = new Sao.View.Form.Container(
                Number(node.getAttribute('col') || 4));
            this.view.containers.push(container);
            this.parse_child(node, container);
            if (this._containers.length > 0) {
                throw 'AssertionError';
            }
            // Append after parsing child to minimize browser reflow
            this.view.el.append(container.el);
        },
        parse_child: function(node, container) {
            if (container) {
                this._containers.push(container);
            }
            for (const child of node.childNodes) {
                this.parse(child);
            }
            if (container) {
                if (container instanceof Sao.View.Form.Container) {
                    container.setup_grid_template();
                }
                this._containers.pop();
            }
        },
        _parse_field: function(node, attributes) {
            var name = attributes.name;
            if (name && (name == this.exclude_field)) {
                this.container.add(null, attributes);
                return;
            }

            if (attributes.loading == 'eager') {
                this.field_attrs[name].loading = 'eager';
            }

            var WidgetFactory = Sao.View.FormXMLViewParser.WIDGETS[
                attributes.widget];
            var widget = new WidgetFactory(this.view, attributes);
            if (!this.view.widgets[name]) {
                this.view.widgets[name] = [];
            }
            this.view.widgets[name].push(widget);
            widget.position = this.view.widget_id += 1;

            if (widget.expand) {
                if (attributes.yexpand === undefined) {
                    attributes.yexpand = true;
                }
                if (attributes.yfill === undefined) {
                    attributes.yfill = true;
                }
            }

            if (attributes.height !== undefined) {
                widget.el.css('min-height', attributes.height + 'px');
                if (widget.el.children().length == 1) {
                    widget.el.children().css('min-height', 'inherit');
                }
            }
            if (attributes.width !== undefined) {
                widget.el.css('min-width', attributes.width + 'px');
            }

            if (attributes.xalign === undefined) {
                if (attributes.xexpand) {
                    attributes.xalign = 0;
                } else {
                    attributes.xalign = 0.5;
                }
            }

            if (attributes.yalign === undefined) {
                if (attributes.yexpand) {
                    attributes.yalign = 0;
                } else {
                    attributes.yalign = 0.5;
                }
            }

            this.container.add(widget, attributes);

            if (this._mnemonics[name] && widget.labelled) {
                var label = this._mnemonics[name];
                var accesskey = Sao.common.accesskey(label.label_el.text());
                label.label_el.uniqueId();
                widget.labelled.uniqueId();
                widget.labelled.attr('aria-labelledby', label.el.attr('id'));
                widget.labelled.attr('accesskey', accesskey);
                if (~['INPUT', 'SELECT'].indexOf(
                    widget.labelled.get(0).tagName)) {
                    jQuery('<span/>', {
                        'data-accesskey': accesskey,
                    }).appendTo(widget.labelled.parent());
                }
                label.label_el.attr('for', widget.labelled.attr('id'));
            }
        },
        _parse_button: function(node, attributes) {
            var button = new Sao.common.Button(attributes);
            button.el.click(button, this.view.button_clicked.bind(this.view));
            this.view.state_widgets.push(button);
            this.container.add(button, attributes);
        },
        _parse_link: function(node, attributes) {
            var link = new Sao.View.Form.Link(attributes);
            this.view.state_widgets.push(link);
            this.container.add(link, attributes);
        },
        _parse_image: function(node, attributes) {
            var image = new Sao.View.Form.Image_(attributes);
            this.view.state_widgets.push(image);
            this.container.add(image, attributes);
        },
        _parse_separator: function(node, attributes) {
            var name = attributes.name;
            if (name && (name == this.exclude_field)) {
                this.container.add(null, attributes);
                return;
            }
            var text = attributes.string;
            var separator = new Sao.View.Form.Separator(text, attributes);
            if (text) {
                var xalign = attributes.xalign;
                if (xalign === undefined) {
                    xalign = 0;
                }
                if (xalign == 0.5) {
                    xalign = 'center';
                } else {
                    xalign = xalign <= 0.5? 'start' : 'end';
                }
                separator.label_el.css('text-align', xalign);
            }
            this.view.state_widgets.push(separator);
            this.container.add(separator, attributes);
            if (name) {
                this._mnemonics[name] = separator;
            }
        },
        _parse_label: function(node, attributes) {
            var name = attributes.name;
            if (name && (name == this.exclude_field)) {
                this.container.add(null, attributes);
                return;
            }
            if (attributes.xexpand === undefined) {
                attributes.xexpand = 0;
            }
            if (attributes.xalign === undefined) {
                attributes.xalign = 1.0;
            }
            if (attributes.yalign === undefined) {
                attributes.yalign = 0.5;
            }
            var label = new Sao.View.Form.Label(attributes.string, attributes);
            this.view.state_widgets.push(label);
            this.container.add(label, attributes);
            if (name) {
                this._mnemonics[name] = label;
            }
        },
        _parse_newline: function(node, attributes) {
            this.container.add_row();
        },
        _parse_notebook: function(node, attributes) {
            if (attributes.colspan === undefined) {
                attributes.colspan = 4;
            }
            var notebook = new Sao.View.Form.Notebook(attributes);
            if (attributes.height !== undefined) {
                notebook.el.css('min-height', attributes.height + 'px');
            }
            if (attributes.width !== undefined) {
                notebook.el.css('min-width', attributes.width + 'px');
            }
            this.view.state_widgets.push(notebook);
            this.view.notebooks.push(notebook);
            this.container.add(notebook, attributes);
            this.parse_child(node, notebook);
        },
        _parse_page: function(node, attributes) {
            if (attributes.name && (attributes.name == this.exclude_field)) {
                return;
            }
            var container = new Sao.View.Form.Container(
                Number(node.getAttribute('col') || 4));
            this.view.containers.push(container);
            this.parse_child(node, container);
            var page = new Sao.View.Form.Page(
                this.container.add(
                    container.el, attributes.string, attributes.icon),
                attributes);
            this.view.state_widgets.push(page);
        },
        _parse_group: function(node, attributes) {
            var group = new Sao.View.Form.Container(
                Number(node.getAttribute('col') || 4));
            this.view.containers.push(group);
            this.parse_child(node, group);

            if (attributes.xalign === undefined) {
                attributes.xalign = 0.5;
            }
            if (attributes.yalign === undefined) {
                attributes.yalign = 0.5;
            }
            if (attributes.name && (attributes.name == this.exclude_field)) {
                this.container.add(null, attributes);
                return;
            }

            var widget;
            if (attributes.expandable !== undefined) {
                widget = new Sao.View.Form.Expander(attributes);
                widget.set_expanded(attributes.expandable === '1');
                this.view.expandables.push(widget);
            } else {
                widget = new Sao.View.Form.Group(attributes);
            }
            widget.add(group);

            this.view.state_widgets.push(widget);
            this.container.add(widget, attributes);
        },
        _parse_hpaned: function(node, attributes) {
            this._parse_paned(node, attributes, 'horizontal');
        },
        _parse_vpaned: function(node, attributes) {
            this._parse_paned(node, attributes, 'vertical');
        },
        _parse_paned: function(node, attributes, orientation) {
            var paned = new Sao.common.Paned(orientation);
            // TODO position
            this.container.add(paned, attributes);
            this.parse_child(node, paned);
        },
        _parse_child: function(node, attributes) {
            var paned = this.container;
            var container = new Sao.View.Form.Container(
                Number(node.getAttribute('col') || 4));
            this.view.containers.push(container);
            this.parse_child(node, container);

            var child;
            if (!paned.get_child1().children().length) {
                child = paned.get_child1();
            } else {
                child = paned.get_child2();
            }
            child.append(container.el);
        },
    });

    Sao.View.Form = Sao.class_(Sao.View, {
        editable: true,
        creatable: true,
        view_type: 'form',
        xml_parser: Sao.View.FormXMLViewParser,
        init: function(view_id, screen, xml) {
            this.el = jQuery('<div/>', {
                'class': 'form'
            });
            this.notebooks = [];
            this.expandables = [];
            this.containers = [];
            this.widget_id = 0;
            Sao.View.Form._super.init.call(this, view_id, screen, xml);
            if (this.attributes.creatable) {
                this.creatable = Boolean(parseInt(this.attributes.creatable, 10));
            }
            if (this.attributes.scan_code) {
                this.scan_code_btn = new Sao.common.Button({
                    'string': Sao.i18n.gettext("Scan"),
                    'icon': 'tryton-barcode-scanner',
                    'states': this.attributes.scan_code_states,
                }, null, 'lg', 'btn-primary');
                this.scan_code_btn.el.click(() => {
                    new Sao.Window.CodeScanner(
                        this.on_scan_code.bind(this),
                        this.attributes.scan_code == 'loop');
                });
                this.el.append(jQuery('<div/>', {
                    'class': 'btn-code-scanner',
                }).append(this.scan_code_btn.el));
                this.state_widgets.push(this.scan_code_btn);
            }
        },
        get_fields: function() {
            return Object.keys(this.widgets);
        },
        get_buttons: function() {
            var buttons = [];
            for (var j in this.state_widgets) {
                var widget = this.state_widgets[j];
                if (widget instanceof Sao.common.Button) {
                    buttons.push(widget);
                }
            }
            return buttons;
        },
        display: function() {
            var record = this.record;
            var field;
            var promesses = [];
            if (this.scan_code_btn) {
                this.scan_code_btn.el.toggle(Boolean(record));
            }
            if (record) {
                // Force to set fields in record
                // Get first the lazy one from the view to reduce number of requests
                var field_names = new Set(this.get_fields());
                for (const name in record.model.fields) {
                    field = record.model.fields[name];
                    if (~field.views.has(this.view_id)) {
                        field_names.add(name);
                    }
                }

                var fields = [];
                for (const fname of field_names) {
                    field = record.model.fields[fname];
                    fields.push([
                        fname,
                        (field.description.loading || 'eager') == 'eager',
                        field.views.size,
                    ]);
                }
                fields.sort(function(a, b) {
                    if (!a[1] && b[1]) {
                        return -1;
                    } else if (a[1] && !b[1]) {
                        return 1;
                    } else {
                        return a[2] - b[2];
                    }
                });
                for (const e of fields) {
                    const name = e[0];
                    promesses.push(record.load(name));
                }
            }
            return jQuery.when.apply(jQuery,promesses)
                .done(() => {
                    var record = this.record;
                    for (const name in this.widgets) {
                        var widgets = this.widgets[name];
                        field = null;
                        if (record) {
                            field = record.model.fields[name];
                        }
                        if (field) {
                            field.set_state(record);
                        }
                        for (const widget of widgets) {
                            widget.display();
                        }
                    }
                    var promesses = [];
                    // We iterate in the reverse order so that the most nested
                    // widgets are computed first and set_state methods can rely
                    // on their children having their state set
                    for (const state_widget of this.state_widgets.toReversed()) {
                        var prm = state_widget.set_state(record);
                        if (prm) {
                            promesses.push(prm);
                        }
                    }
                    for (const container of this.containers) {
                        container.set_grid_template();
                    }
                    // re-set the grid templates for the StateWidget that are
                    // asynchronous
                    jQuery.when.apply(jQuery, promesses).done(() => {
                        for (const container of this.containers) {
                            container.set_grid_template();
                        }
                    });
                });
        },
        set_value: function() {
            var record = this.record;
            if (record) {
                for (var name in this.widgets) {
                    if (name in record.model.fields) {
                        var widgets = this.widgets[name];
                        var field = record.model.fields[name];
                        for (const widget of widgets) {
                            widget.set_value(record, field);
                        }
                    }
                }
            }
        },
        button_clicked: function(event) {
            var button = event.data;
            button.el.prop('disabled', true);  // state will be reset at display
            this.screen.button(button.attributes);
        },
        on_scan_code: function(code) {
            var record = this.record;
            if (record) {
                return record.on_scan_code(
                    code, this.attributes.scan_code_depends || []).done(() => {
                        if (this.attributes.scan_code == 'submit') {
                            this.el.parents('form').submit();
                        }
                    });
            } else {
                return jQuery.when();
            }
        },
        get selected_records() {
            if (this.record) {
                return [this.record];
            }
            return [];
        },
        get modified() {
            for (var name in this.widgets) {
                var widgets = this.widgets[name];
                for (const widget of widgets) {
                    if (widget.modified) {
                        return true;
                    }
                }
            }
            return false;
        },
        set_cursor: function(new_, reset_view) {
            var i, name, j;
            var focus_el, notebook, child, group;
            var widgets, error_el, pages, is_ancestor;

            var currently_focused = jQuery(document.activeElement);
            var has_focus = currently_focused.closest(this.el).length > 0;
            if (reset_view || !has_focus) {
                if (reset_view) {
                    for (i = 0; i < this.notebooks.length; i++) {
                        notebook = this.notebooks[i];
                        notebook.set_current_page();
                    }
                }
                if (this.attributes.cursor in this.widgets) {
                    focus_el = Sao.common.find_focusable_child(
                            this.widgets[this.attributes.cursor][0].el);
                } else {
                    child = Sao.common.find_focusable_child(this.el);
                    if (child) {
                        child.focus();
                    }
                }
            }

            var record = this.record;
            if (record) {
                var invalid_widgets = [];
                // We use the has-error class to find the invalid elements
                // because Sao.common.find_focusable_child use the :visible
                // selector which acts differently than GTK's get_visible
                var error_els = this.el.find('.has-error');
                var invalid_fields = record.invalid_fields();
                for (name in invalid_fields) {
                    widgets = this.widgets[name] || [];
                    for (i = 0; i < error_els.length; i++) {
                        error_el = jQuery(error_els[i]);
                        for (j = 0; j < widgets.length; j++) {
                            if (error_el.closest(widgets[j].el).length > 0) {
                                invalid_widgets.push(error_el);
                                break;
                            }
                        }
                    }
                }
                if (invalid_widgets.length > 0) {
                    focus_el = Sao.common.find_first_focus_widget(this.el,
                            invalid_widgets);
                }
            }

            if (focus_el) {
                for (i = 0; i < this.notebooks.length; i++) {
                    notebook = this.notebooks[i];
                    pages = notebook.get_n_pages();
                    for (j = 0; j < pages; j++) {
                        child = notebook.get_nth_page(j);
                        is_ancestor = (
                                jQuery(focus_el).closest(child).length > 0);
                        if (is_ancestor) {
                            notebook.set_current_page(j);
                            break;
                        }
                    }
                }
                for (i = 0; i < this.expandables.length; i++) {
                    group = this.expandables[i];
                    is_ancestor = (
                            jQuery(focus_el).closest(group.el).length > 0);
                    if (is_ancestor) {
                        group.set_expanded(true);
                    }
                }
                jQuery(focus_el).find('input,select,textarea')
                    .addBack(focus_el).focus();
            }
        }
    });

    Sao.View.Form.Container = Sao.class_(Object, {
        init: function(col=4) {
            if (col < 0) col = 0;
            this.col = col;
            this.el = jQuery('<div/>', {
                'class': 'form-container'
            });
            if (this.col <= 0) {
                this.el.addClass('form-hcontainer');
            } else if (this.col == 1) {
                this.el.addClass('form-vcontainer');
            }
            this._col = 1;
            this._row = 1;
            this._xexpand = new Set();
            this._colspans = [];
            this._yexpand = new Set();
            this._grid_cols = [];
            this._grid_rows = [];
        },
        add_row: function() {
            this._col = 1;
            this._row += 1;
        },
        add: function(widget, attributes) {
            var colspan = attributes.colspan;
            if (colspan === undefined) colspan = 1;
            var xfill = attributes.xfill;
            if (xfill === undefined) xfill = 1;
            var xexpand = attributes.xexpand;
            if (xexpand === undefined) xexpand = 1;

            // CSS grid elements are 1-indexed
            if (this.col > 0) {
                if (colspan > this.col) {
                    colspan = this.col;
                }
                if ((this._col + colspan) > (this.col + 1)) {
                    this._col = 1;
                    this._row += 1;
                }
            }

            var el;
            if (widget) {
                el = widget.el;
            }
            var cell = jQuery('<div/>', {
                'class': 'form-item ' + (widget ? widget.class_ || '' : ''),
            }).append(el);
            cell.css('grid-column', `${this._col} / ${this._col + colspan}`);
            cell.css('grid-row', `${this._row} / ${this._row + 1}`);
            this.el.append(cell);

            if (!widget) {
                this._col += colspan;
                return;
            } else {
                if (xexpand && (colspan == 1)) {
                    this._xexpand.add(this._col);
                } else if (xexpand) {
                    var newspan = [];
                    for (var i=this._col; i < this._col + colspan; i++) {
                        newspan.push(i);
                    }
                    this._colspans.push(newspan);
                }
                if (attributes.yexpand) {
                    this._yexpand.add(this._row);
                }
                this._col += colspan;
            }

            if (attributes.xalign !== undefined) {
                var xalign;
                if (attributes.xalign == 0.5) {
                    xalign = 'center';
                } else {
                    xalign = attributes.xalign <= 0.5? 'start': 'end';
                }
                cell.addClass(`xalign-${xalign}`);
            } else {
                cell.addClass('xalign-start');
            }
            if (xexpand) {
                cell.addClass('xexpand');
            }
            if (xfill) {
                cell.addClass('xfill');
                if (xexpand) {
                    el.addClass('xexpand');
                }
            }

            if (attributes.yalign !== undefined) {
                var yalign;
                if (attributes.yalign == 0.5) {
                    yalign = 'center';
                } else {
                    yalign = attributes.yalign <= 0.5? 'start': 'end';
                }
                cell.addClass(`yalign-${yalign}`);
            }

            if (attributes.yfill) {
                cell.addClass('yfill');
                if (attributes.yexpand) {
                    el.addClass('yexpand');
                }
            }

            if (attributes.help) {
                widget.el.attr('title', attributes.help);
            }
        },
        setup_grid_template: function() {
            for (const span of this._colspans) {
                var found = false;
                for (const col of span) {
                    if (this._xexpand.has(col)) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    this._xexpand.add(
                        Math.round((span[0] + span[span.length - 1]) / 2));
                }
            }

            var i;
            var col = this.col <= 0 ? this._col : this.col;
            if (this._xexpand.size) {
                for (i = 1; i <= col; i++) {
                    if (this._xexpand.has(i)) {
                        this._grid_cols.push(`minmax(min-content, ${col}fr)`);
                    } else {
                        this._grid_cols.push('min-content');
                    }
                }
            } else {
                for (i = 1; i <= col; i++) {
                    this._grid_cols.push("min-content");
                }
            }

            if (this._yexpand.size) {
                for (i = 1; i <= this._row; i++) {
                    if (this._yexpand.has(i)) {
                        this._grid_rows.push(
                            `minmax(min-content, ${this._row}fr)`);
                    } else {
                        this._grid_rows.push('min-content');
                    }
                }
            } else {
                for (i = 1; i <= this._row; i++) {
                    this._grid_rows.push("min-content");
                }
            }
        },
        set_grid_template: function() {
            var i;
            var grid_cols = this._grid_cols.slice();
            var grid_rows = this._grid_rows.slice();
            var cols = [];
            var rows = [];
            for (i = 0; i < grid_cols.length; i++) {
                cols.push([]);
            }
            for (i = 0; i < grid_rows.length; i++) {
                rows.push([]);
            }
            var col_start, col_end, row_start, row_end;
            for (var child of this.el.children()) {
                child = jQuery(child);
                col_start = parseInt(
                    child.css('grid-column-start'), 10);
                col_end = parseInt(child.css('grid-column-end'), 10);
                row_start = parseInt(child.css('grid-row-start'), 10);
                row_end = parseInt(child.css('grid-row-end'), 10);

                for (i = col_start; i < col_end; i++) {
                    cols[i - 1].push(child);
                }
                for (i = row_start; i < row_end; i++) {
                    rows[i - 1].push(child);
                }
            }
            var row, col;
            var is_empty = function(e) {
                var empty = true;
                for (const child of e.children(':not(.tooltip)')) {
                    if (jQuery(child).css('display') != 'none') {
                        empty = false;
                        break;
                    }
                }
                e.toggleClass('form-empty', empty);
                return empty;
            };
            for (i = 0; i < grid_cols.length; i++) {
                col = cols[i];
                if (col.every(is_empty)) {
                    grid_cols[i] = "0px";
                }
            }
            for (i = 0; i < grid_rows.length; i++) {
                row = rows[i];
                if (row.every(is_empty)) {
                    grid_rows[i] = "0px";
                }
            }
            this.el.css(
                'grid-template-columns', grid_cols.join(" "));
            this.el.css(
                'grid-template-rows', grid_rows.join(" "));
        }
    });

    Sao.View.Form.StateWidget = Sao.class_(Object, {
        init: function(attributes) {
            this.attributes = attributes;
        },
        set_state: function(record) {
            var state_changes;
            if (record) {
                state_changes = record.expr_eval(this.attributes.states || {});
            } else {
                state_changes = {};
            }
            var invisible = state_changes.invisible;
            if (invisible === undefined) {
                invisible = this.attributes.invisible;
            }
            if (invisible) {
                this.hide();
            } else {
                this.show();
            }
        },
        show: function() {
            this.el.show();
        },
        hide: function() {
            this.el.hide();
        }
    });

    Sao.View.Form.LabelMixin = Sao.class_(Sao.View.Form.StateWidget, {
        set_state: function(record) {
            Sao.View.Form.LabelMixin._super.set_state.call(this, record);
            var field;
            if (this.attributes.name && record) {
                field = record.model.fields[this.attributes.name];
            }
            if (!((this.attributes.string === undefined) ||
                this.attributes.string)) {
                var text = '';
                if (field && record) {
                    text = field.get_client(record) || '';
                }
                this.label_el.text(text);
            }
            var state_changes;
            if (record) {
                state_changes = record.expr_eval(this.attributes.states || {});
            } else {
                state_changes = {};
            }
            if (state_changes.readonly === undefined) {
                state_changes.readonly = !field;
            }
            Sao.common.apply_label_attributes(
                    this.label_el,
                    ((field && field.description.readonly) ||
                     state_changes.readonly),
                    ((field && field.description.required) ||
                     state_changes.required));
        }
    });

    Sao.View.Form.Separator = Sao.class_(Sao.View.Form.LabelMixin, {
        init: function(text, attributes) {
            Sao.View.Form.Separator._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': 'form-separator'
            });
            this.label_el = jQuery('<label/>');
            if (text) {
                this.label_el.text(text);
            }
            this.el.append(this.label_el);
            this.el.append(jQuery('<hr/>'));
        }
    });

    Sao.View.Form.Label = Sao.class_(Sao.View.Form.LabelMixin, {
        class_: 'form-label',
        init: function(text, attributes) {
            Sao.View.Form.Label._super.init.call(this, attributes);
            this.el = this.label_el = jQuery('<label/>', {
                text: text,
                'class': this.class_
            });
        }
    });

    Sao.View.Form.Notebook = Sao.class_(Sao.View.Form.StateWidget, {
        class_: 'form-notebook',
        init: function(attributes) {
            Sao.View.Form.Notebook._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.nav = jQuery('<ul/>', {
                'class': 'nav nav-tabs',
                role: 'tablist'
            }).appendTo(this.el);
            this.panes = jQuery('<div/>', {
                'class': 'tab-content'
            }).appendTo(this.el);
            this.selected = false;
        },
        add: function(tab, text, icon) {
            var pane = jQuery('<div/>', {
                'role': 'tabpanel',
                'class': 'tab-pane',
            }).uniqueId();
            var tab_id = pane.attr('id');
            var img = Sao.common.ICONFACTORY.get_icon_img(icon);
            var page = jQuery('<li/>', {
                'role': 'presentation'
            }).append(
                jQuery('<a/>', {
                    'aria-controls': tab_id,
                    'role': 'tab',
                    'data-toggle': 'tab',
                    'href': '#' + tab_id
                })
                .text(text)
                .prepend(img))
                .appendTo(this.nav);
            pane.append(tab).appendTo(this.panes);
            if (!this.selected) {
                // Can not use .tab('show')
                page.addClass('active');
                pane.addClass('active');
                this.selected = true;
            }
            return page;
        },
        set_current_page: function(page_index=null) {
            var selector;
            if (page_index === null) {
                selector = ':visible:first';
            } else {
                selector = ':eq(' + page_index + '):visible';
            }
            var tab = this.nav.find('li' + selector + ' a');
            tab.tab('show');
        },
        get_n_pages: function() {
            return this.nav.find("li[role='presentation']").length;
        },
        get_nth_page: function(page_index) {
            return jQuery(this.panes.find("div[role='tabpanel']")[page_index]);
        },
        set_state: function(record) {
            Sao.View.Form.Notebook._super.set_state.call(this, record);

            var n_pages = this.get_n_pages();
            if (n_pages > 0) {
                var to_collapse = true;
                for (let i = 0; i < n_pages; i++) {
                    var page = this.get_nth_page(i);
                    if (page.css('display') != 'none') {
                        to_collapse = false;
                        break;
                    }
                }
                if (to_collapse) {
                    this.hide();
                }
            } else {
                this.hide();
            }
        }
    });

    Sao.View.Form.Page = Sao.class_(Sao.View.Form.StateWidget, {
        init: function(el, attributes) {
            Sao.View.Form.Page._super.init.call(this, attributes);
            this.el = el;
        },
        hide: function() {
            Sao.View.Form.Page._super.hide.call(this);
            if (this.el.hasClass('active')) {
                window.setTimeout(() => {
                    if (this.el.hasClass('active') && this.el.is(':hidden')) {
                        this.el.siblings(':visible').first().find('a').tab('show');
                    }
                });
            }
        }
    });

    Sao.View.Form.Group = Sao.class_(Sao.View.Form.StateWidget, {
        class_: 'form-group_',
        init: function(attributes) {
            Sao.View.Form.Group._super.init.call(this, attributes);
            this.el = jQuery('<fieldset/>', {
                'class': this.class_
            });
            if (attributes.string) {
                this.el.append(jQuery('<legend/>').text(attributes.string));
            }
        },
        add: function(widget) {
            this.el.append(widget.el);
        },
        set_state: function(record) {
            Sao.View.Form.Group._super.set_state.call(this, record);

            var to_collapse = false;
            if (!this.attributes.string) {
                to_collapse = true;
                var children = this.el
                    .find('> .form-container > .form-item')
                    .children(':not(.tooltip)');
                for (const child of children) {
                    if (jQuery(child).css('display') != 'none') {
                        to_collapse = false;
                        break;
                    }
                }
            }
            if (to_collapse) {
                this.hide();
            }
        }
    });

    Sao.View.Form.Expander = Sao.class_(Sao.View.Form.StateWidget, {
        class_: 'form-group-expandable',
        init: function(attributes) {
            Sao.View.Form.Expander._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': 'panel panel-default ' + this.class_
            });
            var heading = jQuery('<div/>', {
                'class': 'panel-heading',
            }).appendTo(this.el);
            heading.uniqueId();

            this.collapsible = jQuery('<div/>', {
                'class': 'panel-collapse collapse',
                'aria-labelledby': heading.attr('id'),
            }).appendTo(this.el);
            this.collapsible.uniqueId();
            this.body = jQuery('<div/>', {
                'class': 'panel-body',
            }).appendTo(this.collapsible);

            var title = jQuery('<label/>', {
                'class': 'panel-title',
            }).appendTo(heading);
            var link = jQuery('<a/>', {
                'role': 'button',
                'data-toggle': 'collapse',
                'href': '#' + this.collapsible.attr('id'),
                'aria-controls': this.collapsible.attr('id'),
                'aria-expanded': attributes.expandable == '1',
            }).appendTo(title);
            if (attributes.string) {
                link.text(attributes.string);
            }
            link.append(jQuery('<span/>', {
                'class': 'caret',
            }));
        },
        add: function(widget) {
            this.body.empty();
            this.body.append(widget.el);
        },
        set_expanded: function(expanded) {
            if (expanded) {
                this.collapsible.collapse('show');
            } else {
                this.collapsible.collapse('hide');
            }
        }
    });

    Sao.View.Form.Link = Sao.class_(Sao.View.Form.StateWidget, {
        class_: 'form-link',
        init: function(attributes) {
            Sao.View.Form.Link._super.init.call(this, attributes);
            this.el = jQuery('<button/>', {
                'class': this.class_ + ' btn btn-link',
                'name': attributes.name,
                'type': 'button',
            });
            if (attributes.icon) {
                var img = jQuery('<img/>', {
                    'class': 'icon',
                }).prependTo(this.el);
                Sao.common.ICONFACTORY.get_icon_url(attributes.icon)
                    .done(function(url) {
                        img.attr('src', url);
                    });
            }
            this.label = jQuery('<div/>').appendTo(this.el);
            this._current = null;
        },
        get action_id() {
            return parseInt(this.attributes.id, 10);
        },
        set_state: function(record) {
            Sao.View.Form.Link._super.set_state.call(this, record);
            if (this.el.css('display') == 'none') {
                return;
            }
            var data = {},
                context = {},
                pyson_ctx = {};
            if (record) {
                if (record.id < 0) {
                    this.hide();
                    return;
                }
                data = {
                    model: record.model.name,
                    id: record.id,
                    ids: [record.id],
                };
                context = record.get_context();
                pyson_ctx = {
                    active_model: record.model.name,
                    active_id: record.id,
                    active_ids: [record.id],
                };
                this._current = record.id;
            } else {
                this._current = null;
            }
            pyson_ctx.context = context;
            this.el.off('click');
            this.el.click([data, context], this.clicked.bind(this));
            var action = Sao.rpc({
                'method': 'model.ir.action.get_action_value',
                'params': [this.action_id, context],
            }, Sao.Session.current_session, false);
            this.label.text(action.name);
            this.el.attr('title', action.name);

            var decoder = new Sao.PYSON.Decoder(pyson_ctx);
            var domain = decoder.decode(action.pyson_domain);
            if (action.pyson_search_value) {
                domain = [domain, decoder.decode(action.pyson_search_value)];
            }
            var tab_domains = action.domains
                .filter(function(d) {
                    return d[2];
                }).map(function(d) {
                    var name = d[0],
                        domain = d[1];
                    return [name, decoder.decode(domain)];
                });
            const promesses = [];
            var counter;
            if (record && record.links_counts[this.action_id]) {
                counter = record.links_counts[this.action_id];
                this.set_label(action.name, tab_domains, counter);
            } else {
                if (tab_domains.length) {
                    counter = tab_domains.map(function() {
                        return 0;
                    });
                } else {
                    counter = [0];
                }
                if (record) {
                    record.links_counts[this.action_id] = counter;
                }
                var current = this._current;
                if (tab_domains.length) {
                    tab_domains.map(function(d, i) {
                        var tab_domain = d[1];
                        const prm = Sao.rpc({
                            'method': (
                                'model.' + action.res_model + '.search_count'),
                            'params': [
                                ['AND', domain, tab_domain], 0, 100, context],
                        }, Sao.Session.current_session, true, false).then(
                            value => {
                                this._set_count(
                                    value, i, current, counter,
                                    action.name, tab_domains);
                        });
                        promesses.push(prm);
                    }, this);
                } else {
                    const prm = Sao.rpc({
                        'method': (
                            'model.' + action.res_model + '.search_count'),
                        'params': [domain, 0, 100, context],
                    }, Sao.Session.current_session, true, false
                    ).then(value => {
                        this._set_count(
                            value, 0, current, counter,
                            action.name, tab_domains);
                    });
                    promesses.push(prm);
                }
            }
            return jQuery.when.apply(jQuery, promesses);
        },
        _set_count: function(value, idx, current, counter, name, domains) {
            if (current != this._current) {
                return;
            }
            if (value > 99) {
                value = '99+';
            }
            counter[idx] = value;
            this.set_label(name, domains, counter);
        },
        set_label: function(name, domains, counter) {
            this.label.text(name);
            this.el.attr('accesskey', Sao.common.accesskey(name));
            if (domains.length) {
                domains.map(function(d, i) {
                    var name = d[0];
                    this.label.append(jQuery('<br/>'));
                    this.label.append(name + ' ');
                    jQuery('<span/>', {
                        'class': 'badge',
                    }).text(counter[i]).appendTo(this.label);
                }, this);
            } else {
                this.label.append(' ');
                jQuery('<span/>', {
                    'class': 'badge',
                }).text(counter[0]).appendTo(this.label);
            }
            if (this.attributes.empty === 'hide') {
                var non_empty = counter.filter(function(number) {
                    return number != 0;
                });
                if (non_empty.length) {
                    this.el.show();
                } else {
                    this.el.hide();
                }
            }
        },
        clicked: function(evt) {
            Sao.Action.execute(this.action_id, evt.data[0], evt.data[1], true);
        },
    });

    Sao.View.Form.Image_ = Sao.class_(Sao.View.Form.StateWidget, {
        class_: 'form-image_',
        init: function(attributes) {
            Sao.View.Form.Image_._super.init.call(this, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.img = jQuery('<img/>', {
                'class': 'center-block',
                'width': (attributes.size || 48) + 'px',
                'height': (attributes.size || 48) + 'px',
            }).appendTo(this.el);
            switch (attributes.border) {
                case 'rounded':
                    this.img.addClass('img-rounded');
                    break;
                case 'circle':
                    this.img.addClass('img-circle');
                    break;
                default:
                    break;
            }
        },
        set_state: function(record) {
            Sao.View.Form.Image_._super.set_state.call(this, record);
            if (!record) {
                return;
            }
            var name = this.attributes.name;
            if (name in record.model.fields) {
                var field = record.model.fields[name];
                name = field.get(record);
            }
            if (this.attributes.type == 'url') {
                if (name) {
                    if (this.attributes.url_size) {
                        var url = new URL(name, window.location);
                        url.searchParams.set(
                            this.attributes.url_size,
                            this.attributes.size || 48);
                        name = url.href;
                    }
                    this.img.attr('src', name);
                } else {
                    this.img.removeAttr('src');
                }
            } else {
                Sao.common.ICONFACTORY.get_icon_url(name)
                    .done(url => {
                        if (url) {
                            this.img.attr('src', url);
                        } else {
                            this.img.removeAttr('src');
                        }
                    });
            }
        }
    });

    Sao.View.Form.Widget = Sao.class_(Object, {
        expand: false,
        init: function(view, attributes) {
            this.view = view;
            this.attributes = attributes;
            this.el = null;
            this.position = 0;
            this.visible = true;
            this.labelled = null;  // Element which received the labelledby
        },
        display: function() {
            var field = this.field;
            var record = this.record;
            var readonly = this.attributes.readonly;
            var invisible = this.attributes.invisible;
            var required = this.attributes.required;
            if (!field) {
                if (readonly === undefined) {
                    readonly = true;
                }
                if (invisible === undefined) {
                    invisible = false;
                }
                if (required === undefined) {
                    required = false;
                }
                this.set_readonly(readonly);
                this.set_invisible(invisible);
                this.set_required(required);
                return;
            }
            var state_attrs = field.get_state_attrs(record);
            if (readonly === undefined) {
                readonly = state_attrs.readonly;
                if (readonly === undefined) {
                    readonly = false;
                }
            }
            if (required === undefined) {
                required = state_attrs.required;
                if (required === undefined) {
                    required = false;
                }
            }
            if (this.view.screen.attributes.readonly) {
                readonly = true;
            }
            this.set_readonly(readonly);
            if (readonly) {
                this.el.addClass('readonly');
            } else {
                this.el.removeClass('readonly');
            }
            var required_el = this._required_el();
            this.set_required(required);
            if (!readonly && required) {
                required_el.addClass('required');
            } else {
                required_el.removeClass('required');
            }
            var invalid = state_attrs.invalid;
            var invalid_el = this._invalid_el();
            if (!readonly && invalid) {
                invalid_el.addClass('has-error');
            } else {
                invalid_el.removeClass('has-error');
            }
            if (invisible === undefined) {
                invisible = field.get_state_attrs(this.record).invisible;
                if (invisible === undefined) {
                    invisible = false;
                }
            }
            this.set_invisible(invisible);
        },
        _required_el: function () {
            return this.el;
        },
        _invalid_el: function() {
            return this.el;
        },
        get field_name() {
            return this.attributes.name;
        },
        get model_name() {
            return this.view.screen.model_name;
        },
        get model() {
            return this.view.screen.model;
        },
        get record() {
            return this.view.record;
        },
        get field() {
            var record = this.record;
            if (record) {
                return record.model.fields[this.field_name];
            } else {
                return null;
            }
        },
        focus_out: function() {
            if (!this.field) {
                return;
            }
            if (!this.visible) {
                return;
            }
            this.set_value();
        },
        get_value: function() {
        },
        set_value: function() {
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
        },
        set_required: function(required) {
        },
        get modified() {
            return false;
        },
        send_modified: function() {
            window.setTimeout(() => {
                var value = this.get_value();
                window.setTimeout(() => {
                    if (this.record &&
                        (this.get_value() == value) &&
                        this.modified) {
                        this.view.screen.record_modified(false);
                    }
                }, 300);
            });
        },
        set_invisible: function(invisible) {
            this.visible = !invisible;
            if (invisible) {
                this.el.hide();
            } else {
                this.el.show();
            }
        },
        focus: function() {
            this.el.focus();
        },
    });

    Sao.View.Form.TranslateDialog = Sao.class_(Object,  {
        class_: 'form',
        init: function(languages, widget) {
            var dialog = new Sao.Dialog(
                Sao.i18n.gettext('Translate'), this.class_, 'md');
            this.languages = languages;
            this.read(widget, dialog);
            jQuery('<button/>', {
                'class': 'btn btn-link',
                'type': 'button',
                'title': Sao.i18n.gettext("Cancel"),
            }).text(Sao.i18n.gettext('Cancel')).click(() => {
                this.close(dialog);
            }).appendTo(dialog.footer);
            jQuery('<button/>', {
                'class': 'btn btn-primary',
                'type': 'button',
                'title': Sao.i18n.gettext("OK"),
            }).text(Sao.i18n.gettext('OK')).click(this.write
                    .bind(this, widget, dialog))
                    .appendTo(dialog.footer);
            dialog.content.submit(function(evt) {
                evt.preventDefault();
                dialog.footer.find('button.btn-primary').first().click();
            });
            dialog.modal.modal('show');
            dialog.modal.on('shown.bs.modal', function() {
                dialog.modal.find('input,select')
                    .filter(':visible').first().focus();
            });
            dialog.modal.on('hide.bs.modal', function(){
                jQuery(this).remove();
            });
        },
        close: function(dialog) {
            dialog.modal.modal('hide');
        },
        read: function(widget, dialog) {
            function field_value(result) {
                return result[0][widget.field_name] || '';
            }
            dialog.content.addClass('form-horizontal');
            this.languages.forEach(lang => {
                var row = jQuery('<div/>', {
                    'class':'form-group'
                });
                var input = widget.translate_widget();
                input.attr('data-lang-id', lang.id);
                var edit = jQuery('<button/>', {
                    'type': 'button',
                    'class': 'btn btn-default',
                }).text(Sao.i18n.gettext('Edit'));
                if (widget._readonly) {
                    edit.attr('disabled', true);
                }
                var fuzzy_label = jQuery('<span>', {
                    'class': 'label',
                });
                var prm1 = Sao.rpc({
                    'method': 'model.' + widget.model.name  + '.read',
                    'params': [
                        [widget.record.id],
                        [widget.field_name],
                        {language: lang.code},
                    ],
                }, widget.model.session).then(field_value);
                var prm2 = Sao.rpc({
                    'method': 'model.' + widget.model.name  + '.read',
                    'params': [
                        [widget.record.id],
                        [widget.field_name],
                        {
                            language: lang.code,
                            fuzzy_translation: true,
                        },
                    ],
                }, widget.model.session).then(field_value);

                jQuery.when(prm1, prm2).done(function(value, fuzzy_value) {
                    widget.translate_widget_set(input, fuzzy_value);
                    widget.translate_widget_set_readonly( input, true);
                    if (value !== fuzzy_value) {
                        fuzzy_label.addClass('label-warning');
                        fuzzy_label.text(Sao.i18n.gettext("Fuzzy"));
                    }
                });
                edit.click(function() {
                    jQuery(this).toggleClass('active');
                    widget.translate_widget_set_readonly(
                        input, !jQuery(this).hasClass('active'));
                });
                dialog.body.append(row);
                input.uniqueId();
                row.append(jQuery('<label/>', {
                    'for': input.attr('id'),
                    'class': 'col-sm-3 control-label',
                }).append(' ' + lang.name));
                row.append(jQuery('<div/>', {
                    'class': 'col-sm-9 input-group',
                }).append(input)
                    .append(jQuery('<span/>', {
                        'class': 'input-group-addon',
                    }).append(edit).append(fuzzy_label)));
            });
        },
        write: function(widget, dialog) {
            for (const lang of this.languages) {
                var input = jQuery('[data-lang-id=' + lang.id + ']');
                if (!input.attr('readonly')) {
                    var context = {};
                    context.language = lang.code;
                    context.fuzzy_translation = false;
                    var values =  {};
                    values[widget.field_name] = widget.translate_widget_get(input);
                    var params = [
                        [widget.record.id],
                        values,
                        context
                    ];
                    var args = {
                        'method': 'model.' + widget.model.name  + '.write',
                        'params': params
                    };
                    Sao.rpc(args, widget.model.session, false);
                }
            }
            widget.record.cancel();
            widget.view.display();
            this.close(dialog);
        }
    });

    Sao.View.Form.TranslateMixin = {};
    Sao.View.Form.TranslateMixin.init = function() {
        if (!this.translate) {
            this.translate = Sao.View.Form.TranslateMixin.translate.bind(this);
        }
        if (!this.translate_dialog) {
            this.translate_dialog =
                Sao.View.Form.TranslateMixin.translate_dialog.bind(this);
        }
        if (!this.translate_widget_set_readonly) {
            this.translate_widget_set_readonly =
                Sao.View.Form.TranslateMixin.translate_widget_set_readonly
                    .bind(this);
        }
        if (!this.translate_widget_set) {
            this.translate_widget_set =
                Sao.View.Form.TranslateMixin.translate_widget_set.bind(this);
        }
        if (!this.translate_widget_get) {
            this.translate_widget_get =
                Sao.View.Form.TranslateMixin.translate_widget_get.bind(this);
        }
    };
    Sao.View.Form.TranslateMixin.translate = function() {
        if (this.record.id < 0 || this.record.modified) {
            var mg = Sao.i18n.gettext(
                'You need to save the record before adding translations.');
            Sao.common.message.run(mg);
            return;
        }
        var session = this.model.session;
        var params = [
            [['translatable', '=', true]]
        ];
        var args = {
            'method': 'model.ir.lang.search',
            'params': params.concat({})
        };
        Sao.rpc(args, session).then(lang_ids => {
            if (jQuery.isEmptyObject(lang_ids)) {
                Sao.common.message.run(Sao.i18n.gettext(
                        'No other language available.'));
                return;
            }
            var params = [
                lang_ids,
                ['code', 'name']
            ];
            var args = {
                'method': 'model.ir.lang.read',
                'params': params.concat({})
            };
            Sao.rpc(args, session).then(languages => {
                this.translate_dialog(languages);
            });
        });
    };
    Sao.View.Form.TranslateMixin.translate_dialog = function(languages) {
        new Sao.View.Form.TranslateDialog(languages, this);
    };
    Sao.View.Form.TranslateMixin.translate_widget_set_readonly =
            function(el, value) {
        el.prop('readonly', value);
    };
    Sao.View.Form.TranslateMixin.translate_widget_set = function(el, value) {
        el.val(value);
    };
    Sao.View.Form.TranslateMixin.translate_widget_get = function(el) {
        return el.val();
    };

    Sao.View.Form.Char = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-char',
        init: function(view, attributes) {
            Sao.View.Form.Char._super.init.call(this, view, attributes);
            Sao.View.Form.TranslateMixin.init.call(this);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(this.el);
            this.input = this.labelled = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm mousetrap',
                'name': attributes.name,
            }).appendTo(this.group);
            if (!jQuery.isEmptyObject(attributes.autocomplete)) {
                this.datalist = jQuery('<datalist/>').appendTo(this.el);
                this.datalist.uniqueId();
                this.input.attr('list', this.datalist.attr('id'));
                // workaround for
                // https://bugzilla.mozilla.org/show_bug.cgi?id=1474137
                this.input.attr('autocomplete', 'off');
            }
            this.el.change(this.focus_out.bind(this));
            this.el.on('keydown', this.send_modified.bind(this));

            if (!attributes.size) {
                this.group.css('width', '100%');
            }
            if (this.attributes.translate) {
                Sao.common.ICONFACTORY.get_icon_img('tryton-translate')
                    .appendTo(jQuery('<div/>', {
                        'class': 'icon-input icon-secondary',
                        'aria-label': Sao.i18n.gettext('Translate'),
                        'title': Sao.i18n.gettext('Translate'),
                    }).appendTo(
                        this.group.addClass('input-icon input-icon-secondary')))
                .click(this.translate.bind(this));
            }
        },
        get_client_value: function() {
            var field = this.field;
            var record = this.record;
            var value = '';
            if (field) {
                value = field.get_client(record);
            }
            return value;
        },
        display: function() {
            Sao.View.Form.Char._super.display.call(this);

            var record = this.record;
            if (this.datalist) {
                this.datalist.empty();
                var selection;
                if (record) {
                    if (!(this.field_name in record.autocompletion)) {
                        record.do_autocomplete(this.field_name);
                    }
                    selection = record.autocompletion[this.field_name] || [];
                } else {
                    selection = [];
                }
                for (const e of selection) {
                    jQuery('<option/>', {
                        'value': e
                    }).appendTo(this.datalist);
                }
            }

            // Set size
            var length = '';
            var width = '100%';
            if (record) {
                length = record.expr_eval(this.attributes.size);
                if (length > 0) {
                    width = (length + 5) + 'ch';
                }
            }
            this.input.val(this.get_client_value());
            this.input.attr('maxlength', length);
            this.input.attr('size', length);
            this.group.css('width', width);
        },
        get modified() {
            if (this.record && this.field) {
                var value = this.get_client_value();
                return value != this.get_value();
            }
            return false;
        },
        set_value: function() {
            this.field.set_client(this.record, this.input.val());
        },
        get_value: function() {
            return this.input.val();
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Char._super.set_readonly.call(this, readonly);
            this.input.prop('readonly', readonly);
        },
        focus: function() {
            this.input.focus();
        },
        translate_widget: function() {
            return jQuery('<input/>', {
                'class': 'form-control',
                'readonly': 'readonly',
                'name': this.attributes.name,
            });
        }
    });

    Sao.View.Form.Password = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-password',
        init: function(view, attributes) {
            Sao.View.Form.Password._super.init.call(this, view, attributes);
            this.input.prop('type', 'password');
            this.button = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm form-control',
                'type': 'button'
            }).appendTo(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).appendTo(this.group));
            this._set_password_label();
            this.button.click(this.toggle_visibility.bind(this));

        },
        toggle_visibility: function() {
            if (this.input.prop('type') == 'password') {
                this.input.prop('type', 'text');
                this.input.attr('autocomplete', 'off');
            } else {
                this.input.prop('type', 'password');
                this.input.removeAttr('autocomplete');
            }
            this._set_password_label();
        },
        _set_password_label: function() {
            if (this.input.prop('type') == 'password') {
                this.button.text(Sao.i18n.gettext('Show'));
                this.button.attr('title', Sao.i18n.gettext("Show"));
            } else {
                this.button.text(Sao.i18n.gettext('Hide'));
                this.button.attr('title', Sao.i18n.gettext("Hide"));
            }
        }
    });

    Sao.View.Form.Date = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-date',
        _input: 'date',
        _input_format: '%Y-%m-%d',
        _format: Sao.common.format_date,
        _parse: Sao.common.parse_date,
        init: function(view, attributes) {
            Sao.View.Form.Date._super.init.call(this, view, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            var group = this.labelled = jQuery('<div/>', {
                'class': ('input-group input-group-sm ' +
                    'input-icon input-icon-secondary'),
            }).appendTo(this.el);
            this.date = this.labelled = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm mousetrap',
                'name': attributes.name,
            }).appendTo(group);
            this.date.uniqueId();
            this.date.on('keydown', this.send_modified.bind(this));
            this.input = jQuery('<input/>', {
                'type': this._input,
                'role': 'button',
                'tabindex': -1,
            });
            this.input.click(() => {
                var value = this.get_value();
                value = this._format(this._input_format, value);
                this.input.val(value);
            });
            this.input.change(() => {
                var value = this.input.val();
                if (value) {
                    value = this._parse(this._input_format, value);
                    value = this._format(this.get_format(), value);
                    this.date.val(value).change();
                    if (!~navigator.userAgent.indexOf("Firefox")) {
                        // Firefox triggers change when navigate by month/year
                        this.date.focus();
                    }
                }
                this.send_modified();
            });
            if (this.input[0].type == this._input) {
                this.icon = jQuery('<div/>', {
                    'class': 'icon-input icon-secondary',
                    'aria-label': Sao.i18n.gettext("Open the calendar"),
                    'title': Sao.i18n.gettext("Open the calendar"),
                    'tabindex': -1,
                }).appendTo(group);
                this.input.appendTo(this.icon);
                Sao.common.ICONFACTORY.get_icon_img('tryton-date')
                    .appendTo(this.icon);
            }
            this.date.change(this.focus_out.bind(this));
            var mousetrap = new Mousetrap(this.date[0]);

            mousetrap.bind('enter', (e, combo) => {
                if (!this.date.prop('readonly')) {
                    this.focus_out();
                }
            });
            mousetrap.bind('=', (e, combo) => {
                if (!this.date.prop('readonly')) {
                    e.preventDefault();
                    this.date.val(this._format(this.get_format(), moment()))
                        .change();
                }
            });

            Sao.common.DATE_OPERATORS.forEach(operator => {
                mousetrap.bind(operator[0], (e, combo) => {
                    if (this.date.prop('readonly')) {
                        return;
                    }
                    e.preventDefault();
                    var date = this.get_value() || Sao.DateTime();
                    date.add(operator[1]);
                    this.date.val(this._format(this.get_format(), date))
                        .change();
                });
            });
        },
        get_format: function() {
            if (this.field && this.record) {
                return this.field.date_format(this.record);
            } else {
                return Sao.common.date_format(
                    this.view.screen.context.date_format);
            }
        },
        get_value: function() {
            return this._parse(this.get_format(), this.date.val());
        },
        display: function() {
            var record = this.record;
            var field = this.field;
            Sao.View.Form.Date._super.display.call(this);
            var value;
            if (record) {
                value = field.get_client(record);
            }
            this.date.val(this._format(this.get_format(), value));
        },
        focus: function() {
            this.date.focus();
        },
        get modified() {
            if (this.record && this.field) {
                var field_value = this.cast(
                    this.field.get_client(this.record));
                return (JSON.stringify(field_value) !=
                    JSON.stringify(this.get_value()));
            }
            return false;
        },
        set_value: function() {
            this.field.set_client(this.record, this.get_value());
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Date._super.set_readonly.call(this, readonly);
            this.el.find('input').prop('readonly', readonly);
            if (this.icon){
                if (readonly) {
                    this.icon.hide();
                } else {
                    this.icon.show();
                }
            }
        },
        cast: function(value){
            if (value && value.isDateTime) {
                value = value.todate();
            }
            return value;
        },
    });

    Sao.View.Form.DateTime = Sao.class_(Sao.View.Form.Date, {
        class_: 'form-datetime',
        _input: 'datetime-local',
        _input_format: '%Y-%m-%dT%H:%M:%S',
        _format: Sao.common.format_datetime,
        _parse: Sao.common.parse_datetime,
        get_format: function() {
            if (this.field && this.record) {
                return (this.field.date_format(this.record) + ' ' +
                    this.field.time_format(this.record));
            } else {
                return (Sao.common.date_format(
                    this.view.screen.context.date_format) + ' %X');
            }
        },
        cast: function(value){
            return value;
        },
    });

    Sao.View.Form.Time = Sao.class_(Sao.View.Form.Date, {
        class_: 'form-time',
        _input: 'time',
        _input_format: '%H:%M:%S',
        _format: Sao.common.format_time,
        _parse: Sao.common.parse_time,
        init: function(view, attributes) {
            Sao.View.Form.Time._super.init.call(this, view, attributes);
            if (~navigator.userAgent.indexOf("Firefox")) {
                // time input on Firefox does not have a pop-up
                this.input.parent().hide();
            }
        },
        get_format: function() {
            if (this.field && this.record) {
                return this.field.time_format(this.record);
            } else {
                return '%X';
            }
        },
        cast: function(value){
            if (value && value.isDateTime) {
                value = value.totime();
            }
            return value;
        },
    });

    Sao.View.Form.TimeDelta = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-timedelta',
        init: function(view, attributes) {
            Sao.View.Form.TimeDelta._super.init.call(this, view, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.input = this.labelled = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm mousetrap',
                'name': attributes.name,
            }).appendTo(this.el);
            this.el.change(this.focus_out.bind(this));
            this.el.on('keydown', this.send_modified.bind(this));
        },
        display: function() {
            Sao.View.Form.TimeDelta._super.display.call(this);
            var record = this.record;
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.input.val(value || '');
            } else {
                this.input.val('');
            }
        },
        focus: function() {
            this.input.focus();
        },
        get modified() {
            if (this.record && this.field) {
                var value = this.input.val();
                return this.field.get_client(this.record) != value;
            }
            return false;
        },
        set_value: function() {
            this.field.set_client(this.record, this.input.val());
        },
        set_readonly: function(readonly) {
            Sao.View.Form.TimeDelta._super.set_readonly.call(this, readonly);
            this.input.prop('readonly', readonly);
        }
    });

    var switch_id = function(a, b) {
        var a_id = a.attr('id');
        var a_labelledby = a.attr('aria-labelledby');
        var b_id = b.attr('id');
        var b_labelledby = b.attr('aria-labelledby');
        a.attr('id', b_id);
        a.attr('aria-labelledby', b_labelledby);
        b.attr('id', a_id);
        b.attr('aria-labelledby', a_labelledby);
    };

    var integer_input = function(input) {
        var input_text = input.clone().prependTo(input.parent());
        input_text.attr('type', 'text');
        input.attr('type', 'number');
        input.attr('step', 1);
        input.attr('lang', Sao.i18n.getlang());

        input.hide().on('focusout', function() {
            if (input[0].checkValidity()) {
                switch_id(input, input_text);
                input.hide();
                input_text.show();
            }
        });
        input_text.on('focusin', function() {
            if (!input.prop('readonly')) {
                switch_id(input, input_text);
                input_text.hide();
                input.show();
                window.setTimeout(function() {
                    input.focus();
                });
            }
        });
        return input_text;
    };

    Sao.View.Form.Integer = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-integer',
        init: function(view, attributes) {
            Sao.View.Form.Integer._super.init.call(this, view, attributes);
            this.input_text = this.labelled = integer_input(this.input);
            if (this.attributes.symbol) {
                this.symbol_start = jQuery('<span/>', {
                    'class': 'input-group-addon symbol symbol-start'
                }).prependTo(this.group);
                this.symbol_end = jQuery('<span/>', {
                    'class': 'input-group-addon symbol symbol-end'
                }).appendTo(this.group);
            }
            this.group.css('width', '');
            this.factor = Number(attributes.factor || 1);
            this.grouping = Boolean(Number(attributes.grouping || 1));
        },
        get modified() {
            if (this.record && this.field) {
                var value = this.get_client_value();
                return (JSON.stringify(this.field.convert(value)) !=
                    JSON.stringify(this.field.convert(this.get_value())));
            }
            return false;
        },
        set_value: function() {
            this.field.set_client(
                this.record, this.get_value(), undefined, this.factor);
        },
        get_value: function() {
            return this.input.val();
        },
        get_client_value: function() {
            var value = '';
            var field = this.field;
            if (field) {
                value = field.get(this.record);
                if (value !== null) {
                    value *= this.factor;
                    var digits = field.digits(this.record, this.factor);
                    if (digits) {
                        // Round to avoid float precision error
                        // after the multiplication
                        value = value.toFixed(digits[1]);
                    }
                } else {
                    value = '';
                }
            }
            return value;
        },
        get width() {
            return this.attributes.width || 8;
        },
        display: function() {
            var set_symbol = function(el, text) {
                if (text) {
                    el.text(text);
                    el.show();
                } else {
                    el.text('');
                    el.hide();
                }
            };
            Sao.View.Form.Integer._super.display.call(this);
            var field = this.field,
                record = this.record;
            var value = '';
            if (this.width !== null){
                this.input_text.css('width', this.width + 'ch');
                this.input.css('width', (this.width + 5) + 'ch');
                this.group.css('width', (this.width + 5) + 'ch');
            }
            if (field) {
                value = field.get_client(record, this.factor, this.grouping);
            }
            if (field && this.attributes.symbol) {
                var result = field.get_symbol(record, this.attributes.symbol);
                var symbol = result[0],
                    position = result[1];
                if (position < 0.5) {
                    set_symbol(this.symbol_start, symbol);
                    set_symbol(this.symbol_end, '');
                } else {
                    set_symbol(this.symbol_start, '');
                    set_symbol(this.symbol_end, symbol);
                }
            }
            this.input_text.val(value);
            this.input_text.attr('maxlength', this.input.attr('maxlength'));
            this.input_text.attr('size', this.input.attr('size'));
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Integer._super.set_readonly.call(this, readonly);
            this.input_text.prop('readonly', readonly);
        },
        focus: function() {
            if (!this.input.prop('readonly')) {
                this.input_text.hide();
                this.input.show().focus();
            } else {
                this.input_text.focus();
            }
        }
    });

    Sao.View.Form.Float = Sao.class_(Sao.View.Form.Integer, {
        class_: 'form-float',
        get digits() {
            var record = this.record,
                field = this.field;
            if (record && field) {
                return field.digits(record, this.factor);
            } else {
                return null;
            }
        },
        get width() {
            var digits = this.digits;
            if (digits) {
                return digits.reduce(function(acc, cur) {
                    return acc + cur;
                });
            } else {
                return this.attributes.width || 18;
            }
        },
        display: function() {
            var record = this.record;
            var step = 'any';
            if (record) {
                var digits = this.digits;
                if (digits) {
                    step = Math.pow(10, -digits[1]).toFixed(digits[1]);
                }
            }
            this.input.attr('step', step);
            Sao.View.Form.Float._super.display.call(this);
        }
    });

    Sao.View.Form.Selection = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-selection',
        init: function(view, attributes) {
            Sao.View.Form.Selection._super.init.call(this, view, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.select = this.labelled = jQuery('<select/>', {
                'class': 'form-control input-sm mousetrap',
                'name': attributes.name,
            });
            this.el.append(this.select);
            this.select.change(this.focus_out.bind(this));
            Sao.common.selection_mixin.init.call(this);
            this.init_selection();
        },
        init_selection: function(key) {
            Sao.common.selection_mixin.init_selection.call(this, key,
                this.set_selection.bind(this));
        },
        update_selection: function(record, field, callbak) {
            Sao.common.selection_mixin.update_selection.call(this, record,
                field, (selection, help) => {
                    this.set_selection(selection, help);
                    if (callbak) {
                        callbak(help);
                    }
                });
        },
        set_selection: function(selection, help) {
            var select = this.select;
            select.empty();
            for (const e of selection) {
                select.append(jQuery('<option/>', {
                    'value': JSON.stringify(e[0]),
                    'text': e[1],
                    'title': help[e[0]],
                }));
            }
        },
        display_update_selection: function() {
            var record = this.record;
            var field = this.field;
            this.update_selection(record, field, help => {
                if (!field) {
                    this.select.val('');
                    return;
                }
                var value = field.get(record);
                var prm, found = false;
                for (const option of this.selection) {
                    if (option[0] === value) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    prm = Sao.common.selection_mixin.get_inactive_selection
                        .call(this, value);
                    prm.done(inactive => {
                        this.select.append(jQuery('<option/>', {
                            value: JSON.stringify(inactive[0]),
                            text: inactive[1],
                            disabled: true
                        }));
                    });
                } else {
                    prm = jQuery.when();
                }
                prm.done(() => {
                    this.select.val(JSON.stringify(value));
                    var title = help[value] || null;
                    if (this.attributes.help && title) {
                        title = this.attributes.help + '\n' + title;
                    }
                    this.select.attr('title', title);
                });
            });
        },
        display: function() {
            Sao.View.Form.Selection._super.display.call(this);
            this.display_update_selection();
        },
        focus: function() {
            this.select.focus();
        },
        get_value: function() {
            return JSON.parse(this.select.val());
        },
        get modified() {
            if (this.record && this.field) {
                return this.field.get(this.record) != this.get_value();
            }
            return false;
        },
        set_value: function() {
            var value = this.get_value();
            this.field.set_client(this.record, value);
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Selection._super.set_readonly.call(this, readonly);
            this.select.prop('disabled', readonly);
        }
    });

    Sao.View.Form.Boolean = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-boolean',
        init: function(view, attributes) {
            Sao.View.Form.Boolean._super.init.call(this, view, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.input = this.labelled = jQuery('<input/>', {
                'type': 'checkbox',
                'class': 'form-control input-sm mousetrap',
                'name': attributes.name,
            }).appendTo(this.el);
            this.input.change(this.focus_out.bind(this));
            this.input.click(function() {
                // Dont trigger click if field is readonly as readonly has no
                // effect on checkbox
                return !jQuery(this).prop('readonly');
            });
        },
        display: function() {
            Sao.View.Form.Boolean._super.display.call(this);
            var record = this.record;
            if (record) {
                this.input.prop('checked', record.field_get(this.field_name));
            } else {
                this.input.prop('checked', false);
            }
        },
        focus: function() {
            this.input.focus();
        },
        set_value: function() {
            var value = this.input.prop('checked');
            this.field.set_client(this.record, value);
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Boolean._super.set_readonly.call(this, readonly);
            this.input.prop('readonly', readonly);
        }
    });

    Sao.View.Form.Text = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-text',
        expand: true,
        init: function(view, attributes) {
            Sao.View.Form.Text._super.init.call(this, view, attributes);
            Sao.View.Form.TranslateMixin.init.call(this);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            this.group = jQuery('<div/>', {
                'class': 'input-group',
            }).appendTo(this.el);
            this.input = this.labelled = jQuery('<textarea/>', {
                'class': 'form-control input-sm mousetrap',
                'name': attributes.name,
            }).appendTo(this.group);
            this.input.change(this.focus_out.bind(this));
            this.input.on('keydown', this.send_modified.bind(this));
            if (this.attributes.translate) {
                var button  = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm form-control',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('Translate'),
                    'title': Sao.i18n.gettext("Translate"),
                }).appendTo(jQuery('<span/>', {
                    'class': 'input-group-btn'
                }).appendTo(this.group));
                button.append(
                    Sao.common.ICONFACTORY.get_icon_img('tryton-translate'));
                button.click(this.translate.bind(this));
            }
        },
        display: function() {
            Sao.View.Form.Text._super.display.call(this);
            var record = this.record;
            if (record) {
                var value = record.field_get_client(this.field_name);
                this.input.val(value);
                if(this.attributes.spell) {
                    this.input.attr('lang',
                        Sao.i18n.BC47(record.expr_eval(this.attributes.spell)));
                    this.input.attr('spellcheck', 'true');
                }
            } else {
                this.input.val('');
            }
        },
        focus: function() {
            this.input.focus();
        },
        get modified() {
            if (this.record && this.field) {
                var value = this._normalize_newline(
                    this.field.get_client(this.record));
                return value != this.get_value();
            }
            return false;
        },
        get_value: function() {
            return this._normalize_newline(this.input.val() || '');
        },
        set_value: function() {
            // avoid modification of not normalized value
            var value = this.get_value();
            var prev_value = this.field.get_client(this.record);
            if (value == this._normalize_newline(prev_value)) {
                value = prev_value;
            }
            this.field.set_client(this.record, value);
        },
        _normalize_newline: function(content) {
            return content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Text._super.set_readonly.call(this, readonly);
            this.input.prop('readonly', readonly);
        },
        translate_widget: function() {
            var widget = jQuery('<textarea/>', {
                    'class': 'form-control',
                    'readonly': 'readonly',
                });
            widget.css('min-height', this.el.height());
            return widget;
        }
    });

    Sao.View.Form.RichText = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-richtext',
        expand: true,
        init: function(view, attributes) {
            Sao.View.Form.RichText._super.init.call(this, view, attributes);
            Sao.View.Form.TranslateMixin.init.call(this);
            this.el = jQuery('<div/>', {
                'class': this.class_ + ' panel panel-default'
            });
            if (parseInt(attributes.toolbar || '1', 10)) {
                this.toolbar = Sao.common.richtext_toolbar().appendTo(
                    jQuery('<div/>', {
                        'class': 'panel-heading',
                    }).appendTo(this.el));
            }
            this.group = jQuery('<div/>', {
                'class': 'input-group',
            }).appendTo(jQuery('<div/>', {
                'class': 'panel-body',
            }).appendTo(this.el));
            this.input = this.labelled = jQuery('<div/>', {
                'class': 'richtext mousetrap',
                'contenteditable': true,
            }).appendTo(this.group);
            this.group.focusout(this.focus_out.bind(this));
            if (this.attributes.translate) {
                var button = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm form-control',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext("Translate"),
                    'title': Sao.i18n.gettext("Translate"),
                }).appendTo(jQuery('<span/>', {
                    'class': 'input-group-btn',
                }).appendTo(this.group));
                button.append(
                    Sao.common.ICONFACTORY.get_icon_img('tryton-translate'));
                button.click(this.translate.bind(this));
            }
        },
        focus_out: function() {
            // Let browser set the next focus before testing
            // if it moved out of the widget
            window.setTimeout(() => {
                if (this.el.find(':focus').length === 0) {
                    Sao.View.Form.RichText._super.focus_out.call(this);
                }
            }, 0);
        },
        display: function() {
            Sao.View.Form.RichText._super.display.call(this);
            var value = '';
            var record = this.record;
            if (record) {
                value = record.field_get_client(this.field_name);
                if(this.attributes.spell) {
                    this.input.attr('lang',
                        Sao.i18n.BC47(record.expr_eval(this.attributes.spell)));
                    this.input.attr('spellcheck', 'true');
                }
            }
            this.input.html(Sao.HtmlSanitizer.sanitize(value || ''));
        },
        focus: function() {
            this.input.focus();
        },
        get_value: function() {
            return this._normalize_markup(this.input.html());
        },
        set_value: function() {
            // avoid modification of not normalized value
            var value = this.get_value();
            var prev_value  = this.field.get_client(this.record);
            if (value == this._normalize_markup(prev_value)) {
                value = prev_value;
            }
            this.field.set_client(this.record, value);
        },
        _normalize_markup: function(content) {
            return Sao.common.richtext_normalize(
                Sao.HtmlSanitizer.sanitize(content || ''));
        },
        get modified() {
            if (this.record && this.field) {
                var value = this._normalize_markup(
                    this.field.get_client(this.record));
                return value != this.get_value();
            }
            return false;
        },
        set_readonly: function(readonly) {
            Sao.View.Form.RichText._super.set_readonly.call(this, readonly);
            this.input.prop('contenteditable', !readonly);
            if (this.toolbar) {
                this.toolbar.find('button,input,select')
                    .prop('disabled', readonly);
            }
        },
        translate_widget: function() {
            var widget = jQuery('<div/>', {
                'class': this.class_ + ' panel panel-default',
            });
            if (parseInt(this.attributes.toolbar || '1', 10)) {
                Sao.common.richtext_toolbar().appendTo(
                    jQuery('<div/>', {
                        'class': 'panel-heading',
                    }).appendTo(widget));
            }
            jQuery('<div/>', {
                'class': 'richtext mousetrap',
                'contenteditable': true
            }).appendTo(jQuery('<div/>', {
                'class': 'panel-body'
            }).appendTo(widget));
            return widget;
        },
        translate_widget_set_readonly: function(el, value) {
            Sao.View.Form.TranslateMixin.translate_widget_set_readonly.call(
                this, el, value);
            el.find('button,input,select').prop('disabled', value);
            el.find('div[contenteditable]').prop('contenteditable', !value);
        },
        translate_widget_set: function(el, value) {
            el.find('div[contenteditable]').html(
                Sao.HtmlSanitizer.sanitize(value || ''));
        },
        translate_widget_get: function(el) {
            return this._normalize_markup(
                el.find('div[contenteditable]').html());
        }
    });

    Sao.View.Form.Many2One = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-many2one',
        init: function(view, attributes) {
            Sao.View.Form.Many2One._super.init.call(this, view, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm input-icon'
            }).appendTo(this.el);
            this.entry = this.labelled = jQuery('<input/>', {
                'type': 'input',
                'class': 'form-control input-sm mousetrap',
                'name': attributes.name,
            }).appendTo(group);
            this.but_primary = jQuery('<img/>', {
                'class': 'icon',
            }).appendTo(jQuery('<div/>', {
                'class': 'icon-input icon-primary',
            }).appendTo(group));
            this.but_secondary = jQuery('<img/>', {
                'class': 'icon',
            }).appendTo(jQuery('<div/>', {
                'class': 'icon-input icon-secondary',
            }).appendTo(group));
            this.but_primary.click('primary', this.edit.bind(this));
            this.but_secondary.click('secondary', this.edit.bind(this));

            // Use keydown to not receive focus-in TAB
            this.entry.on('keydown', this.send_modified.bind(this));
            this.entry.on('keydown', this.key_press.bind(this));

            if (!attributes.completion || attributes.completion == "1") {
                this.wid_completion = Sao.common.get_completion(
                    group,
                    this._update_completion.bind(this),
                    this._completion_match_selected.bind(this));
                this.entry.completion = this.wid_completion;
            }
            this.el.change(this.focus_out.bind(this));
            this._readonly = false;
            this._popup = false;
        },
        get_screen: function(search) {
            var domain = this.field.get_domain(this.record);
            var context;
            if (search) {
                context = this.field.get_search_context(this.record);
            } else {
                context = this.field.get_context(this.record);
            }
            var view_ids = (this.attributes.view_ids || '').split(',');
            if (!jQuery.isEmptyObject(view_ids)) {
                // Remove the first tree view as mode is form only
                view_ids.shift();
            }
            var model = this.get_model();
            var breadcrumb = jQuery.extend([], this.view.screen.breadcrumb);
            breadcrumb.push(
                this.attributes.string || Sao.common.MODELNAME.get(model));
            return new Sao.Screen(this.get_model(), {
                'context': context,
                'domain': domain,
                'mode': ['form'],
                'view_ids': view_ids,
                'views_preload': this.attributes.views,
                'readonly': this._readonly,
                exclude_field: this.attributes.relation_field,
                breadcrumb: breadcrumb,
            });
        },
        set_text: function(value) {
            if (jQuery.isEmptyObject(value)) {
                value = '';
            }
            this.entry.val(value);
        },
        get_text: function() {
            var record = this.record;
            if (record) {
                return record.field_get_client(this.field_name);
            }
            return '';
        },
        focus_out: function() {
            if (!this.attributes.completion ||
                    this.attributes.completion == "1") {
                if (this.el.find('.dropdown').hasClass('open')) {
                    return;
                }
            }
            Sao.View.Form.Many2One._super.focus_out.call(this);
        },
        set_value: function() {
            var record = this.record;
            var field = this.field;
            if (field.get_client(record) != this.entry.val()) {
                field.set_client(record, this.value_from_id(null, ''));
                this.entry.val('');
            }
        },
        display: function() {
            var record = this.record;
            var field = this.field;
            var value;
            Sao.View.Form.Many2One._super.display.call(this);

            this._set_button_sensitive();
            this._set_completion();

            if (!record) {
                this.entry.val('');
                return;
            }
            this.set_text(field.get_client(record));
            var primary, tooltip1, secondary, tooltip2;
            value = field.get(record);
            if (this.has_target(value)) {
                primary = 'tryton-open';
                tooltip1 = Sao.i18n.gettext("Open the record");
                secondary = 'tryton-clear';
                tooltip2 = Sao.i18n.gettext("Clear the field");
            } else {
                primary = null;
                tooltip1 = '';
                secondary = 'tryton-search';
                tooltip2 = Sao.i18n.gettext("Search a record");
            }
            if (this.entry.prop('readonly')) {
                secondary = null;
            }
            [
                [primary, tooltip1, this.but_primary, 'primary'],
                [secondary, tooltip2, this.but_secondary, 'secondary']
            ].forEach(function(items) {
                var icon_name = items[0];
                var tooltip = items[1];
                var button = items[2];
                var icon_input = button.parent();
                var type = 'input-icon-' + items[3];
                // don't use .hide/.show because the display value is not
                // correctly restored on modal.
                if (!icon_name) {
                    icon_input.hide();
                    icon_input.parent().removeClass(type);
                } else {
                    icon_input.show();
                    icon_input.parent().addClass(type);
                    Sao.common.ICONFACTORY.get_icon_url(icon_name).then(function(url) {
                        button.attr('src', url);
                    });
                }
                button.attr('aria-label', tooltip);
                button.attr('title', tooltip);
            });
        },
        focus: function() {
            this.entry.focus();
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Many2One._super.set_readonly.call(this, readonly);
            this._readonly = readonly;
            this._set_button_sensitive();
        },
        _set_button_sensitive: function() {
            this.entry.prop('readonly', this._readonly);
            this.but_primary.prop('disabled', !this.read_access);
            this.but_secondary.prop('disabled', this._readonly);
        },
        get_access: function(type) {
            var model = this.get_model();
            if (model) {
                return Sao.common.MODELACCESS.get(model)[type];
            }
            return true;
        },
        get read_access() {
            return this.get_access('read');
        },
        get create_access() {
            var create = this.attributes.create;
            if (create === undefined) {
                create = true;
            } else if (typeof create == 'string') {
                create = Boolean(parseInt(create, 10));
            }
            return create && this.get_access('create');
        },
        get modified() {
            if (this.record && this.field) {
                var value = this.entry.val();
                return this.field.get_client(this.record) != value;
            }
            return false;
        },
        id_from_value: function(value) {
            return value;
        },
        value_from_id: function(id, str='') {
            return [id, str];
        },
        get_model: function() {
            return this.attributes.relation;
        },
        has_target: function(value=null) {
            return value !== null;
        },
        edit: function(evt) {
            var model = this.get_model();
            if (!model || !Sao.common.MODELACCESS.get(model).read) {
                return;
            }
            var record = this.record;
            var value = record.field_get(this.field_name);

            if ((evt && evt.data == 'secondary') &&
                    !this._readonly &&
                    this.has_target(value)) {
                this.record.field_set_client(this.field_name,
                        this.value_from_id(null, ''));
                this.entry.val('');
                this.focus();
                return;
            }
            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }
            if (this.has_target(value)) {
                var m2o_id =
                    this.id_from_value(record.field_get(this.field_name));
                if (evt && (evt.ctrlKey || evt.metaKey)) {
                    var params = {};
                    params.model = this.get_model();
                    params.res_id = m2o_id;
                    params.mode = ['form'];
                    params.name = this.attributes.string;
                    params.context = this.field.get_context(this.record);
                    Sao.Tab.create(params);
                    this._popup = false;
                    return;
                }
                var screen = this.get_screen();
                let callback = result => {
                    if (result) {
                        var rec_name_prm = screen.current_record.rec_name();
                        rec_name_prm.done(name => {
                            var value = this.value_from_id(
                                screen.current_record.id, name);
                            this.record.field_set_client(this.field_name,
                                value, true);
                        });
                    }
                    this._popup = false;
                };
                screen.switch_view().done(() => {
                    screen.load([m2o_id]);
                    screen.current_record = screen.group.get(m2o_id);
                    new Sao.Window.Form(screen, callback, {
                        save_current: true,
                    });
                });
                return;
            }
            if (model) {
                var domain = this.field.get_domain(record);
                var context = this.field.get_search_context(record);
                var order = this.field.get_search_order(record);
                var text = this.entry.val();
                let callback = result => {
                    if (!jQuery.isEmptyObject(result)) {
                        var value = this.value_from_id(result[0][0],
                                result[0][1]);
                        this.record.field_set_client(this.field_name,
                                value, true);
                    }
                    this._popup = false;
                };
                var parser = new Sao.common.DomainParser();
                new Sao.Window.Search(
                    model, callback, {
                            sel_multi: false,
                            context: context,
                            domain: domain,
                            order: order,
                            view_ids: (this.attributes.view_ids ||
                                '').split(','),
                            views_preload: (this.attributes.views || {}),
                            new_: this.create_access,
                            search_filter: parser.quote(text),
                            title: this.attributes.string,
                            exclude_field: this.attributes.relation_field,
                        });
                return;
            }
            this._popup = false;
        },
        new_: function(defaults=null) {
            var model = this.get_model();
            if (!model || ! Sao.common.MODELACCESS.get(model).create) {
                return;
            }
            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }
            var screen = this.get_screen(true);
            if (defaults) {
                defaults = jQuery.extend({}, defaults);
            } else {
                defaults = {};
            }
            defaults.rec_name = this.entry.val();

            const callback = result => {
                if (result) {
                    var rec_name_prm = screen.current_record.rec_name();
                    rec_name_prm.done(name => {
                        var value = this.value_from_id(
                            screen.current_record.id, name);
                        this.record.field_set_client(this.field_name, value);
                    });
                }
                this._popup = false;
            };
            screen.switch_view().done(() => {
                new Sao.Window.Form(screen, callback, {
                    new_: true,
                    save_current: true,
                    defaults: defaults,
                });
            });
        },
        key_press: function(event_) {
            var editable = !this.entry.prop('readonly');
            var activate_keys = [Sao.common.TAB_KEYCODE];
            var delete_keys = [Sao.common.BACKSPACE_KEYCODE,
                Sao.common.DELETE_KEYCODE];
            if (!this.wid_completion) {
                activate_keys.push(Sao.common.RETURN_KEYCODE);
            }

            if (event_.which == Sao.common.F3_KEYCODE &&
                    editable &&
                    this.create_access) {
                event_.preventDefault();
                this.new_();
            } else if (event_.which == Sao.common.F2_KEYCODE &&
                    this.read_access) {
                event_.preventDefault();
                this.edit();
            } else if (~activate_keys.indexOf(event_.which) && editable) {
                if (!this.attributes.completion ||
                        this.attributes.completion == "1") {
                    if (this.el.find('.dropdown').hasClass('open')) {
                        return;
                    }
                }
                this.activate();
            } else if (this.has_target(this.record.field_get(
                            this.field_name)) && editable) {
                var value = this.get_text();
                if ((value != this.entry.val()) ||
                        ~delete_keys.indexOf(event_.which)) {
                    this.entry.val('');
                    this.record.field_set_client(this.field_name,
                        this.value_from_id(null, ''));
                }
            }
        },
        activate: function() {
            var model = this.get_model();
            if (!model || !Sao.common.MODELACCESS.get(model).read) {
                return;
            }
            var record = this.record;
            var value = record.field_get(this.field_name);

            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }
            if (model && !this.has_target(value)) {
                var text = this.entry.val();
                if (!this._readonly && (text ||
                            this.field.get_state_attrs(this.record)
                            .required)) {
                    var domain = this.field.get_domain(record);
                    var context = this.field.get_search_context(record);
                    var order = this.field.get_search_order(record);

                    const callback = result => {
                        if (!jQuery.isEmptyObject(result)) {
                            var value = this.value_from_id(result[0][0],
                                result[0][1]);
                            this.record.field_set_client(this.field_name,
                                value, true);
                        } else {
                            this.entry.val('');
                        }
                        this._popup = false;
                    };
                    var parser = new Sao.common.DomainParser();
                    new Sao.Window.Search(
                        model, callback, {
                                sel_multi: false,
                                context: context,
                                domain: domain,
                                order: order,
                                view_ids: (this.attributes.view_ids ||
                                    '').split(','),
                                views_preload: (this.attributes.views ||
                                    {}),
                                new_: this.create_access,
                                search_filter: parser.quote(text),
                                title: this.attributes.string,
                                exclude_field: this.attributes.relation_field,
                            });
                    return;
                }
            }
            this._popup = false;
        },
        _set_completion: function() {
            if (this.wid_completion) {
                this.wid_completion.set_actions(
                    this._completion_action_activated.bind(this),
                    this.read_access, this.create_access);
            }
        },
        _update_completion: function(text) {
            var record = this.record;
            if (!record) {
                return jQuery.when();
            }
            var field = this.field;
            var value = field.get(record);
            if (this.has_target(value)) {
                var id = this.id_from_value(value);
                if ((id !== undefined) && (id >= 0)) {
                    return jQuery.when();
                }
            }
            var model = this.get_model();

            return Sao.common.update_completion(
                    this.entry, record, field, model);
        },
        _completion_match_selected: function(value) {
            if (value.id !== null) {
                this.record.field_set_client(this.field_name,
                    this.value_from_id(
                        value.id, value.rec_name), true);
            } else {
                this.new_(value.defaults);
            }
        },
        _completion_action_activated: function(action) {
            if (action == 'search') {
                this.edit();
            } else if (action == 'create') {
                this.new_();
            }
        }
    });

    Sao.View.Form.One2One = Sao.class_(Sao.View.Form.Many2One, {
        class_: 'form-one2one'
    });

    Sao.View.Form.Reference = Sao.class_(Sao.View.Form.Many2One, {
        class_: 'form-reference',
        init: function(view, attributes) {
            Sao.View.Form.Reference._super.init.call(this, view, attributes);
            this.el.addClass('form-inline');
            this.select = jQuery('<select/>', {
                'class': 'form-control input-sm',
                'aria-label': attributes.string,
                'title': attributes.string,
            });
            this.el.prepend(this.select);
            this.select.change(this.select_changed.bind(this));
            Sao.common.selection_mixin.init.call(this);
            this.init_selection();
        },
        init_selection: function(key) {
            Sao.common.selection_mixin.init_selection.call(this, key,
                this.set_selection.bind(this));
        },
        update_selection: function(record, field, callback) {
            Sao.common.selection_mixin.update_selection.call(this, record,
                field, (selection, help) => {
                    this.set_selection(selection, help);
                    if (callback) {
                        callback();
                    }
                });
        },
        set_selection: function(selection, help) {
            var select = this.select;
            select.empty();
            for (const e of selection) {
                select.append(jQuery('<option/>', {
                    'value': e[0],
                    'text': e[1],
                    'title': help[e[0]],
                }));
            }
        },
        get modified() {
            if (this.record && this.field) {
                var value = this.field.get_client(this.record);
                var model = '',
                    name = '';
                if (value) {
                    model = value[0];
                    name = value[1];
                }
                return ((model != this.get_model()) ||
                    (name != this.entry.val()));
            }
            return false;
        },
        id_from_value: function(value) {
            return parseInt(value.split(',')[1], 10);
        },
        value_from_id: function(id, str) {
            if (!str) {
                str = '';
            }
            return [this.get_model(), [id, str]];
        },
        get_text: function() {
            var record = this.record;
            if (record) {
                return record.field_get_client(this.field_name)[1];
            }
            return '';
        },
        get_model: function() {
            return this.select.val();
        },
        has_target: function(value) {
            if (value === null) {
                return false;
            }
            var model = value.split(',')[0];
            value = value.split(',')[1];
            if (jQuery.isEmptyObject(value)) {
                value = null;
            } else {
                value = parseInt(value, 10);
                if (isNaN(value)) {
                    value = null;
                }
            }
            return (model == this.get_model()) && (value >= 0);
        },
        _set_button_sensitive: function() {
            Sao.View.Form.Reference._super._set_button_sensitive.call(this);
            this.select.prop('disabled', this.entry.prop('readonly'));
        },
        select_changed: function() {
            this.entry.val('');
            var model = this.get_model();
            var value;
            if (model) {
                value = [model, [-1, '']];
            } else {
                value = ['', ''];
            }
            this.record.field_set_client(this.field_name, value);
        },
        set_value: function() {
            var value;
            var record = this.record;
            var field = this.field;
            if (!this.get_model()) {
                value = this.entry.val();
                if (jQuery.isEmptyObject(value)) {
                    field.set_client(record, null);
                } else {
                    field.set_client(record, ['', value]);
                }
            } else {
                value = field.get_client(record, this.field_name);
                var model, name;
                if (value instanceof Array) {
                    model = value[0];
                    name = value[1];
                } else {
                    model = '';
                    name = '';
                }
                if ((model != this.get_model()) ||
                        (name != this.entry.val())) {
                    field.set_client(record, null);
                    this.entry.val('');
                }
            }
        },
        set_text: function(value) {
            var model;
            if (value) {
                model = value[0];
                value = value[1];
            } else {
                model = null;
                value = null;
            }
            Sao.View.Form.Reference._super.set_text.call(this, value);
            if (model) {
                this.select.val(model);
            } else {
                this.select.val('');
            }
        },
        display: function() {
            this.update_selection(this.record, this.field, () => {
                Sao.View.Form.Reference._super.display.call(this);
            });
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Reference._super.set_readonly.call(this, readonly);
            this.select.prop('disabled', readonly);
        }
    });

    Sao.View.Form.One2Many = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-one2many',
        expand: true,
        init: function(view, attributes) {
            Sao.View.Form.One2Many._super.init.call(this, view, attributes);

            this._readonly = true;
            this._required = false;
            this._position = 0;
            this._length = 0;

            this.el = jQuery('<div/>', {
                'class': this.class_ + ' panel panel-default'
            });
            this.menu = jQuery('<div/>', {
                'class': this.class_ + '-menu panel-heading'
            });
            this.el.append(this.menu);

            this.title = jQuery('<label/>', {
                'class': this.class_ + '-string',
                text: attributes.string
            });
            this.menu.append(this.title);

            this.title.uniqueId();
            this.el.uniqueId();
            this.el.attr('aria-labelledby', this.title.attr('id'));
            this.title.attr('for', this.el.attr('id'));

            var toolbar = jQuery('<div/>', {
                'class': this.class_ + '-toolbar'
            });
            this.menu.append(toolbar);

            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(toolbar);

            var buttons = jQuery('<div/>', {
                'class': 'input-group-btn'
            }).appendTo(group);

            var disable_during = function(callback) {
                return function(evt) {
                    var button = jQuery(evt.target);
                    button.prop('disabled', true);
                    (callback(evt) || jQuery.when())
                        .always(function() {
                            button.prop('disabled', false);
                        });
                };
            };

            this.but_switch = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Switch"),
                'title': Sao.i18n.gettext("Switch"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-switch')
            ).appendTo(buttons);
            this.but_switch.click(disable_during(this.switch_.bind(this)));

            this.but_previous = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Previous"),
                'title': Sao.i18n.gettext("Previous"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-back')
            ).appendTo(buttons);
            this.but_previous.click(disable_during(this.previous.bind(this)));

            this.label = jQuery('<span/>', {
                'class': 'badge',
            }).text('_ / 0'
            ).appendTo(jQuery('<span/>', {
                'class': 'btn hidden-xs',
            }).appendTo(buttons));

            this.but_next = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Next"),
                'title': Sao.i18n.gettext("Next"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-forward')
            ).appendTo(buttons);
            this.but_next.click(disable_during(this.next.bind(this)));

            if (attributes.add_remove) {
                this.wid_text = jQuery('<input/>', {
                    type: 'text',
                    'class': 'form-control input-sm',
                    'name': attributes.name,
                }).appendTo(group);

                if (!attributes.completion || attributes.completion == '1') {
                    this.wid_completion = Sao.common.get_completion(
                        this.wid_text,
                        this._update_completion.bind(this),
                        this._completion_match_selected.bind(this),
                        this._completion_action_activated.bind(this),
                        this.read_access, this.create_access);
                    this.wid_text.completion = this.wid_completion;
                }

                buttons =  jQuery('<div/>', {
                    'class': 'input-group-btn',
                }).appendTo(group);

                this.but_add = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'tabindex': -1,
                    'aria-label': Sao.i18n.gettext("Add"),
                    'title': Sao.i18n.gettext("Add"),
                }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-add')
                ).appendTo(buttons);
                this.but_add.click(disable_during(this.add.bind(this)));

                this.but_remove = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'tabindex': -1,
                    'aria-label': Sao.i18n.gettext("Remove"),
                    'title': Sao.i18n.gettext("Remove"),
                }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-remove')
                ).appendTo(buttons);
                this.but_remove.click(disable_during(this.remove.bind(this)));
            }

            this.but_new = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("New"),
                'title': Sao.i18n.gettext("New"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-create')
            ).appendTo(buttons);
            this.but_new.click(disable_during(() => this.new_()));

            this.but_open = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Open"),
                'title': Sao.i18n.gettext("Open"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-open')
            ).appendTo(buttons);
            this.but_open.click(disable_during(this.open.bind(this)));

            this.but_del = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Delete"),
                'title': Sao.i18n.gettext("Delete"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-delete')
            ).appendTo(buttons);
            this.but_del.click(disable_during(this.delete_.bind(this)));

            this.but_undel = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Undelete"),
                'title': Sao.i18n.gettext("Undelete"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-undo')
            ).appendTo(buttons);
            this.but_undel.click(disable_during(this.undelete.bind(this)));

            this.content = jQuery('<div/>', {
                'class': this.class_ + '-content panel-body'
            });
            this.el.append(this.content);

            var modes = (attributes.mode || 'tree,form').split(',');
            var model = attributes.relation;
            var breadcrumb = jQuery.extend([], this.view.screen.breadcrumb);
            breadcrumb.push(
                attributes.string || Sao.common.MODELNAME.get(model));
            this.screen = new Sao.Screen(model, {
                mode: modes,
                view_ids: (attributes.view_ids || '').split(','),
                views_preload: attributes.views || {},
                order: attributes.order,
                row_activate: this.activate.bind(this),
                exclude_field: attributes.relation_field || null,
                limit: null,
                context: this.view.screen.context,
                pre_validate: attributes.pre_validate,
                breadcrumb: breadcrumb,
            });
            this.screen.pre_validate = attributes.pre_validate == 1;

            this.screen.windows.push(this);
            this.prm = this.screen.switch_view().done(() => {
                this.content.append(this.screen.screen_container.el);
            });

            if (attributes.add_remove) {
                // Use keydown to not receive focus-in TAB
                this.wid_text.on('keydown', this.key_press.bind(this));
            }

            this._popup = false;
        },
        get_access: function(type) {
            var model = this.attributes.relation;
            if (model) {
                return Sao.common.MODELACCESS.get(model)[type];
            }
            return true;
        },
        get read_access() {
            return this.get_access('read');
        },
        get create_access() {
            var create = this.attributes.create;
            if (create === undefined) {
                create = true;
            } else if (typeof create == 'string') {
                create = Boolean(parseInt(create, 10));
            }
            return create && this.get_access('create');
        },
        get write_access() {
            return this.get_access('write');
        },
        get delete_access() {
            var delete_ = this.attributes.delete;
            if (delete_ === undefined) {
                delete_ = true;
            } else if (typeof delete_ == 'string') {
                delete_ = Boolean(parseInt(delete_, 10));
            }
            return delete_ && this.get_access('delete');
        },
        get modified() {
            return this.screen.current_view.modified;
        },
        set_readonly: function(readonly) {
            Sao.View.Form.One2Many._super.set_readonly.call(this, readonly);
            this.prm.done(() => this._set_button_sensitive());
            this._set_label_state();
        },
        set_required: function(required) {
            this._required = required;
            this._set_label_state();
        },
        _set_label_state: function() {
            Sao.common.apply_label_attributes(this.title, this._readonly,
                    this._required);
        },
        _set_button_sensitive: function() {
            var size_limit, o2m_size;
            var record = this.record;
            var field = this.field;
            if (record && field) {
                var field_size = record.expr_eval(this.attributes.size);
                o2m_size = field.get_eval(record).length;
                size_limit = (((field_size !== undefined) &&
                            (field_size !== null)) &&
                        (o2m_size >= field_size) && (field_size >= 0));
            } else {
                o2m_size = null;
                size_limit = false;
            }
            var deletable = this.screen.deletable;
            const view_type = this.screen.current_view.view_type;
            const has_views = this.screen.number_of_views > 1;

            this.but_switch.prop(
                'disabled',
                !((this._position || (view_type == 'form')) && has_views));
            this.but_new.prop(
                'disabled',
                this._readonly ||
                !this.create_access ||
                size_limit);
            this.but_del.prop(
                'disabled',
                this._readonly ||
                !this.delete_access ||
                !this._position ||
                !deletable);
            this.but_undel.prop(
                'disabled',
                this._readonly ||
                size_limit ||
                !this._position);
            this.but_open.prop(
                'disabled',
                !this._position ||
                !this.read_access);
            this.but_next.prop(
                'disabled',
                (this.position > 0) &&
                ( this._position >= this._length));
            this.but_previous.prop(
                'disabled',
                this._position <= 1);
            if (this.attributes.add_remove) {
                this.but_add.prop(
                    'disabled',
                    this._readonly ||
                    size_limit ||
                    !this.write_access ||
                    !this.read_access);
                this.wid_text.prop('disabled', this.but_add.prop('disabled'));
                this.but_remove.prop(
                    'disabled',
                    this._readonly ||
                    !this.position ||
                    !this.write_access ||
                    !this.read_access);
            }
        },
        _sequence: function() {
            for (const view of this.screen.views) {
                if (view.view_type == 'tree') {
                    const sequence = view.attributes.sequence;
                    if (sequence) {
                        return sequence;
                    }
                }
            }
        },
        display: function() {
            Sao.View.Form.One2Many._super.display.call(this);

            this.prm.done(() => {
                this._set_button_sensitive();

                var record = this.record;
                var field = this.field;

                if (!field) {
                    this.screen.new_group();
                    this.screen.current_record = null;
                    this.screen.group.parent = null;
                    this.screen.display();
                    return;
                }

                var new_group = record.field_get_client(this.field_name);
                if (new_group != this.screen.group) {
                    this.screen.set_group(new_group);
                    if ((this.screen.current_view.view_type == 'form') &&
                        this.screen.group.length) {
                        this.screen.current_record = this.screen.group[0];
                    }
                }
                var domain = [];
                var size_limit = null;
                if (record) {
                    domain = field.get_domain(record);
                    size_limit = record.expr_eval(this.attributes.size);
                }
                if (this._readonly || !this.create_access) {
                    if ((size_limit === null) || (size_limit === undefined)) {
                        size_limit = this.screen.group.length;
                    } else {
                        size_limit = Math.min(
                                size_limit, this.screen.group.length);
                    }
                }
                if (!Sao.common.compare(this.screen.domain, domain)) {
                    this.screen.domain = domain;
                }
                this.screen.size_limit = size_limit;
                this.screen.display();
                if (this.attributes.height !== undefined) {
                    this.screen.current_view.el
                        .find('.treeview,.list-form').first()
                        .css('min-height', this.attributes.height + 'px')
                        .css('max-height', this.attributes.height + 'px');
                }
            });
        },
        focus: function() {
            if (this.attributes.add_remove) {
                this.wid_text.focus();
            }
        },
        activate: function(event_) {
            this.edit();
        },
        add: function(event_) {
            if (!this.write_access || !this.read_access) {
                return;
            }
            this.view.set_value();
            var domain = this.field.get_domain(this.record);
            var context = this.field.get_search_context(this.record);
            domain = [domain,
                this.record.expr_eval(this.attributes.add_remove)];
            var removed_ids = this.field.get_removed_ids(this.record);
            domain = ['OR', domain, ['id', 'in', removed_ids]];
            var text = this.wid_text.val();

            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }

            var sequence = this._sequence();

            const callback = result => {
                var prm = jQuery.when();
                if (!jQuery.isEmptyObject(result)) {
                    var ids = [];
                    var i, len;
                    for (i = 0, len = result.length; i < len; i++) {
                        ids.push(result[i][0]);
                    }
                    this.screen.group.load(ids, true, -1, null);
                    prm = this.screen.display();
                    if (sequence) {
                        this.screen.group.set_sequence(
                            sequence, this.screen.new_position);
                    }
                }
                prm.done(() => {
                    this.screen.set_cursor();
                });
                this.wid_text.val('');
                this._popup = false;
            };
            var parser = new Sao.common.DomainParser();
            var order = this.field.get_search_order(this.record);
            new Sao.Window.Search(this.attributes.relation,
                    callback, {
                        sel_multi: true,
                        context: context,
                        domain: domain,
                        order: order,
                        view_ids: (this.attributes.view_ids ||
                                '').split(','),
                        views_preload: this.attributes.views || {},
                        new_: !this.but_new.prop('disabled'),
                        search_filter: parser.quote(text),
                        title: this.attributes.string,
                        exclude_field: this.attributes.relation_field,
                    });
        },
        remove: function(event_) {
            var writable = !this.screen.readonly;
            if (!this.write_access || !this.read_access || !writable) {
                return;
            }
            this.screen.remove(false, true, false);
        },
        new_: function(defaults=null) {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).create) {
                return;
            }
            if (this.attributes.add_remove) {
                if (defaults) {
                    defaults = jQuery.extend({}, defaults);
                } else {
                    defaults = {};
                }
                defaults.rec_name = this.wid_text.val();
            }
            this.validate().done(() => {
                if (this.attributes.product) {
                    this.new_product(defaults);
                } else {
                    this.new_single(defaults);
                }
            });
        },
        new_single: function(defaults=null) {
            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }
            var sequence = this._sequence();
            const update_sequence = () => {
                if (sequence) {
                    this.screen.group.set_sequence(
                        sequence, this.screen.new_position);
                }
                this._popup = false;
            };
            if (this.screen.current_view.creatable) {
                this.screen.new_().then(update_sequence);
                this.screen.current_view.el.prop('disabled', false);
            } else {
                var record = this.record;
                var field_size = record.expr_eval(
                    this.attributes.size) || -1;
                field_size -= this.field.get_eval(record).length;
                new Sao.Window.Form(this.screen, update_sequence, {
                    new_: true,
                    defaults: defaults,
                    many: field_size,
                });
            }
        },
        new_product: function(defaults=null) {
            var fields = this.attributes.product.split(',');
            var product = {};
            var screen = this.screen;

            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }

            screen.new_(false).then(first => {
                first.default_get(defaults).then(default_ => {
                    first.set_default(default_);

                    const search_set = () => {
                        if (jQuery.isEmptyObject(fields)) {
                            return make_product();
                        }
                        var field = screen.model.fields[fields.pop()];
                        var relation = field.description.relation;
                        if (!relation) {
                            search_set();
                        }

                        var domain = field.get_domain(first);
                        var context = field.get_search_context(first);
                        var order = field.get_search_order(first);

                        var callback = function(result) {
                            if (!jQuery.isEmptyObject(result)) {
                                product[field.name] = result;
                            }
                            search_set();
                        };
                        new Sao.Window.Search(relation,
                                callback, {
                                    sel_multi: true,
                                    context: context,
                                    domain: domain,
                                    order: order,
                                    search_filter: '',
                                    title: this.attributes.string

                        });
                    };

                    const make_product = () => {
                        this._popup = false;
                        screen.group.remove(first, true);
                        if (jQuery.isEmptyObject(product)) {
                            return;
                        }

                        var fields = Object.keys(product);
                        var values = fields.map(function(field) {
                            return product[field];
                        });
                        Sao.common.product(values).forEach(function(values) {
                            screen.new_(false).then(function(record) {
                                var default_value = jQuery.extend({}, default_);
                                fields.forEach(function(field, i) {
                                    default_value[field] = values[i][0];
                                    default_value[field + '.rec_name'] = values[i][1];
                                });
                                record.set_default(default_value);
                            });
                        });
                        var sequence = this._sequence();
                        if (sequence) {
                            screen.group.set_sequence(
                                sequence, screen.new_position);
                        }
                    };

                    search_set();
                });
            });
        },
        open: function(event_) {
            return this.edit();
        },
        delete_: function(event_) {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name)['delete'] ||
                !this.screen.deletable) {
                return;
            }
            this.screen.remove(false, false, false);
        },
        undelete: function(event_) {
            this.screen.unremove();
        },
        previous: function(event_) {
            return this.validate().then(() => this.screen.display_previous());
        },
        next: function(event_) {
            return this.validate().then(() => this.screen.display_next());
        },
        switch_: function(event_) {
            return this.screen.switch_view();
        },
        edit: function() {
            if (!Sao.common.MODELACCESS.get(this.screen.model_name).read) {
                return;
            }
            return this.validate().then(() => {
                var record = this.screen.current_record;
                if (record) {
                    if (this._popup) {
                        return;
                    } else {
                        this._popup = true;
                    }
                    new Sao.Window.Form(this.screen, () => {
                        this._popup = false;
                    });
                }
            });
        },
        key_press: function(event_) {
            if (event_.which == Sao.common.F3_KEYCODE) {
                event_.preventDefault();
                this.new_();
            } else if (event_.which ==  Sao.common.F2_KEYCODE) {
                event_.preventDefault();
                this.add(event_);
            }
            if (this.attributes.add_remove) {
                var activate_keys = [Sao.common.TAB_KEYCODE];
                if (!this.wid_completion) {
                    activate_keys.push(Sao.common.RETURN_KEYCODE);
                }
                if (~activate_keys.indexOf(event_.which) && this.wid_text.val()) {
                    this.add(event_);
                }
            }
        },
        record_message: function(position, size) {
            this._position = position;
            this._length = size;
            var name = "_";
            if (position) {
                var selected = this.screen.selected_records.length;
                name = ' ' + position;
                if (selected > 1) {
                    name += '#' + selected;
                }
            }
            var message = name + ' / ' + Sao.common.humanize(size);
            this.label.text(message).attr('title', message);
            this.prm.done(() => this._set_button_sensitive());
        },
        validate: function() {
            var prm = jQuery.Deferred();
            this.view.set_value();
            var record = this.screen.current_record;
            if (record) {
                var fields = this.screen.current_view.get_fields();
                record.validate(fields).then(validate => {
                    if (!validate) {
                        this.screen.display(true);
                        prm.reject();
                        return;
                    }
                    if (this.screen.pre_validate) {
                        return record.pre_validate().then(
                            prm.resolve, prm.reject);
                    }
                    prm.resolve();
                });
            } else {
                prm.resolve();
            }
            return prm;
        },
        set_value: function() {
            this.screen.save_tree_state();
            if (this.screen.modified()) {  // TODO check if required
                this.view.screen.record_modified(false);
            }
        },
        _update_completion: function(text) {
            if (!this.record) {
                return jQuery.when();
            }
            var model = this.attributes.relation;
            var domain = this.field.get_domain(this.record);
            domain = [domain,
                this.record.expr_eval(this.attributes.add_remove)];
            var removed_ids = this.field.get_removed_ids(this.record);
            domain = ['OR', domain, ['id', 'in', removed_ids]];
            return Sao.common.update_completion(
                this.wid_text, this.record, this.field, model, domain);
        },
        _completion_match_selected: function(value) {
            if (value.id !== null) {
                this.screen.group.load([value.id], true);
                this.wid_text.val('');
            } else {
                this.new_(value.defaults);
            }
        },
        _completion_action_activated: function(action) {
            if (action == 'search') {
                this.add();
            } else if (action == 'create') {
                this.new_();
            }
        },
    });

    Sao.View.Form.Many2Many = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-many2many',
        expand: true,
        init: function(view, attributes) {
            Sao.View.Form.Many2Many._super.init.call(this, view, attributes);

            this._readonly = true;
            this._required = false;
            this._position = 0;

            this.el = jQuery('<div/>', {
                'class': this.class_ + ' panel panel-default'
            });
            this.menu = jQuery('<div/>', {
                'class': this.class_ + '-menu panel-heading'
            });
            this.el.append(this.menu);

            this.title = jQuery('<label/>', {
                'class': this.class_ + '-string',
                text: attributes.string
            });
            this.menu.append(this.title);

            this.title.uniqueId();
            this.el.uniqueId();
            this.el.attr('aria-labelledby', this.title.attr('id'));
            this.title.attr('for', this.el.attr('id'));

            var toolbar = jQuery('<div/>', {
                'class': this.class_ + '-toolbar'
            });
            this.menu.append(toolbar);

            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(toolbar);
            this.entry = jQuery('<input/>', {
                type: 'text',
                'class': 'form-control input-sm mousetrap',
                'name': attributes.name,
            }).appendTo(group);
            // Use keydown to not receive focus-in TAB
            this.entry.on('keydown', this.key_press.bind(this));

            if (!attributes.completion || attributes.completion == '1') {
                this.wid_completion = Sao.common.get_completion(
                    group,
                    this._update_completion.bind(this),
                    this._completion_match_selected.bind(this),
                    this._completion_action_activated.bind(this),
                    this.read_access, this.create_access);
                this.entry.completion = this.wid_completion;
            }

            var buttons = jQuery('<div/>', {
                'class': 'input-group-btn'
            }).appendTo(group);
            this.but_add = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Add"),
                'title': Sao.i18n.gettext("Add"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-add')
            ).appendTo(buttons);
            this.but_add.click(this.add.bind(this));

            this.label = jQuery('<span/>', {
                'class': 'badge',
            }).text('_ / 0'
            ).appendTo(jQuery('<span/>', {
                'class': 'btn hidden-xs',
            }).appendTo(buttons));

            this.but_remove = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'tabindex': -1,
                'aria-label': Sao.i18n.gettext("Remove"),
                'title': Sao.i18n.gettext("Remove"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-remove')
            ).appendTo(buttons);
            this.but_remove.click(this.remove.bind(this));

            this.content = jQuery('<div/>', {
                'class': this.class_ + '-content panel-body'
            });
            this.el.append(this.content);
            var model = attributes.relation;
            var breadcrumb = jQuery.extend([], this.view.screen.breadcrumb);
            breadcrumb.push(attributes.string || Sao.common.MODELNAME.get(model));
            this.screen = new Sao.Screen(attributes.relation, {
                mode: ['tree'],
                view_ids: (attributes.view_ids || '').split(','),
                views_preload: attributes.views || {},
                order: attributes.order,
                row_activate: this.activate.bind(this),
                readonly: true,
                limit: null,
                context: this.view.screen.context,
                breadcrumb: breadcrumb,
            });
            this.screen.windows.push(this);
            this.prm = this.screen.switch_view('tree').done(() => {
                this.content.append(this.screen.screen_container.el);
            });
            this._popup = false;
        },
        get_access: function(type) {
            var model = this.attributes.relation;
            if (model) {
                return Sao.common.MODELACCESS.get(model)[type];
            }
            return true;
        },
        get read_access() {
            return this.get_access('read');
        },
        get create_access() {
            var create = this.attributes.create;
            if (create === undefined) {
                create = true;
            } else if (typeof create == 'string') {
                create = Boolean(parseInt(create, 10));
            }
            return create && this.get_access('create');
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Many2Many._super.set_readonly.call(this, readonly);
            this._set_button_sensitive();
            this._set_label_state();
        },
        set_required: function(required) {
            this._required = required;
            this._set_label_state();
        },
        _set_label_state: function() {
            Sao.common.apply_label_attributes(this.title, this._readonly,
                    this._required);
        },
        _set_button_sensitive: function() {
            var size_limit = false,
                record = this.record,
                field = this.field;
            if (record && field) {
                var field_size = record.expr_eval(this.attributes.size);
                var m2m_size = field.get_eval(record).length;
                size_limit = (((field_size !== undefined) &&
                            (field_size !== null)) &&
                        (m2m_size >= field_size) && (field_size >= 0));
            }

            this.entry.prop('disabled', this._readonly);
            this.but_add.prop('disabled', this._readonly || size_limit);
            this.but_remove.prop('disabled', this._readonly ||
                this._position === 0);
        },
        record_message: function(position, size) {
            this._position = position;
            var name = "_";
            if (position) {
                var selected = this.screen.selected_records.length;
                name = ' ' + position;
                if (selected > 1) {
                    name += '#' + selected;
                }
            }
            var message = name + ' / ' + Sao.common.humanize(size);
            this.label.text(message).attr('title', message);
            this._set_button_sensitive();
        },
        display: function() {
            Sao.View.Form.Many2Many._super.display.call(this);

            this.prm.done(() => {
                var record = this.record;
                var field = this.field;

                if (!field) {
                    this.screen.new_group();
                    this.screen.current_record = null;
                    this.screen.group.parent = null;
                    this.screen.display();
                    return;
                }
                var new_group = record.field_get_client(this.field_name);
                if (new_group != this.screen.group) {
                    this.screen.set_group(new_group);
                }
                this.screen.display();
                if (this.attributes.height !== undefined) {
                    this.screen.current_view.el
                        .find('.treeview,.list-form').first()
                        .css('min-height', this.attributes.height + 'px')
                        .css('max-height', this.attributes.height + 'px');
                }
            });
        },
        focus: function() {
            this.entry.focus();
        },
        activate: function() {
            this.edit();
        },
        add: function() {
            var domain = this.field.get_domain(this.record);
            var add_remove = this.record.expr_eval(
                this.attributes.add_remove);
            if (!jQuery.isEmptyObject(add_remove)) {
                domain = [domain, add_remove];
            }
            var context = this.field.get_search_context(this.record);
            var order = this.field.get_search_order(this.record);
            var value = this.entry.val();

            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }

            const callback = result => {
                if (!jQuery.isEmptyObject(result)) {
                    var ids = [];
                    var i, len;
                    for (i = 0, len = result.length; i < len; i++) {
                        ids.push(result[i][0]);
                    }
                    this.screen.group.load(ids, true);
                    this.screen.display();
                }
                this.entry.val('');
                this._popup = false;
            };
            var parser = new Sao.common.DomainParser();
            new Sao.Window.Search(this.attributes.relation,
                    callback, {
                        sel_multi: true,
                        context: context,
                        domain: domain,
                        order: order,
                        view_ids: (this.attributes.view_ids ||
                            '').split(','),
                        views_preload: this.attributes.views || {},
                        new_: this.create_access,
                        search_filter: parser.quote(value),
                        title: this.attributes.string
                    });
        },
        remove: function() {
            this.screen.remove(false, true, false);
        },
        key_press: function(event_) {
            var activate_keys = [Sao.common.TAB_KEYCODE];
            if (!this.wid_completion) {
                activate_keys.push(Sao.common.RETURN_KEYCODE);
            }

            if (event_.which == Sao.common.F3_KEYCODE) {
                event_.preventDefault();
                this.new_();
            } else if (event_.which == Sao.common.F2_KEYCODE) {
                event_.preventDefault();
                this.add();
            } else if (~activate_keys.indexOf(event_.which) && this.entry.val()) {
                this.add();
            }
        },
        _get_screen_form: function() {
            var domain = this.field.get_domain(this.record);
            var add_remove = this.record.expr_eval(
                    this.attributes.add_remove);
            if (!jQuery.isEmptyObject(add_remove)) {
                domain = [domain, add_remove];
            }
            var context = this.field.get_context(this.record);
            var view_ids = (this.attributes.view_ids || '').split(',');
            if (!jQuery.isEmptyObject(view_ids)) {
                // Remove the first tree view as mode is form only
                view_ids.shift();
            }
            var model = this.attributes.relation;
            var breadcrumb = jQuery.extend([], this.view.screen.breadcrumb);
            breadcrumb.push(this.attributes.string || Sao.common.MODELNAME.get(model));
            return new Sao.Screen(model, {
                'domain': domain,
                'view_ids': view_ids,
                'mode': ['form'],
                'views_preload': this.attributes.views,
                'context': context,
                'breadcrumb': breadcrumb,
            });
        },
        edit: function() {
            if (jQuery.isEmptyObject(this.screen.current_record)) {
                return;
            }
            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }
            // Create a new screen that is not linked to the parent otherwise
            // on the save of the record will trigger the save of the parent
            var screen = this._get_screen_form();
            const callback = result => {
                if (result) {
                    screen.current_record.save().done(() => {
                        var added = 'id' in this.screen.current_record.modified_fields;
                        // Force a reload on next display
                        this.screen.current_record.cancel();
                        if (added) {
                            this.screen.current_record.modified_fields.id = true;
                        }
                    });
                }
                this._popup = false;
            };
            screen.switch_view().done(() => {
                screen.load([this.screen.current_record.id]);
                screen.current_record = screen.group.get(
                    this.screen.current_record.id);
                new Sao.Window.Form(screen, callback);
            });
        },
        new_: function(defaults=null) {
            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }
            var screen = this._get_screen_form();
            if (defaults) {
                defaults = jQuery.extend({}, defaults);
            } else {
                defaults = {};
            }
            defaults.rec_name = this.entry.val();

            const callback = result => {
                if (result) {
                    var record = screen.current_record;
                    this.screen.group.load([record.id], true);
                }
                this.entry.val('');
                this._popup = false;
            };
            screen.switch_view().done(() => {
                new Sao.Window.Form(screen, callback, {
                    'new_': true,
                    'save_current': true,
                    'defaults': defaults,
                });
            });
        },
        _update_completion: function(text) {
            if (!this.record) {
                return jQuery.when();
            }
            var model = this.attributes.relation;
            var domain = this.field.get_domain(this.record);
            var add_remove = this.record.expr_eval(
                this.attributes.add_remove);
            if (!jQuery.isEmptyObject(add_remove)) {
                domain = [domain, add_remove];
            }
            return Sao.common.update_completion(
                this.entry, this.record, this.field, model, domain);
        },
        _completion_match_selected: function(value) {
            if (value.id !== null) {
                this.screen.group.load([value.id], true);
                this.entry.val('');
            } else {
                this.new_(value.defaults);
            }
        },
        _completion_action_activated: function(action) {
            if (action == 'search') {
                this.add();
            } else if (action == 'create') {
                this.new_();
            }
        },
    });

    Sao.View.Form.BinaryMixin = Sao.class_(Sao.View.Form.Widget, {
        init: function(view, attributes) {
            Sao.View.Form.BinaryMixin._super.init.call(
                this, view, attributes);
            this.filename = attributes.filename || null;
        },
        toolbar: function(class_) {
            var group = jQuery('<div/>', {
                'class': class_,
                'role': 'group'
            });

            this.but_save_as = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button',
                'aria-label': Sao.i18n.gettext("Save As"),
                'title': Sao.i18n.gettext("Save As..."),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-download')
            ).appendTo(group);
            this.but_save_as.click(this.save_as.bind(this));

            this.input_select = jQuery('<input/>', {
                'type': 'file',
            }).change(this.select.bind(this));
            this.but_select = jQuery('<div/>', {
                'class': 'btn btn-default input-file',
                'type': 'button',
                'aria-label': Sao.i18n.gettext("Select"),
                'title': Sao.i18n.gettext("Select..."),
            }).append(this.input_select
            ).append(Sao.common.ICONFACTORY.get_icon_img('tryton-search')
            ).appendTo(group);
            this.but_select
                .on('dragover', false)
                .on('drop', this.select_drop.bind(this));

            this.but_clear = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button',
                'aria-label': Sao.i18n.gettext("Clear"),
                'title': Sao.i18n.gettext("Clear"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-clear')
            ).appendTo(group);
            this.but_clear.click(this.clear.bind(this));

            return group;
        },
        get filename_field() {
            if (this.filename) {
                var record = this.record;
                if (record) {
                    return record.model.fields[this.filename];
                }
            }
            return null;
        },
        update_buttons: function(value) {
            if (value) {
                this.but_save_as.show();
                this.but_select.hide();
                this.but_clear.show();
            } else {
                this.but_save_as.hide();
                this.but_select.show();
                this.but_clear.hide();
            }
        },
        select: function() {
            var record = this.record,
                field = this.field,
                filename_field = this.filename_field;

            Sao.common.get_input_data(this.input_select, function(data, filename) {
                field.set_client(record, data);
                if (filename_field) {
                    filename_field.set_client(record, filename);
                }
            }, !field.get_size);
        },
        select_drop: function(evt) {
            evt.preventDefault();
            evt.stopPropagation();
            evt = evt.originalEvent;
            var files = [];
            if (evt.dataTransfer.items) {
                Sao.Logger.debug("Select drop items:", evt.dataTransfer.items);
                for (let i=0; i < evt.dataTransfer.items.length; i++) {
                    let file = evt.dataTransfer.items[i].getAsFile();
                    if (file) {
                        files.push(file);
                    }
                }
            } else {
                for (let i=0; i < evt.dataTransfer.files.length; i++) {
                    let file = evt.dataTransfer.files[i];
                    if (file) {
                        files.push(file);
                    }
                }
            }
            for (const file of files) {
                Sao.common.get_file_data(file, (data, filename) => {
                    this.field.set_client(this.record, data);
                    if (this.filename_field) {
                        this.filename_field.set_client(this.record, filename);
                    }
                });
            }
        },
        open: function() {
            this.save_as();
        },
        save_as: function() {
            var field = this.field;
            var record = this.record;
            var prm;
            if (field.get_data) {
                prm = field.get_data(record);
            } else {
                prm = jQuery.when(field.get(record));
            }
            prm.done(data => {
                var name;
                var field = this.filename_field;
                if (field) {
                    name = field.get(this.record);
                }
                Sao.common.download_file(data, name);
            });
        },
        clear: function() {
            this.input_select.val(null);
            var filename_field = this.filename_field;
            if (filename_field) {
                filename_field.set_client(this.record, null);
            }
            this.field.set_client(this.record, null);
        }
    });

    Sao.View.Form.Binary = Sao.class_(Sao.View.Form.BinaryMixin, {
        class_: 'form-binary',
        blob_url: '',
        init: function(view, attributes) {
            Sao.View.Form.Binary._super.init.call(this, view, attributes);

            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(this.el);

            this.size = jQuery('<input/>', {
                type: 'input',
                'class': 'form-control input-sm',
                'readonly': true,
                'name': attributes.name,
            }).appendTo(group);

            if (this.filename && attributes.filename_visible) {
                this.text = jQuery('<input/>', {
                    type: 'input',
                    'class': 'form-control input-sm'
                }).prependTo(group);
                this.text.change(this.focus_out.bind(this));
                // Use keydown to not receive focus-in TAB
                this.text.on('keydown', this.key_press.bind(this));
                this.text.css('width', '50%');
                this.size.css('width', '50%');

                this.but_open = jQuery('<button/>', {
                    'class': 'btn btn-default',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext("Open..."),
                    'title': Sao.i18n.gettext("Open..."),
                }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-open')
                ).appendTo(jQuery('<span/>', {
                    'class': 'input-group-btn',
                }).prependTo(group));
                this.but_open.click(this.open.bind(this));
            }

            this.toolbar('input-group-btn').appendTo(group);
        },
        display: function() {
            Sao.View.Form.Binary._super.display.call(this);

            var record = this.record, field = this.field;
            if (!field) {
                if (this.text) {
                    this.text.val('');
                }
                this.size.val('');
                this.but_save_as.hide();
                return;
            }
            var size;
            if (field.get_size) {
                size = field.get_size(record);
            } else {
                size = field.get(record).length;
            }
            this.size.val(Sao.common.humanize(size, 'B'));

            if (this.text) {
                this.text.val(this.filename_field.get(record) || '');
                if (size) {
                    this.but_open.parent().show();
                } else {
                    this.but_open.parent().hide();
                }
            }
            this.update_buttons(Boolean(size));
        },
        key_press: function(evt) {
            var editable = !this.text.prop('readonly');
            if (evt.which == Sao.common.F3_KEYCODE && editable) {
                evt.preventDefault();
                this.new_();
            } else if (evt.which == Sao.common.F2_KEYCODE) {
                evt.preventDefault();
                this.open();
            }
        },
        set_value: function() {
            if (this.text) {
                this.filename_field.set_client(this.record,
                        this.text.val() || '');
            }
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Binary._super.set_readonly.call(this, readonly);
            this.but_select.prop('disabled', readonly);
            this.but_clear.prop('disabled', readonly);
            if (this.text) {
                this.text.prop('readonly', readonly);
            }
        }
    });

    Sao.View.Form.MultiSelection = Sao.class_(Sao.View.Form.Selection, {
        class_: 'form-multiselection',
        expand: true,
        init: function(view, attributes) {
            this.nullable_widget = false;
            Sao.View.Form.MultiSelection._super.init.call(
                this, view, attributes);
            this.select.prop('multiple', true);
        },
        set_selection: function(selection, help) {
            Sao.View.Form.MultiSelection._super.set_selection.call(
                this, selection, help);
            var widget_help = this.attributes.help;
            if (widget_help) {
                this.select.children().each(function() {
                    var option = jQuery(this);
                    var help = option.attr('title');
                    if (help) {
                        help = widget_help + '\n' + help;
                        option.attr('title', help);
                    }
                });
            }
        },
        get modified() {
            if (this.record && this.field) {
                var group = new Set(this.field.get_eval(this.record));
                var value = new Set(this.get_value());
                return !Sao.common.compare(value, group);
            }
            return false;
        },
        display_update_selection: function() {
            var record = this.record;
            var field = this.field;
            this.update_selection(record, field, () => {
                var yexpand = this.attributes.yexpand;
                if (yexpand === undefined) {
                    yexpand = this.expand;
                }
                if (!yexpand) {
                    this.select.prop('size', this.select.children().length);
                }
                if (!field) {
                    return;
                }
                var value = field.get_eval(record);
                value = value.map(function(e) { return JSON.stringify(e); });
                this.select.val(value);
            });
        },
        get_value: function() {
            var value = this.select.val();
            if (value) {
                return value.map(function(e) { return JSON.parse(e); });
            }
            return [];
        },
    });

    Sao.View.Form.Image = Sao.class_(Sao.View.Form.BinaryMixin, {
        class_: 'form-image',
        init: function(view, attributes) {
            Sao.View.Form.Image._super.init.call(this, view, attributes);
            this.height = parseInt(attributes.height || 100, 10);
            this.width = parseInt(attributes.width || 300, 10);

            this.el = jQuery('<div/>', {
                'class': this.class_ + ' thumbnail',
            });
            this.image = jQuery('<img/>', {
                'class': 'center-block'
            }).appendTo(this.el);
            this.el
                .on('dragover', false)
                .on('drop', this.select_drop.bind(this));
            this.image.css('max-height', this.height);
            this.image.css('max-width', this.width);
            this.image.css('height', 'auto');
            this.image.css('width', 'auto');
            switch (attributes.border) {
                case 'rounded':
                    this.image.addClass('img-rounded');
                    break;
                case 'circle':
                    this.image.addClass('img-circle');
                    break;
                default:
                    break;
            }
            var group = this.toolbar('btn-group');
            if (!attributes.readonly) {
                jQuery('<div/>', {
                    'class': 'text-center caption',
                }).append(group).appendTo(this.el);
            }
            this._readonly = false;
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Image._super.set_readonly.call(this, readonly);
            this._readonly = readonly;
            this.but_select.prop('disabled', readonly);
            this.but_clear.prop('disabled', readonly);
        },
        select_drop: function(evt) {
            if (this._readonly) {
                return;
            }
            Sao.View.Form.Image._super.select_drop.call(this, evt);
            this.update_img();
        },
        clear: function() {
            Sao.View.Form.Image._super.clear.call(this);
            this.update_img();
        },
        update_img: function() {
            var value;
            var record = this.record;
            if (record) {
                value = record.field_get_client(this.field_name);
            }
            if (value) {
                if (value > Sao.config.image_max_size) {
                    value = jQuery.when(null);
                } else {
                    value = record.model.fields[this.field_name]
                        .get_data(record);
                }
            } else {
                value = jQuery.when(null);
            }
            value.done(data => {
                if (record !== this.record) {
                    return;
                }
                this.image.attr('src', Sao.common.image_url(data));
                this.update_buttons(Boolean(data));
            });
        },
        display: function() {
            Sao.View.Form.Image._super.display.call(this);
            this.update_img();
        }
    });

    Sao.View.Form.Document = Sao.class_(Sao.View.Form.BinaryMixin, {
        class_: 'form-document',
        expand: true,
        init: function(view, attributes) {
            Sao.View.Form.Document._super.init.call(this, view, attributes);

            this._blob_url = null;
            this.el = jQuery('<div/>', {
                'class': this.class_,
            });

            this.object = jQuery('<object/>', {
                'class': 'center-block',
            }).appendTo(this.el);
            if (attributes.height) {
                this.object.css('height', parseInt(attributes.height, 10));
            }
            if (attributes.width) {
                this.object.css('width', parseInt(attributes.width, 10));
            }
        },
        display: function() {
            Sao.View.Form.Document._super.display.call(this);
            var data, filename;
            var record = this.record;
            if (record) {
                data = record.model.fields[this.field_name].get_data(record);
            } else {
                data = jQuery.when(null);
            }
            var filename_field = this.filename_field;
            if (filename_field) {
                filename = filename_field.get_client(record);
            }
            data.done(data => {
                var url, blob;
                if (record !== this.record) {
                    return;
                }
                // in case onload was not yet triggered
                window.URL.revokeObjectURL(this.object.attr('data'));
                if (!data) {
                    url = null;
                } else {
                    var mimetype = Sao.common.guess_mimetype(filename);
                    if (mimetype == 'application/octet-binary') {
                        mimetype = null;
                    }
                    blob = new Blob([data], {
                        'type': mimetype,
                    });
                    url = window.URL.createObjectURL(blob);
                }
                // duplicate object to force refresh on buggy browsers
                const object = this.object.clone();
                // set onload before data to be always called
                object.get(0).onload = function() {
                    this.onload = null;
                    window.URL.revokeObjectURL(url);
                };
                object.attr('data', url);
                this.object.replaceWith(object);
                this.object = object;
            });
        },
    });

    Sao.View.Form.URL = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-url',
        _type: 'url',
        init: function(view, attributes) {
            Sao.View.Form.URL._super.init.call(this, view, attributes);
            this.input.attr('type', this._type);
            this.button = this.labelled = jQuery('<a/>', {
                'class': 'btn btn-default',
                'target': '_blank',
                'rel': 'noreferrer noopener',
            }).appendTo(jQuery('<span/>', {
                'class': 'input-group-btn'
            }).appendTo(this.group));
            this.icon = jQuery('<img/>').appendTo(this.button);
            this.set_icon();
        },
        display: function() {
            Sao.View.Form.URL._super.display.call(this);
            var url = '';
            var record = this.record;
            if (record) {
                url = record.field_get_client(this.field_name);
            }
            this.set_url(url);
            if (record & this.attributes.icon) {
                var icon = this.attributes.icon;
                var value;
                if (icon in record.model.fields) {
                    value = record.field_get_client(icon);
                } else {
                    value = icon;
                }
                this.set_icon(value);
            }
        },
        set_icon: function(value) {
            value = value || 'tryton-public';
            Sao.common.ICONFACTORY.get_icon_url(value).done(url => {
                this.icon.attr('src', url);
            });
        },
        set_url: function(value) {
            this.button.attr('href', value);
            this.button.toggle(Boolean(value));
        },
        set_invisible: function(invisible) {
            Sao.View.Form.URL._super.set_invisible.call(this, invisible);
            if (invisible) {
                this.input.attr('type', '');
            } else {
                this.input.attr('type', this._type);
            }
        },
    });

    Sao.View.Form.Email = Sao.class_(Sao.View.Form.URL, {
        class_: 'form-email',
        _type: 'email',
        set_url: function(value) {
            Sao.View.Form.Email._super.set_url.call(this, 'mailto:' + value);
        }
    });

    Sao.View.Form.CallTo = Sao.class_(Sao.View.Form.URL, {
        class_: 'form-callto',
        set_url: function(value) {
            Sao.View.Form.CallTo._super.set_url.call(this, 'callto:' + value);
        }
    });

    Sao.View.Form.SIP = Sao.class_(Sao.View.Form.URL, {
        class_: 'form-sip',
        set_url: function(value) {
            Sao.View.Form.SIP._super.set_url.call(this, 'sip:' + value);
        }
    });

    Sao.View.Form.HTML = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-html',
        init: function(view, attributes) {
            Sao.View.Form.HTML._super.init.call(this, view, attributes);
            Sao.View.Form.TranslateMixin.init.call(this);
            this.el = jQuery('<div/>', {
                'class': this.class_,
            });
            this.button = jQuery('<a/>', {
                'class': 'btn btn-lnk',
                'target': '_blank',
                'rel': 'noreferrer noopener',
            }).text(attributes.string).appendTo(this.el);
            if (attributes.translate) {
                var button = jQuery('<button/>', {
                    'class': 'btn btn-default btn-sm',
                    'type': 'button',
                    'aria-label': Sao.i18n.gettext('Translate'),
                    'title': Sao.i18n.gettext("Translate"),
                }).appendTo(this.el);
                button.append(
                    Sao.common.ICONFACTORY.get_icon_img('tryton-translate'));
                button.click(this.translate.bind(this));
            }
        },
        uri: function(language) {
            var record = this.record,
                uri;
            if (!record || (record.id < 0)) {
                uri = '';
            } else {
                uri = '/' + record.model.session.database +
                    '/ir/html/' + record.model.name + '/' + record.id + '/' +
                    this.field_name;
                uri += '?language=' + encodeURIComponent(
                    language || Sao.i18n.getlang());
                uri += '&title=' + encodeURIComponent(Sao.config.title);
            }
            return uri;
        },
        display: function() {
            Sao.View.Form.HTML._super.display.call(this);
            this.button.attr('href', this.uri());
        },
        set_readonly: function(readonly) {
            Sao.View.Form.HTML._super.set_readonly.call(this, readonly);
            this.el.find('button').prop('disabled', readonly);
            if (readonly) {
                this.el.find('a').hide();
            } else {
                this.el.find('a').show();
            }
        },
        translate_dialog: function(languages) {
            var options = {};
            for (const language of languages) {
                options[language.name] = language.code;
            }
            Sao.common.selection(Sao.i18n.gettext("Choose a language"), options)
            .done(language => {
                window.open(this.uri(language), '_blank', 'noreferrer,noopener');
            });
        },
    });

    Sao.View.Form.ProgressBar = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-char',
        init: function(view, attributes) {
            Sao.View.Form.ProgressBar._super.init.call(
                this, view, attributes);
            this.el = jQuery('<div/>', {
                'class': this.class_ + ' progress'
            });
            this.progressbar = jQuery('<div/>', {
                'class': 'progress-bar',
                'role': 'progressbar',
                'aria-valuemin': 0,
                'aria-valuemax': 100
            }).appendTo(this.el);
            this.progressbar.css('min-width: 2em');
        },
        display: function() {
            Sao.View.Form.ProgressBar._super.display.call(this);
            var value, text;
            var record = this.record;
            var field = this.field;
            if (!field) {
                value = 0;
                text = '';
            } else {
                value = field.get(record);
                text = field.get_client(record, 100);
                if (text) {
                    text = Sao.i18n.gettext('%1%', text);
                }
            }
            this.progressbar.attr('aria-valuenow', value * 100);
            this.progressbar.css('width', value * 100 + '%');
            this.progressbar.text(text);
        }
    });

    Sao.View.Form.Dict = Sao.class_(Sao.View.Form.Widget, {
        class_: 'form-dict',
        expand: true,
        init: function(view, attributes) {
            Sao.View.Form.Dict._super.init.call(this, view, attributes);

            this.schema_model = attributes.schema_model;
            this.fields = {};
            this.rows = {};

            this.el = jQuery('<div/>', {
                'class': this.class_ + ' panel panel-default'
            });
            var heading = jQuery('<div/>', {
                'class': this.class_ + '-heading panel-heading'
            }).appendTo(this.el);
            var label = jQuery('<label/>', {
                'class': this.class_ + '-string',
                'text': attributes.string
            }).appendTo(heading);

            label.uniqueId();
            this.el.uniqueId();
            this.el.attr('aria-labelledby', label.attr('id'));
            label.attr('for', this.el.attr('id'));

            var body = jQuery('<div/>', {
                'class': this.class_ + '-body panel-body form-horizontal'
            }).appendTo(this.el);
            this.container = jQuery('<div/>', {
                'class': this.class_ + '-container'
            }).appendTo(body);

            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(jQuery('<div>', {
                'class': 'col-sm-10 col-sm-offset-2'
            }).appendTo(jQuery('<div/>', {
                'class': 'form-group'
            }).appendTo(body)));
            this.wid_text = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm',
                'placeholder': Sao.i18n.gettext('Search'),
                'name': attributes.name,
            }).appendTo(group);

            if (!attributes.completion || attributes.completion == '1') {
                this.wid_completion = Sao.common.get_completion(
                    group,
                    this._update_completion.bind(this),
                    this._completion_match_selected.bind(this));
                this.wid_text.completion = this.wid_completion;
            }

            this.but_add = jQuery('<button/>', {
                'class': 'btn btn-default btn-sm',
                'type': 'button',
                'aria-label': Sao.i18n.gettext("Add"),
                'title': Sao.i18n.gettext("Add"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-add')
            ).appendTo(jQuery('<div/>', {
                'class': 'input-group-btn'
            }).appendTo(group));
            this.but_add.click(this.add.bind(this));

            this._readonly = false;
            this._record_id = null;
            this._popup = false;
        },
        _required_el: function() {
            return this.wid_text;
        },
        _invalid_el: function() {
            return this.wid_text;
        },
        add: function() {
            var context = this.field.get_context(this.record);
            var value = this.wid_text.val();
            var domain = this.field.get_domain(this.record);

            if (this._popup) {
                return;
            } else {
                this._popup = true;
            }

            const callback = result => {
                if (!jQuery.isEmptyObject(result)) {
                    var ids = result.map(function(e) {
                        return e[0];
                    });
                    this.add_new_keys(ids);
                }
                this.wid_text.val('');
                this._popup = false;
            };

            var parser = new Sao.common.DomainParser();
            new Sao.Window.Search(this.schema_model,
                    callback, {
                        sel_multi: true,
                        context: context,
                        domain: domain,
                        new_: false,
                        search_filter: parser.quote(value),
                        title: this.attributes.string
                    });
        },
        add_new_keys: function(ids) {
            var field = this.field;
            field.add_new_keys(ids, this.record)
                .then(new_names => {
                    this.send_modified();
                    var value = this.field.get_client(this.record);
                    for (const key of new_names) {
                        value[key] = null;
                    }
                    this.field.set_client(this.record, value);
                    this._display().then(() => {
                        this.fields[new_names[0]].input.focus();
                    });
                });
        },
        remove: function(key, modified=true) {
            delete this.fields[key];
            this.rows[key].remove();
            delete this.rows[key];
            if (modified) {
                this.send_modified();
                this.set_value(this.record, this.field);
            }
        },
        set_value: function() {
            this.field.set_client(this.record, this.get_value());
        },
        get_value: function() {
            var value = {};
            for (var key in this.fields) {
                var widget = this.fields[key];
                value[key] = widget.get_value();
            }
            return value;
        },
        get modified() {
            if (this.record && this.field) {
                var value = this.field.get_client(this.record);
                for (var key in this.fields) {
                    var widget = this.fields[key];
                    if (widget.modified(value)) {
                        return true;
                    }
                }
            }
            return false;
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Dict._super.set_readonly.call(this, readonly);
            this._set_button_sensitive();
            for (var key in this.fields) {
                var widget = this.fields[key];
                widget.set_readonly(readonly);
            }
            this.wid_text.prop('disabled', readonly);
        },
        _set_button_sensitive: function() {
            var create = this.attributes.create;
            if (create === undefined) {
                create = 1;
            } else if (typeof create == 'string') {
                create = Boolean(parseInt(create, 10));
            }
            var delete_ = this.attributes['delete'];
            if (delete_ === undefined) {
                delete_ = 1;
            } else if (typeof delete_ == 'string') {
                delete_ = Boolean(parseInt(delete_, 10));
            }
            this.but_add.prop('disabled', this._readonly || !create);
            for (var key in this.fields) {
                var button = this.fields[key].button;
                button.prop('disabled', this._readonly || !delete_);
            }
        },
        add_line: function(key, position) {
            var field, row;
            var key_schema = this.field.keys[key];
            this.fields[key] = field = new (
                this.get_entries(key_schema.type))(key, this);
            this.rows[key] = row = jQuery('<div/>', {
                'class': 'form-group'
            });
            var text = key_schema.string + Sao.i18n.gettext(':');
            var label = jQuery('<label/>', {
                'text': text
            }).appendTo(jQuery('<div/>', {
                'class': 'dict-label col-sm-2 control-label'
            }).appendTo(row));

            field.el.addClass('col-sm-10').appendTo(row);

            label.uniqueId();
            field.labelled.uniqueId();
            field.labelled.attr('aria-labelledby', label.attr('id'));
            label.attr('for', field.labelled.attr('id'));

            field.button.click(() => {
                this.remove(key, true);
            });

            var previous = null;
            if (position > 0) {
                previous = this.container.children().eq(position - 1);
            }
            if (previous) {
                previous.after(row);
            } else {
                this.container.prepend(row);
            }
        },
        display: function() {
            this._display();
        },
        _display: function() {
            Sao.View.Form.Dict._super.display.call(this);

            var record = this.record;
            var field = this.field;
            if (!field) {
                return;
            }

            var record_id = record ? record.id : null;
            var key;

            if (record_id != this._record_id) {
                for (key in this.fields) {
                    this.remove(key, false);
                }
                this._record_id = record_id;
            }

            var value = field.get_client(record);
            var new_key_names = Object.keys(value).filter(
                e => !this.fields[e]);

            var prm;
            if (!jQuery.isEmptyObject(new_key_names)) {
                prm = field.add_keys(new_key_names, record);
            } else {
                prm = jQuery.when();
            }
            prm.then(() => {
                var i, len, key;
                var keys = Object.keys(value)
                    .filter(function(key) {
                        return field.keys[key];
                    })
                    .sort(function(key1, key2) {
                        var seq1 = field.keys[key1].sequence;
                        var seq2 = field.keys[key2].sequence;
                        if (seq1 < seq2) {
                            return -1;
                        } else if (seq1 > seq2) {
                            return 1;
                        } else {
                            return 0;
                        }
                    });
                // We remove first the old keys in order to keep the order
                // inserting the new ones
                var removed_key_names = Object.keys(this.fields).filter(
                        function(e) {
                            return !(e in value);
                        });
                for (i = 0, len = removed_key_names.length; i < len; i++) {
                    key = removed_key_names[i];
                    this.remove(key, false);
                }
                var decoder = new Sao.PYSON.Decoder();
                var inversion = new Sao.common.DomainInversion();
                for (i = 0, len = keys.length; i < len; i++) {
                    key = keys[i];
                    var val = value[key];
                    if (!this.fields[key]) {
                        this.add_line(key, i);
                    }
                    var widget = this.fields[key];
                    widget.set_value(val);
                    widget.set_readonly(this._readonly);
                    var key_domain = (decoder.decode(field.keys[key].domain ||
                        'null'));
                    if (key_domain !== null) {
                        if (!inversion.eval_domain(key_domain, value)) {
                            widget.el.addClass('has-error');
                        } else {
                            widget.el.removeClass('has-error');
                        }
                    }
                }
            });
            this._set_button_sensitive();
            return prm;
        },
        _update_completion: function(text) {
            if (this.wid_text.prop('disabled')) {
                return jQuery.when();
            }
            if (!this.record) {
                return jQuery.when();
            }
            return Sao.common.update_completion(
                this.wid_text, this.record, this.field, this.schema_model);
        },
        _completion_match_selected: function(value) {
            this.add_new_keys([value.id]);
            this.wid_text.val('');
        },
        get_entries: function(type) {
            switch (type) {
                case 'char':
                    return Sao.View.Form.Dict.Entry;
                case 'boolean':
                    return Sao.View.Form.Dict.Boolean;
                case 'selection':
                    return Sao.View.Form.Dict.Selection;
                case 'multiselection':
                    return Sao.View.Form.Dict.MultiSelection;
                case 'integer':
                    return Sao.View.Form.Dict.Integer;
                case 'float':
                    return Sao.View.Form.Dict.Float;
                case 'numeric':
                    return Sao.View.Form.Dict.Numeric;
                case 'date':
                    return Sao.View.Form.Dict.Date;
                case 'datetime':
                    return Sao.View.Form.Dict.DateTime;
            }
        }
    });

    Sao.View.Form.Dict.Entry = Sao.class_(Object, {
        init: function(name, parent_widget) {
            this.name = name;
            this.definition = parent_widget.field.keys[name];
            this.parent_widget = parent_widget;
            this.create_widget();
            if (this.definition.help) {
                this.el.attr('title', this.definition.help);
            }
        },
        create_widget: function() {
            this.el = jQuery('<div/>', {
                'class': this.class_
            });
            var group = jQuery('<div/>', {
                'class': 'input-group input-group-sm'
            }).appendTo(this.el);
            this.input = this.labelled = jQuery('<input/>', {
                'type': 'text',
                'class': 'form-control input-sm mousetrap',
                'name': this.name,
            }).appendTo(group);
            this.button = jQuery('<button/>', {
                'class': 'btn btn-default',
                'type': 'button',
                'arial-label': Sao.i18n.gettext("Remove"),
                'title': Sao.i18n.gettext("Remove"),
            }).append(Sao.common.ICONFACTORY.get_icon_img('tryton-remove')
            ).appendTo(jQuery('<div/>', {
                'class': 'input-group-btn'
            }).appendTo(group));

            this.el.on('keydown',
                this.parent_widget.send_modified.bind(this.parent_widget));
            this.el.change(
                this.parent_widget.focus_out.bind(this.parent_widget));
        },
        modified: function(value) {
            return (JSON.stringify(this.get_value()) !=
                JSON.stringify(value[this.name]));
        },
        get_value: function() {
            return this.input.val();
        },
        set_value: function(value) {
            this.input.val(value || '');
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this.input.prop('readonly', readonly);
        }
    });

    Sao.View.Form.Dict.Char = Sao.class_(Sao.View.Form.Dict.Entry, {
        class_: 'dict-char',
        modified: function(value) {
            return (JSON.stringify(this.get_value()) !=
                JSON.stringify(value[this.name] || ""));
        }
    });

    Sao.View.Form.Dict.Boolean = Sao.class_(Sao.View.Form.Dict.Entry, {
        class_: 'dict-boolean',
        create_widget: function() {
            Sao.View.Form.Dict.Boolean._super.create_widget.call(this);
            this.input.attr('type', 'checkbox');
            this.input.change(
                    this.parent_widget.focus_out.bind(this.parent_widget));
        },
        get_value: function() {
            return this.input.prop('checked');
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this.input.prop('disabled', readonly);
        },
        set_value: function(value) {
            this.input.prop('checked', value);
        }
    });

    Sao.View.Form.Dict.SelectionEntry = Sao.class_(Sao.View.Form.Dict.Entry, {
        create_widget: function() {
            Sao.View.Form.Dict.SelectionEntry._super.create_widget.call(this);
            var select = jQuery('<select/>', {
                'class': 'form-control input-sm mousetrap',
                'name': this.name,
            });
            select.change(
                    this.parent_widget.focus_out.bind(this.parent_widget));
            this.input.replaceWith(select);
            this.input = this.labelled = select;
            var selection = jQuery.extend([], this.definition.selection);
            if (this.definition.sort === undefined || this.definition.sort) {
                selection.sort(function(a, b) {
                    return a[1].localeCompare(b[1]);
                });
            }
            for (const e of selection) {
                select.append(jQuery('<option/>', {
                    'value': JSON.stringify(e[0]),
                    'text': e[1],
                    'title': this.definition.help_selection[e[0]],
                }));
            }
        },
        set_readonly: function(readonly) {
            this._readonly = readonly;
            this.input.prop('disabled', readonly);
        }
    });

    Sao.View.Form.Dict.Selection = Sao.class_(
        Sao.View.Form.Dict.SelectionEntry, {
            class_: 'dict-selection',
            create_widget: function() {
                Sao.View.Form.Dict.Selection._super.create_widget.call(this);
                this.input.prepend(jQuery('<option/>', {
                    'value': JSON.stringify(null),
                    'text': '',
                }));
            },
            get_value: function() {
                return JSON.parse(this.input.val());
            },
            set_value: function(value) {
                this.input.val(JSON.stringify(value));
                var title = this.definition.help_selection[value] || null;
                if (this.definition.help && title) {
                    title = this.definition.help + '\n' + title;
                }
                this.input.attr('title', title);
            },
        });

    Sao.View.Form.Dict.MultiSelection = Sao.class_(
        Sao.View.Form.Dict.SelectionEntry, {
            class_: 'dict-multiselection',
            create_widget: function() {
                Sao.View.Form.Dict.MultiSelection._super
                    .create_widget.call(this);
                this.input.prop('multiple', true);
                var widget_help = this.definition.help;
                if (widget_help) {
                    this.input.children().each(function() {
                        var option = jQuery(this);
                        var help = option.attr('title');
                        if (help) {
                            help = widget_help + '\n' + help;
                            option.attr('title', help);
                        }
                    });
                }
            },
            get_value: function() {
                var value = this.input.val();
                return value.map(function(e) { return JSON.parse(e); });
            },
            set_value: function(value) {
                if (value) {
                    value = value.map(function(e) { return JSON.stringify(e); });
                }
                this.input.val(value);
            }
        });

    Sao.View.Form.Dict.Integer = Sao.class_(Sao.View.Form.Dict.Entry, {
        class_: 'dict-integer',
        create_widget: function() {
            Sao.View.Form.Dict.Integer._super.create_widget.call(this);
            this.input_text = this.labelled = integer_input(this.input);
        },
        get_value: function() {
            var value = parseInt(this.input.val(), 10);
            if (isNaN(value)) {
                return null;
            }
            return value;
        },
        set_value: function(value, options) {
            if (value !== null) {
                this.input.val(value);
                this.input_text.val(value.toLocaleString(
                    Sao.i18n.BC47(Sao.i18n.getlang()), options));
            } else {
                this.input.val('');
                this.input_text.val('');
            }
        },
        set_readonly: function(readonly) {
            Sao.View.Form.Dict.Integer._super.set_readonly.call(this, readonly);
            this.input_text.prop('readonly', readonly);
        },
    });

    Sao.View.Form.Dict.Float = Sao.class_(Sao.View.Form.Dict.Integer, {
        class_: 'dict-float',
        get digits() {
            var record = this.parent_widget.record;
            if (record) {
                var digits = record.expr_eval(this.definition.digits);
                if (!digits || !digits.every(function(e) {
                    return e !== null;
                })) {
                    return null;
                }
                return digits;
            } else {
                return null;
            }
        },
        get_value: function() {
            var value = this.input.val();
            if (!value && (value !== 0)) {
                return null;
            }
            value = Number(value);
            if (isNaN(value)) {
                return null;
            }
            return value;
        },
        set_value: function(value) {
            var step = 'any',
                options = {};
            var digits = this.digits;
            if (digits) {
                step = Math.pow(10, -digits[1]).toFixed(digits[1]);
                options.minimumFractionDigits = digits[1];
                options.maximumFractionDigits = digits[1];
            }
            this.input.attr('step', step);
            Sao.View.Form.Dict.Float._super.set_value.call(this, value, options);
        },
    });

    Sao.View.Form.Dict.Numeric = Sao.class_(Sao.View.Form.Dict.Float, {
        class_: 'dict-numeric',
        get_value: function() {
            var value = this.input.val();
            if (!value && (value !== 0)) {
                return null;
            }
            value = new Sao.Decimal(value);
            if (isNaN(value.valueOf())) {
                return null;
            }
            return value;
        }
    });

    Sao.View.Form.Dict.Date = Sao.class_(Sao.View.Form.Dict.Entry, {
        class_: 'dict-date',
        format: '%x',
        _input: 'date',
        _input_format: '%Y-%m-%d',
        _format: Sao.common.format_date,
        _parse: Sao.common.parse_date,
        create_widget: function() {
            Sao.View.Form.Dict.Date._super.create_widget.call(this);
            var group = this.input.parent().find('.input-group-btn');
            this.input_date = jQuery('<input/>', {
                'type': this._input,
                'role': 'button',
                'tabindex': -1,
            });
            this.input_date.click(() => {
                var value = this.get_value();
                value = this._format(this._input_format, value);
                this.input_date.val(value);
            });
            this.input_date.change(() => {
                var value = this.input_date.val();
                if (value) {
                    value = this._parse(this._input_format, value);
                    value = this._format(this.format, value);
                    this.input.val(value).change();
                    this.input.focus();
                }
            });
            if (this.input_date[0].type == this._input) {
                var icon = jQuery('<div/>', {
                    'class': 'btn btn-default',
                    'aria-label': Sao.i18n.gettext("Open the calendar"),
                    'title': Sao.i18n.gettext("Open the calendar"),
                }).prependTo(group);
                this.input_date.appendTo(icon);
                Sao.common.ICONFACTORY.get_icon_img('tryton-date')
                    .appendTo(icon);
            }
            var mousetrap = new Mousetrap(this.el[0]);

            mousetrap.bind('enter', (e, combo) => {
                var value = this._parse(this.format, this.input.val());
                value = this._format(this.format, value);
                this.input.val(value).change();
            });
            mousetrap.bind('=', (e, combo) => {
                e.preventDefault();
                this.input.val(this._format(this.format, moment())).change();
            });

            Sao.common.DATE_OPERATORS.forEach(operator => {
                mousetrap.bind(operator[0], (e, combo) => {
                    e.preventDefault();
                    var date = this.get_value() || Sao.DateTime();
                    date.add(operator[1]);
                    this.input.val(this._format(this.format, date)).change();
                });
            });
        },
        get_value: function() {
            return this._parse(this.format, this.input.val());
        },
        set_value: function(value) {
            this.input.val(this._format(this.format, value));
        },
    });

    Sao.View.Form.Dict.DateTime = Sao.class_(Sao.View.Form.Dict.Date, {
        class_: 'dict-datetime',
        format: '%x %X',
        _input: 'datetime-local',
        _input_format: '%Y-%m-%dT%H:%M:%S',
        _format: Sao.common.format_datetime,
        _parse: Sao.common.parse_datetime,
    });

    Sao.View.Form.PYSON = Sao.class_(Sao.View.Form.Char, {
        class_: 'form-pyson',
        init: function(view, attributes) {
            Sao.View.Form.PYSON._super.init.call(this, view, attributes);
            this.encoder = new Sao.PYSON.Encoder({});
            this.decoder = new Sao.PYSON.Decoder({}, true);
            this.el.keyup(this.validate_pyson.bind(this));
            this.icon = jQuery('<img/>', {
                'class': 'icon form-control-feedback',
            }).appendTo(this.group);
            this.group.addClass('has-feedback');
        },
        display: function() {
            Sao.View.Form.PYSON._super.display.call(this);
            this.validate_pyson();
        },
        get_encoded_value: function() {
            var value = this.input.val();
            if (!value) {
                return value;
            }
            try {
                return this.encoder.encode(eval_pyson(value));
            }
            catch (err) {
                return null;
            }
        },
        set_value: function() {
            // avoid modification because different encoding
            var value = this.get_encoded_value();
            var record = this.record;
            var field = this.field;
            var previous = field.get_client(record);
            if (value && previous && Sao.common.compare(
                value, this.encoder.encode(this.decoder.decode(previous)))) {
                value = previous;
            }
            field.set_client(record, value);
        },
        get_client_value: function() {
            var value = Sao.View.Form.PYSON._super.get_client_value.call(this);
            if (value) {
                value = Sao.PYSON.toString(this.decoder.decode(value));
            }
            return value;
        },
        validate_pyson: function() {
            var icon = 'ok';
            if (this.get_encoded_value() === null) {
                icon = 'error';
            }
            Sao.common.ICONFACTORY.get_icon_url('tryton-' + icon)
                .then(url => {
                    this.icon.attr('src', url);
                });
        },
        focus_out: function() {
            this.validate_pyson();
            Sao.View.Form.PYSON._super.focus_out.call(this);
        }
    });

    Sao.View.FormXMLViewParser.WIDGETS = {
        'binary': Sao.View.Form.Binary,
        'boolean': Sao.View.Form.Boolean,
        'callto': Sao.View.Form.CallTo,
        'char': Sao.View.Form.Char,
        'date': Sao.View.Form.Date,
        'datetime': Sao.View.Form.DateTime,
        'dict': Sao.View.Form.Dict,
        'document': Sao.View.Form.Document,
        'email': Sao.View.Form.Email,
        'float': Sao.View.Form.Float,
        'html': Sao.View.Form.HTML,
        'image': Sao.View.Form.Image,
        'integer': Sao.View.Form.Integer,
        'many2many': Sao.View.Form.Many2Many,
        'many2one': Sao.View.Form.Many2One,
        'multiselection': Sao.View.Form.MultiSelection,
        'numeric': Sao.View.Form.Float,
        'one2many': Sao.View.Form.One2Many,
        'one2one': Sao.View.Form.One2One,
        'password': Sao.View.Form.Password,
        'progressbar': Sao.View.Form.ProgressBar,
        'pyson': Sao.View.Form.PYSON,
        'reference': Sao.View.Form.Reference,
        'richtext': Sao.View.Form.RichText,
        'selection': Sao.View.Form.Selection,
        'sip': Sao.View.Form.SIP,
        'text': Sao.View.Form.Text,
        'time': Sao.View.Form.Time,
        'timedelta': Sao.View.Form.TimeDelta,
        'timestamp': Sao.View.Form.DateTime,
        'url': Sao.View.Form.URL,
    };
}());
