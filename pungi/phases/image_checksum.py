# -*- coding: utf-8 -*-

import os
from kobo import shortcuts

from .base import PhaseBase
from ..util import get_format_substs


MULTIPLE_CHECKSUMS_ERROR = (
    'Config option "media_checksum_one_file" requires only one checksum'
    ' to be configured in "media_checksums".'
)


class ImageChecksumPhase(PhaseBase):
    """Go through images specified in image manifest and generate their
    checksums. The manifest will be updated with the checksums.
    """

    name = 'image_checksum'

    def __init__(self, compose):
        super(ImageChecksumPhase, self).__init__(compose)
        self.checksums = self.compose.conf['media_checksums']
        self.one_file = self.compose.conf['media_checksum_one_file']

    def validate(self):
        errors = []
        try:
            super(ImageChecksumPhase, self).validate()
        except ValueError as exc:
            errors = exc.message.split('\n')

        if self.one_file and len(self.checksums) != 1:
            errors.append(MULTIPLE_CHECKSUMS_ERROR)

        if errors:
            raise ValueError('\n'.join(errors))

    def _get_images(self):
        """Returns a mapping from directories to sets of ``Image``s.

        The paths to dirs are absolute.
        """
        top_dir = self.compose.paths.compose.topdir()
        images = {}
        for variant in self.compose.im.images:
            for arch in self.compose.im.images[variant]:
                for image in self.compose.im.images[variant][arch]:
                    path = os.path.dirname(os.path.join(top_dir, image.path))
                    images.setdefault((variant, arch, path), set()).add(image)
        return images

    def _get_base_filename(self, variant, arch):
        base_checksum_name = self.compose.conf['media_checksum_base_filename']
        if base_checksum_name:
            substs = get_format_substs(self.compose, variant=variant, arch=arch)
            base_checksum_name = (base_checksum_name % substs).format(**substs)
            base_checksum_name += '-'
        return base_checksum_name

    def run(self):
        for (variant, arch, path), images in self._get_images().iteritems():
            checksums = {}
            base_checksum_name = self._get_base_filename(variant, arch)
            for image in images:
                filename = os.path.basename(image.path)
                full_path = os.path.join(path, filename)
                if not os.path.exists(full_path):
                    continue

                digests = shortcuts.compute_file_checksums(full_path, self.checksums)
                for checksum, digest in digests.iteritems():
                    checksums.setdefault(checksum, {})[filename] = digest
                    image.add_checksum(None, checksum, digest)
                    if not self.one_file:
                        dump_checksums(path, checksum,
                                       {filename: digest},
                                       '%s.%sSUM' % (filename, checksum.upper()))

            if not checksums:
                continue

            if self.one_file:
                dump_checksums(path, self.checksums[0],
                               checksums[self.checksums[0]],
                               base_checksum_name + 'CHECKSUM')
            else:
                for checksum in self.checksums:
                    dump_checksums(path, checksum,
                                   checksums[checksum],
                                   '%s%sSUM' % (base_checksum_name, checksum.upper()))


def dump_checksums(dir, alg, checksums, filename):
    """Create file with checksums.

    :param dir: where to put the file
    :param alg: which method was used
    :param checksums: mapping from filenames to checksums
    :param filename: what to call the file
    """
    with open(os.path.join(dir, filename), 'w') as f:
        for file, checksum in checksums.iteritems():
            f.write('%s (%s) = %s\n' % (alg.upper(), file, checksum))
