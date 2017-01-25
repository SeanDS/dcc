#!/usr/bin/env python

from __future__ import print_function
import os
import io
import sys
import shutil
import logging
import argparse
import textwrap
import cookielib
import subprocess
import collections

from .comms import HttpFetcher
from .record import DccArchive, DccNumber
from .patterns import DccNumberNotFoundException, NotLoggedInException, \
UnauthorisedAccessException

logging.basicConfig(format='%(message)s',
                    level=os.getenv('LOG_LEVEL', 'INFO').upper(),
                    )

##################################################

def _get_cookie_path():
    return '/tmp/ecpcookie.u{}'.format(os.getuid())

def _load_dcc_archive():
    # this is where the above writes the cookie.  not a very friendly
    # interface
    cookie_path = _get_cookie_path()
    if not os.path.exists(cookie_path):
        # load ECP cookies
        cmd = ['ecp-cookie-init', '-k', '-q', '-n', 'https://dcc.ligo.org/dcc/']
        out = subprocess.check_output(cmd)
    # FIXME: not sure why i couldn't just load the cookie file via
    # cookielib, but for some reason it won't load
    # https://docs.python.org/2/library/cookielib.html
    #
    # cj = cookielib.FileCookieJar(cookie_path)
    # cj.load()
    # cdata = cj._cookies['dcc.ligo.org']['/']
    #
    # stupid manual extraction
    with open(cookie_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line[0] in ['#', '', ' ']:
                continue
            data = line.split()
            if data[0] == 'dcc.ligo.org':
                cookie = '{}={}'.format(data[5], data[6])
                break
    fetcher = HttpFetcher(cookie)
    archive = DccArchive(fetcher=fetcher)
    return archive

##################################################
# The following is a custom subcommand CLI implementation based on
# callable objects.  Each command is represented by Cmd object, whose
#
#  * docstring is the command documentation
#  * self.parser attribute is the ArgumentParser
#  * __call__ method is the command execution
#
# It's an attempt to make things as self documenting as possible.
# Cmds are registered in the CMDS and ALIAS dictionaries.  The
# functions at the bottom parse the command line and generate help and
# man output.  To create a new subcommand simply define a new Cmd and
# register it in CMDS.
#
# FIXME: support options to the base command.

PROG = 'dcc'
DESC = 'LIGO DCC command line utility'

SYNOPSIS = '{} <command> [<args>...]'.format(PROG)

# NOTE: double spaces are interpreted by text2man to be paragraph
# breaks.  NO DOUBLE SPACES.  Also two spaces at the end of a line
# indicate an element in a tag list.
MANPAGE = """
NAME
  {prog} - {desc}

SYNOPSIS
  {synopsis}

DESCRIPTION

  Command line interface to the LIGO DCC.  View document metadata or
  download/view document files. Uses the 'ecp-cookie-init' program
  available from the LIGO AuthProject to handle LIGO.ORG Kerberos
  authentication to the DCC servers. See:

    https://wiki.ligo.org/AuthProject/LinuxKerbProxyInit

  Before running this program make sure you have a valid kerberos
  credential by running 'kinit' with your LIGO.ORG principle
  (e.g. "albert.einstein@ligo.org").

COMMANDS

{{cmds}}

AUTHOR
    Jameson Graef Rollins <jameson.rollins@ligo.org>
    Sean Leavey <sean.leavey@ligo.org>
""".format(prog=PROG,
           desc=DESC,
           synopsis=SYNOPSIS,
           ).strip()

class Cmd(object):
    """base class for commands"""
    cmd = ''
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog='{} {}'.format(PROG, self.cmd),
            description=self.__doc__.strip(),
            # formatter_class=argparse.RawDescriptionHelpFormatter,
        )

class View(Cmd):
    """View entry metadata.

    If no field is specified, the full entry will be printed to
    stdout.  If a field is specifed, the data from just that field
    will be printed.

    """
    cmd = 'view'
    def __init__(self):
        Cmd.__init__(self)
        self.parser.add_argument('dccid',
                                 help="DCC document number")
        # self.parser.add_argument('field', nargs='?',
        #                          help="document field")

    def __call__(self, args):
        args = self.parser.parse_args(args)
        archive = _load_dcc_archive()
        try:
            record = archive.fetch_record(args.dccid)
        except DccNumberNotFoundException:
            sys.exit("Could not find DCC document '{}'.".format(args.dccid))
        except NotLoggedInException:
            sys.exit("You are not logged in, or your authentication cookie is \
invalid; see `{prog} {cmd}` for more information".format(prog=PROG, cmd=Help.cmd))
        except UnauthorisedAccessException:
            sys.exit("You are not authorised to view this document")

        print('number: {}'.format(record.dcc_number))
        print('title: {}'.format(record.title))
        print('authors:')
        for a in record.authors:
            print('  {}'.format(a.name.strip()))
        print('files:')
        for i,f in enumerate(record.files):
            print('  {} {}'.format(i, f))
        print('referenced by:')
        for r in record.referenced_by:
            print('  {}'.format(r))
        print('related:')
        for r in record.related:
            print('  {}'.format(r))

