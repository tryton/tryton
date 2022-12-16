/*
Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

(function () {
    'use strict';

    var tag_whitelist = {
        B: true,
        BODY: true,
        BR: true,
        DIV: true,
        FONT: true,
        I: true,
        U: true,
    };

    var attribute_whitelist = {
        align: true,
        color: true,
        face: true,
        size: true,
    };

    Sao.HtmlSanitizer = {};
    Sao.HtmlSanitizer.sanitize = function(input) {
        input = input.trim();
        // to save performance and not create iframe
        if (input == "") return "";

        // firefox "bogus node" workaround
        if (input == "<br>") return "";

        var iframe = document.createElement('iframe');
        if (iframe.sandbox === undefined) {
            // Browser does not support sandboxed iframes
            Sao.Logger.warn("Your browser do not support sandboxed iframes," +
                " unable to sanitize HTML.");
            return input;
        }
        iframe.sandbox = 'allow-same-origin';
        iframe.style.display = 'none';
        // necessary so the iframe contains a document
        document.body.appendChild(iframe);
        var iframedoc = (iframe.contentDocument ||
            iframe.contentWindow.document);
        // null in IE
        if (iframedoc.body == null) {
            iframedoc.write("<body></body>");
        }
        iframedoc.body.innerHTML = input;

        function make_sanitized_copy(node) {
            var new_node;
            if (node.nodeType == Node.TEXT_NODE) {
                new_node = node.cloneNode(true);
            } else if (node.nodeType == Node.ELEMENT_NODE &&
                    tag_whitelist[node.tagName]) {
                //remove useless empty tags
                if ((node.tagName != "BR") && node.innerHTML.trim() == "") {
                    return document.createDocumentFragment();
                }

                new_node = iframedoc.createElement(node.tagName);

                for (var i = 0; i < node.attributes.length; i++) {
                    var attr = node.attributes[i];
                    if (attribute_whitelist[attr.name]) {
                        new_node.setAttribute(attr.name, attr.value);
                    }
                }
                for (i = 0; i < node.childNodes.length; i++) {
                    var sub_copy = make_sanitized_copy(node.childNodes[i]);
                    new_node.appendChild(sub_copy, false);
                }
            } else {
                new_node = document.createDocumentFragment();
                if (node.tagName != 'SCRIPT') {
                    new_node.textContent = node.textContent;
                }
            }
            return new_node;
        }

        var result_element = make_sanitized_copy(iframedoc.body);
        document.body.removeChild(iframe);
        // replace is just for cleaner code
        return result_element.innerHTML
            .replace(/<br[^>]*>(\S)/g, "<br>\n$1")
            .replace(/div><div/g, "div>\n<div");
    };
})();
