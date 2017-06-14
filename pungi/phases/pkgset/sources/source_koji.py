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
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://gnu.org/licenses/>.


import os
import cPickle as pickle
import json

import pungi.wrappers.kojiwrapper
import pungi.phases.pkgset.pkgsets
from pungi.arch import get_valid_arches
from pungi.util import is_arch_multilib, retry

from pungi.phases.pkgset.common import create_arch_repos, create_global_repo, populate_arch_pkgsets


import pungi.phases.pkgset.source

try:
    from pdc_client import PDCClient
    import modulemd
    WITH_MODULES = True
except:
    WITH_MODULES = False


def get_pdc_client_session(compose):
    if not WITH_MODULES:
        compose.log_warning("pdc_client module is not installed, "
                            "support for modules is disabled")
        return None
    try:
        return PDCClient(
            server=compose.conf['pdc_url'],
            develop=compose.conf['pdc_develop'],
            ssl_verify=not compose.conf['pdc_insecure'],
        )
    except KeyError:
        return None


def variant_dict_from_str(module_str):
    module_info = {}

    release_start = module_str.rfind('-')
    module_info['variant_version'] = module_str[release_start+1:]
    module_info['variant_id'] = module_str[:release_start]
    module_info['variant_type'] = 'module'

    return module_info


@retry(wait_on=IOError)
def get_module(session, module_info, strict=False):
    """
    :param session : PDCClient instance
    :param module_info: pdc variant_dict, str, mmd or module dict
    :param strict: Normally this function returns None if no module can be
           found.  If strict=True, then a ValueError is raised.

    :return final list of module_info which pass repoclosure
    """

    module_info = variant_dict_from_str(module_info)

    query = dict(
        variant_id=module_info['variant_id'],
        variant_version=module_info['variant_version'],
        active=True,
    )
    if module_info.get('variant_release'):
        query['variant_release'] = module_info['variant_release']

    retval = session['unreleasedvariants'](page_size=-1, **query)

    # Error handling
    if not retval:
        if strict:
            raise ValueError("Failed to find module in PDC %r" % query)
        else:
            return None

    module = None
    # If we specify 'variant_release', we expect only single module to be
    # returned, but otherwise we have to pick the one with the highest
    # release ourselves.
    if 'variant_release' in query:
        assert len(retval) <= 1, "More than one module returned from PDC: %s" % retval
        module = retval[0]
    else:
        module = retval[0]
        for m in retval:
            if int(m['variant_release']) > int(module['variant_release']):
                module = m

    return module


class PkgsetSourceKoji(pungi.phases.pkgset.source.PkgsetSourceBase):
    enabled = True

    def __call__(self):
        compose = self.compose
        koji_profile = compose.conf["koji_profile"]
        self.koji_wrapper = pungi.wrappers.kojiwrapper.KojiWrapper(koji_profile)
        # path prefix must contain trailing '/'
        path_prefix = self.koji_wrapper.koji_module.config.topdir.rstrip("/") + "/"
        package_sets = get_pkgset_from_koji(self.compose, self.koji_wrapper, path_prefix)
        return (package_sets, path_prefix)


def get_pkgset_from_koji(compose, koji_wrapper, path_prefix):
    event_info = get_koji_event_info(compose, koji_wrapper)
    pkgset_global = populate_global_pkgset(compose, koji_wrapper, path_prefix, event_info)
    package_sets = populate_arch_pkgsets(compose, path_prefix, pkgset_global)
    package_sets["global"] = pkgset_global

    create_global_repo(compose, path_prefix)
    for arch in compose.get_arches():
        # TODO: threads? runroot?
        create_arch_repos(compose, arch, path_prefix)

    return package_sets


