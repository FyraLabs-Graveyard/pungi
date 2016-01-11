===============
 Configuration
===============

Please read
`productmd documentation <http://release-engineering.github.io/productmd/index.html>`_
for
`terminology <http://release-engineering.github.io/productmd/terminology.html>`_
and other release and compose related details.


Minimal Config Example
======================
::

    # RELEASE
    release_name = "Fedora"
    release_short = "Fedora"
    release_version = "23"

    # GENERAL SETTINGS
    comps_file = "comps-f23.xml"
    variants_file = "variants-f23.xml"

    # KOJI
    koji_profile = "koji"
    runroot = False

    # PKGSET
    sigkeys = [None]
    pkgset_source = "koji"
    pkgset_koji_tag = "f23"

    # CREATEREPO
    createrepo_checksum = "sha256"

    # GATHER
    gather_source = "comps"
    gather_method = "deps"
    greedy_method = "build"
    multilib_methods = []
    check_deps = False

    # BUILDINSTALL
    bootable = True
    buildinstall_method = "lorax"


Release
=======
Following **mandatory** options describe a release.


Options
-------

**release_name** [mandatory]
    (*str*) -- release name

**release_short** [mandatory]
    (*str*) -- release short name, without spaces and special characters

**release_version** [mandatory]
    (*str*) -- release version

**release_type** = "ga"
    (*str*) -- release type, "ga" or "updates"

**release_is_layered** = False
    (*bool*) -- typically False for an operating system, True otherwise


Example
-------
::

    release_name = "Fedora"
    release_short = "Fedora"
    release_version = "23"
    # release_type = "ga"


Base Product
============
Base product options are **optional** and we need
to them only if we're composing a layered product
built on another (base) product.


Options
-------

**base_product_name**
    (*str*) -- base product name

**base_product_short**
    (*str*) -- base product short name, without spaces and special characters

**base_product_version**
    (*str*) -- base product **major** version


Example
-------
::

    release_name = "RPM Fusion"
    release_short = "rf"
    release_version = "23.0"

    release_is_layered = True

    base_product_name = "Fedora"
    base_product_short = "Fedora"
    base_product_version = "23"


General Settings
================

Options
-------

**comps_file** [mandatory]
    (*scm_dict*, *str* or None) -- reference to comps XML file with installation groups

**variants_file** [mandatory]
    (*scm_dict* or *str*) -- reference to variants XML file that defines release variants and architectures

**failable_deliverables** [optional]
    (*list*) -- list which deliverables on which variant and architecture can
    fail and not abort the whole compose

    Currently handled deliverables are:
     * buildinstall
     * iso
     * live

    Please note that ``*`` as a wildcard matches all architectures but ``src``.


Example
-------
::

    comps_file = {
        "scm": "git",
        "repo": "https://git.fedorahosted.org/git/comps.git",
        "branch": None,
        "file": "comps-f23.xml.in",
    }

    variants_file = {
        "scm": "git",
        "repo": "https://pagure.io/pungi-fedora.git ",
        "branch": None,
        "file": "variants-fedora.xml",
    }

    failable_deliverables = [
        ('^.*$', {
            # Buildinstall can fail on any variant and any arch
            '*': ['buildinstall'],
            'src': ['buildinstall'],
            # Nothing on i386 blocks the compose
            'i386': ['buildinstall', 'iso', 'live'],
        })
    ]


Image Naming
============

Both image name and volume id are generated based on the configuration. Since
the volume id is limited to 32 characters, there are more settings available.
The process for generating volume id is to get a list of possible formats and
try them sequentially until one fits in the length limit. If substitutions are
configured, each attempted volume id will be modified by it.

For layered products, the candidate formats are first
``image_volid_layered_product_formats`` followed by ``image_volid_formats``.
Otherwise, only ``image_volid_formats`` are tried.

If no format matches the length limit, an error will be reported and compose
aborted.

Options
-------

There a couple common format specifiers available for both the options:
 * compose_id
 * release_short
 * version
 * date
 * respin
 * type
 * type_suffix
 * label
 * label_major_version
 * variant
 * arch
 * disc_type

**image_name_format** [optional]
    (*str*) -- Python's format string to serve as template for image names

    This format will be used for all phases generating images. Currently that
    means ``createiso``, ``live_images`` and ``buildinstall``.

    Available extra keys are:
     * disc_num
     * suffix

