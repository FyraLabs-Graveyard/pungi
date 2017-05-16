==================
Gathering packages
==================

A compose created by Pungi consists of one or more variants. A variant contains
a subset of the content targeted at a particular use case.

There are different types of variants. The type affects how packages are
gathered into the variant.

The inputs for gathering are defined by the ``gather_source`` option. It
provides a list of package names, comps groups names and a list of packages
that should be filtered out.

Next, ``gather_method`` defines how the list is processed. For ``nodeps``, the
results from source are used pretty much as is [#]_. For ``deps`` method, a
process will be launched to figure out what dependencies are needed and those
will be pulled in.

.. [#] The lists are filtered based on what packages are available in the
   package set, but nothing else will be pulled in.


Variant types
=============

*Variant*
    is a base type that has no special behaviour.

*Addon*
    is built on top of a regular variant. Any packages that should go to both
    the addon and its parent will be removed from addon. Packages that are only
    in addon but pulled in because of ``gather_fulltree`` option will be moved
    to parent.

*Integrated Layered Product*
    works similarly to *addon*. Additionally, all packages from addons on the
    same parent variant are removed integrated layered products.

    The main difference between an *addon* and *integrated layered product* is
    that *integrated layered product* has its own identity in the metadata
    (defined with product name and version).

    .. note::
        There's also *Layered Product* as a term, but this is not related to
        variants. It's used to describe a product that is not a standalone
        operating system and is instead meant to be used on some other base
        system.

*Optional*
    contains packages that complete the base variants' package set. It always
    has ``fulltree`` and ``selfhosting`` enabled, so it contains build
    dependencies and packages which were not specifically requested for base
    variant.


Some configuration options are overridden for particular variant types.

.. table:: Depsolving configuration

   +-----------+--------------+--------------+
   | Variant   | Fulltree     | Selfhosting  |
   +===========+==============+==============+
   | base      | configurable | configurable |
   +-----------+--------------+--------------+
   | addon/ILP | enabled      | disabled     |
   +-----------+--------------+--------------+
   | optional  | enabled      | enabled      |
   +-----------+--------------+--------------+
