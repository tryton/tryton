module.exports = function(grunt) {

  var _ = grunt.util._;
  var locales = ["bg", "ca", "cs", "de", "es", "es_419", "fr", "fa", "hu",
      "it", "lo", "lt", "nl", "pl", "pt", "ru", "sl", "zh_CN"];
  var jsfiles = [
      'src/sao.js',
      'src/rpc.js',
      'src/pyson.js',
      'src/session.js',
      'src/common.js',
      'src/model.js',
      'src/tab.js',
      'src/screen.js',
      'src/view.js',
      'src/view/form.js',
      'src/view/tree.js',
      'src/view/graph.js',
      'src/view/calendar.js',
      'src/view/list_form.js',
      'src/action.js',
      'src/window.js',
      'src/wizard.js',
      'src/board.js',
      'src/bus.js',
      'src/plugins.js',
      'src/html_sanitizer.js'
  ];
  var less_paths = [
      'src',
      'bower_components',
      'bower_components/bootstrap',
      'bower_components/bootstrap/less',
      'bower_components/bootstrap-rtl-ondemand/less',
  ];

  // Project configuration.
  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),
    shell: {
        options: {
            failOnError: true
        },
        msgmerge: {
            command: _.map(locales, function(locale) {
                var po = "locale/" + locale + ".po";
                return (
                    "msgmerge " +
                    "-U " + po + " " +
                    "--no-location " +
                    "locale/messages.pot;");
            }).join("")
        },
        xgettext: {
            command: (
                "xgettext " +
                "--language=JavaScript --from-code=UTF-8 " +
                "--omit-header --no-location " +
                "-o locale/messages.pot " +
                jsfiles.join(" "))
        }
    },
    po2json: {
        options: {
            format: 'raw'
        },
        all: {
            src: ['locale/*.po'],
            dest: 'locale/'
        }
    },
    concat: {
        dist: {
            src: jsfiles,
            dest: 'dist/<%= pkg.name %>.js'
        }
    },
    less: {
        'default': {
            options: {
                paths: less_paths,
            },
            files: {
                'dist/<%= pkg.name %>.css': 'src/sao.less'
            }
        }
    },
    watch: {
        scripts: {
            files: ['src/**/*.js'],
            tasks: ['concat']
        },
        styles: {
            files: ['src/*.less'],
            tasks: 'less'
        },
        translations: {
            files: ['locale/*.po'],
            tasks: 'po2json'
        }
    },
    qunit: {
        options: {
            timeout: 300000,
            puppeteer: {
                headless: true,
                args: [
                    '--no-sandbox',
                ],
                env: {
                    TZ: 'UTC',
                },
            },
        },
        all: ['tests/*.html']
    }
  });

  grunt.loadNpmTasks('grunt-contrib-concat');
  grunt.loadNpmTasks('grunt-contrib-less');
  grunt.loadNpmTasks('grunt-po2json');
  grunt.loadNpmTasks('grunt-qunit-junit');

  grunt.registerTask('default', 'Build for production.', function() {
    grunt.task.run(['concat', 'less', 'po2json']);
    });
  grunt.registerTask('watch', 'Watch development', function() {
    grunt.loadNpmTasks('grunt-contrib-watch');
    grunt.task.run(['watch']);
    });
  grunt.registerTask('msgmerge', 'Update locale messages.', function() {
    grunt.loadNpmTasks('grunt-shell');
    grunt.task.run(['shell:msgmerge']);
    });
  grunt.registerTask('xgettext', ' Extracts translatable messages', function() {
    grunt.loadNpmTasks('grunt-shell');
    grunt.task.run(['shell:xgettext']);
  });
  grunt.registerTask('test', 'Run tests', function() {
    grunt.loadNpmTasks('grunt-contrib-qunit');
    grunt.task.run(['concat', 'less', 'qunit_junit', 'qunit']);
    });

};
