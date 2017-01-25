# DCC API

An API for the [LIGO Scientific Collaboration](http://www.ligo.org/)
[Document Control Center](https://dcc.ligo.org/) (DCC).

## Features

 - Downloading of records
 - Parsing of record information, including previous versions
 - Extraction of attachment descriptions and URLs

## Prerequisites

  - LIGO.org credentials (`albert.einstein`)
  - Python 2.7+
  - [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)
  - [pytz](https://pypi.python.org/pypi/pytz)
  - (Optional) [graphviz](https://pypi.python.org/pypi/graphviz) for Python

LIGO.org credentials are given to members of the interferometric gravitational
wave community and are not publicly available. The API may work with the public
DCC without these credentials, but it has not been tested.

The `graphviz` package is for creating graphs of connected DCC documents, and
is optional if you don't need to do this. All of the packages above can be
obtained using [pip](https://pip.pypa.io/). On Ubuntu, just run
```bash
sudo pip install bs4 pytz graphviz
```
from a terminal.

The `graphviz` above is just an interface package for Python. You also need to
make sure you have the full `graphviz` program installed too. On Ubuntu:
```bash
sudo apt-get install graphviz
```

## Quick start
Before doing anything else, add the `dcc` package to your Python path.

### Downloading a record
To download a record, import `DccArchive`:
```python
from dcc.record import DccArchive
```
then create a new archive:
```python
# create a new archive with the session cookie created by Shibboleth
archive = DccArchive(cookies="_shibsession_xxx=yyy")
```
You'll need the `_shibsession_xxx=yyy` session cookie that is created when you
log in to the DCC using a web browser. One way in which to extract this cookie
is to load the DCC in your browser, then copy and paste the following
Javascript into your location bar:
```javascript
javascript:document.cookie.split(";")
```
That should show you the contents of the cookies associated with the DCC on your
browser. Simply copy and paste the one resembling `_shibsession_xxx=yyy` into
the constructor for `DccArchive`. Note, this string is typically around 130
characters long.

To fetch the record, use the `fetch_record` method of the `archive` you created:
```python
# fetch a DCC record
record = archive.fetch_record("P1500227")
```
The `fetch_record` method accepts any of the arguments that `DccNumber` does.
You can construct the DCC number to download in a few different ways:
```python
# fetch a DCC record
record = archive.fetch_record("P1500227")

# fetch a specific version
record = archive.fetch_record("P1500227-v3")

# fetch by category and number
record = archive.fetch_record("P", 1500227) # equivalent to P1500227

# fetch by category, number and version
record = archive.fetch_record("P", 1500227, 3) # equivalent to P1500227-v3

# fetch by separate DCC number and version
record = archive.fetch_record("P1500227", 3) # equivalent to P1500227-v3
```

You may also specify the optional argument to download the files associated
with the record:
```python
record = archive.fetch_record("P1500227-v3", download_files=True)
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

## Future improvements
 - Local archiving

## Credits
Sean Leavey <sean.leavey@ligo.org>
Jameson Graef Rollins <jameson.rollins@ligo.org>
