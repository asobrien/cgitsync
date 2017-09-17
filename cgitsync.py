#!/usr/bin/env python3

"""Cgit mirror and sync utility.

This is a simple utility that allows easy cloning and updating of a
git repository that is defined in a cgitrepos configuration file.
Multiple cgit sections can be specified that point at specific
provider.

When a repo is added to a section this utility will clone the repo to
the repo.path. On subsequent runs this will just update the repo at
repo.path.

PROVIDERS
---------
github      The repo.url must be formatted '{username|org}/repo'.
            Clones via ssh protocol (e.g., git@github.com:org/repo.git).
custom      Clone from a custom provider. Note that this provider is
            specified by passing the '--template' option. Any of the
            repo keys can be be specified in the template, e.g.:
            'ssh://mygit.com/{mykey}/{owner}/{url}.git'.

See also: https://git.zx2c4.com/cgit/tree/cgitrc.5.txt

"""

__author__ = "Anthony O'Brien"
__copyright__ = "Copyright 2017, Anthony O'Brien"

__license__ = "MIT"
__version__ = "0.1.0-rc.1"
__maintainer__ = "Anthony O'Brien"
__email__ = "anthony@bearonis.com"


import os
import sys
import logging
import argparse
import threading
import subprocess

GIT_TIMEOUT = 900
GIT_BIN = None
TARGET_TEMPLATE = None

log = logging.getLogger('cgitsync')


# ----------------------------------------------------
#  Helpers
# ----------------------------------------------------
def which(program):
    """Returns full path to `program` if found in $PATH or else None
    if the executable is not found.
    SRC: http://stackoverflow.com/a/377028/983310
    """
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def process(cmd, env=None):
    """Run the cmd as a subprocess, optionally specifying an environment.
    By default the cnd runs with the inherited environment. The return
    code from the process is returned.
    """
    def pipe_writer(log_level, pipe):
        """Readlines from a specified `pipe` and write to the
        specified file descriptor `fd`."""
        while retcode is None:
            for line in iter(pipe.readline, b''):
                log.log(log_level, line.decode())
        pipe.close()

    retcode = None

    p = subprocess.Popen(cmd,
                         env=env,
                         bufsize=0,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True)

    t_out = threading.Thread(target=pipe_writer, args=(logging.INFO, p.stdout))
    t_err = threading.Thread(target=pipe_writer, args=(logging.ERROR, p.stderr))
    t_out.daemon = True
    t_err.daemon = True
    t_out.start()
    t_err.start()

    retcode = p.wait(timeout=GIT_TIMEOUT)

    t_out.join()
    t_err.join()
    return retcode


def setup_logger(verbosity=0, log_file=None):
    global log
    log_fmt = logging.Formatter('%(message)s')

    loglevel = 30 - (verbosity * 15)  # WARN+, INFO, DEBUG, DEBUG + libs
    loglevel = loglevel if loglevel > 0 else 10  # let's be reasonable

    if verbosity > 2:
        log = logging.getLogger()  # all the logs!

    log.setLevel(loglevel)

    if log_file:
        handler = logging.FileHandler(os.path.abspath(
                                      os.path.expandvars(
                                      os.path.expanduser(log_file))))
    else:
        handler = logging.StreamHandler(stream=sys.stderr)

    handler.setLevel(loglevel)
    handler.setFormatter(log_fmt)
    log.addHandler(handler)
    return


def git(args):
    """Run a git command."""
    cmd = GIT_BIN + ' ' + args
    out = process(cmd)
    return out


# ----------------------------------------------------
#  cgitsync
# ----------------------------------------------------
def get_section(cfg, section):
    """Parse a cgitrepos cfg returning specified section."""
    section_lines = []
    is_append_section = False

    for line in cfg.splitlines():
        line = line.strip()

        if line.startswith('section') and not is_append_section:
            cfg_section = line.split('=', 1)[1].strip()
            if cfg_section == section:
                is_append_section = True
        elif line.startswith('section') and is_append_section:
            break  # skip any subsequent sections

        if is_append_section:
            section_lines.append(line)

    return section_lines


