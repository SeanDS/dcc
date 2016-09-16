# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup as bs
import patterns

class DccNumber(object):
    def __init__(self, category, numeric, version=None):
        if not patterns.DccPatterns.is_category_letter(category):
            raise Exception("Invalid category letter")
        
        if not patterns.DccPatterns.is_dcc_numeric(numeric):
            raise Exception("Invalid numeric")
        
        if version is not None:
            version = int(version)
            
            if not patterns.DccPatterns.is_dcc_version(version):
                raise Exception("Invalid version")
        
        self.category = category
        self.numeric = numeric
        self.version = version
    
    @classmethod
    def init_from_num(cls, dcc_num):
        dcc_patterns = patterns.DccPatterns()
        
        return dcc_patterns.get_dcc_number_from_string(dcc_num, mixed=False)
    
    def get_version_str(self):
        if self.version is None:
            return "v?"
        elif self.version is 0:
            return "x0"
        
        return "v{0}".format(self.version)
    
    def __repr__(self):
        return "{0}{1}-{2}".format(self.category, self.numeric, self.get_version_str())

class DccRecord(object):
    def __init__(self, dcc_number):
        self.dcc_number = dcc_number
        
        # default empty content
        self.content = None
    
    def has_content(self):
        return self.content is not None
    
    def set_content(self, content):
        self.content = content
    
    @classmethod
    def init_from_page(cls, page):
        # patterns object
        dcc_patterns = patterns.DccPatterns()
        
        navigator = cls._get_html_navigator(page)
        
        # get dcc number using page title
        dcc_number = cls._extract_full_dcc_number_from_page_title(navigator, dcc_patterns)
        
        return cls(dcc_number)
    
    @classmethod
    def _extract_full_dcc_number_from_page_title(cls, navigator, dcc_patterns):
        # find title h1
        title = navigator.find(id='title')
        
        if title.name != 'h1':
            raise UnexpectedHtmlElementException()
        
        # get DCC number
        return dcc_patterns.get_dcc_number_from_string(title.string, mixed=True, require_full=True)

    @classmethod
    def _get_html_navigator(cls, page_content):
        return bs(page_content, 'html.parser')
    
    def _get_content_navigator(self):
        if not self.has_content():
            raise Exception("Page content not yet downloaded")
        
        # parse page content in navigator
        return self._get_html_navigator(self.content)
    
    def _extract_versions(self):
        navigator = self._get_content_navigator()
        
        # get div containing other versions
        versions_div = navigator.find(id='OtherVersions')
        
        if versions_div.name != 'div':
            raise UnexpectedHtmlElementException()
        
        # create dcc pattern matcher
        dcc_patterns = patterns.DccPatterns()
        
        # find all DCC strings in the list of anchor elements        
        return [dcc_patterns.get_dcc_number_from_string(tag['title'], require_version=True) for tag in versions_div.find_all('a')]
    
    def _extract_files(self):
        navigator = self._get_content_navigator()
        
        # get files lists
        files_classes = navigator.find_all("dd", class_="FileList")
        
        files = []
        
        for files_class in files_classes:
            files.extend([DccFile(url_tag.string, url_tag['title'], url_tag['href']) for url_tag in files_class.find_all("a")])
        
        return files

class DccFile(object):
    def __init__(self, title, filename, url):
        self.title = title
        self.filename = filename
        self.url = url

class UnexpectedHtmlElementException(Exception):
    pass