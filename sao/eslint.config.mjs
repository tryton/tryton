import js from "@eslint/js";
import globals from "globals";

export default [
    js.configs.recommended,
    {
        languageOptions: {
            ecmaVersion: 6,
            sourceType: "script",
            globals: {
                Mousetrap: "readonly",
                Papa: "readonly",
                QUnit: "readonly",
                Sao: "readonly",
                Sortable: "readonly",
                c3: "readonly",
                i18n: "readonly",
                jQuery: "readonly",
                moment: "readonly",
                ...globals.browser
            },
        },
        rules: {
            "no-unused-vars": ["error", { "args": "none" }],
            "no-useless-escape": "off",
            "no-with": "off",
        },
    }, {
        files: ['tests/**/*.js'],
        languageOptions: {
            globals: {
                Sao: "readonly",
                eval_pyson: "readonly",
            },
        },
    },
];
