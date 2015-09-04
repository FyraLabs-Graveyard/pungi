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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.


import os

from kobo.shortcuts import force_list


class LoraxWrapper(object):
    def _handle_optional_arg_type(self, f_arg, c_arg):
        """
        _handle_optional_arg_type
            private function to handle arguments to LoraxWrapper get_*_cmd
            functions that can optionally be different types (such as string
            or list). This effectively allows to repeat args to the commands
            wrapped by LoraxWrapper.

        @param      uknown type : f_arg
        - Function argument that is passed to the get_*_cmd function.

        @param      string: c_arg
        - Command line argument to append to cmd

        @return     list
        - returns a list of strings to join with the cmd list in the get_*_cmd
          functions
        """

        cmd_args = []

        if type(f_arg) is list:
            for item in f_arg:
                cmd_args.append("%s=%s" % (c_arg, item))
        if type(f_arg) is str:
            cmd_args.append("%s=%s" % (c_arg, item))
        else:
            raise Exception(
                f_arg,
                "Incorrect type passed to LoraxWrapper for " % c_arg
            )
        return cmd_args

    def get_lorax_cmd(self, product, version, release, repo_baseurl, output_dir, variant=None, bugurl=None, nomacboot=False, noupgrade=False, is_final=False, buildarch=None, volid=None, add_template=None, add_template_var=None, add_arch_template=None, add_arch_template_var=None):
        cmd = ["lorax"]
        cmd.append("--product=%s" % product)
        cmd.append("--version=%s" % version)
        cmd.append("--release=%s" % release)

        for i in force_list(repo_baseurl):
            if "://" not in i:
                i = "file://%s" % os.path.abspath(i)
            cmd.append("--source=%s" % i)

        if variant is not None:
            cmd.append("--variant=%s" % variant)

        if bugurl is not None:
            cmd.append("--bugurl=%s" % variant)

        if nomacboot:
            cmd.append("--nomacboot")

        if noupgrade:
            cmd.append("--noupgrade")

        if is_final:
            cmd.append("--isfinal")

        if buildarch:
            cmd.append("--buildarch=%s" % buildarch)

        if volid:
            cmd.append("--volid=%s" % volid)

        if add_template:
            cmd.extend(
                self._handle_optional_arg_type(add_template, "--add-template")
            )

        if add_template_var:
            cmd.extend(
                self._handle_optional_arg_type(
                    add_template_var, "--add-template-var"
                )
            )

        if add_arch_template:
            cmd.extend(
                self._handle_optional_arg_type(
                    add_arch_template, "--add-arch-template"
                )
            )

        if add_arch_template_var:
            cmd.extend(
                self._handle_optional_arg_type(
                    add_arch_template_var, "--add-arch-template-var"
                )
            )

        output_dir = os.path.abspath(output_dir)
        cmd.append(output_dir)

        # TODO: workdir

        return cmd

    def get_buildinstall_cmd(self, product, version, release, repo_baseurl, output_dir, variant=None, bugurl=None, nomacboot=False, noupgrade=False, is_final=False, buildarch=None, volid=None, brand=None):
        # RHEL 6 compatibility
        # Usage: buildinstall [--debug] --version <version> --brand <brand> --product <product> --release <comment> --final [--output outputdir] [--discs <discstring>] <root>

        brand = brand or "redhat"
        # HACK: ignore provided release
        release = "%s %s" % (brand, version)
        bugurl = bugurl or "https://bugzilla.redhat.com"

        cmd = ["/usr/lib/anaconda-runtime/buildinstall"]

        cmd.append("--debug")

        cmd.extend(["--version", version])
        cmd.extend(["--brand", brand])
        cmd.extend(["--product", product])
        cmd.extend(["--release", release])

        if is_final:
            cmd.append("--final")

        if buildarch:
            cmd.extend(["--buildarch", buildarch])

        if bugurl:
            cmd.extend(["--bugurl", bugurl])

        output_dir = os.path.abspath(output_dir)
        cmd.extend(["--output", output_dir])

        for i in force_list(repo_baseurl):
            if "://" not in i:
                i = "file://%s" % os.path.abspath(i)
            cmd.append(i)

        return cmd