def get_repos(section):
    """TK"""
    repos = {}
    repo = {}

    for line in section:
        line = line.strip()

        if line.startswith('repo.url'):
            if repo.get('url'):
                repos[repo['url']] = repo

            url = line.split('=', 1)[1].strip()
            repo = {'url' : url}

        elif line.startswith('repo.'):
            repodata = line.split('.', 1)[1]
            key, val = [item.strip() for item in repodata.strip().split('=', 1)]
            repo[key] = val

    if repo.get('url'):
        repos[repo['url']] = repo

    return repos


def set_source_target(template=None, provider='github'):
    global TARGET_TEMPLATE

    if template:
        TARGET_TEMPLATE = template
    elif provider == 'github':
        TARGET_TEMPLATE = 'git@github.com:{url}.git'
    else:
        log.error('No provider or custom format provided.')
        sys.exit(-1)
    return


def get_source_target(repo):
    return TARGET_TEMPLATE.format(**repo)


def mirror_or_update(repo):
    source_repo = get_source_target(repo)
    if not os.path.exists(repo['path']):
        log.info('Cloning: {} ...'.format(repo['url']))
        log.debug('Source target: {}'.format(source_repo))
        retcode = git('clone --mirror {} {}'.format(source_repo, repo['path']))
    else:
        log.info('Updating: {} ...'.format(repo['url']))
        retcode = git('-C {} remote update'.format(repo['path']))

    if retcode:
        log.error('Git exited with code: %i\n' % retcode)

    return retcode


def parse_args():
    parser = argparse.ArgumentParser(prog='cgitsync',
                                     description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('section', metavar='SECTION', nargs='+',
                        help='Section in cgitrepos to sync, multiple sections may be specified')
    parser.add_argument('-v', action='count', default=0,
                        help='Verbosity, can be repeated (default: WARNING)')
    parser.add_argument('-c', '--config', metavar='CONFIG', default='/etc/cgitrepos',
                        help='Path to cgitrepos configuration (default: /etc/cgitrepos)')
    parser.add_argument('-g', '--git', metavar='GIT',
                        help='Path to git (default: {})'.format(
                        (GIT_BIN if GIT_BIN else 'git on $PATH')))
    parser.add_argument('-l', '--log-file', metavar='LOGFILE',
                        help='Path to logfile (default: stderr)')

    providers = parser.add_mutually_exclusive_group()

    providers.add_argument('-p', '--provider', metavar='PROVIDER', default='github',
                           choices=['github'],
                           help='Sync from selected provider (default: github)')
    providers.add_argument('-t', '--template', metavar='TEMPLATE',
                           help='Custom provider format string (e.g., '
                                'https://mygit.com/{url}/{owner}). Any of the '
                                'repo keys in cgitrepos is valid.')

    parser.add_argument('--version', action='version',
                        version=('%(prog)s ' + __version__),
                        help='Print version information')

    args = parser.parse_args()

    if GIT_BIN is None:
        log.error('No git binary found on $PATH')
        sys.exit(-1)

    return args


def main():
    global GIT_BIN
    GIT_BIN = which('git')
    error_count = 0

    args = parse_args()


    setup_logger(verbosity=args.v, log_file=args.log_file)
    set_source_target(template=args.template, provider=args.provider)

    with open(args.config, 'r') as f:
        cfg = f.read()

    for section_name in args.section:
        section = get_section(cfg, section_name)

        if not section:
            log.warning('section={} not found in {}'.format(section_name, args.config))
            continue

        log.info('Processing repos in section={}'.format(section_name))
        for repo in get_repos(section).values():
            try:
                retcode = mirror_or_update(repo)
                error_count += (1 if retcode else 0)
            except Exception as e:
                error_count += 1
                log.error('Error cloning/updating: {}'.format(repo['url']))
                log.exception(e)

    sys.exit(error_count)


if __name__ == '__main__':
    main()
