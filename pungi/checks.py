# -*- coding: utf-8 -*-


# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
This module exports a couple functions for checking configuration and
environment.

Validation of the configuration is the most complicated part here: here is the
outline of the process:

1. The configuration is checked against JSON schema. The errors encountered are
   reported as string. The validator also populates default values.

2. The requirements/conflicts among options are resolved separately. This is
   because expressing those relationships in JSON Schema is very verbose and
   the error message is not very descriptive.

3. Extra validation can happen in ``validate()`` method of any phase.

When a new config option is added, the schema must be updated (see the
``_make_schema`` function). The dependencies should be encoded into
``CONFIG_DEPS`` mapping.
"""

import os.path
import platform
import jsonschema

from . import util


def _will_productimg_run(conf):
    return conf.get('productimg', False) and conf.get('bootable', False)


def is_jigdo_needed(conf):
    return conf.get('create_jigdo', True)


def is_isohybrid_needed(conf):
    """The isohybrid command is needed locally only for productimg phase and
    createiso phase without runroot. If that is not going to run, we don't need
    to check for it. Additionally, the syslinux package is only available on
    x86_64 and i386.
    """
    runroot = conf.get('runroot', False)
    if runroot and not _will_productimg_run(conf):
        return False
    if platform.machine() not in ('x86_64', 'i686', 'i386'):
        msg = ('Not checking for /usr/bin/isohybrid due to current architecture. '
               'Expect failures in productimg phase.')
        print msg
        return False
    return True


def is_genisoimage_needed(conf):
    """This is only needed locally for productimg and createiso without runroot.
    """
    runroot = conf.get('runroot', False)
    if runroot and not _will_productimg_run(conf):
        return False
    return True

# The first element in the tuple is package name expected to have the
# executable (2nd element of the tuple). The last element is an optional
# function that should determine if the tool is required based on
# configuration.
tools = [
    ("isomd5sum", "/usr/bin/implantisomd5", None),
    ("isomd5sum", "/usr/bin/checkisomd5", None),
    ("jigdo", "/usr/bin/jigdo-lite", is_jigdo_needed),
    ("genisoimage", "/usr/bin/genisoimage", is_genisoimage_needed),
    ("gettext", "/usr/bin/msgfmt", None),
    ("syslinux", "/usr/bin/isohybrid", is_isohybrid_needed),
    ("yum-utils", "/usr/bin/createrepo", None),
    ("yum-utils", "/usr/bin/mergerepo", None),
    ("yum-utils", "/usr/bin/repoquery", None),
    ("git", "/usr/bin/git", None),
    ("cvs", "/usr/bin/cvs", None),
]

imports = [
    ("kobo", "kobo"),
    ("kobo-rpmlib", "kobo.rpmlib"),
    ("python-lxml", "lxml"),
    ("koji", "koji"),
    ("python-productmd", "productmd"),
]


def check(conf):
    """Check runtime environment and report errors about missing dependencies."""
    fail = False

    # Check python modules
    for package, module in imports:
        try:
            __import__(module)
        except ImportError:
            print("Module '%s' doesn't exist. Install package '%s'." % (module, package))
            fail = True

    # Check tools
    for package, path, test_if_required in tools:
        if test_if_required and not test_if_required(conf):
            # The config says this file is not required, so we won't even check it.
            continue
        if not os.path.exists(path):
            print("Program '%s' doesn't exist. Install package '%s'." % (path, package))
            fail = True

    return not fail


def check_umask(logger):
    """Make sure umask is set to something reasonable. If not, log a warning."""
    mask = os.umask(0)
    os.umask(mask)

    if mask > 0o022:
        logger.warning('Unusually strict umask detected (0%03o), '
                       'expect files with broken permissions.', mask)


def _validate_requires(schema, conf, valid_options):
    """
    Check if all requires and conflicts are ok in configuration.

    :param conf: Python dict with configuration to check
    :param valid_options: mapping with option dependencies
    :param with_default: a set of options that have default value
    :returns: list of errors
    """
    errors = []

    def has_default(x):
        return schema['properties'].get(x, {}).get('default') == conf[x]

    for name, opt in valid_options.iteritems():
        value = conf.get(name)

        errors.extend(_check_dep(name, value, opt.get('conflicts', []),
                                 lambda x: x in conf and not has_default(x), CONFLICTS))
        errors.extend(_check_dep(name, value, opt.get('requires', []),
                                 lambda x: x not in conf, REQUIRES))

    return errors


def _check_dep(name, value, lst, matcher, fmt):
    for deps in [deps for (func, deps) in lst if func(value)]:
        for dep in [d for d in deps if matcher(d)]:
            yield fmt.format(name, value, dep)


def validate(config):
    """Test the configuration against schema.

    Undefined values for which a default value exists will be filled in.
    """
    schema = _make_schema()
    DefaultValidator = _extend_with_default(jsonschema.Draft4Validator)
    validator = DefaultValidator(schema, {'array': (tuple, list)})
    errors = []
    for error in validator.iter_errors(config):
        if isinstance(error, ConfigDeprecation):
            errors.append(DEPRECATED.format('.'.join(error.path), error.message))
        else:
            if not error.path and error.validator == 'additionalProperties':
                allowed_keys = set(error.schema['properties'].keys())
                used_keys = set(error.instance.keys())
                for key in used_keys - allowed_keys:
                    suggestion = _get_suggestion(key, allowed_keys)
                    if suggestion:
                        errors.append(UNKNOWN_SUGGEST.format(key, suggestion))
                    else:
                        errors.append(UNKNOWN.format(key))
            else:
                errors.append('Failed validation in %s: %s' % (
                    '.'.join([str(x) for x in error.path]), error.message))
    return errors + _validate_requires(schema, config, CONFIG_DEPS)


def _get_suggestion(desired, names):
    """Find a value in ``names`` that is the closest match for ``desired``.

    The edit distance must be at most half the length of target string.
    """
    closest = None
    closest_match = len(desired) + 1
    for name in names:
        match = util.levenshtein(desired, name)
        if match < closest_match and match < len(desired) // 2:
            closest = name
            closest_match = match

    return closest


CONFLICTS = 'Config option {0}={1} conflicts with option {2}.'
REQUIRES = 'Config option {0}={1} requires {2} which is not set.'
DEPRECATED = 'Deprecated config option: {0}; {1}.'
UNKNOWN = 'Unrecognized config option: {0}.'
UNKNOWN_SUGGEST = 'Unrecognized config option: {0}. Did you mean {1}?'


def _extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.iteritems():
            if "default" in subschema and property not in instance:
                instance.setdefault(property, subschema["default"])

        for error in validate_properties(validator, properties, instance, schema):
            yield error

    def error_on_deprecated(validator, properties, instance, schema):
        yield ConfigDeprecation(
            'use %s instead' % properties
        )

    return jsonschema.validators.extend(
        validator_class, {"properties": set_defaults,
                          "deprecated": error_on_deprecated},
    )


class ConfigDeprecation(jsonschema.exceptions.ValidationError):
    pass


def _make_schema():
    return {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Pungi Configuration",

        "definitions": {
            "multilib_list": {
                "type": "object",
                "patternProperties": {
                    "^.+$": {"$ref": "#/definitions/list_of_strings"},
                },
                "additionalProperties": False,
            },

            "package_mapping": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": [
                        {
                            "type": "string",
                        },
                        {
                            "type": "object",
                            "patternProperties": {
                                ".+": {"$ref": "#/definitions/list_of_strings"},
                            },
                            "additionalProperties": False,
                        }
                    ],
                    "additionalItems": False,
                },
            },

            "scm_dict": {
                "type": "object",
                "properties": {
                    "scm": {
                        "type": "string",
                        "enum": ["file", "cvs", "git", "rpm"],
                    },
                    "repo": {"type": "string"},
                    "branch": {"type": "string"},
                    "file": {"type": "string"},
                    "dir": {"type": "string"},
                },
                "additionalProperties": False,
            },

            "str_or_scm_dict": {
                "anyOf": [
                    {"type": "string"},
                    {"$ref": "#/definitions/scm_dict"},
                ]
            },

            "list_of_strings": {
                "type": "array",
                "items": {"type": "string"},
            },

            "strings": {
                "anyOf": [
                    {"type": "string"},
                    {"$ref": "#/definitions/list_of_strings"},
                ]
            },

            "optional_string": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"},
                ],
            },

            "live_image_config": {
                "type": "object",
                "properties": {
                    "kickstart": {"type": "string"},
                    "ksurl": {"type": "string"},
                    "name": {"type": "string"},
                    "subvariant": {"type": "string"},
                    "version": {"type": "string"},
                    "additional_repos": {"$ref": "#/definitions/strings"},
                    "repo_from": {"$ref": "#/definitions/strings"},
                    "specfile": {"type": "string"},
                    "scratch": {"type": "boolean"},
                    "type": {"type": "string"},
                    "sign": {"type": "boolean"},
                    "failable": {"type": "boolean"},
                    "release": {"$ref": "#/definitions/optional_string"},
                },
                "required": ["kickstart"],
                "additionalProperties": False,
                "type": "object",
            },

            "string_tuples": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": [
                        {"type": "string"},
                        {"type": "string"},
                    ],
                    "additionalItems": False,
                }
            }
        },

        "type": "object",
        "properties": {
            "release_name": {"type": "string"},
            "release_short": {"type": "string"},
            "release_version": {"type": "string"},
            "release_type": {
                "type": "string",
                "enum": ["fast", "ga", "updates", "eus", "aus", "els"],
                "default": "ga",
            },
            "release_is_layered": {"type": "boolean"},
            "release_discinfo_description": {"type": "string"},

            "base_product_name": {"type": "string"},
            "base_product_short": {"type": "string"},
            "base_product_version": {"type": "string"},
            "base_product_type": {
                "type": "string",
                "default": "ga"
            },

            "runroot": {
                "type": "boolean",
                "default": False,
            },
            "create_jigdo": {
                "type": "boolean",
                "default": True,
            },
            "check_deps": {
                "type": "boolean",
                "default": True
            },
            "bootable": {
                "type": "boolean",
                "default": False
            },

            "gather_method": {
                "type": "string",
                "enum": ["deps", "nodeps"],
            },
            "gather_source": {
                "type": "string",
                "enum": ["json", "comps", "none"],
            },
            "gather_fulltree": {
                "type": "boolean",
                "default": False,
            },
            "gather_selfhosting": {
                "type": "boolean",
                "default": False,
            },
            "gather_prepopulate": {"$ref": "#/definitions/str_or_scm_dict"},
            "gather_source_mapping": {"type": "string"},

            "pkgset_source": {
                "type": "string",
                "enum": ["koji", "repos"],
            },

            "createrepo_c": {
                "type": "boolean",
                "default": True,
            },
            "createrepo_checksum": {
                "type": "string",
                "enum": ["sha", "sha256"],
            },
            "createrepo_use_xz": {
                "type": "boolean",
                "default": False,
            },

            "hashed_directories": {
                "type": "boolean",
                "default": False,
            },
            "multilib_whitelist": {
                "$ref": "#/definitions/multilib_list",
                "default": {},
            },
            "multilib_blacklist": {
                "$ref": "#/definitions/multilib_list",
                "default": {},
            },
            "greedy_method": {
                "type": "string",
                "enum": ["none", "all", "build"],
                "default": "none",
            },
            "additional_packages": {
                "$ref": "#/definitions/package_mapping",
                "default": [],
            },
            "filter_packages": {
                "$ref": "#/definitions/package_mapping",
                "default": [],
            },
            "sigkeys": {
                "type": "array",
                "items": {"$ref": "#/definitions/optional_string"},
            },
            "variants_file": {"$ref": "#/definitions/str_or_scm_dict"},
            "comps_file": {"$ref": "#/definitions/str_or_scm_dict"},
            "comps_filter_environments": {
                "type": "boolean",
                "default": True
            },

            "pkgset_repos": {
                "type": "object",
                "patternProperties": {
                    ".+": {"$ref": "#/definitions/strings"},
                },
                "additionalProperties": False,
            },
            "create_optional_isos": {
                "type": "boolean",
                "default": False
            },
            "symlink_isos_to": {"type": "string"},
            "createiso_skip": _variant_arch_mapping({"type": "boolean"}),
            "multilib": _variant_arch_mapping({
                "$ref": "#/definitions/list_of_strings"
            }),

            "runroot_tag": {"type": "string"},
            "runroot_channel": {
                "$ref": "#/definitions/optional_string",
            },
            "createrepo_deltas": {
                "type": "boolean",
                "default": False,
            },

            "buildinstall_method": {
                "type": "string",
                "enum": ["lorax", "buildinstall"],
            },
            "buildinstall_kickstart": {"$ref": "#/definitions/str_or_scm_dict"},

            "global_ksurl": {"type": "string"},
            "global_version": {"type": "string"},
            "global_target": {"type": "string"},
            "global_release": {"$ref": "#/definitions/optional_string"},

            "koji_profile": {"type": "string"},

            "pkgset_koji_tag": {"type": "string"},
            "pkgset_koji_inherit": {
                "type": "boolean",
                "default": True
            },

            "disc_types": {
                "type": "object",
                "default": {},
            },

            "paths_module": {"type": "string"},
            "skip_phases": {
                "$ref": "#/definitions/list_of_strings",
                "default": [],
            },

            "image_name_format": {"type": "string"},
            "image_volid_formats": {
                "$ref": "#/definitions/list_of_strings",
                "default": [
                    "{release_short}-{version} {variant}.{arch}",
                    "{release_short}-{version} {arch}",
                ],
            },
            "image_volid_layered_product_formats": {
                "$ref": "#/definitions/list_of_strings",
                "default": [
                    "{release_short}-{version} {base_product_short}-{base_product_version} {variant}.{arch}",
                    "{release_short}-{version} {base_product_short}-{base_product_version} {arch}",
                ],
            },
            "volume_id_substitutions": {
                "type": "object",
                "default": {},
            },

            "live_images_no_rename": {
                "type": "boolean",
                "default": False,
            },
            "live_images_ksurl": {"type": "string"},
            "live_images_release": {"$ref": "#/definitions/optional_string"},
            "live_images_version": {"type": "string"},

            "image_build_ksurl": {"type": "string"},
            "image_build_target": {"type": "string"},
            "image_build_release": {"$ref": "#/definitions/optional_string"},
            "image_build_version": {"type": "string"},

            "live_media_ksurl": {"type": "string"},
            "live_media_target": {"type": "string"},
            "live_media_release": {"$ref": "#/definitions/optional_string"},
            "live_media_version": {"type": "string"},

            "media_checksums": {
                "$ref": "#/definitions/list_of_strings",
                "default": ['md5', 'sha1', 'sha256']
            },
            "media_checksum_one_file": {
                "type": "boolean",
                "default": False
            },
            "media_checksum_base_filename": {
                "type": "string",
                "default": ""
            },

            "filter_system_release_packages": {
                "type": "boolean",
                "default": True,
            },
            "keep_original_comps": {
                "deprecated": "no <groups> tag for respective variant in variants XML"
            },

            "link_type": {
                "type": "string",
                "enum": ["hardlink", "copy", "hardlink-or-copy", "symlink", "abspath-symlink"],
                "default": "hardlink-or-copy"
            },

            "product_id": {"$ref": "#/definitions/str_or_scm_dict"},
            "product_id_allow_missing": {
                "type": "boolean",
                "default": False
            },

            "live_target": {
                "type": "string",
                "default": "rhel-7.0-candidate",
            },

            "tree_arches": {
                "$ref": "#/definitions/list_of_strings",
                "default": []
            },
            "tree_variants": {
                "$ref": "#/definitions/list_of_strings",
                "default": []
            },

            "translate_paths": {
                "$ref": "#/definitions/string_tuples",
                "default": [],
            },

            "failable_deliverables": _variant_arch_mapping({
                "$ref": "#/definitions/list_of_strings"
            }),

            "live_media": {
                "type": "object",
                "patternProperties": {
                    ".+": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "install_tree_from": {"type": "string"},
                                "kickstart": {"type": "string"},
                                "ksversion": {"type": "string"},
                                "ksurl": {"type": "string"},
                                "version": {"type": "string"},
                                "scratch": {"type": "boolean"},
                                "skip_tag": {"type": "boolean"},
                                "name": {"type": "string"},
                                "subvariant": {"type": "string"},
                                "title": {"type": "string"},
                                "repo": {"$ref": "#/definitions/strings"},
                                "repo_from": {"$ref": "#/definitions/strings"},
                                "target": {"type": "string"},
                                "arches": {"$ref": "#/definitions/list_of_strings"},
                                "failable": {"$ref": "#/definitions/list_of_strings"},
                                "release": {"$ref": "#/definitions/optional_string"},
                            },
                            "required": ["name", "kickstart"],
                            "additionalProperties": False,
                        },
                    }
                },
                "additionalProperties": False,
            },

            "ostree": _variant_arch_mapping({
                "type": "object",
                "properties": {
                    "treefile": {"type": "string"},
                    "config_url": {"type": "string"},
                    "source_repo_from": {"type": "string"},
                    "ostree_repo": {"type": "string"},
                    "failable": {"$ref": "#/definitions/list_of_strings"},
                    "config_branch": {"type": "string"},
                },
                "required": ["treefile", "config_url", "source_repo_from", "ostree_repo"],
                "additionalProperties": False,
            }),

            "ostree_installer": _variant_arch_mapping({
                "type": "object",
                "properties": {
                    "source_repo_from": {"type": "string"},
                    "release": {"$ref": "#/definitions/optional_string"},
                    "failable": {"$ref": "#/definitions/list_of_strings"},
                    "installpkgs": {"$ref": "#/definitions/list_of_strings"},
                    "add_template": {"$ref": "#/definitions/list_of_strings"},
                    "add_arch_template": {"$ref": "#/definitions/list_of_strings"},
                    "add_template_var": {"$ref": "#/definitions/list_of_strings"},
                    "add_arch_template_var": {"$ref": "#/definitions/list_of_strings"},
                    "template_repo": {"type": "string"},
                    "template_branch": {"type": "string"},
                },
                "required": ["source_repo_from"],
                "additionalProperties": False,
            }),

            "live_images": _variant_arch_mapping({
                "anyOf": [
                    {"$ref": "#/definitions/live_image_config"},
                    {
                        "type": "array",
                        "items": {
                            "$ref": "#/definitions/live_image_config"
                        }
                    }
                ]
            }),

            "image_build": {
                "type": "object",
                "patternProperties": {
                    ".+": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "image-build": {
                                    "type": "object",
                                    "properties": {
                                        "failable": {"$ref": "#/definitions/list_of_strings"},
                                        "disc_size": {"type": "number"},
                                        "distro": {"type": "string"},
                                        "name": {"type": "string"},
                                        "kickstart": {"type": "string"},
                                        "arches": {"$ref": "#/definitions/list_of_strings"},
                                        "repo_from": {"$ref": "#/definitions/strings"},
                                        "install_tree_from": {"type": "string"},
                                        "subvariant": {"type": "string"},
                                        "format": {"$ref": "#/definitions/string_tuples"},
                                    },
                                },
                                "factory-parameters": {
                                    "type": "object",
                                },
                            },
                            "required": ["image-build"],
                            "additionalProperties": False,
                        }
                    }
                },
                "additionalProperties": False,
            },

            "lorax_options": _variant_arch_mapping({
                "type": "object",
                "properties": {
                    "bugurl": {"type": "string"},
                    "nomacboot": {"type": "boolean"},
                    "noupgrade": {"type": "boolean"},
                },
                "additionalProperties": False,
            }),

            "signing_key_id": {"type": "string"},
            "signing_key_password_file": {"type": "string"},
            "signing_command": {"type": "string"},
            "productimg": {
                "type": "boolean",
                "default": False
            },
            "productimg_install_class": {"$ref": "#/definitions/str_or_scm_dict"},
            "productimg_po_files": {"$ref": "#/definitions/str_or_scm_dict"},
            "iso_size": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                ],
                "default": 4700000000,
            },
            "split_iso_reserve": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                ],
                "default": 10 * 1024 * 1024
            },

            "osbs": {
                "type": "object",
                "patternProperties": {
                    ".+": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "target": {"type": "string"},
                            "name": {"type": "string"},
                            "version": {"type": "string"},
                            "scratch": {"type": "boolean"},
                            "priority": {"type": "number"},
                        },
                        "required": ["url", "target"]
                    }
                },
                "additionalProperties": False,
            },

            "extra_files": _variant_arch_mapping({
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scm": {"type": "string"},
                        "repo": {"type": "string"},
                        "branch": {"$ref": "#/definitions/optional_string"},
                        "file": {"$ref": "#/definitions/strings"},
                        "dir": {"type": "string"},
                        "target": {"type": "string"},
                    },
                    "additionalProperties": False,
                }
            }),

            "gather_lookaside_repos": _variant_arch_mapping({
                "$ref": "#/definitions/strings",
            }),

            # Deprecated options
            "multilib_arches": {
                "deprecated": "multilib"
            },
            "multilib_methods": {
                "deprecated": "multilib"
            },
            "additional_packages_multiarch": {
                "deprecated": "multilib_whitelist"
            },
            "filter_packages_multiarch": {
                "deprecated": "multilib_blacklist"
            },
            "buildinstall_upgrade_image": {
                "deprecated": "lorax_options"
            },
            "pkgset_koji_path_prefix": {
                "deprecated": "koji_profile",
            },
            "pkgset_koji_url": {
                "deprecated": "koji_profile",
            },
        },

        "required": ["release_name", "release_short", "release_version",
                     "release_is_layered",
                     "variants_file", "sigkeys", "createrepo_checksum",
                     "runroot", "pkgset_source",
                     "gather_source", "gather_method"],
        "additionalProperties": False,
    }


def _variant_arch_mapping(value):
    return {
        "type": "array",
        "items": {
            "type": "array",
            "items": [
                {"type": "string"},
                {
                    "type": "object",
                    "patternProperties": {".+": value},
                    "additionalProperties": False
                }
            ],
            "additionalItems": False,
            "minItems": 2,
        },
        "default": []
    }


# This is a mapping of configuration option dependencies and conflicts.
#
# The key in this mapping is the trigger for the check. When the option is
# encountered and its value satisfies the lambda, an error is reported for each
# missing (for requires) option in the list.
CONFIG_DEPS = {
    "gather_source": {
        "conflicts": [
            (lambda val: val != 'json', ['gather_source_mapping']),
            (lambda val: val != 'comps', ['comps_file']),
        ],
        "requires": [
            (lambda val: val == 'json', ['gather_source_mapping']),
            (lambda val: val == 'comps', ['comps_file']),
        ]
    },
    "productimg": {
        "requires": (
            (lambda x: bool(x), ["productimg_install_class"]),
            (lambda x: bool(x), ["productimg_po_files"]),
        ),
    },

    "bootable": {
        "requires": (
            (lambda x: x, ["buildinstall_method"]),
        ),
        "conflicts": (
            (lambda x: not x, ["buildinstall_method"]),
        ),
    },
    "buildinstall_method": {
        "conflicts": (
            (lambda val: val == "buildinstall", ["lorax_options"]),
            (lambda val: not val, ["lorax_options", "buildinstall_kickstart"]),
        ),
    },
    "release_is_layered": {
        "requires": (
            (lambda x: x, ["base_product_name", "base_product_short",
                           "base_product_version", "base_product_type"]),
        ),
        "conflicts": (
            (lambda x: not x, ["base_product_name", "base_product_short",
                               "base_product_version", "base_product_type"]),
        ),
    },
    "runroot": {
        "requires": (
            (lambda x: x, ["koji_profile", "runroot_tag", "runroot_channel"]),
        ),
        "conflicts": (
            (lambda x: not x, ["runroot_tag", "runroot_channel"]),
        ),
    },
    "product_id": {
        "conflicts": [
            (lambda x: not x, ['product_id_allow_missing']),
        ],
    },
    "pkgset_source": {
        "requires": [
            (lambda x: x == "koji", ["pkgset_koji_tag"]),
            (lambda x: x == "repos", ["pkgset_repos"]),
        ],
        "conflicts": [
            (lambda x: x == "koji", ["pkgset_repos"]),
            (lambda x: x == "repos", ["pkgset_koji_tag", "pkgset_koji_inherit"]),
        ],
    },
}