**image_volid_formats** [optional]
    (*list*) -- A list of format strings for generating volume id.

    The extra available keys are:
     * base_product_short
     * base_product_version

**image_volid_layered_product_formats** [optional]
    (*list*) -- A listof format strings for generating volume id for layered
    products. The keys available are the same as for ``image_volid_formats``.

**volume_id_substitutions** [optional]
    (*dict*) -- A mapping of string replacements to shorten the volume id.

Example
-------
::

    # Image name respecting Fedora's image naming policy
    image_name_format = "%(release_short)s-%(variant)s-%(disc_type)s-%(arch)s-%(version)s%(suffix)s"
    # Use the same format for volume id
    image_volid_formats = [
        "%(release_short)s-%(variant)s-%(disc_type)s-%(arch)s-%(version)s"
    ]
    # No special handling for layered products, use same format as for regular images
    image_volid_layered_product_formats = []
    # Replace "Cloud" with "C" in volume id etc.
    volume_id_substitutions = {
        'Cloud': 'C',
        'Alpha': 'A',
        'Beta': 'B',
        'TC': 'T',
    }


Createrepo Settings
===================


Options
-------

**createrepo_checksum** [mandatory]
    (*str*) -- specify checksum type for createrepo; expected values: sha256, sha

**createrepo_c** = True
    (*bool*) -- use createrepo_c (True) or legacy createrepo (False)



Example
-------
::

    createrepo_checksum = "sha256"


Package Set Settings
====================


Options
-------

**sigkeys**
    ([*str* or None]) -- priority list of sigkeys, *None* means unsigned

**pkgset_source** [mandatory]
    (*str*) -- "koji" (any koji instance) or "repos" (arbitrary yum repositories)

**pkgset_koji_tag** [mandatory]
    (*str*) -- tag to read package set from

**pkgset_koji_inherit** = True
    (*bool*) -- inherit builds from parent tags; we can turn it off only if we have all builds tagged in a single tag


Example
-------
::

    sigkeys = [None]
    pkgset_source = "koji"
    pkgset_koji_tag = "f23"


Buildinstall Settings
=====================
Script or process that creates bootable images with
Anaconda installer is historically called
`buildinstall <https://git.fedorahosted.org/cgit/anaconda.git/tree/scripts/buildinstall?h=f15-branch>`_.

Options:
--------

**bootable**
    (*bool*) -- whether to run the buildinstall phase
**buildinstall_method**
    (*str*) -- "lorax" (f16+, rhel7+) or "buildinstall" (older releases)
**buildinstall_upgrade_image** [deprecated]
    (*bool*) -- use ``noupgrade`` with ``lorax_options`` instead
**lorax_options**
    (*list*) -- special options passed on to *lorax*.

    Format: ``[(variant_uid_regex, {arch|*: {option: name}})]``.

    Recognized options are:
      * ``bugurl`` -- *str* (default ``None``)
      * ``nomacboot`` -- *bool* (default ``True``)
      * ``noupgrade`` -- *bool* (default ``True``)

Example
-------
::

    bootable = True
    buildinstall_method = "lorax"

    # Enables macboot on x86_64 for all variants and builds upgrade images
    # everywhere.
    lorax_options = [
        ("^.*$", {
            "x86_64": {
                "nomacboot": False
            }
            "*": {
                "noupgrade": False
            }
        })
    ]


.. note::

    It is advised to run buildinstall (lorax) in koji,
    i.e. with **runroot enabled** for clean build environments, better logging, etc.


.. warning::

    Lorax installs RPMs into a chroot. This involves running %post scriptlets
    and they frequently run executables in the chroot.
    If we're composing for multiple architectures, we **must** use runroot for this reason.


Gather Settings
===============

Options
-------

**gather_source** [mandatory]
    (*str*) -- from where to read initial package list; expected values: "comps", "none"

**gather_method** [mandatory]
    (*str*) -- "deps", "nodeps"

**greedy_method**
    (*str*) -- see :doc:`gather`, recommended value: "build"

**multilib_methods** = []
    ([*str*]) -- see :doc:`gather`, recommended value: ["devel", "runtime"]

**multilib_arches**
    ([*str*] or None) -- list of compose architectures entitled for multilib; set to None to apply multilib on all compose arches

**additional_packages**
    (*list*) -- additional packages to be included in a variant and architecture; format: [(variant_uid_regex, {arch|*: [package_globs]})]

