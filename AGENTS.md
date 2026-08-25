# Repository rules

## No Python implementation code

Never use Python to implement functionality in this repository. Production
features—including languages, dialects, readers, parsers, converters, compiler
paths, runtimes, applications, and command-line tools—must be implemented in
Coil or in the implementation language explicitly chosen by the user.

Python is permitted only for test harnesses and repository-development tooling
that is not required by, invoked by, or shipped as part of the implemented
functionality. A Coil program must never shell out to Python to implement its
behavior.

If an existing implementation violates this rule, do not extend it. Replace the
production Python path before claiming the work is complete.