class Fetch(Cmd):
    """Fetch/view entry files.

    Files may be specified by index or name, index 0 corresponding to
    the 'main' file for the entry.  If no name or index is specified
    the first file is retrieved.  If the  option is not provided
    the file will be opened in an appropriate viewer.

    """
    cmd = 'fetch'
    def __init__(self):
        Cmd.__init__(self)
        self.parser.add_argument('dccid',
                                 help="DCC document number")
        self.parser.add_argument('fileid', nargs='?', default=0,
                                 help="file number or name")
        self.parser.add_argument('-s', '--save', action='store_true',
                                 help="save file to the current directory")

    def __call__(self, args):
        args = self.parser.parse_args(args)
        archive = _load_dcc_archive()
        try:
            record = archive.fetch_record(args.dccid)
        except UnknownDccErrorException:
            sys.exit("Could not find DCC document '{}'.".format(args.dccid))
        if not record.files:
            sys.exit("No files for document.")
        try:
            i = int(args.fileid)
        except ValueError:
            i = record.filenames.index(args.fileid)
        try:
            f = record.files[i]
        except IndexError:
            sys.exit("Could not find file '{}'.".format(args.fileid))
        archive.download_file_data(f)
        if args.save:
            out = f.filename
            if os.path.exists(out):
                sys.exit("File '{}' already exists.".format(out))
            with open(out, 'w') as fd:
                fd.write(f.data)
            print("Saved file: {}".format(out), file=sys.stderr)
        else:
            f.open_file()

class Open(Cmd):
    """Open entry in browser."""
    cmd = 'open'
    def __init__(self):
        Cmd.__init__(self)
        self.parser.add_argument('dccid',
                                 help="DCC document number")

    def __call__(self, args):
        args = self.parser.parse_args(args)
        archive = _load_dcc_archive()
        url = archive.fetcher.get_url(DccNumber(args.dccid))
        cmd = ['xdg-open', url]
        subprocess.Popen(cmd)

class Reset(Cmd):
    """Reset authentication.

    Deletes the cookie associated with the user's session.
    """

    cmd = 'reset'

    def __init__(self):
        Cmd.__init__(self)

    def __call__(self, args):
        # parse arguments (needed to allow -h flag)
        args = self.parser.parse_args(args)

        cookie_path = _get_cookie_path()

        if not os.path.exists(cookie_path):
            sys.exit("No existing session detected")

        # delete cookie
        os.remove(cookie_path)

        print("Authentication data reset")

class Help(Cmd):
    """Print manpage or command help (also '-h' after command).

    """
    cmd = 'help'
    def __init__(self):
        Cmd.__init__(self)
        self.parser.add_argument('cmd', nargs='?',
                                 help="command")

    def __call__(self, args):
        args = self.parser.parse_args(args)
        if args.cmd:
            get_func(args.cmd)()(['-h'])
        else:
            print(MANPAGE.format(cmds=format_commands(man=True)))

CMDS = collections.OrderedDict([
    ('view', View),
    ('fetch', Fetch),
    ('open', Open),
    ('reset', Reset),
    ('help', Help),
    ])

ALIAS = {
    '--help': 'help',
    '-h': 'help',
    }

##################################################

def format_commands(man=False):
    prefix = ' '*8
    wrapper = textwrap.TextWrapper(
        width=70,
        initial_indent=prefix,
        subsequent_indent=prefix,
        )
    with io.StringIO() as f:
        for name, func in CMDS.items():
            if man:
                fo = func()
                usage = fo.parser.format_usage()[len('usage: {} '.format(PROG)):].strip()
                desc = wrapper.fill(u'\n'.join([l.strip() for l in fo.parser.description.splitlines() if l]))
                f.write(u'  {}  \n'.format(usage))
                f.write(desc+'\n')
                f.write(u'\n')
            else:
                desc = func.__doc__.splitlines()[0]
                f.write(u'  {:10}{}\n'.format(name, desc))
        output = f.getvalue()
    return output.rstrip()

def get_func(cmd):
    if cmd in ALIAS:
        cmd = ALIAS[cmd]
    try:
        return CMDS[cmd]
    except KeyError:
        print('Unknown command:', cmd, file=sys.stderr)
        print("See 'help' for usage.", file=sys.stderr)
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print('Command not specified.', file=sys.stderr)
        print('usage: '+SYNOPSIS, file=sys.stderr)
        print(file=sys.stderr)
        print(format_commands(), file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    func = get_func(cmd)
    func()(args)

##################################################

if __name__ == '__main__':
    main()