def populate_global_pkgset(compose, koji_wrapper, path_prefix, event_id):
    all_arches = set(["src"])
    for arch in compose.get_arches():
        is_multilib = is_arch_multilib(compose.conf, arch)
        arches = get_valid_arches(arch, is_multilib)
        all_arches.update(arches)

    # List of compose tags from which we create this compose
    compose_tags = []

    # List of compose_tags per variant
    variant_tags = {}

    session = get_pdc_client_session(compose)
    for variant in compose.all_variants.values():
        variant.pkgset = pungi.phases.pkgset.pkgsets.KojiPackageSet(
            koji_wrapper, compose.conf["sigkeys"], logger=compose._logger,
            arches=all_arches)
        variant_tags[variant] = []

        # Find out all modules in every variant and add their compose tags
        # to compose_tags list.
        if session:
            for module in variant.get_modules():
                pdc_module = get_module(session, module["name"])
                mmd = modulemd.ModuleMetadata()
                mmd.loads(pdc_module["modulemd"])

                # Add RPMs from PDC response to modulemd, so we can track
                # what RPM is in which module later in gather phase.
                for rpm_nevra in pdc_module["rpms"]:
                    if rpm_nevra.endswith(".rpm"):
                        rpm_nevra = rpm_nevra[:-len(".rpm")]
                    mmd.artifacts.add_rpm(str(rpm_nevra))

                tag = pdc_module["koji_tag"]
                variant.mmds.append(mmd)
                variant_tags[variant].append(tag)
                if tag not in compose_tags:
                    compose_tags.append(tag)

        if not variant_tags[variant]:
            variant_tags[variant].append(compose.conf["pkgset_koji_tag"])

    # In case we have no compose tag from module, use the default
    # one from config.
    if not compose_tags:
        compose_tags.append(compose.conf["pkgset_koji_tag"])

    inherit = compose.conf["pkgset_koji_inherit"]
    global_pkgset_path = os.path.join(
        compose.paths.work.topdir(arch="global"), "pkgset_global.pickle")
    if compose.DEBUG and os.path.isfile(global_pkgset_path):
        msg = "Populating the global package set from tag '%s'" % compose_tags
        compose.log_warning("[SKIP ] %s" % msg)
        global_pkgset = pickle.load(open(global_pkgset_path, "r"))
    else:
        global_pkgset = pungi.phases.pkgset.pkgsets.KojiPackageSet(
            koji_wrapper, compose.conf["sigkeys"], logger=compose._logger,
            arches=all_arches)
        # Get package set for each compose tag and merge it to global package
        # list. Also prepare per-variant pkgset, because we do not have list
        # of binary RPMs in module definition - there is just list of SRPMs.
        for compose_tag in compose_tags:
            compose.log_info("Populating the global package set from tag "
                             "'%s'" % compose_tag)
            pkgset = pungi.phases.pkgset.pkgsets.KojiPackageSet(
                koji_wrapper, compose.conf["sigkeys"], logger=compose._logger,
                arches=all_arches)
            # Create a filename for log with package-to-tag mapping. The tag
            # name is included in filename, so any slashes in it are replaced
            # with underscores just to be safe.
            logfile = compose.paths.log.log_file(
                None, 'packages_from_%s' % compose_tag.replace('/', '_'))
            pkgset.populate(compose_tag, event_id, inherit=inherit, logfile=logfile)
            for variant in compose.all_variants.values():
                if compose_tag in variant_tags[variant]:
                    # Optimization for case where we have just single compose
                    # tag - we do not have to merge in this case...
                    if len(compose_tags) == 1:
                        variant.pkgset = pkgset
                    else:
                        variant.pkgset.merge(pkgset, None, list(all_arches))
            # Optimization for case where we have just single compose
            # tag - we do not have to merge in this case...
            if len(compose_tags) == 1:
                global_pkgset = pkgset
            else:
                global_pkgset.merge(pkgset, None, list(all_arches))
        with open(global_pkgset_path, 'w') as f:
            f.write(pickle.dumps(global_pkgset))

    # write global package list
    global_pkgset.save_file_list(
        compose.paths.work.package_list(arch="global"),
        remove_path_prefix=path_prefix)
    return global_pkgset


def get_koji_event_info(compose, koji_wrapper):
    koji_proxy = koji_wrapper.koji_proxy
    event_file = os.path.join(compose.paths.work.topdir(arch="global"), "koji-event")

    if compose.koji_event:
        koji_event = koji_proxy.getEvent(compose.koji_event)
        compose.log_info("Setting koji event to a custom value: %s" % compose.koji_event)
        json.dump(koji_event, open(event_file, "w"))
        return koji_event

    msg = "Getting koji event"
    if compose.DEBUG and os.path.exists(event_file):
        compose.log_warning("[SKIP ] %s" % msg)
        result = json.load(open(event_file, "r"))
    else:
        compose.log_info(msg)
        result = koji_proxy.getLastEvent()
        json.dump(result, open(event_file, "w"))
    compose.log_info("Koji event: %s" % result["id"])
    return result
