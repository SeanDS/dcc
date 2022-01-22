.. _examples:

Examples
========

Archive presentations from a conference session
-----------------------------------------------

This can be useful to help mitigate the effects of a DCC outage during a conference.

Find the relevant `event page
<https://dcc.ligo.org/cgi-bin/private/DocDB/ListAllMeetings>`__ on the DCC, find the URL
for the session, and specify it as the argument to :program:`dcc scrape`:

.. code-block:: text

    # Archive the latest files from the QNWG session from the September 2021 LVK Meeting.
    $ dcc scrape -s /path/to/local/archive --files --force "https://dcc.ligo.org/cgi-bin/private/DocDB/DisplayMeeting?sessionid=5120"

The archive directory at ``/path/to/local/archive`` will then contain the DCC records
and files associated with the session.
