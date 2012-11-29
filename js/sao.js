/* This file is part of Tryton.  The COPYRIGHT file at the top level of
   this repository contains the full copyright notices and license terms. */
'use strict';

var Sao = {};

Sao.error = function(title, message) {
    alert(title + '\n' + (message || ''));
};

Sao.warning = function(title, message) {
    alert(title + '\n' + (message || ''));
};
