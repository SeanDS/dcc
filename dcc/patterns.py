# -*- coding: utf-8 -*-
import logging
import re
import record
from bs4 import BeautifulSoup as bs

class DccPatterns(object):
    """Handles extraction of useful information from DCC pages.
    """
    
    """DCC document type designators and descriptions"""
    document_type_letters = {
        "C": "Contractual or procurement",
        "D": "Drawings",
        "E": "Engineering documents",
        "F": "Forms and Templates",
        "G": "Presentations (eg Graphics)",
        "L": "Letters and Memos",
        "M": "Management or Policy",
        "P": "Publications",
        "Q": "Quality Assurance documents",
        "S": "Serial numbers",
        "T": "Techical notes"
    }
    
    """DCC category and number regular expression"""
    _regex_dcc_number_str = "([a-z])(\\d+)(-[vx](\\d+))?"
    
    """DCC record version regular expression
    Version strings on the DCC are either -vX where X is an integer > 0, or -x0
    """
    _regex_dcc_record_version_str_full = "[a-z]\\d+-[vx](\\d+)"
    
    """Regex string match settings"""
    str_match_settings = re.IGNORECASE
    
    def __init__(self):
        """Instantiates a DccPatterns object, compiling some useful regular expressions"""
        
        # create logger
        self.logger = logging.getLogger("patterns")
        
        # regex matching DCC category and number in strings of the form "T0000000"
        self._regex_dcc_number_string = re.compile(self._regex_dcc_number_str, self.str_match_settings)
    
        # regex matching DCC category and number within a larger string
        self._regex_dcc_number_mixed_string = re.compile(".*?" + self._regex_dcc_number_str + ".*?", self.str_match_settings)
        
        # regex matching DCC record version in strings of the form "T0000000-v5"
        self._regex_dcc_record_version_string = re.compile(self._regex_dcc_record_version_str_full, self.str_match_settings)
        
        # regex matching DCC record version within a larger string
        self._regex_dcc_record_version_mixed_string = re.compile(".*?" + self._regex_dcc_record_version_str_full + ".*?", self.str_match_settings)
    
    def get_dcc_number_from_string(self, string):
        """Extracts the DCC number from a string and returns a DccNumber object
        
        :param string: string to match DCC number in
        """
        
        # search for matches and pass them to another function to validate and create the object; return this object
        return self._dcc_number_from_regex_search(self._regex_dcc_number_mixed_string.search(string))

    def get_dcc_record_version_from_string(self, string):
        """Extracts the DCC record version from a string and returns it
        
        :param string: string to match DCC record version in
        """
        
        # search for matches and pass them to another function to validate and create the object; return this object
        return self._dcc_record_version_from_regex_search(self._regex_dcc_record_version_mixed_string.search(string))
    
    def _dcc_number_from_regex_search(self, regex_search):
        """Validates the matched values in a regular expression search for a DCC number in a string
        
        :param regex_search: search results object from regular expression
        """
        
        # if the regex search is NoneType, that means no valid values were found
        if regex_search is None:
            raise DccNumberNotFoundException()
        
        # extract group
        group = regex_search.groups()
        
        # first match is the category
        category_letter = str(group[0])
        
        # second match is the number
        dcc_numeric = int(group[1])
        
        # check if a version was matched
        if len(group) > 3:
            # version is 3rd item
            version = group[3]
        else:
            version = None
        
        # check category is valid
        if not self.is_category_letter(category_letter):
            raise InvalidDccNumberException()
        
        # check number is valid
        if not self.is_dcc_numeric(dcc_numeric):
            raise InvalidDccNumberException()
        
        # check if version is valid, if it was matched
        if version is not None:
            if not self.is_dcc_version(version):
                raise InvalidDccNumberException()
        
        # return a new DccNumber object representing the matched information
        return record.DccNumber(category_letter, dcc_numeric, version)

    def _dcc_record_version_from_regex_search(self, regex_search):
        """Validates the matched values in a regular expression search for a DCC record version in a string
        
        :param regex_search: search results object from regular expression
        """
        
        # if the regex search is NoneType, that means no valid values were found
        if regex_search is None:
            raise DccNumberNotFoundException()
        
        # extract group
        group = regex_search.groups()
        
        # first match is the version
        version = int(group[0])
        
        # check version is valid
        if not self.is_dcc_version(version):
            raise InvalidDccNumberException()
        
        return version

    def is_category_letter(self, letter):
        """Checks if the specified category letter is valid
        
        :param letter: category letter to check
        """
        
        # check if letter is in list of valid letters
        return letter in self.document_type_letters.keys()
    
    def is_dcc_numeric(self, numeric):
        """Checks if the specified number is a valid DCC numeral
        
        :param numeric: DCC numeral to check
        """
        
        # for now, just check if the number is a positive integer
        # TODO: any other constraints to check, e.g. length?
        return int(numeric) > 0
    
    def is_dcc_version(self, version):
        """Checks if the specified version number is valid
        
        :param version: version to check
        """
        
        return int(version) >= 0