**filter_packages**
    (*list*) -- packages to be excluded from a variant and architecture; format: [(variant_uid_regex, {arch|*: [package_globs]})]

**multilib_blacklist**
    (*dict*) -- multilib blacklist; format: {arch|*: [package_globs]}

**multilib_whitelist**
    (*dict*) -- multilib blacklist; format: {arch|*: [package_globs]}

**gather_lookaside_repos** = []
    (*list*) -- lookaside repositories used for package gathering; format: [(variant_uid_regex, {arch|*: [repo_urls]})]

**hashed_directories** = False
    (*bool*) -- put packages into "hashed" directories, for example Packages/k/kernel-4.0.4-301.fc22.x86_64.rpm


Example
-------
::

    gather_source = "comps"
    gather_method = "deps"
    greedy_method = "build"
    multilib_methods = ["devel", "runtime"]
    multilib_arches = ["ppc64", "s390x", "x86_64"]
    check_deps = False
    hashed_directories = True

    additional_packages = [
        # bz#123456
        ('^(Workstation|Server)$', {
            '*': [
                'grub2',
                'kernel',
            ],
        }),
    ]

    filter_packages = [
        # bz#111222
        ('^.*$', {
            '*': [
                'kernel-doc',
            ],
        }),
    ]

    multilib_blacklist = {
        "*": [
            "gcc",
        ],
    }

    multilib_whitelist = {
        "*": [
            "alsa-plugins-*",
        ],
    }

    # gather_lookaside_repos = [
    #     ('^.*$', {
    #         'x86_64': [
    #             "https://dl.fedoraproject.org/pub/fedora/linux/releases/22/Everything/x86_64/os/",
    #             "https://dl.fedoraproject.org/pub/fedora/linux/releases/22/Everything/source/SRPMS/",
    #         ]
    #     }),
    # ]


.. note::

   It is a good practice to attach bug/ticket numbers
   to additional_packages, filter_packages, multilib_blacklist and multilib_whitelist
   to track decisions.


Koji Settings
=============


Options
-------

**koji_profile**
    (*str*) -- koji profile name

**runroot** [mandatory]
    (*bool*) -- run some tasks such as buildinstall or createiso in koji build root (True) or locally (False)

**runroot_channel**
    (*str*) -- name of koji channel

**runroot_tag**
    (*str*) -- name of koji **build** tag used for runroot


Example
-------
::

    koji_profile = "koji"
    runroot = True
    runroot_channel = "runroot"
    runroot_tag = "f23-build"


Extra Files Settings
====================


Options
-------

**extra_files**
    (*list*) -- references to external files to be placed in os/ directory and media; format: [(variant_uid_regex, {arch|*: [scm_dicts]})]


Example
-------
::

    extra_files = [
        ('^.*$', {
            '*': [
                # GPG keys
                {
                    "scm": "rpm",
                    "repo": "fedora-repos",
                    "branch": None,
                    "file": [
                        "/etc/pki/rpm-gpg/RPM-GPG-KEY-22-fedora",
                    ],
                    "target": "",
                },
                # GPL
                {
                    "scm": "git",
                    "repo": "https://pagure.io/pungi-fedora",
                    "branch": None,
                    "file": [
                        "GPL",
                    ],
                    "target": "",
                },
            ],
        }),
    ]


Productimg Settings
===================
Product images are placed on installation media and provide additional branding
and Anaconda changes specific to product variants.

Options
-------

**productimg** = False
    (*bool*) -- create product images; requires bootable=True

**productimg_install_class**
    (*scm_dict*, *str*) -- reference to install class **file**

**productimg_po_files**
    (*scm_dict*, *str*) -- reference to a **directory** with po files for install class translations


Example
-------
::

    productimg = True
    productimg_install_class = {
        "scm": "git",
        "repo": "http://git.example.com/productimg.git",
        "branch": None,
        "file": "fedora23/%(variant_id)s.py",
    }
    productimg_po_files = {
        "scm": "git",
        "repo": "http://git.example.com/productimg.git",
        "branch": None,
        "dir": "po",
    }


CreateISO Settings
==================

Options
-------

**createiso_skip** = False
    (*list*) -- mapping that defines which variants and arches to skip during createiso; format: [(variant_uid_regex, {arch|*: True})]

**create_jigdo** = True
    (*bool*) -- controls the creation of jigdo from ISO

