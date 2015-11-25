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
    buildinstall_upgrade_image = True


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

* bootable (*bool*) -- 
* buildinstall_method (*str*) -- "lorax" (f16+, rhel7+) or "buildinstall" (older releases)
* buildinstall_upgrade_image (*bool*) -- build upgrade images, applicable on "lorax" buildinstall method

Example::

    bootable = True
    buildinstall_method = "lorax"


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
    (*list*) -- config for koji image-build; format: [(variant_uid_regex, {arch|*: [{opt: value}])]

.. note::
    Config can contain anything what is accepted by
    koji image-build --config configfile.ini
    Repo is currently the only option which is being automatically transformed
    into a string.

    Please don't set install_tree as it would get overriden by pungi.
    The 'format' attr is [('image_type', 'image_suffix'), ...].
    productmd should ideally contain all of image types and suffixes.

Example
-------
::

    image_build = [
        ('^Server$', {
            'x86_64': [
                {
                    'format': [('docker', 'tar.gz'), ('qcow2', 'qcow2')]
                    'name': 'fedora-qcow-and-docker-base',
                    'target': 'koji-target-name',
                    'ksversion': 'F23', # value from pykickstart
                    'version': '23',
                    'ksurl': 'https://git.fedorahosted.org/git/spin-kickstarts.git?somedirectoryifany#HEAD',
                    'kickstart': "fedora-docker-base.ks",
                    'repo': ["http://someextrarepos.org/repo", "ftp://rekcod.oi/repo].
    #               'install_tree': 'http://sometpath',  # this is set automatically by pungi to os_dir for given variant/$arch 
                    'distro': 'Fedora-20',
                    'disk_size': 3
                },
                {
                    'format': [('qcow2','qcow2')]
                    'name': 'fedora-qcow-base',
                    'target': 'koji-target-name',
                    'ksversion': 'F23', # value from pykickstart
                    'version': '23',
                    'ksurl': 'https://git.fedorahosted.org/git/spin-kickstarts.git?somedirectoryifany#HEAD',
                    'kickstart': "fedora-docker-base.ks",
                    'distro': 'Fedora-23'
                }
            ]
       }),
    ]


Media Checksums Settings
========================

**media_checksums**
    (*list*) -- list of checksum types to compute, allowed values are ``md5``,
    ``sha1`` and ``sha256``

**media_checksum_one_file**
    (*bool*) -- when ``True``, only one ``CHECKSUM`` file will be created per
    directory; this option requires ``media_checksums`` to only specify one
    type

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


Progress notification
=====================

*Pungi* has the ability to emit notification messages about progress and
status. These can be used to e.g. send messages to *fedmsg*. This is
implemented by actually calling a separate script.

The script will be called with one argument describing action that just
happened. A JSON-encoded object will be passed to standard input to provide
more information about the event. At least, the object will contain a
``compose_id`` key.

Currently these messages are sent:

 * ``start`` -- when composing starts
 * ``abort`` -- when compose is aborted due to incorrect configuration
 * ``finish`` -- on successful finish of compose
 * ``doomed`` -- when an error happens
 * ``phase-start`` -- on start of a phase
 * ``phase-stop`` -- when phase is finished

For phase related messages ``phase_name`` key is provided as well.

The script is invoked in compose directory and can read other information
there.

A ``pungi-fedmsg-notification`` script is provided and understands this
interface.

Config options
--------------

**notification_script**
    (*str*) -- executable to be invoked to send the message
