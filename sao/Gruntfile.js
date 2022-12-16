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
    jshint: {
        dist: {
            options: {
                jshintrc: 'src/.jshintrc'
            },
            src: ['dist/<%= pkg.name %>.js']
        },
        grunt: {
            src: ['Gruntfile.js']
        },
        tests: {
            options: {
                jshintrc: 'tests/.jshintrc'
            },
            src: ['tests/*.js']
        }
    },
    uglify: {
      options: {
        banner: '/*! <%= pkg.name %>-<%= pkg.version %> | GPL-3\n' +
        'This file is part of Tryton.  ' +
        'The COPYRIGHT file at the top level of\n' +
        'this repository contains the full copyright notices ' +
        'and license terms. */\n'
      },
      dist: {
        src: 'dist/<%= pkg.name %>.js',
        dest: 'dist/<%= pkg.name %>.min.js'
      }
    },
    less: {
        dev: {
            options: {
                paths: less_paths,
            },
            files: {
                'dist/<%= pkg.name %>.css': 'src/sao.less'
            }
        },
        'default': {
            options: {
                paths: less_paths,
                yuicompress: true
            },
            files: {
                'dist/<%= pkg.name %>.min.css': 'src/sao.less'
            }
        }
    },
    watch: {
        scripts: {
            files: ['src/**/*.js'],
            tasks: ['concat', 'jshint']
        },
        styles: {
            files: ['src/*.less'],
            tasks: 'less:dev'
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
  grunt.loadNpmTasks('grunt-contrib-jshint');
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-contrib-less');
  grunt.loadNpmTasks('grunt-po2json');

  grunt.registerTask('default', 'Build for production.', function() {
    grunt.task.run(['concat', 'jshint', 'uglify', 'less', 'po2json']);
    });
  grunt.registerTask('dev', 'Build for development.', function() {
    grunt.task.run(['concat', 'jshint', 'less:dev']);
    });
  grunt.registerTask('devwatch', 'Watch development', function() {
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
    grunt.task.run(['concat', 'jshint', 'less:dev', 'qunit']);
    });

};
