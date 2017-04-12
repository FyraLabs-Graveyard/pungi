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

            append_common_info(doc, group_node, group, force_description=True)
            append_bool(doc, group_node, "default", group.default)
            append_bool(doc, group_node, "uservisible", group.uservisible)

            if group.lang_only:
                append(doc, group_node, "langonly", group.lang_only)

            packagelist = doc.createElement("packagelist")

            packages_by_type = collections.defaultdict(list)
            for pkg in group.packages:
                packages_by_type[TYPE_MAPPING[pkg.type]].append(pkg)

            for type_name in TYPE_MAPPING.values():
                for package in sorted(packages_by_type[type_name], key=attrgetter('name')):
                    node = append(doc, packagelist, "packagereq", package.name, type=type_name)
                    if type_name == "conditional":
                        node.setAttribute("requires", pkg.requires)

            group_node.appendChild(packagelist)

        for category in self.comps.categories:
            groups = set(x.name for x in category.group_ids) & set(self.get_comps_groups())
            if not groups:
                continue
            cat_node = doc.createElement("category")
            msg_elem.appendChild(cat_node)

            append_common_info(doc, cat_node, category)

            if category.display_order is not None:
                append(doc, cat_node, "display_order", str(category.display_order))

            append_grouplist(doc, cat_node, groups)

        for environment in sorted(self.comps.environments, key=attrgetter('id')):
            groups = set(x.name for x in environment.group_ids) & set(self.get_comps_groups())
            if not groups:
                continue
            env_node = doc.createElement("environment")
            msg_elem.appendChild(env_node)

            append_common_info(doc, env_node, environment)

            if environment.display_order is not None:
                append(doc, env_node, "display_order", str(environment.display_order))

            append_grouplist(doc, env_node, groups)

            if environment.option_ids:
                append_grouplist(doc, env_node, (x.name for x in environment.option_ids), "optionlist")

        if self.comps.langpacks:
            lang_node = doc.createElement("langpacks")
            msg_elem.appendChild(lang_node)

            for name in sorted(self.comps.langpacks):
                append(doc, lang_node, "match", name=name, install=self.comps.langpacks[name])

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
                matcher = fnmatch.fnmatch if group_dict["glob"] else lambda x, y: x == y
                if matcher(group_obj.id, group_dict["name"]):
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


def append(doc, parent, elem, content=None, lang=None, **kwargs):
    """Create a new DOM element and append it to parent."""
    node = doc.createElement(elem)
    if content:
        node.appendChild(doc.createTextNode(content))
    if lang:
        node.setAttribute("xml:lang", lang)
    for attr, value in kwargs.iteritems():
        node.setAttribute(attr, value)
    parent.appendChild(node)
    return node


def append_grouplist(doc, parent, groups, elem="grouplist"):
    grouplist_node = doc.createElement(elem)
    for groupid in sorted(groups):
        append(doc, grouplist_node, "groupid", groupid)
    parent.appendChild(grouplist_node)


def append_common_info(doc, parent, obj, force_description=False):
    """Add id, name and description (with translations)."""
    append(doc, parent, "id", obj.id)
    append(doc, parent, "name", obj.name)

    for lang in sorted(obj.name_by_lang):
        text = obj.name_by_lang[lang]
        append(doc, parent, "name", text, lang=lang)

    if obj.desc or force_description:
        append(doc, parent, "description", obj.desc or '')

        for lang in sorted(obj.desc_by_lang):
            text = obj.desc_by_lang[lang]
            append(doc, parent, "description", text, lang=lang)


def append_bool(doc, parent, elem, value):
    node = doc.createElement(elem)
    node.appendChild(doc.createTextNode("true" if value else "false"))
    parent.appendChild(node)
