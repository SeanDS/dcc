# DCC API

An API for the [LIGO Scientific Collaboration](http://www.ligo.org/)
[Document Control Center](https://dcc.ligo.org/) (DCC).

## Features

 - Downloading of records
 - Parsing of record information, including previous versions
 - Extraction of attachment descriptions and URLs
 - Modification of record metadata

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
record = archive.fetch_record("P150914-v13", download_files=True)
```
When this is set, the files associated with the version specified will be
downloaded.

### Extracting useful information
Most of the record's information can be accessed like a dictionary:
```python
# prints "P150914-v13"
print(record["dcc_number"])

# prints "Observation of Gravitational Waves from a Binary Black Hole Merger"
print(record["title"])

# prints "2016-02-02 05:59:52-08:00"
print(record['contents_revision_date'])

# prints list of attached files
print(record['files'])
```

Some other information can be accessed through properties:
```python
# prints "13"
print(record.dcc_number.version)

# prints "14"
print(record.latest_version_num)

# prints "[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]"
print(record.version_nums)

# prints "False"
print(record.is_latest_version())
```

### Opening files
If you specified the `download_files=True` flag as part of the `fetch_record`
constructor, then you will be able to view the attached files. You can extract
the file objects by calling the appropriate index:
```python
# gets first file (usually the main attachment)
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

### Updating metadata
To update a record's metadata, use the `update_record_metadata` method of `HttpFetcher`:
```python
from dcc.comms import HttpFetcher
from dcc.record import DccNumber

fetcher = HttpFetcher()
dcc_number = DccNumber("Pxxxxxxx")
fetcher.update_record_metadata(dcc_number, note="https://doi.org/10.1103/PhysRevLett.yyy.zzzzzz", related="Gxxxxxxx")
```

### Logging
`DCC API` has logging capabilities. To log to `stdout`, just put this at the
top of your script:
```python
import logging

# create debug message logger on stdout
logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.DEBUG)
```

## Credits

 - Sean Leavey <sean.leavey@ligo.org>  
 - Jameson Graef Rollins <jameson.rollins@ligo.org>
 - Christopher Wipf
