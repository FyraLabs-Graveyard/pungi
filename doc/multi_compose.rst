.. _multi_compose:

Managing compose from multiple parts
====================================

There may be cases where it makes sense to split a big compose into separate
parts, but create a compose output that links all output into one familiar
structure.

The `pungi-orchestrate` tools allows that.

It works with an INI-style configuration file. The ``[general]`` section
contains information about identity of the main compose. Other sections define
individual parts.

The parts are scheduled to run in parallel, with the minimal amount of
serialization. The final compose directory will contain hard-links to the
files.


General settings
----------------

**target**
   Path to directory where the final compose should be created.
**compose_type**
   Type of compose to make.
**release_name**
   Name of the product for the final compose.
**release_short**
   Short name of the product for the final compose.
**release_version**
   Version of the product for the final compose.
**release_type**
   Type of the product for the final compose.
**extra_args**
   Additional arguments that wil be passed to the child Pungi processes.
**koji_profile**
   If specified, a current event will be retrieved from the Koji instance and
   used for all parts.


Partial compose settings
------------------------

Each part should have a separate section in the config file.

It can specify these options:

**config**
   Path to configuration file that describes this part. If relative, it is
   resolved relative to the file with parts configuration.
**just_phase**, **skip_phase**
   Customize which phases should run for this part.
**depends_on**
   A comma separated list of other parts that must be finished before this part
   starts.
**failable**
   A boolean toggle to mark a part as failable. A failure in such part will
   mark the final compose as incomplete, but still successful.
