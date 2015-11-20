# -*- coding: utf-8 -*-

import os

from .base import PhaseBase


class ImageChecksumPhase(PhaseBase):
    """Go through images generated in ImageBuild phase and generate their
    checksums.
    """

    name = 'image_checksum'

    def run(self):
        compose = self.compose
        # merge checksum files
        for variant in compose.get_variants(types=["variant", "layered-product"]):
            for arch in variant.arches + ["src"]:
                iso_dir = compose.paths.compose.iso_dir(arch, variant, create_dir=False)
                if not iso_dir or not os.path.exists(iso_dir):
                    continue
                for checksum_type in ("md5", "sha1", "sha256"):
                    checksum_upper = "%sSUM" % checksum_type.upper()
                    checksums = sorted([i for i in os.listdir(iso_dir) if i.endswith(".%s" % checksum_upper)])
                    fo = open(os.path.join(iso_dir, checksum_upper), "w")
                    for i in checksums:
                        data = open(os.path.join(iso_dir, i), "r").read()
                        fo.write(data)
                    fo.close()
