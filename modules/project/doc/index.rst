Project Module
##############

The Project module provides the concepts of project and task and the
basis for simple project management.


Work
****

The Work model from the Timesheet module is extended and is used for
creating both projects and tasks. This allows for instance to
transform a task into a project if it gets bigger and need to be
split. The following fields are added to the work model:


- Type: Can be *Project* or *Task*.
- State: Can be *Opened* or *Done*.
- Parent and Children: Define the tree structure of projects and
  tasks.
- Party and Party Address: The optional party (and the contact
  address) for which the project is made. Available on projects.
- Effort: The estimated effort of a task.
- Total Effort: Available on projects. Gives the total effort of the
  sub-tasks (I.E. tasks of the project and tasks of the sub-projects)
  of the current project.
- Timesheet Lines: The list of timesheet lines associated to the
  current project or the current task.
- Comment: A description.
