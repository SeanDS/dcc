# -*- coding: utf-8 -*-
import logging
import patterns

class DccNumber(object):
    """Represents a DCC number, including category and numeric identifier"""
    
    def __init__(self, category, numeric):
        """Instantiates a DccNumber object
        
        :param category: DCC category
        :param numeric: DCC record number
        """
        
        # set the values
        self.category = str(category)
        self.numeric = int(numeric)
    
    def __str__(self):
        """String representation of the DCC number"""
        
        return "{0}{1}".format(self.category, self.numeric)
    
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

class DccRecord(object):
    """Represents a DCC record"""
    
    """Title"""
    title = None
    
    """Versions associated with this record"""
    record_versions = []
    
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
    
    def add_version(self, record_version):
        """Adds the specified record version to the record
        
        :param record_version: record version to add
        """
        
        self.logger.info("Adding record version {0}".format(record_version.version))
        
        # add to version list
        self.record_versions.append(record_version)

class DccRecordVersion(object):
    """Represents a DCC record with a version"""
    
    """Whether the record has been downloaded"""
    fetched = False
    
    """Version"""
    version = None
    
    """Files"""
    files = []
    
    def __init__(self, dcc_record, version):
        """Instantiates the record version for the associated record
        
        :param dcc_record: DCC record associated with this version
        :param version: record version
        """
        
        # create logger
        self.logger = logging.getLogger("record-version")
        
        self.dcc_record = dcc_record
        self.version = int(version)
    
    @property
    def fetched(self):
        return self.__fetched
    
    @fetched.setter
    def fetched(self, status):
        # set boolean value
        self.__fetched = (status)
    
    def add_file(self, version_file):
        """Adds the specified file to the record version
        
        :param version_file: file to add
        """
        
        self.logger.info("Adding file \"{0}\" to version {1}".format(version_file, self.version))
        
        # add to files list
        self.files.append(version_file)

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