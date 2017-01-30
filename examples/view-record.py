# -*- coding: utf-8 -*-

"""Example of record functionality"""

from dcc.record import DccArchive, DccNumber
import html2text

# terminal colours
class term_col:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    END = '\033[0m'

def print_kv(key, val):
    """Prints a key and value pair to the terminal with colours"""

    print('{0}{1}: {2}{3}{4}'.format(term_col.BLUE, key, term_col.GREEN, val, term_col.END))

def print_k(key):
    """Prints a key to the terminal"""

    print('{0}{1}:{2}'.format(term_col.BLUE, key, term_col.END))

def print_v(val):
    """Prints a value to the terminal"""

    print('{0}{1}{2}'.format(term_col.GREEN, val, term_col.END))

# create new archive
archive = DccArchive()

# fetch the record
record = archive.fetch_record("P150914")

# print some information
print_kv('number', record['dcc_number'])
print_kv('url', archive.fetcher.get_record_url(DccNumber(record['dcc_number']), xml=False))
print_kv('title', record['title'])
print_kv('modified', record['contents_revision_date'])
print_k('authors')
for a in record.authors:
    print_v(a['name'].strip())
print_k('abstract')
print_v(html2text.html2text(record['abstract']))
print_k('note')
print_v(html2text.html2text(record['note']))
print_kv('keywords', ", ".join(record['keywords']))
print_k('files')
for i, f in enumerate(record['files']):
    print_v('  {} {}'.format(i, f))
print_k('referenced by')
for r in record['referenced_by']:
    print_v('  {}'.format(r))
print_k('related')
for r in record['related']:
    print_v('  {}'.format(r))
