# DCC
Tools for interactive and programmatic access to the [LIGO Scientific
Collaboration](http://www.ligo.org/) [Document Control Center](https://dcc.ligo.org/)
(DCC).

## Features
- Interactive command line interface
- Retrieval and modification of DCC record metadata
- Extraction of attachment descriptions and URLs
- Local archival of downloaded content
- URL scraping and automatic, recursive archival of related documents and files

## Prerequisites
Access to the DCC requires [ligo.org](https://my.ligo.org/) ("albert.einstein")
credentials. You only get these if you're part of the LIGO Scientific Collaboration. The
tool may eventually work with the public DCC without these credentials, but this is not
a primary aim for the time being.

## Installation
`dcc` has the following system requirements:

- Python 3.8 or later
- `kinit` and `klist` provided as part of Kerberos

Most users will find it easiest to use one of the [reference software
environments](https://computing.docs.ligo.org/guide/software/environments/) provided by
IGWN. The `igwn-py38` environment, for example, provides the required dependencies. If
you choose to manage system dependencies yourself, ensure you have the relevant Kerberos
packages above (provided on Linux by e.g. `krb5-user` on Debian derivatives or
`krb5-workstation` on Red Hat derivatives).

Once you have the required system dependencies, you can install `dcc` using your
favourite Python package manager, e.g. using pip:

```bash
$ pip install dcc
```

## Usage
Typically `dcc` is used via its command line interface (CLI). On most platforms this is
exposed as the console command `dcc`. To get an overview of the available subcommands,
type `dcc --help`.

### Kerberos authentication
You must obtain a Kerberos token to authenticate yourself against the LIGO Kerberos
directory, otherwise `dcc` will not be able to obtain a session cookie to access the
DCC. This is one possible way to authenticating with Kerberos:

```bash
kinit albert.einstein@LIGO.ORG
```

where `albert.einstein` is your username. Note that the `@LIGO.ORG` realm is case
sensitive.

With a valid Kerberos ticket, requests made by `dcc` should transparently use your
credentials. Alternatively, if you do not run `kinit`, you will be asked for your
credentials the first time the tool needs to connect to the DCC, each time the tool is
invoked.

You can also revoke your Kerberos token later with `kdestroy`.

## Credits
- Sean Leavey `<sean.leavey@ligo.org>`
- Jameson Graef Rollins `<jameson.rollins@ligo.org>`
- Christopher Wipf
- Duncan Macleod
