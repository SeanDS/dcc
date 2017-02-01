# DCC API

An API for the [LIGO Scientific Collaboration](http://www.ligo.org/)
[Document Control Center](https://dcc.ligo.org/) (DCC).

## Features

 - Downloading of records
 - Parsing of record information, including previous versions
 - Extraction of attachment descriptions and URLs

## Prerequisites

  - LIGO.org credentials (`albert.einstein`)
  - Python 3.5+
  - Kerberos (`krb5-user`)
  - `ecp-cookie-init` from [LIGO Data Grid](https://www.lsc-group.phys.uwm.edu/lscdatagrid/doc/installclient.html)
  - [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)
  - [pytz](https://pypi.python.org/pypi/pytz)
  - html2text
  - (Optional) [graphviz](https://pypi.python.org/pypi/graphviz) for Python

LIGO.ORG credentials are given to members of the interferometric gravitational
wave community and are not publicly available. The API may work with the public
DCC without these credentials, but it has not been tested.

The `graphviz` package is for creating graphs of connected DCC documents, and
is optional if you don't need to do this.

## Quick start
Before doing anything else, add the `dcc` package to your Python path.

### Kerberos authentication
You must obtain a Kerberos token to authenticate yourself against the LIGO
Kerberos directory, otherwise `dcc-api` will not be able to obtain a session
cookie to access the DCC. This is one possible way to authenticating with
Kerberos:
```bash
kinit albert.einstein@LIGO.ORG
```
where `albert.einstein` is your username. Note that the `@LIGO.ORG` realm is
case sensitive.

Note: you can also revoke your Kerberos token later with `kdestroy`.

### Command line interpreter
`dcc-api` has a command line interpreter. In your terminal, type
```bash
python3 -m dcc help
```
to get started.

### Downloading a record
To download a record, import `DccArchive`:
```python
from dcc.record import DccArchive
```
then create a new archive:
```python
# create a new archive
archive = DccArchive()
```
The archiver by default uses `dcc.comms.HttpFetcher` to retrieve documents from
the DCC, and handles authentication via the cookies set by visiting
https://dcc.ligo.org/dcc. Note that you must already have a valid Kerberos
ticket for the LIGO.ORG realm (see `Kerberos authentication`).

To fetch the record, use the `fetch_record` method of the `archive` you created:
```python
# fetch a DCC record
record = archive.fetch_record("P150914")
```
The `fetch_record` method accepts any of the arguments that `DccNumber` does.
You can construct the DCC number to download in a few different ways:
```python
# fetch a DCC record
record = archive.fetch_record("P150914")

# fetch a specific version
record = archive.fetch_record("P150914-v14")

# fetch by category and number
record = archive.fetch_record("P", 150914) # equivalent to P150914

# fetch by category, number and version
record = archive.fetch_record("P", 150914, 14) # equivalent to P150914-v14

# fetch by separate DCC number and version
record = archive.fetch_record("P150914", 14) # equivalent to P150914-v14
```

You may also specify the optional argument to download the files associated
with the record:
```python
record = archive.fetch_record("P150914-v14", download_files=True)
```
When this is set, the files associated with the version specified will be
downloaded.

### Extracting useful information
You can then print some useful information:
```python
# DCC number
print record.dcc_number

# document title
print record.title

# latest version number of this record
print record.latest_version_num

# list of version numbers associated with this record
print record.version_nums

# useful dates (as Python date objects)
print record.creation_date
print record.metadata_revision_date
print record.contents_revision_date

# list of names of files attached to this document revision
print record.filenames
```

### Opening files
If you specified the `download_files=True` flag as part of the `fetch_record`
constructor, then you will be able to access the files using `record.files`:
```python
# list of files attached to this document revision
print record.files
```
You can extract the files by calling the appropriate index:
```python
# get first file (usually the main attachment)
f = record.files[0]
```

Open the file by calling `open_file`:
```python
f.open_file()
```
This should launch an appropriate program to open the file. Note that the file
is stored in a temporary location by default, so if you wish to make a local
copy you should save it somewhere else from within the program that is launched.

### Graphs
You can use `graphviz` to generate graphs representing the connections between
DCC documents, authors and more. There is an example provided in
`examples/graph.py`.

### Logging
`DCC API` has logging capabilities. To log to `stdout`, just put this at the
top of your script:
```python
import logging

logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.DEBUG)
```

## Credits
Sean Leavey <sean.leavey@ligo.org>  
Jameson Graef Rollins <jameson.rollins@ligo.org>
