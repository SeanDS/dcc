# -*- coding: utf-8 -*-
import sys
import os
import logging
import urllib2
import urlparse
import record
import patterns

class Scraper(object):
    # DCC servers, in order of preference
    net_locations = ["dcc.ligo.org", "dcc-backup.ligo.org", "dcc-lho.ligo.org", "dcc-llo.ligo.org"]
    protocol = "https"
    
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    retrieved_dcc_records = {}
    
    def __init__(self, cookies, logger_stream=sys.stdout):
        self.cookies = cookies
        
        # get pattern matcher
        self.patterns = patterns.DccPatterns()
        
        # create logger
        self._create_logger(logger_stream)
    
    def _create_logger(self, stream):
        # create logger instance
        self.logger = logging.getLogger('DCC Archiver')

        # set minimum level
        self.logger.setLevel(logging.INFO)

        # set OS-specific logging black holes if necessary
        if stream is None:
            stream = open(os.devnull, "w")
        
        # get log handler
        log_handler = logging.StreamHandler(stream)

        # set formatter
        formatter = logging.Formatter(self.log_format)
        log_handler.setFormatter(formatter)

        # add stream handler to logger
        self.logger.addHandler(log_handler)
    
    def scrape(self, url=None, dcc=None):
        if url is not None:
            return self._scrape_by_url(url)
        
        if dcc is not None:
            return self._scrape_by_dcc_str(dcc)
            
        raise Exception("Either the url or dcc number must be specified")
    
    def _scrape_by_url(self, url):
        dcc_number = self._get_dcc_number_from_url(url)
        
        return self._get_dcc_page(dcc_number)
    
    def _scrape_by_dcc_str(self, dcc_str):
        dcc_number = record.DccNumber.init_from_num(dcc_str)
        
        return self._get_dcc_page(dcc_number)
    
    def _get_dcc_page(self, dcc_number):        
        if self._dcc_record_already_gotten(dcc_number):
            self.logger.info("DCC record found in cache")
            
            return self._get_saved_dcc_record(dcc_number)
        
        self._fetch_and_save_dcc_record(dcc_number)
        
        return self._get_saved_dcc_record(dcc_number)
    
    def _dcc_record_already_gotten(self, dcc_number):
        return str(dcc_number) in self.retrieved_dcc_records.keys()
    
    def _get_saved_dcc_record(self, dcc_number):
        return self.retrieved_dcc_records[str(dcc_number)]

    def _fetch_and_save_dcc_record(self, dcc_number):
        url = self._build_dcc_url(dcc_number)
        
        contents = self._get_url_contents(url)
        
        dcc_record = record.DccRecord(dcc_number)
        dcc_record.set_content(contents)
        
        # save
        self.retrieved_dcc_records[str(dcc_number)] = dcc_record
    
    def _build_dcc_url(self, dcc):
        return self.protocol + "://" + self.net_locations[0] + "/" + str(dcc)
    
    def _get_url_contents(self, url):
        opener = urllib2.build_opener()
        opener.addheaders.append(["Cookie", self.cookies])
        
        stream = opener.open(url)
        
        return stream.read()
    
    def _get_dcc_number_from_url(self, url):
        parsed_url = urlparse.urlparse(url)
        
        if parsed_url.netloc not in self.net_locations:
            raise Exception("Specified URL is not a DCC one")
        
        return self._get_dcc_number_from_path(parsed_url.path)
    
    def _get_dcc_number_from_path(self, path):        
        # search for DCC number in path
        return self.patterns.get_dcc_number_from_string(path, mixed=True)