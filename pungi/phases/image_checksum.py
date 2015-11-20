# -*- coding: utf-8 -*-

import os
from kobo import shortcuts

from .base import PhaseBase


MULTIPLE_CHECKSUMS_ERROR = (
    'Config option "media_checksum_one_file" requires only one checksum'
    ' to be configured in "media_checksums".'
)


class ImageChecksumPhase(PhaseBase):
    """Go through images specified in image manifest and generate their
    checksums. The manifest will be updated with the checksums.
    """

    name = 'image_checksum'

    config_options = (
        {
            "name": "media_checksums",
            "expected_types": [list],
            "optional": True,
        },
        {
            "name": "media_checksum_one_file",
            "expected_types": [bool],
            "optional": True,
        }
    )

    def __init__(self, compose):
        super(ImageChecksumPhase, self).__init__(compose)
        self.checksums = self.compose.conf.get('media_checksums', ['md5', 'sha1', 'sha256'])
        self.one_file = self.compose.conf.get('media_checksum_one_file', False)

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
                    images.setdefault(path, set()).add(image)
        return images

    def run(self):
        for path, images in self._get_images().iteritems():
            checksums = {}
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
                        dump_individual(full_path, digest, checksum)

            if not checksums:
                continue

            if self.one_file:
                dump_checksums(path, checksums[self.checksums[0]])
            else:
                for checksum in self.checksums:
                    dump_checksums(path, checksums[checksum], '%sSUM' % checksum.upper())


def dump_checksums(dir, checksums, filename='CHECKSUM'):
    """Create file with checksums.

    :param dir: where to put the file
    :param checksums: mapping from filenames to checksums
    :param filename: what to call the file
    """
    with open(os.path.join(dir, filename), 'w') as f:
        for file, checksum in checksums.iteritems():
            f.write('{} *{}\n'.format(checksum, file))


def dump_individual(path, checksum, ext):
    """Create a file with a single checksum, saved into a file with an extra
    extension.

    :param path: path to the checksummed file
    :param checksum: the actual digest value
    :param ext: what extension to add to the checksum file
    """
    with open('%s.%sSUM' % (path, ext.upper()), 'w') as f:
        f.write('{} *{}\n'.format(checksum, os.path.basename(path)))
