/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
'use strict';

var Class = function(Parent, props) {

    var ClassConstructor = function() {
        if (!(this instanceof ClassConstructor))
            throw Error('Constructor function requires new operator');
        if (this.init) {
            this.init.apply(this, arguments);
        }
    };

    // Plug prototype chain
    ClassConstructor.prototype = Object.create(Parent.prototype);
    ClassConstructor._super = Parent.prototype;
    if (props) {
        for (var name in props) {
            ClassConstructor.prototype[name] = props[name];
        }
    }
    return ClassConstructor;
};
