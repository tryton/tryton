module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),
    concat: {
        dist: {
            src: [
                'js/sao.js',
                'js/rpc.js',
                'js/pyson.js',
                'js/session.js',
                'js/model.js',
                'js/tab.js',
                'js/screen.js',
                'js/view.js',
                'js/action.js',
                'js/common.js'
            ],
            dest: 'dist/<%= pkg.name %>.js'
        }
    },
    jshint: {
        dist: {
            options: {
                jshintrc: 'js/.jshintrc'
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
    watch: {
        files: ['js/*.js'],
        tasks: 'dev'
    }
  });

  // Load the plugin that provides the "uglify" task.
  grunt.loadNpmTasks('grunt-contrib-concat');
  grunt.loadNpmTasks('grunt-contrib-jshint');
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-contrib-watch');

  // Default task(s).
  grunt.registerTask('default', ['concat', 'jshint', 'uglify']);
  grunt.registerTask('dev', ['concat', 'jshint']);

};
