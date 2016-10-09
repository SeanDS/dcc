from __future__ import unicode_literals

import sys
import logging
import graphviz
import textwrap
import dcc.record

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(name)-16s - %(levelname)-10s - %(message)s'))
logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def unique(dcc_num):
    """Get a unique representation of the DCC number"""

    # just use the numeric part of the DCC number
    return dcc_num.numeric

# fill colours representing each DCC document class
fill_colors = {
    "C": "#E24A33",
    "D": "#92C6FF",
    "E": "#0072B2",
    "F": "#001C7F",
    "G": "#30a2da",
    "L": "#4C72B0",
    "M": "#8EBA42",
    "P": "#6d904f",
    "Q": "#bcbcbc",
    "S": "#7600A1",
    "T": "#D55E00"
}

def get_fill_color(dcc_number):
    """Return an appropriate fill colour for the specified DCC number"""

    return fill_colors[dcc_number.category]

def add_node(record):
    """Add a node to the graph

    :param record: DCC record the node represents
    """

    # wrap the record title into lines
    lines = textwrap.wrap(unicode(record.title), 30)

    # add title in bold
    lines.insert(0, "<B>{0}</B>".format(unicode(record.dcc_number)))

    # implode the lines
    joined_lines = "<BR/>".join(lines)

    # create the full label (wrapped in < and > for graphviz to recognise HTML)
    label = "<<FONT face=\"Helvetica\">{0}</FONT>>".format(joined_lines)

    # add the node, with a colour representing the document type
    dot.node(unique(record.dcc_number), label=label, style="filled", \
    fillcolor=get_fill_color(record.dcc_number))

def download_record_relations(dcc_record, current_level, max_level):
    """Downloads related records to the specified one

    :param dcc_record: DCC record to start at
    :param current_level: current recursion level
    :param max_level: maximum recursion level
    """

    # loop over records related to and referencing this one
    for dcc_number in list(set(dcc_record.related) | set(dcc_record.referenced_by)):
        logger.info("Processing %s", dcc_number)

        # get the related record if necessary
        if not archive.has_record(dcc_number):
            logger.info("Fetching %s", dcc_number)

            # fetch the record
            record = archive.fetch_record(dcc_number)

            # add the record node
            add_node(record)

            # perform recursive search on this record if it's within range
            if current_level + 1 <= max_level:
                download_record_relations(record, current_level + 1, max_level)
        else:
            # fetch the record from the archive
            record = archive.records[archive.get_dcc_number_str(dcc_number)]

        # add a link between the base node and the related node
        dot.edge(unique(dcc_record.dcc_number), unique(record.dcc_number))
    return

# session cookies
print("Enter your session cookies: ")
cookies = raw_input()

# seed DCC number
seed = "P150914"

# output filename (for dot file and PDF)
filename = 'gw150914.gv'

# maximum recusion level beyond seed node
max_level = 10

# directional graph
dot = graphviz.Digraph(comment="GW150914 relations")

# DCC archive
archive = dcc.record.DccArchive(cookies=cookies)

# seed DCC record
seed_record = archive.fetch_record(seed)

# add seed record node
add_node(seed_record)

# download related records
download_record_relations(seed_record, 1, max_level)

# save and display
dot.render(filename, view=True)
