.. _examples:

Examples
========

Archive presentations from a conference session
-----------------------------------------------

This can be useful to help mitigate the effects of a DCC outage during a conference.

Find the relevant `event page
<https://dcc.ligo.org/cgi-bin/private/DocDB/ListAllMeetings>`__ on the DCC, find the URL
for the session, and specify it as the argument to :program:`dcc convert`. Chain the
output into :program:`dcc archive`, passing a directory to store the results.

.. code-block:: text

    # Scrape the page for the QNWG session from the September 2021 LVK Meeting, then
    # archive the records and attachments corresponding to the extracted DCC numbers.
    $ dcc convert "https://dcc.ligo.org/cgi-bin/private/DocDB/DisplayMeeting?sessionid=5120" - | dcc archive -s /path/to/archive --from-file - --files --force

The archive directory at ``/path/to/archive`` will then contain the DCC records
and files associated with the session.

Check existing archive for missing downloads
--------------------------------------------

The :option:`--max-file-size <dcc --max-file-size>` option allows ignoring large files
when archiving. You may wish to archive files of a certain type without size limits.
This script searches the archive for (latest) records with missing files with certain
extensions and reports them:

.. code-block:: python

    from pathlib import Path
    from dcc import DCCArchive

    # Attachment extensions to check exist.
    KEEP = [".stl", ".step", ".dwg"]

    # The local archive.
    archive = DCCArchive("/path/to/archive")

    for record in archive.latest_revisions:
        report = False
        for file_ in record.files:
            if file_.exists():
                continue
            path = Path(file_.filename)
            if path.suffix.casefold() in KEEP:
                report = True

        if report:
            print(record.dcc_number)

The output from this program is in a form that can be easily passed to :program:`dcc
archive`:

.. code-block:: text

    # Assume script above is stored in "file_missing.py".
    $ python find_missing.py > missing.txt
    $ dcc archive -s /path/to/archive --from-file missing.txt --files

The interactive mode flag :option:`-i <dcc archive -i>` (or :option:`--interactive <dcc
archive --interactive>`) can be useful here, which prompts before downloading each file,
allowing you to skipones you don't want.