class DccRecordParser(object):
    """Represents a parser for DCC HTML documents"""
    
    def __init__(self, content):
        """Instantiates a record parser with the provided page content
        
        :param content: DCC record page HTML
        """
        
        # create logger
        self.logger = logging.getLogger("patterns")
        
        # create patterns object
        self.dcc_patterns = DccPatterns()
        
        # set page content
        self.content = content
    
    def to_record(self):
        """Returns a DccRecord representing the content"""
        
        # get DCC number
        dcc_number = self._extract_dcc_number()
        
        # create the new DCC record
        dcc_record = record.DccRecord(dcc_number)
        
        # set its title
        dcc_record.title = self._extract_title()
        
        # get other version numbers
        other_version_numbers = self._extract_other_version_numbers()
        
        # set the other versions
        map(dcc_record.add_version_number, other_version_numbers)
        self.logger.info("Found %d other version number(s)", len(other_version_numbers))
        
        # get attached files
        files = self._extract_attached_files()
        
        # set the files
        map(dcc_record.add_file, files)
        self.logger.info("Found %d attached file(s)", len(files))
        
        # return the new record
        return dcc_record
    
    def _get_content_navigator(self):
        """Gets a navigator object for the page content"""
        
        # create and return a BeautifulSoup object
        return bs(self.content, 'html.parser')

    def _extract_dcc_number(self):
        """Extracts the DCC number"""
        
        # get a navigator object for the record
        navigator = self._get_content_navigator()
        
        # find document number element
        doc_num_h = navigator.find("h1", id='title')
        
        # make sure it was found
        if doc_num_h is None:
            raise DccRecordTitleNotFoundException()
        
        # get and return DCC number
        return self.dcc_patterns.get_dcc_number_from_string(doc_num_h.string)

    def _extract_title(self):
        """Extracts the title from the page content"""
        
        # get a navigator object for the record
        navigator = self._get_content_navigator()
        
        # find div holding title
        doc_title_div = navigator.find("div", id='DocTitle')
        
        # make sure it was found
        if doc_title_div is None:
            raise DccRecordTitleNotFoundException()
        
        # the document title is the entire string contained within h1 within this div
        title = str(doc_title_div.find("h1").string)
        
        return title

    def _extract_other_version_numbers(self):
        """Extract a list of other version numbers from the page content"""
        
        # get a navigator object for the record
        navigator = self._get_content_navigator()
        
        # get div containing other versions
        versions_div = navigator.find("div", id='OtherVersions')
        
        # check it was found
        if versions_div is None:
            raise DccRecordTitleNotFoundException()
        
        # find all DCC strings in the list of anchor elements
        return [self.dcc_patterns.get_dcc_record_version_from_string(str(tag['title'])) for tag in versions_div.find_all('a')]
    
    def _extract_attached_files(self):
        """Extract a list of attached files from the page content"""
        
        # get a navigator object for the record
        navigator = self._get_content_navigator()
        
        # get files lists
        files_classes = navigator.find_all("dd", class_="FileList")
        
        # empty files list
        files = []
        
        # loop over found classes, searching for URLs and creating corresponding DccFile objects in the list
        for files_class in files_classes:
            files.extend([record.DccFile(str(url_tag.string), str(url_tag['title']), str(url_tag['href'])) for url_tag in files_class.find_all("a")])
        
        # return list of DccFile objects
        return files

class DccNumberNotFoundException(Exception):
    """Exception for when a DCC number is not found"""
    pass

class InvalidDccNumberException(Exception):
    """Exception for when a DCC number is invalid"""
    pass

class DccRecordTitleNotFoundException(Exception):
    """Exception for when a DCC record title is not found in the page content"""
    pass