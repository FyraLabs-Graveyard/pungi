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


Example
-------
::

    gather_source = "comps"
    gather_method = "deps"
    greedy_method = "build"
    multilib_methods = ["devel", "runtime"]
    multilib_arches = ["ppc64", "s390x", "x86_64"]
    check_deps = False

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

.. note::

    Source architecture needs to be listed explicitly.
    Excluding '*' applies only on binary arches.


Example
-------
::

    createiso_skip = [
        ('^Workstation$', {
            '*': True,
            'src': True
        }),
    ]
