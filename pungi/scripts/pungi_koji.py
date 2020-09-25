# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import print_function

import argparse
import getpass
import json
import locale
import logging
import os
import socket
import signal
import sys
import traceback
import shutil

from six.moves import shlex_quote

from pungi.phases import PHASES_NAMES
from pungi import get_full_version, util


# force C locales
try:
    locale.setlocale(locale.LC_ALL, "C.UTF-8")
except locale.Error:
    # RHEL < 8 does not have C.UTF-8 locale...
    locale.setlocale(locale.LC_ALL, "C")


COMPOSE = None


def main():
    global COMPOSE

    PHASES_NAMES_MODIFIED = PHASES_NAMES + ["productimg"]

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--target-dir",
        metavar="PATH",
        help="a compose is created under this directory",
    )
    group.add_argument(
        "--compose-dir",
        metavar="PATH",
        help="specify compose directory in which the compose will be generated."
        "If directory already exists, Pungi will reuse it (DANGEROUS!).",
    )
    parser.add_argument(
        "--label",
        help="specify compose label (example: Snapshot-1.0); required for production composes",  # noqa: E501
    )
    parser.add_argument(
        "--no-label",
        action="store_true",
        default=False,
        help="make a production compose without label",
    )
    parser.add_argument(
        "--supported",
        action="store_true",
        default=False,
        help="set supported flag on media (automatically on for 'RC-x.y' labels)",
    )
    parser.add_argument(
        "--old-composes",
        metavar="PATH",
        dest="old_composes",
        default=[],
        action="append",
        help="Path to directory with old composes. Reuse an existing repodata from the most recent compose.",  # noqa: E501
    )
    parser.add_argument("--config", help="Config file", required=True)
    parser.add_argument(
        "--skip-phase",
        metavar="PHASE",
        choices=PHASES_NAMES_MODIFIED,
        action="append",
        default=[],
        help="skip a compose phase",
    )
    parser.add_argument(
        "--just-phase",
        metavar="PHASE",
        choices=PHASES_NAMES_MODIFIED,
        action="append",
        default=[],
        help="run only a specified compose phase",
    )
    parser.add_argument(
        "--nightly",
        action="store_const",
        const="nightly",
        dest="compose_type",
        help="make a nightly compose",
    )
    parser.add_argument(
        "--test",
        action="store_const",
        const="test",
        dest="compose_type",
        help="make a test compose",
    )
    parser.add_argument(
        "--ci",
        action="store_const",
        const="ci",
        dest="compose_type",
        help="make a CI compose",
    )
    parser.add_argument(
        "--production",
        action="store_const",
        const="production",
        dest="compose_type",
        help="make production compose (default unless config specifies otherwise)",
    )
    parser.add_argument(
        "--development",
        action="store_const",
        const="development",
        dest="compose_type",
        help="make a development compose",
    )
    parser.add_argument(
        "--koji-event",
        metavar="ID",
        type=util.parse_koji_event,
        help="specify a koji event for populating package set, either as event ID "
        "or a path to a compose from which to reuse the event",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=get_full_version(),
        help="output version information and exit",
    )
    parser.add_argument(
        "--notification-script",
        action="append",
        default=[],
        help="script for sending progress notification messages",
    )
    parser.add_argument(
        "--no-latest-link",
        action="store_true",
        default=False,
        dest="no_latest_link",
        help="don't create latest symbol link to this compose",
    )
    parser.add_argument(
        "--latest-link-status",
        metavar="STATUS",
        action="append",
        default=[],
        help="only create latest symbol link to this compose when compose status matches specified status",  # noqa: E501
    )
    parser.add_argument(
        "--latest-link-components",
        type=int,
        default=-1,
        help="number of product version components used when creating latest symlink",  # noqa: E501
    )
    parser.add_argument(
        "--parent-compose-id",
        action="append",
        default=[],
        help="List of compose IDs which should be marked as parents of this "
        "compose in Compose Tracking Service",
    )
    parser.add_argument(
        "--print-output-dir",
        action="store_true",
        default=False,
        help="print the compose directory",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="quiet mode, don't print log on screen",
    )

    opts = parser.parse_args()
    import pungi.notifier

    notifier = pungi.notifier.PungiNotifier(opts.notification_script)

    def fail_to_start(msg, **kwargs):
        notifier.send(
            "fail-to-start",
            workdir=opts.target_dir,
            command=sys.argv,
            target_dir=opts.target_dir,
            config=opts.config,
            detail=msg,
            **kwargs
        )

    def abort(msg):
        fail_to_start(msg)
        parser.error(msg)

    if opts.target_dir and not opts.compose_dir:
        opts.target_dir = os.path.abspath(opts.target_dir)
        if not os.path.isdir(opts.target_dir):
            abort(
                "The target directory does not exist or is not a directory: %s"
                % opts.target_dir
            )
    else:
        opts.compose_dir = os.path.abspath(opts.compose_dir)
        if os.path.exists(opts.compose_dir) and not os.path.isdir(opts.compose_dir):
            abort("The compose directory is not a directory: %s" % opts.compose_dir)

    opts.config = os.path.abspath(opts.config)

    create_latest_link = not opts.no_latest_link
    latest_link_status = opts.latest_link_status or None
    latest_link_components = opts.latest_link_components

    import kobo.conf
    import kobo.log
    import productmd.composeinfo

    if opts.label:
        try:
            productmd.composeinfo.verify_label(opts.label)
        except ValueError as ex:
            abort(str(ex))

    from pungi.compose import Compose

    logger = logging.getLogger("pungi")
    logger.setLevel(logging.DEBUG)
    if not opts.quiet:
        kobo.log.add_stderr_logger(logger)

    conf = util.load_config(opts.config)

    compose_type = opts.compose_type or conf.get("compose_type", "production")
    if compose_type == "production" and not opts.label and not opts.no_label:
        abort("must specify label for a production compose")

    if (
        compose_type != "test"
        and conf.get("pkgset_koji_scratch_tasks", None) is not None
    ):
        abort('pkgset_koji_scratch_tasks can be used only for "test" compose type')

    # check if all requirements are met
    import pungi.checks

    if not pungi.checks.check(conf):
        sys.exit(1)
    pungi.checks.check_umask(logger)
    if not pungi.checks.check_skip_phases(
        logger, opts.skip_phase + conf.get("skip_phases", []), opts.just_phase
    ):
        sys.exit(1)
    errors, warnings = pungi.checks.validate(conf)

    if not opts.quiet:
        # TODO: workaround for config files containing skip_phase = productimg
        # Remove when all config files are up to date
        if "productimg" in opts.skip_phase + opts.just_phase + conf["skip_phases"]:
            print(
                "WARNING: productimg phase has been removed, please remove it from "
                "--skip-phase or --just-phase option",
                file=sys.stderr,
            )
        for err in errors[:]:
            if "'productimg' is not one of" in err:
                errors.remove(err)
                print("WARNING: %s" % err, file=sys.stderr)

        for warning in warnings:
            print(warning, file=sys.stderr)

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        fail_to_start("Config validation failed", errors=errors)
        sys.exit(1)

    if opts.target_dir:
        compose_dir = Compose.get_compose_dir(
            opts.target_dir, conf, compose_type=compose_type, compose_label=opts.label
        )
    else:
        compose_dir = opts.compose_dir
        ci_path = os.path.join(compose_dir, "work", "global", "composeinfo-base.json")
        if not os.path.exists(ci_path):
            ci = Compose.get_compose_info(
                conf,
                compose_type=compose_type,
                compose_label=opts.label,
                parent_compose_ids=opts.parent_compose_id,
            )
            Compose.write_compose_info(compose_dir, ci)

    if opts.print_output_dir:
        print("Compose dir: %s" % compose_dir)

    compose = Compose(
        conf,
        topdir=compose_dir,
        skip_phases=opts.skip_phase,
        just_phases=opts.just_phase,
        old_composes=opts.old_composes,
        koji_event=opts.koji_event,
        supported=opts.supported,
        logger=logger,
        notifier=notifier,
    )
    notifier.compose = compose
    COMPOSE = compose
    run_compose(
        compose,
        create_latest_link=create_latest_link,
        latest_link_status=latest_link_status,
        latest_link_components=latest_link_components,
    )


