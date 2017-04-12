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


import collections
from operator import attrgetter
import fnmatch
import libcomps
import sys
import xml.dom.minidom


if sys.version_info[:2] < (2, 7):
    # HACK: remove spaces from text elements on py < 2.7
    OldElement = xml.dom.minidom.Element

    class Element(OldElement):
        def writexml(self, writer, indent="", addindent="", newl=""):
            if len(self.childNodes) == 1 and self.firstChild.nodeType == 3:
                writer.write(indent)
                OldElement.writexml(self, writer)
                writer.write(newl)
            else:
                OldElement.writexml(self, writer, indent, addindent, newl)

    xml.dom.minidom.Element = Element


TYPE_MAPPING = collections.OrderedDict([
    (libcomps.PACKAGE_TYPE_MANDATORY, 'mandatory'),
    (libcomps.PACKAGE_TYPE_DEFAULT, 'default'),
    (libcomps.PACKAGE_TYPE_OPTIONAL, 'optional'),
    (libcomps.PACKAGE_TYPE_CONDITIONAL, 'conditional'),
])


class CompsWrapper(object):
    """Class for reading and retreiving information from comps XML files"""

    def __init__(self, comps_file):
        self.comps = libcomps.Comps()
        self.comps.fromxml_f(comps_file)
        self.comps_file = comps_file

    def get_comps_groups(self):
        """Return a list of group IDs."""
        return [group.id for group in self.comps.groups]

    def write_comps(self, comps_obj=None, target_file=None):
        if not comps_obj:
            comps_obj = self.generate_comps()
        if not target_file:
            target_file = self.comps_file

        with open(target_file, "w") as stream:
            stream.write(comps_obj.toprettyxml(indent="  ", encoding="UTF-8"))

    def generate_comps(self):
        impl = xml.dom.minidom.getDOMImplementation()
        doctype = impl.createDocumentType("comps", "-//Red Hat, Inc.//DTD Comps info//EN", "comps.dtd")
        doc = impl.createDocument(None, "comps", doctype)
        msg_elem = doc.documentElement

        for group in sorted(self.comps.groups, key=attrgetter('id')):
            group_node = doc.createElement("group")
            msg_elem.appendChild(group_node)

            id_node = doc.createElement("id")
            id_node.appendChild(doc.createTextNode(group.id))
            group_node.appendChild(id_node)

            name_node = doc.createElement("name")
            name_node.appendChild(doc.createTextNode(group.name))
            group_node.appendChild(name_node)

            for lang in sorted(group.name_by_lang):
                text = group.name_by_lang[lang]
                node = doc.createElement("name")
                node.setAttribute("xml:lang", lang)
                node.appendChild(doc.createTextNode(text))
                group_node.appendChild(node)

            node = doc.createElement("description")
            group_node.appendChild(node)
            if group.desc and group.desc != "":
                node.appendChild(doc.createTextNode(group.desc))

                for lang in sorted(group.desc_by_lang):
                    text = group.desc_by_lang[lang]
                    node = doc.createElement("description")
                    node.setAttribute("xml:lang", lang)
                    node.appendChild(doc.createTextNode(text))
                    group_node.appendChild(node)

            node = doc.createElement("default")
            node.appendChild(doc.createTextNode("true" if group.default else "false"))
            group_node.appendChild(node)

            node = doc.createElement("uservisible")
            node.appendChild(doc.createTextNode("true" if group.uservisible else "false"))
            group_node.appendChild(node)

            if group.lang_only:
                node = doc.createElement("langonly")
                node.appendChild(doc.createTextNode(group.lang_only))
                group_node.appendChild(node)

            packagelist = doc.createElement("packagelist")

            packages_by_type = collections.defaultdict(list)
            for pkg in group.packages:
                packages_by_type[TYPE_MAPPING[pkg.type]].append(pkg)

            for type_name in TYPE_MAPPING.values():
                for package in sorted(packages_by_type[type_name], key=attrgetter('name')):
                    node = doc.createElement("packagereq")
                    node.appendChild(doc.createTextNode(package.name))
                    node.setAttribute("type", type_name)
                    packagelist.appendChild(node)
                    if type_name == "conditional":
                        node.setAttribute("requires", pkg.requires)

            group_node.appendChild(packagelist)

        for category in self.comps.categories:
            groups = set(x.name for x in category.group_ids) & set(self.get_comps_groups())
            if not groups:
                continue
            cat_node = doc.createElement("category")
            msg_elem.appendChild(cat_node)

            id_node = doc.createElement("id")
            id_node.appendChild(doc.createTextNode(category.id))
            cat_node.appendChild(id_node)

            name_node = doc.createElement("name")
            name_node.appendChild(doc.createTextNode(category.name))
            cat_node.appendChild(name_node)

            for lang in sorted(category.name_by_lang):
                text = category.name_by_lang[lang]
                node = doc.createElement("name")
                node.setAttribute("xml:lang", lang)
                node.appendChild(doc.createTextNode(text))
                cat_node.appendChild(node)

            if category.desc and category.desc != "":
                node = doc.createElement("description")
                node.appendChild(doc.createTextNode(category.desc))
                cat_node.appendChild(node)

                for lang in sorted(category.desc_by_lang):
                    text = category.desc_by_lang[lang]
                    node = doc.createElement("description")
                    node.setAttribute("xml:lang", lang)
                    node.appendChild(doc.createTextNode(text))
                    cat_node.appendChild(node)

            if category.display_order is not None:
                display_node = doc.createElement("display_order")
                display_node.appendChild(doc.createTextNode(str(category.display_order)))
                cat_node.appendChild(display_node)

            grouplist_node = doc.createElement("grouplist")
            groupids = sorted(groups)

            for groupid in groupids:
                node = doc.createElement("groupid")
                node.appendChild(doc.createTextNode(groupid))
                grouplist_node.appendChild(node)

            cat_node.appendChild(grouplist_node)

        environments = sorted(self.comps.environments, key=attrgetter('id'))
        if environments:
            for environment in environments:
                groups = set(x.name for x in environment.group_ids) & set(self.get_comps_groups())
                if not groups:
                    continue
                env_node = doc.createElement("environment")
                msg_elem.appendChild(env_node)

                id_node = doc.createElement("id")
                id_node.appendChild(doc.createTextNode(environment.id))
                env_node.appendChild(id_node)

                name_node = doc.createElement("name")
                name_node.appendChild(doc.createTextNode(environment.name))
                env_node.appendChild(name_node)

                for lang in sorted(environment.name_by_lang):
                    text = environment.name_by_lang[lang]
                    node = doc.createElement("name")
                    node.setAttribute("xml:lang", lang)
                    node.appendChild(doc.createTextNode(text))
                    env_node.appendChild(node)

                if environment.desc:
                    node = doc.createElement("description")
                    node.appendChild(doc.createTextNode(environment.desc))
                    env_node.appendChild(node)

                    for lang in sorted(environment.desc_by_lang):
                        text = environment.desc_by_lang[lang]
                        node = doc.createElement("description")
                        node.setAttribute("xml:lang", lang)
                        node.appendChild(doc.createTextNode(text))
                        env_node.appendChild(node)

                if environment.display_order is not None:
                    display_node = doc.createElement("display_order")
                    display_node.appendChild(doc.createTextNode("%s" % environment.display_order))
                    env_node.appendChild(display_node)

                grouplist_node = doc.createElement("grouplist")
                groupids = sorted(groups)
                for groupid in groupids:
                    node = doc.createElement("groupid")
                    node.appendChild(doc.createTextNode(groupid))
                    grouplist_node.appendChild(node)
                env_node.appendChild(grouplist_node)

                if environment.option_ids:
                    optionlist_node = doc.createElement("optionlist")
                    for optionid in sorted(x.name for x in environment.option_ids):
                        node = doc.createElement("groupid")
                        node.appendChild(doc.createTextNode(optionid))
                        optionlist_node.appendChild(node)
                    env_node.appendChild(optionlist_node)

        if self.comps.langpacks:
            lang_node = doc.createElement("langpacks")
            msg_elem.appendChild(lang_node)

            for name in sorted(self.comps.langpacks):
                match_node = doc.createElement("match")
                match_node.setAttribute("name", name)
                match_node.setAttribute("install", self.comps.langpacks[name])
                lang_node.appendChild(match_node)

        return doc

    def _tweak_group(self, group_obj, group_dict):
        if group_dict["default"] is not None:
            group_obj.default = group_dict["default"]
        if group_dict["uservisible"] is not None:
            group_obj.uservisible = group_dict["uservisible"]

    def _tweak_env(self, env_obj, env_dict):
        if env_dict["display_order"] is not None:
            env_obj.display_order = env_dict["display_order"]
        else:
            # write actual display order back to env_dict
            env_dict["display_order"] = env_obj.display_order
        # write group list back to env_dict
        env_dict["groups"] = [g.name for g in env_obj.group_ids]

    def filter_groups(self, group_dicts):
        """Filter groups according to group definitions in group_dicts.
        group_dicts = [{
            "name": group ID,
            "glob": True/False -- is "name" a glob?
            "default: True/False/None -- if not None, set "default" accordingly
            "uservisible": True/False/None -- if not None, set "uservisible" accordingly
        }]
        """
        to_remove = []
        for group_obj in self.comps.groups:
            for group_dict in group_dicts:
                if group_dict["glob"]:
                    if fnmatch.fnmatch(group_obj.id, group_dict["name"]):
                        self._tweak_group(group_obj, group_dict)
                        break
                else:
                    if group_obj.id == group_dict["name"]:
                        self._tweak_group(group_obj, group_dict)
                        break
            else:
                to_remove.append(group_obj)

        for group in to_remove:
            self.comps.groups.remove(group)

        # Sanity check to report warnings on unused group_dicts
        unmatched = set()
        for group_dict in group_dicts:
            matcher = fnmatch.fnmatch if group_dict["glob"] else lambda x, y: x == y
            for group_obj in self.comps.groups:
                if matcher(group_obj.id, group_dict["name"]):
                    break
            else:
                unmatched.add(group_dict["name"])
        return unmatched

    def filter_environments(self, env_dicts):
        """Filter environments according to group definitions in group_dicts.
        env_dicts = [{
            "name": environment ID,
            "display_order: <int>/None -- if not None, set "display_order" accordingly
        }]
        """
        to_remove = []
        for env_obj in self.comps.environments:
            for env_dict in env_dicts:
                if env_obj.id == env_dict["name"]:
                    self._tweak_env(env_obj, env_dict)
                    break
            else:
                to_remove.append(env_obj)

        for env in to_remove:
            self.comps.environments.remove(env)
