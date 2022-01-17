# DCC
Tools for interactive and programmatic access to the [LIGO Scientific
Collaboration](http://www.ligo.org/) [Document Control Center](https://dcc.ligo.org/)
(DCC).

## Features
- Interactive command line interface
- Retrieval and modification of record metadata
- Extraction of attachment descriptions and URLs
- Local archival of downloaded content

## Prerequisites
Access to the DCC requires [ligo.org](https://my.ligo.org/) ("albert.einstein")
credentials. You only get these if you're part of the LIGO Scientific Collaboration. The
tool may eventually work with the public DCC without these credentials, but this is not
a primary aim for the time being.

You also need the following system requirements:
- Python 3.8 or later
- `kinit` and `klist` (provided by e.g. `krb5-user` on Debian or `krb5-workstation` on
  RHEL)

These are available as part of the reference software environments provided by IGWN. See
[this guide](https://computing.docs.ligo.org/guide/software/environments/) for more
information.

These Python packages are also needed:
- `BeautifulSoup4`
- `pytz`
- `html2text`
- `ciecplib`
- `click`
- `toml`

These can be installed manually or automatically by a Python package manager (see
below).

## Installation
Most users will find it easiest to use `dcc` with one of the [reference software
environments](https://computing.docs.ligo.org/guide/software/environments/) provided by
IGWN.

If you choose to manage system dependencies yourself, you can install `dcc` using your
favourite Python package manager, e.g.:

```
$ git clone https://git.ligo.org/sean-leavey/dcc.git
$ cd /path/to/dcc
$ pip install .
```

The project will be packaged for [PyPI](https://pypi.org/) at some point in the future.

## Usage
Typically `dcc` is used via its command line interface (CLI). On most platforms this is
available via the console command `dcc`. To get an overview of the available
subcommands, type `dcc --help`.

### Kerberos authentication
You must obtain a Kerberos token to authenticate yourself against the LIGO Kerberos
directory, otherwise `dcc` will not be able to obtain a session cookie to access the
DCC. This is one possible way to authenticating with Kerberos:

```
$ kinit albert.einstein@LIGO.ORG
```
where `albert.einstein` is your username. Note that the `@LIGO.ORG` realm is case
sensitive.

With a valid Kerberos ticket, requests made by `dcc` should transparently use your
credentials. Alternatively, if you do not run `kinit`, you will be asked for your
credentials the first time the tool needs to connect to the DCC, each time the tool is
invoked.

You can also revoke your Kerberos token later with `kdestroy`.

## Credits
- Sean Leavey <sean.leavey@ligo.org>
- Jameson Graef Rollins <jameson.rollins@ligo.org>
- Christopher Wipf
- Duncan Macleod