def run_compose(
    compose, create_latest_link=True, latest_link_status=None, latest_link_components=-1
):
    import pungi.phases
    import pungi.metadata
    import pungi.util

    errors = []

    compose.write_status("STARTED")
    compose.log_info("Host: %s" % socket.gethostname())
    compose.log_info("Pungi version: %s" % get_full_version())
    compose.log_info("User name: %s" % getpass.getuser())
    compose.log_info("Working directory: %s" % os.getcwd())
    compose.log_info(
        "Command line: %s" % " ".join([shlex_quote(arg) for arg in sys.argv])
    )
    compose.log_info("Compose top directory: %s" % compose.topdir)
    compose.log_info("Current timezone offset: %s" % pungi.util.get_tz_offset())
    compose.read_variants()

    # dump the config file
    config_copy_path = os.path.join(compose.paths.log.topdir(), "config-copy")
    if not os.path.exists(config_copy_path):
        os.makedirs(config_copy_path)
    for config_file in compose.conf.opened_files:
        shutil.copy2(config_file, config_copy_path)
    config_dump_full = compose.paths.log.log_file("global", "config-dump")
    with open(config_dump_full, "w") as f:
        json.dump(compose.conf, f, sort_keys=True, indent=4)

    # initialize all phases
    init_phase = pungi.phases.InitPhase(compose)
    pkgset_phase = pungi.phases.PkgsetPhase(compose)
    buildinstall_phase = pungi.phases.BuildinstallPhase(compose, pkgset_phase)
    gather_phase = pungi.phases.GatherPhase(compose, pkgset_phase)
    extrafiles_phase = pungi.phases.ExtraFilesPhase(compose, pkgset_phase)
    createrepo_phase = pungi.phases.CreaterepoPhase(compose, pkgset_phase)
    ostree_installer_phase = pungi.phases.OstreeInstallerPhase(
        compose, buildinstall_phase, pkgset_phase
    )
    ostree_phase = pungi.phases.OSTreePhase(compose, pkgset_phase)
    createiso_phase = pungi.phases.CreateisoPhase(compose, buildinstall_phase)
    extra_isos_phase = pungi.phases.ExtraIsosPhase(compose)
    liveimages_phase = pungi.phases.LiveImagesPhase(compose)
    livemedia_phase = pungi.phases.LiveMediaPhase(compose)
    image_build_phase = pungi.phases.ImageBuildPhase(compose)
    osbs_phase = pungi.phases.OSBSPhase(compose)
    image_checksum_phase = pungi.phases.ImageChecksumPhase(compose)
    repoclosure_phase = pungi.phases.RepoclosurePhase(compose)
    test_phase = pungi.phases.TestPhase(compose)

    # check if all config options are set
    for phase in (
        init_phase,
        pkgset_phase,
        createrepo_phase,
        buildinstall_phase,
        gather_phase,
        extrafiles_phase,
        createiso_phase,
        liveimages_phase,
        livemedia_phase,
        image_build_phase,
        image_checksum_phase,
        test_phase,
        ostree_phase,
        ostree_installer_phase,
        extra_isos_phase,
        osbs_phase,
    ):
        if phase.skip():
            continue
        try:
            phase.validate()
        except ValueError as ex:
            for i in str(ex).splitlines():
                errors.append("%s: %s" % (phase.name.upper(), i))
    if errors:
        for i in errors:
            compose.log_error(i)
            print(i)
        raise RuntimeError("Configuration is not valid")

    # PREP

    # Note: This may be put into a new method of phase classes (e.g. .prep())
    # in same way as .validate() or .run()

    # Prep for liveimages - Obtain a password for signing rpm wrapped images
    if (
        "signing_key_password_file" in compose.conf
        and "signing_command" in compose.conf
        and "%(signing_key_password)s" in compose.conf["signing_command"]
        and not liveimages_phase.skip()
    ):
        # TODO: Don't require key if signing is turned off
        # Obtain signing key password
        signing_key_password = None

        # Use appropriate method
        if compose.conf["signing_key_password_file"] == "-":
            # Use stdin (by getpass module)
            try:
                signing_key_password = getpass.getpass("Signing key password: ")
            except EOFError:
                compose.log_debug("Ignoring signing key password")
                pass
        else:
            # Use text file with password
            try:
                signing_key_password = (
                    open(compose.conf["signing_key_password_file"], "r")
                    .readline()
                    .rstrip("\n")
                )
            except IOError:
                # Filename is not print intentionally in case someone puts
                # password directly into the option
                err_msg = "Cannot load password from file specified by 'signing_key_password_file' option"  # noqa: E501
                compose.log_error(err_msg)
                print(err_msg)
                raise RuntimeError(err_msg)

        if signing_key_password:
            # Store the password
            compose.conf["signing_key_password"] = signing_key_password

    init_phase.start()
    init_phase.stop()

    pkgset_phase.start()
    pkgset_phase.stop()

    # WEAVER phase - launches other phases which can safely run in parallel
    essentials_schema = (
        buildinstall_phase,
        (gather_phase, createrepo_phase),
        extrafiles_phase,
        (ostree_phase, ostree_installer_phase),
    )
    essentials_phase = pungi.phases.WeaverPhase(compose, essentials_schema)
    essentials_phase.start()
    essentials_phase.stop()

    # write treeinfo before ISOs are created
    for variant in compose.get_variants():
        for arch in variant.arches + ["src"]:
            pungi.metadata.write_tree_info(
                compose, arch, variant, bi=buildinstall_phase
            )

    # write .discinfo and media.repo before ISOs are created
    for variant in compose.get_variants():
        if variant.type == "addon" or variant.is_empty:
            continue
        for arch in variant.arches + ["src"]:
            timestamp = pungi.metadata.write_discinfo(compose, arch, variant)
            pungi.metadata.write_media_repo(compose, arch, variant, timestamp)

    # Run phases for image artifacts in parallel
    compose_images_schema = (
        createiso_phase,
        extra_isos_phase,
        liveimages_phase,
        image_build_phase,
        livemedia_phase,
    )
    compose_images_phase = pungi.phases.WeaverPhase(compose, compose_images_schema)
    extra_phase_schema = (
        (compose_images_phase, image_checksum_phase),
        osbs_phase,
        repoclosure_phase,
    )
    extra_phase = pungi.phases.WeaverPhase(compose, extra_phase_schema)

    extra_phase.start()
    extra_phase.stop()

    pungi.metadata.write_compose_info(compose)
    if not (
        buildinstall_phase.skip()
        and ostree_installer_phase.skip()
        and createiso_phase.skip()
        and liveimages_phase.skip()
        and livemedia_phase.skip()
        and image_build_phase.skip()
    ):
        compose.im.dump(compose.paths.compose.metadata("images.json"))
    osbs_phase.dump_metadata()

    test_phase.start()
    test_phase.stop()

    compose.write_status("FINISHED")
    osbs_phase.request_push()
    latest_link = False
    if create_latest_link:
        if latest_link_status is None:
            # create latest symbol link by default if latest_link_status
            # is not specified
            latest_link = True
        else:
            latest_link_status = [s.upper() for s in latest_link_status]
            if compose.get_status() in [s.upper() for s in latest_link_status]:
                latest_link = True
            else:
                compose.log_warning(
                    "Compose status (%s) doesn't match with specified "
                    "latest-link-status (%s), not create latest link."
                    % (compose.get_status(), str(latest_link_status))
                )

    if latest_link:
        compose_dir = os.path.basename(compose.topdir)
        # Omit version entirely if latest_link_components == 0
        if latest_link_components == 0:
            symlink_name = "latest-%s" % compose.conf["release_short"]
        else:
            hunks = compose.conf["release_version"].split(".")
            # Set up our min/max so we don't overrun our array
            if latest_link_components > 0:
                latest_link_components = min(len(hunks), latest_link_components)
            else:
                latest_link_components = max(1, len(hunks) + latest_link_components)
            symlink_name = "latest-%s-%s" % (
                compose.conf["release_short"],
                ".".join(hunks[:latest_link_components]),
            )
        if compose.conf.get("base_product_name", ""):
            symlink_name += "-%s-%s" % (
                compose.conf["base_product_short"],
                compose.conf["base_product_version"],
            )
        symlink = os.path.join(compose.topdir, "..", symlink_name)

        try:
            os.unlink(symlink)
        except OSError as ex:
            if ex.errno != 2:
                raise
        try:
            os.symlink(compose_dir, symlink)
        except Exception as ex:
            compose.log_error("Couldn't create latest symlink: %s" % ex)
            raise

    compose.log_info("Compose finished: %s" % compose.topdir)


def sigterm_handler(signum, frame):
    if COMPOSE:
        COMPOSE.log_error("Compose run failed: signal %s" % signum)
        COMPOSE.log_error("Traceback:\n%s" % "\n".join(traceback.format_stack(frame)))
        COMPOSE.log_critical("Compose failed: %s" % COMPOSE.topdir)
        COMPOSE.write_status("TERMINATED")
    else:
        print("Signal %s captured" % signum)
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(1)


def cli_main():
    signal.signal(signal.SIGTERM, sigterm_handler)

    try:
        main()
    except (Exception, KeyboardInterrupt) as ex:
        if COMPOSE:
            tb_path = COMPOSE.paths.log.log_file("global", "traceback")
            COMPOSE.log_error("Compose run failed: %s" % ex)
            COMPOSE.log_error("Extended traceback in: %s" % tb_path)
            COMPOSE.log_critical("Compose failed: %s" % COMPOSE.topdir)
            COMPOSE.write_status("DOOMED")
            import kobo.tback

            with open(tb_path, "wb") as f:
                f.write(kobo.tback.Traceback().get_traceback())
        else:
            print("Exception: %s" % ex)
            raise
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(1)
