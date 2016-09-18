# DCC API

An API for the [LIGO Scientific Collaboration](http://www.ligo.org/) [Document Control Center](https://dcc.ligo.org/) (DCC).

## Features

 - Downloading of records
 - Parsing of record information, including previous versions
 - Extraction of attachment descriptions and URLs

## Prerequisites

  - Python 2.7+
  - [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)
  - [pytz](https://pypi.python.org/pypi/pytz)
  - LIGO.org credentials (`albert.einstein`)

`BeautifulSoup4` and `pytz` can be obtained using [pip](https://pip.pypa.io/). On Ubuntu, just run
```bash
sudo pip install bs4 pytz
```
from a terminal.

## Quick start
Before doing anything else, add the `dcc` package to your Python path.

```python
import dcc.comms

# create a fetcher with the session cookie created by Shibboleth
fetcher = dcc.comms.HttpFetcher("_shibsession_xxx=yyy")

# fetch a DCC record
record = fetcher.fetch_dcc_record("P1500227")
```

You can then print some useful information:
```
print record.dcc_number
print record.title
print record.version
print record.other_version_numbers
print record.creation_date
print record.metadata_revision_date
```

The Shibboleth cookie must be provided in order for `DCC API` to access the DCC without needing to support login capabilities. To obtain it, log in to the DCC and then extract the cookie with a name and value similar to `_shibsession_xxx=yyy`. You'll need to give both the name and value.

`DCC API` has logging capabilities. To log to `stdout`, just put this at the top of your script:
```python
import logging

logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.DEBUG)
```

## Future improvements
 - Graceful handling of non 2xx HTTP codes
 - Local archiving
 - Log in
