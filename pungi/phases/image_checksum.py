# -*- coding: utf-8 -*-

import os
from kobo import shortcuts

from .base import PhaseBase
from ..util import get_format_substs, get_file_size


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

    def skip(self):
        # Skipping this phase does not make sense:
        #  * if there are no images, it doesn't do anything and is quick
        #  * if there are images, they must have checksums computed or else
        #    writing metadata will fail
        return False

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
        topdir = self.compose.paths.compose.topdir()
        for (variant, arch, path), images in get_images(topdir, self.compose.im).iteritems():
            base_checksum_name = self._get_base_filename(variant, arch)
            make_checksums(variant, arch, path, images,
                           self.checksums, base_checksum_name, self.one_file)


def make_checksums(variant, arch, path, images, checksum_types, base_checksum_name, one_file):
    checksums = {}
    filesizes = {}
    for image in images:
        filename = os.path.basename(image.path)
        full_path = os.path.join(path, filename)
        if not os.path.exists(full_path):
            continue

        filesize = image.size or get_file_size(full_path)
        filesizes[filename] = filesize

        digests = shortcuts.compute_file_checksums(full_path, checksum_types)
        for checksum, digest in digests.iteritems():
            checksums.setdefault(checksum, {})[filename] = digest
            image.add_checksum(None, checksum, digest)
            if not one_file:
                checksum_filename = '%s.%sSUM' % (filename, checksum.upper())
                dump_filesizes(path, {filename: filesize}, checksum_filename)
                dump_checksums(path, checksum,
                               {filename: digest},
                               checksum_filename)

    if not checksums:
        return

    if one_file:
        checksum_filename = base_checksum_name + 'CHECKSUM'
        dump_filesizes(path, filesizes, checksum_filename)
        dump_checksums(path, checksum_types[0],
                       checksums[checksum_types[0]],
                       checksum_filename)
    else:
        for checksum in checksums:
            checksum_filename = '%s%sSUM' % (base_checksum_name, checksum.upper())
            dump_filesizes(path, filesizes, checksum_filename)
            dump_checksums(path, checksum,
                           checksums[checksum],
                           checksum_filename)


def dump_filesizes(dir, filesizes, filename):
    """Write filesizes to file with comment lines.

    :param dir: where to put the file
    :param filesizes: mapping from filenames to filesizes
    :param filename: what to call the file
    """
    filesize_file = os.path.join(dir, filename)
    with open(filesize_file, 'a') as f:
        for file, filesize in filesizes.iteritems():
            f.write('# %s: %s bytes\n' % (file, filesize))


def dump_checksums(dir, alg, checksums, filename):
    """Write checksums to file.

    :param dir: where to put the file
    :param alg: which method was used
    :param checksums: mapping from filenames to checksums
    :param filename: what to call the file
    """
    checksum_file = os.path.join(dir, filename)
    with open(checksum_file, 'a') as f:
        for file, checksum in checksums.iteritems():
            f.write('%s (%s) = %s\n' % (alg.upper(), file, checksum))
    return checksum_file


def get_images(top_dir, manifest):
    """Returns a mapping from directories to sets of ``Image``s.

    The paths to dirs are absolute.
    """
    images = {}
    for variant in manifest.images:
        for arch in manifest.images[variant]:
            for image in manifest.images[variant][arch]:
                path = os.path.dirname(os.path.join(top_dir, image.path))
                images.setdefault((variant, arch, path), []).append(image)
    return images
