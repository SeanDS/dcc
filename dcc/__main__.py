#!/usr/bin/env python3


import os
import io
import sys
import logging
import argparse
import textwrap
import subprocess
import html2text
import collections

from .record import DccArchive, DccNumber
from .comms import KerberosError
from .patterns import DccNumberNotFoundException, NotLoggedInException, \
UnauthorisedAccessException

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
    Sean Leavey <sean.leavey@ligo.org>
    Jameson Graef Rollins <jameson.rollins@ligo.org>
""".format(prog=PROG,
           desc=DESC,
           synopsis=SYNOPSIS,
           ).strip()

def enable_verbose_logs():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def fetch_dcc_record(archive, dccid):
    try:
        return archive.fetch_record(dccid)
    except DccNumberNotFoundException:
        sys.exit("Could not find DCC document '{}'.".format(args.dccid))
    except KerberosError:
        sys.exit("You are not logged in.  Use 'kinit' to initialize kerberos credential.")
    except UnauthorisedAccessException:
        sys.exit("You are not authorised to view this document")

class Cmd(object):
    """base class for commands"""
    cmd = ''
    def __init__(self):
        """Initialize argument parser"""
        self.parser = argparse.ArgumentParser(
            prog='{} {}'.format(PROG, self.cmd),
            description=self.__doc__.strip(),
            # formatter_class=argparse.RawDescriptionHelpFormatter,
        )
    def parse_args(self, args):
        """Parse arguments and returned ArgumentParser Namespace object"""
        return self.parser.parse_args(args)
    def __call__(self, args):
        """Take Namespace object as input and execute command"""
        pass

class View(Cmd):
    """View entry metadata.

    If no field is specified, the full entry will be printed to
    stdout. If a field is specifed, the data from just that field will
    be printed.

    """
    cmd = 'view'
    def __init__(self):
        Cmd.__init__(self)
        self.parser.add_argument('dccid',
                                 help="DCC document number")
        self.parser.add_argument('-v', '--verbose', action='store_true',
                                 help="enable verbose output")
        # self.parser.add_argument('field', nargs='?',
        #                          help="document field")

    def __call__(self, args):
        if args.verbose:
            enable_verbose_logs()

        archive = DccArchive()
        record = fetch_dcc_record(archive, args.dccid)

        # wrapper for outputting text paragraphs (abstract, note,
        # etc.)
        __, width = subprocess.check_output(['stty', 'size']).split()
        wrapper = textwrap.TextWrapper(
            width=int(width),
            initial_indent='  ',
            subsequent_indent='  ',
            )

        print('number: {}'.format(record.dcc_number))
        print('url: {}'.format(archive.fetcher.get_record_url(DccNumber(args.dccid), xml=False)))
        print('title: {}'.format(record.title))
        print('modified: {}'.format(record.contents_revision_date))
        print('authors:')
        for a in record.authors:
            print('  {}'.format(a.name.strip()))
        print('abstract:')
        print(wrapper.fill(html2text.html2text(record.abstract)))
        print('note:')
        print(wrapper.fill(html2text.html2text(record.note)))
        print('keywords: {}'.format(", ".join(record.keywords)))
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
        self.parser.add_argument('-v', '--verbose', action='store_true',
                                 help="enable verbose output")

    def __call__(self, args):
        if args.verbose:
            enable_verbose_logs()

        archive = DccArchive()
        record = fetch_dcc_record(archive, args.dccid)

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
        archive = DccArchive()
        url = archive.fetcher.get_record_url(DccNumber(args.dccid), xml=False)
        cmd = ['xdg-open', url]
        subprocess.run(cmd, check=True)

class Help(Cmd):
    """Print manpage or command help (also '-h' after command).

    """
    cmd = 'help'
    def __init__(self):
        Cmd.__init__(self)
        self.parser.add_argument('cmd', nargs='?',
                                 help="command")

    def __call__(self, args):
        if args.cmd:
            get_func(args.cmd).parser.print_help()
        else:
            print(MANPAGE.format(cmds=format_commands(man=True)))

CMDS = collections.OrderedDict([
    ('view', View),
    ('fetch', Fetch),
    ('open', Open),
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
                desc = wrapper.fill('\n'.join([l.strip() for l in fo.parser.description.splitlines() if l]))
                f.write('  {}  \n'.format(usage))
                f.write(desc+'\n')
                f.write('\n')
            else:
                desc = func.__doc__.splitlines()[0]
                f.write('  {:10}{}\n'.format(name, desc))
        output = f.getvalue()
    return output.rstrip()

def get_func(cmd):
    if cmd in ALIAS:
        cmd = ALIAS[cmd]
    try:
        return CMDS[cmd]()
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
    func(func.parse_args(args))

##################################################

if __name__ == '__main__':
    main()
