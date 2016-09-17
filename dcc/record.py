# -*- coding: utf-8 -*-
import logging
import patterns

class DccNumber(object):
    """Represents a DCC number, including category and numeric identifier"""
    
    """Category"""
    category = None
    
    """Numeric part"""
    numeric = None
    
    """Version of the DCC record"""
    version = None
    
    def __init__(self, first_id, numeric=None, version=None):
        """Instantiates a DccNumber object
        
        You must either provide a string containing the DCC number, or the
        separate category and numeric parts, with optional version, e.g.
            __init__("T1234567")
            __init__("T", 1234567) # equivalent to T1234567
            __init__("T", 1234567, 4) # equivalent to T1234567-v4
        
        :param first_id: category character, or the full DCC number
        :param numeric: numeric designator of DCC document
        :param version: version number of DCC document
        """
        
        if numeric is None:
            # full number specified, so check it's long enough
            if len(first_id) < 2:
                raise ValueError("Invalid DCC number; should be of the form \"T1234567\"")
            
            try:
                # find where the hyphen denoting version is
                hyphen_index = first_id.index('-')
            except ValueError as e:
                # couldn't find it
                hyphen_index = None
            
            if hyphen_index is not None:
                # numeric part is between second character and index
                numeric = first_id[1:hyphen_index]
                
                # version is last part, two places beyond start of hyphen
                version = first_id[hyphen_index+2:]
            else:
                # numeric is everything after first character
                numeric = first_id[1:]
            
            # category should be first
            category = first_id[0]
        else:
            # category is the first argument
            category = first_id
        
        # set the values
        self.category = str(category)
        self.numeric = int(numeric)
        
        # validate version if it was found
        if version is not None:
            self.version = int(version)
    
    def __str__(self):
        """String representation of the DCC number"""
        
        return "{0}{1}{2}".format(self.category, self.numeric, self.get_version_suffix())
    
    def __eq__(self, other_dcc_number):
        """Checks if the specified DCC number is equal to this one
        
        :param other_dcc_number: other DCC number to compare
        """
        
        # compare the category and number
        return (other_dcc_number.category == self.category) and (other_dcc_number.numeric == self.numeric)
    
    def __ne__(self, other_dcc_number):
        """Checks if the specified DCC number is not equal to this one
        
        :param other_dcc_number: other DCC number to compare
        """
        
        return not self.__eq__(other_dcc_number)
    
    def get_version_suffix(self):
        """Returns the DCC URL suffix for the version number"""
        
        # version 0 should end "x0", otherwise "v1" etc.
        if self.version is None:
            return "-v?"
        elif self.version is 0:
            return "-x0"
        else:
            return "-v{0}".format(self.version)

class DccRecord(object):
    """Represents a DCC record"""
    
    """Title"""
    title = None
    
    """Other version numbers associated with this record"""
    other_version_numbers = []
    
    """Files associated with this record"""
    files = []
    
    def __init__(self, dcc_number):
        """Instantiates a DCC record
        
        :param dcc_number: DCC number object representing the record
        """
        
        # create logger
        self.logger = logging.getLogger("record")
        
        self.dcc_number = dcc_number

    def __str__(self):
        """String representation of the DCC record"""
        
        return "{0}: {1}".format(self.dcc_number, self.title)
    
    @property
    def versions(self):
        """Returns a list of versions associated with this record"""
        
        versions_list = self.other_version_numbers
        versions_list.append(self.dcc_number.version)
        
        return versions_list
    
    @property
    def filenames(self):
        """Returns a list of filenames associated with this record"""
        
        return [str(dcc_file) for dcc_file in self.files]
    
    def add_version_number(self, version_number):
        """Adds the specified other version number to the record
        
        :param version_number: version number to add
        """
        
        # validate
        version_number = int(version_number)
        
        self.logger.debug("Adding other version number {0}".format(version_number))
        
        # add to version list
        self.other_version_numbers.append(version_number)
    
    def add_file(self, dcc_file):
        """Adds the specified file to the record
        
        :param dcc_file: DCC file to add
        """
        
        self.logger.debug("Adding file {0}".format(dcc_file))
        
        # add to file list
        self.files.append(dcc_file)
    
    def get_lastest_version_number(self):
        """Returns the latest version number for this record"""
            
        # find highest other version
        max_other_version = max(self.other_version_numbers)
        
        # check if this is greater than the current version
        if max_other_version > self.dcc_number.version:
            return max_other_version
        else:
            return self.dcc_number.version

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
    
    def __str__(self):
        """String representation of the DCC record"""
        
        return "{0} ({1})".format(self.title, self.filename)