Account Dunning Module
######################

The account_dunning module adds dunning for receivable move lines.

Procedure
*********

A *Procedure* defines the dunning process with an ordered list of levels.
A dunning will raise from one level to an other by selecting the next level
that pass the test.
The Procedure is set per *Party* and a default one can be configured in the
accounting configuration.

Level
*****

A *Level* defines the parameters to reach it:

- Days: The number of overdue days.

Dunning
*******

A *Dunning* defines the dunning level of an overdue move line. Once processed,
it triggers the communication defined on the procedure level. It is mainly
defined by:

- Line: The overdue move line
- Procedure: The *Procedure* followed.
- Level: The current *Level*.
- Blocked: If true, it blocks the dunning to raise.

The dunning can be in one of this states:

* Draft

  The current level is not yet processed.

* Done

  The current level has been processed.
