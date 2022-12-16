Glossary
########

.. glossary::
   :sorted:

   Actions
      An *action* is a function which is triggered by a user intervention.
      *Actions* are called from activating menu items or pushing buttons.
      Actions often provide :term:`wizards`.

   Board
      The *board* is a type of :term:`views` able to handle other views. This
      view type is not documented or not used for now.

   Character Encoding
      See [WP-ENCOD]_

   CSV
      File format for Comma Separated Values. See [WP-CSV]_

   Data
      *Data* means information content produced by users.


   Dialog
      A *dialog* is a :term:`popup` window, which overlays other windows and
      request user interaction. *Dialogs* are used to set up special
      :term:`actions`.

   Fields
      *Fields* are attributes of a *data object*. *Fields* are
      represented as table fields in relational databases.

   Form View
      The *form* is a mode of :term:`views`, which displays single
      :term:`records` of data.

   Form
      The *form* is the general type of :term:`views` used in Tryton. The
      *form* provides several modes for presenting :term:`data`:

      * :term:`Form View`
      * :term:`Tree View`
      * :term:`Graph View`

   Graph View
      *Graph view* is a mode of :term:`views` to show sets of data in a
      diagram. *Graph views* can be pie-charts or bar-charts.

   Main Frame
      The *main frame* is a huge part arranged in the center of the
      :term:`Tryton client`. *Using the Tryton client* means mainly using the
      *main frame* part. It contains :term:`tabs` to organize and to show
      different :term:`views`.

   Model
      A *model* describes how data is represented and accessed. Models
      formally define records and relationships for a certain domain
      of interest.

   Modules
      *Modules* are enclosed file packages for the :term:`Tryton server`. A
      *Module* defines the :term:`Model`, the presentation of the
      information (:term:`views`), functions, :term:`actions` and default
      presets. Additionally *modules* may provide standardized data like ISO
      names for countries. *Modules* in Tryton are build up generically. That
      is, they are constructed as simple as possible to provide the
      desired functionality.

   Plugins
      A *plugin* is an add-on module for the :term:`Tryton client`.

   Popup
      A small window which pops up the main window.

   Records
      A *record* is a singular dataset in a :term:`Model`. *Records* are
      represented as lines or *records* in a relational database table.

   Tabs
      *Tabs* are :term:`widgets` to arrange different contents side by side.
      They are used to switch quickly between different domains of interest.
      Tryton uses *tabs* in two layer:

      * A tabbed :term:`Main Frame`.
      * Tabs inside :term:`Views`.

      The main frame consists of *tabs* that embed the main menu and all views
      to an appropriate :term:`model`. The other type of *tabs* is used
      inside of :term:`views` to split them into visual domains of the same
      model. These *tabs* are used for structuring contents of one model to
      different sub headings.

   Three-Tiers
      A *three-tiers* application framework like Tryton, is build up of three
      different software components:

      1. The storage or data tier.
      2. The logic or application tier.
      3. The presentation tier.

      The storage tier in the Tryton framework is provided by the PostgreSQL
      database engine. The application logic tier is provided by
      :term:`Tryton server` and its :term:`modules`. The presentation tier is
      mainly provided by the :term:`Tryton client`. In a *three tiers*
      framework, the presentation tier (client) never connects directly to the
      storage tier. All communication is controlled by the application tier.

   Tree View
      *Tree view* is a mode of :term:`views` showing sets of :term:`data`.
      *Tree views* can be flat lists or tables as well as tree-like nested
      lists.

   Tryton Server
      The *Tryton server* is the application or logic tier in the
      :term:`three-tiers` application platform *Tryton*. The *Tryton server*
      connects the underlying application logic of the different
      :term:`modules` with corresponding database records. The
      *Tryton server* provides different interfaces to present the
      generated information:

      * :term:`Tryton client`: (graphical user interface GUI)
      * XMLRPC see [WP-XMLRPC]_
      * WebDAV see [WP-WebDAV]_
      * OpenOffice

   Tryton Client
      The *Tryton client* application is the graphical user interface (GUI)
      of the :term:`Tryton server`.

   Views
      A *view* is the visual presentation of :term:`data`.
      *Views* resides inside :term:`tabs` in the :term:`main frame` of the
      :term:`Tryton client`. There are two general types of *views* in Tryton:

      1. :term:`Form`
      2. :term:`Board`

      Each of the view types has different modes to show data. *Views*
      are built of several :term:`widgets` and provide often additional
      :term:`actions`. It is also possible to present the same data in
      different view modes alternately.

   Widgets
      A *Widget* is a visual element of a graphical user interface (GUI). Some
      *Widgets* solely show information, others allow manipulation from user
      side. Example *Widgets* are buttons, check-boxes, entry-boxes, selection
      lists, tables, lists, trees, ...

   Wizards
      *Wizards* define stateful sequences of interaction to proceed
      complex :term:`actions`. A *wizard* divides the complexity of some actions
      into several user guided steps.

References
**********

.. [WP-XMLRPC] http://en.wikipedia.org/wiki/Xmlrpc

.. [WP-WebDAV] http://en.wikipedia.org/wiki/Webdav

.. [WP-CSV] http://en.wikipedia.org/wiki/Comma-separated_values
.. [WP-ENCOD] http://en.wikipedia.org/wiki/Character_encoding


