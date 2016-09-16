# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup as bs
import patterns

class DccNumber(object):
    """Represents a DCC number, including category, numeric and version"""
    
    def __init__(self, category, numeric, version=None):
        """Instantiates a DccNumber object
        
        :param category: DCC category
        :param numeric: DCC record number
        :param version: DCC record version
        """
        
        # check that the category is valid
        if not patterns.DccPatterns.is_category_letter(category):
            raise Exception("Invalid category letter")
        
        # check that the DCC number is valid
        if not patterns.DccPatterns.is_dcc_numeric(numeric):
            raise Exception("Invalid numeric")
        
        # check that the version is valid, if it is specified
        if version is not None:            
            if not patterns.DccPatterns.is_dcc_version(version):
                raise Exception("Invalid version")
        
        # set the values
        self.category = category
        self.numeric = numeric
        self.version = version
    
    @classmethod
    def init_from_num(cls, dcc_str):
        """Instantiate a DccNumber object from a DCC string
        
        :param dcc_str: string presenting DCC designator
        """
        
        # create a pattern matcher object
        dcc_patterns = patterns.DccPatterns()
        
        # match the DCC number and return a new object representing it
        return dcc_patterns.get_dcc_number_from_string(dcc_str, mixed=False)
    
    def get_version_str(self):
        """Get the version suffix"""
        
        # when no version is known, use a question mark
        if self.version is None:
            return "v?"
        # when the version is zero, use an x (consistent with DCC)
        elif self.version is 0:
            return "x0"
        
        # return the formatted version string
        return "v{0}".format(self.version)
    
    def __repr__(self):
        """String representation of the DCC number"""
        return "{0}{1}-{2}".format(self.category, self.numeric, self.get_version_str())

class DccRecord(object):
    """Represents a DCC record"""
    
    def __init__(self, dcc_number):
        """Instantiates a DCC record
        
        :param dcc_number: DCC number object representing the record
        """
        
        self.dcc_number = dcc_number
        
        # default empty content
        self.content = None
    
    def has_content(self):
        """Checks if the record content has been downloaded"""
        
        return self.content is not None
    
    def set_content(self, content):
        """Sets the record content"""
        
        self.content = content
    
    @classmethod
    def init_from_page(cls, content):
        """Instantiates a DccRecord given page content
        
        :param content: page content to set
        """
        
        # create a pattern matcher object
        dcc_patterns = patterns.DccPatterns()
        
        # get a navigator object for the content
        navigator = cls._get_html_navigator(content)
        
        # get dcc number using content title
        dcc_number = cls._extract_full_dcc_number_from_page_title(navigator, dcc_patterns)
        
        # instantiate and return the object given the DCC number
        return cls(dcc_number)
    
    @classmethod
    def _extract_full_dcc_number_from_page_title(cls, navigator, dcc_patterns):
        """Extracts the DCC number with version from the DCC record page's title
        
        :param navigator: navigator object to search document
        :param dcc_patterns: patterns object to match DCC number
        """
        
        # find title
        title = navigator.find("h1", id='title')
        
        # make sure it was found
        if title is None:
            raise DccRecordTitleNotFoundException()
        
        # get and return DCC number
        return dcc_patterns.get_dcc_number_from_string(title.string, mixed=True, require_full=True)

    @classmethod
    def _get_html_navigator(cls, content):
        """Creates a navigator object for the specified HTML document
        
        :param content: content to navigate
        """
        
        # create and return a BeautifulSoup object
        return bs(content, 'html.parser')
    
    def _get_content_navigator(self):
        """Gets a navigator object for the page content"""
        
        # make sure the page content has been downloaded
        if not self.has_content():
            raise Exception("Page content not yet downloaded")
        
        # parse page content in navigator
        return self._get_html_navigator(self.content)
    
    def _extract_versions(self):
        """Extract the version from the page content"""
        
        # get a navigator object for the record
        navigator = self._get_content_navigator()
        
        # get div containing other versions
        versions_div = navigator.find("div", id='OtherVersions')
        
        # check it was found
        if versions_div is None:
            raise DccRecordTitleNotFoundException()
        
        # create dcc pattern matcher
        dcc_patterns = patterns.DccPatterns()
        
        # find all DCC strings in the list of anchor elements        
        return [dcc_patterns.get_dcc_number_from_string(tag['title'], require_version=True) for tag in versions_div.find_all('a')]
    
    def _extract_files(self):
        """Extract a list of files within this DCC record"""
        
        # get a navigator object for the record
        navigator = self._get_content_navigator()
        
        # get files lists
        files_classes = navigator.find_all("dd", class_="FileList")
        
        # empty files list
        files = []
        
        # loop over found classes, searching for URLs and creating corresponding DccFile objects in the list
        for files_class in files_classes:
            files.extend([DccFile(url_tag.string, url_tag['title'], url_tag['href']) for url_tag in files_class.find_all("a")])
        
        # return list of DccFile objects
        return files

class DccFile(object):
    """Represents a file attached to a DCC document"""
    
    def __init__(self, title, filename, url):
        """Instantiates a DCC file object
        
        :param title: file title
        :param filename: filename
        :param url: file URL string
        """
        
        self.title = title
        self.filename = filename
        self.url = url

class DccRecordTitleNotFoundException(Exception):
    pass