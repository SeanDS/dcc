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

## Documentation
For help in installing and using `dcc`, please visit the [online
documentation](https://docs.ligo.org/sean-leavey/dcc/).

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

## Credits
- Sean Leavey `<sean.leavey@ligo.org>`
- Jameson Graef Rollins `<jameson.rollins@ligo.org>`
- Christopher Wipf
- Duncan Macleod