.. note::

    Source architecture needs to be listed explicitly.
    Excluding '*' applies only on binary arches.
    Jigdo causes significant increase of time to ISO creation.


Example
-------
::

    createiso_skip = [
        ('^Workstation$', {
            '*': True,
            'src': True
        }),
    ]

Image Build Settings
====================

**image_build**
    (*dict*) -- config for ``koji image-build``; format: {variant_uid_regex: [{opt: value}]}

    By default, images will be built for each binary arch valid for the
    variant. The config can specify a list of arches to narrow this down.

.. note::
    Config can contain anything what is accepted by
    ``koji image-build --config configfile.ini``

    Repo can be specified either as a string or a list of strings. It will
    automatically transformed into format suitable for ``koji``. A repo for the
    currently built variant will be added as well.

    You can also add extra variants to get repos from with key ``repo_from``.
    The value should be a list of variant names.

    Please don't set ``install_tree``. This gets automatically set by *pungi*
    based on current variant. You can use ``install_tree_from`` key to use
    install tree from another variant.

    The ``format`` attr is [('image_type', 'image_suffix'), ...].
    See productmd documentation for list of supported types and suffixes.

    If ``ksurl`` ends with ``#HEAD``, Pungi will figure out the SHA1 hash of
    current HEAD and use that instead.


Example
-------
::

    image_build = {
        '^Server$': [
            {
                'format': [('docker', 'tar.gz'), ('qcow2', 'qcow2')]
                'name': 'fedora-qcow-and-docker-base',
                'target': 'koji-target-name',
                'ksversion': 'F23',     # value from pykickstart
                'version': '23',
                # correct SHA1 hash will be put into the URL below automatically
                'ksurl': 'https://git.fedorahosted.org/git/spin-kickstarts.git?somedirectoryifany#HEAD',
                'kickstart': "fedora-docker-base.ks",
                'repo': ["http://someextrarepos.org/repo", "ftp://rekcod.oi/repo].
                'distro': 'Fedora-20',
                'disk_size': 3,

                # this is set automatically by pungi to os_dir for given variant
                # 'install_tree': 'http://sometpath',
            },
            {
                'format': [('qcow2','qcow2')]
                'name': 'fedora-qcow-base',
                'target': 'koji-target-name',
                'ksversion': 'F23',     # value from pykickstart
                'version': '23',
                'ksurl': 'https://git.fedorahosted.org/git/spin-kickstarts.git?somedirectoryifany#HEAD',
                'kickstart': "fedora-docker-base.ks",
                'distro': 'Fedora-23',

                # only build this type of image on x86_64
                'arches': ['x86_64']

                # Use install tree and repo from Everything variant.
                'install_tree_from': 'Everything',
                'repo_from': ['Everything'],
            }
        ]
    }


Media Checksums Settings
========================

**media_checksums**
    (*list*) -- list of checksum types to compute, allowed values are ``md5``,
    ``sha1`` and ``sha256``

**media_checksum_one_file**
    (*bool*) -- when ``True``, only one ``CHECKSUM`` file will be created per
    directory; this option requires ``media_checksums`` to only specify one
    type

**media_checksum_base_filename**
    (*str*) -- when not set, all checksums will be save to a file named either
    ``CHECKSUM`` or based on the digest type; this option allows adding any
    prefix to that name

    It is possible to use format strings that will be replace by actual values.
    The allowed keys are ``%(release_showrt)s``, ``%(release_short)s``,
    ``%(release_id)s``, ``%(variant)s``, ``%(version)s``, ``%(date)s``,
    ``%(type_suffix)s`` and ``%(respin)s``

    For example, for Fedora the prefix should be
    ``%(release_short)s-%(variant)s-%(version)s-%(date)s%(type_suffix)s.%(respin)s``.


Translate Paths Settings
========================

**translate_paths**
    (*list*) -- list of paths to translate; format: [(path,translated_path)]

.. note::
    This feature becomes useful when you need to transform compose location
    into e.g. a http repo which is can be passed to koji image-build.
    Translation needs to be invoked by a function call in pungi.
    os.path.normpath() is applied on both path and translated_path
    

Example config
--------------
::

    translate_paths = [
        ("/mnt/a", "http://b/dir"),
    ]

Example usage
-------------
::

    >>> from pungi.paths import translate_paths
    >>> print translate_paths(compose_object_with_mapping, "/mnt/a/c/somefile")
    http://b/dir/c/somefile
