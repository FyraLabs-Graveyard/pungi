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
import time

import productmd.composeinfo
import productmd.treeinfo
from productmd.common import get_major_version
from kobo.shortcuts import relative_path

from pungi.compose_metadata.discinfo import write_discinfo as create_discinfo
from pungi.compose_metadata.discinfo import write_media_repo as create_media_repo


def get_description(compose, variant, arch):
    if "product_discinfo_description" in compose.conf:
        result = compose.conf["product_discinfo_description"]
    elif variant.type == "layered-product":
        # we need to make sure the layered product behaves as it was composed separately
        result = "%s %s for %s %s" % (variant.product_name, variant.product_version, compose.conf["product_name"], get_major_version(compose.conf["product_version"]))
    else:
        result = "%s %s" % (compose.conf["product_name"], compose.conf["product_version"])
        if compose.conf.get("is_layered", False):
            result += "for %s %s" % (compose.conf["base_product_name"], compose.conf["base_product_version"])

    result = result % {"variant_name": variant.name, "arch": arch}
    return result


def write_discinfo(compose, arch, variant):
    if variant.type == "addon":
        return
    os_tree = compose.paths.compose.os_tree(arch, variant)
    path = os.path.join(os_tree, ".discinfo")
    # description = get_volid(compose, arch, variant)
    description = get_description(compose, variant, arch)
    return create_discinfo(path, description, arch)


def write_media_repo(compose, arch, variant, timestamp=None):
    if variant.type == "addon":
        return
    os_tree = compose.paths.compose.os_tree(arch, variant)
    path = os.path.join(os_tree, "media.repo")
    # description = get_volid(compose, arch, variant)
    description = get_description(compose, variant, arch)
    return create_media_repo(path, description, timestamp)

def write_compose_info(compose):
    ci = compose.dumps()

    msg = "Writing composeinfo"
    compose.log_info("[BEGIN] %s" % msg)

    path = compose.paths.compose.metadata("composeinfo.json")
    ci.dump(path)

    compose.log_info("[DONE ] %s" % msg)


def write_tree_info(compose, arch, variant, timestamp=None):
    if variant.type in ("addon", ):
        return

    if not timestamp:
        timestamp = int(time.time())
    else:
        timestamp = int(timestamp)

    os_tree = compose.paths.compose.os_tree(arch=arch, variant=variant).rstrip("/") + "/"

    ti = productmd.treeinfo.TreeInfo()
    # load from buildinstall .treeinfo

    if variant.type == "layered-product":
        # we need to make sure the layered product behaves as it was composed separately

        # product
        # TODO: read from variants.xml
        ti.release.name = variant.product_name
        ti.release.version = variant.product_version
        ti.release.short = variant.product_short
        ti.release.is_layered = True

        # base product
        ti.base_product.name = compose.conf["product_name"]
        if "." in compose.conf["product_version"]:
            # remove minor version if present
            ti.base_product.version = get_major_version(compose.conf["product_version"])
        else:
            ti.base_product.version = compose.conf["product_version"]
        ti.base_product.short = compose.conf["product_short"]
    else:
        # product
        ti.release.name = compose.conf["product_name"]
        ti.release.version = compose.conf["product_version"]
        ti.release.short = compose.conf["product_short"]
        ti.release.is_layered = compose.conf.get("product_is_layered", False)

        # base product
        if ti.release.is_layered:
            ti.base_product.name = compose.conf["base_product_name"]
            ti.base_product.version = compose.conf["base_product_version"]
            ti.base_product.short = compose.conf["base_product_short"]

    # tree
    ti.tree.arch = arch
    ti.tree.build_timestamp = timestamp
    # ti.platforms

    # main variant
    var = productmd.treeinfo.Variant(ti)
    if variant.type == "layered-product":
        var.id = variant.parent.id
        var.uid = variant.parent.uid
        var.name = variant.parent.name
        var.type = "variant"
    else:
        var.id = variant.id
        var.uid = variant.uid
        var.name = variant.name
        var.type = variant.type

    var.packages = relative_path(compose.paths.compose.packages(arch=arch, variant=variant, create_dir=False).rstrip("/") + "/", os_tree).rstrip("/") or "."
    var.repository = relative_path(compose.paths.compose.repository(arch=arch, variant=variant, create_dir=False).rstrip("/") + "/", os_tree).rstrip("/") or "."

    ti.variants.add(var)

    repomd_path = os.path.join(var.repository, "repodata", "repomd.xml")
    ti.checksums.add(repomd_path, "sha256", os_tree)

    for i in variant.get_variants(types=["addon"], arch=arch):
        addon = productmd.treeinfo.Variant(ti)
        addon.id = i.id
        addon.uid = i.uid
        addon.name = i.name
        addon.type = i.type

        os_tree = compose.paths.compose.os_tree(arch=arch, variant=i).rstrip("/") + "/"
        addon.packages = relative_path(compose.paths.compose.packages(arch=arch, variant=i, create_dir=False).rstrip("/") + "/", os_tree).rstrip("/") or "."
        addon.repository = relative_path(compose.paths.compose.repository(arch=arch, variant=i, create_dir=False).rstrip("/") + "/", os_tree).rstrip("/") or "."
        var.add(addon)

        repomd_path = os.path.join(addon.repository, "repodata", "repomd.xml")
        ti.checksums.add(repomd_path, "sha256", os_tree)

    class LoraxProduct(productmd.treeinfo.Release):
        def _check_short(self):
            # HACK: set self.short so .treeinfo produced by lorax can be read
            if not self.short:
                self.short = compose.conf["product_short"]

    class LoraxTreeInfo(productmd.TreeInfo):
        def clear(self):
            productmd.TreeInfo.clear(self)
            self.product = LoraxProduct(self)

    # images
    if variant.type == "variant":
        os_tree = compose.paths.compose.os_tree(arch, variant)

        # clone all but 'general' sections from buildinstall .treeinfo
        bi_treeinfo = os.path.join(compose.paths.work.buildinstall_dir(arch), ".treeinfo")
        if os.path.exists(bi_treeinfo):
            bi_ti = LoraxTreeInfo()
            bi_ti.load(bi_treeinfo)

            # stage2 - mainimage
            if bi_ti.stage2.mainimage:
                ti.stage2.mainimage = bi_ti.stage2.mainimage
                ti.checksums.add(ti.stage2.mainimage, "sha256", os_tree)

            # stage2 - instimage
            if bi_ti.stage2.instimage:
                ti.stage2.instimage = bi_ti.stage2.instimage
                ti.checksums.add(ti.stage2.instimage, "sha256", os_tree)

            # images
            for platform in bi_ti.images.images:
                ti.images.images[platform] = {}
                ti.tree.platforms.add(platform)
                for image, path in bi_ti.images.images[platform].items():
                    ti.images.images[platform][image] = path
                    ti.checksums.add(path, "sha256", os_tree)

        # add product.img to images-$arch
        product_img = os.path.join(os_tree, "images", "product.img")
        product_img_relpath = relative_path(product_img, os_tree.rstrip("/") + "/")
        if os.path.isfile(product_img):
            for platform in ti.images.images:
                ti.images.images[platform]["product.img"] = product_img_relpath
                ti.checksums.add(product_img_relpath, "sha256", os_tree)

    path = os.path.join(compose.paths.compose.os_tree(arch=arch, variant=variant), ".treeinfo")
    compose.log_info("Writing treeinfo: %s" % path)
    ti.dump(path)
