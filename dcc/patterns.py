import re
import record

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
    _regex_str_dcc = "([a-z])(\\d+)"
    
    """DCC category, number and version regular expression
    Version strings on the DCC are either -vX where X is an integer > 0, or -x0
    """
    _regex_str_full_dcc = "([a-z])(\\d+)(-[vx](\\d+))?"
    
    def __init__(self):
        """Instantiates a DccPatterns object, compiling some useful regular expressions"""
        
        # regex matching DCC category and number in strings of the form "T0000000"
        self._regex_dcc_string = re.compile(self._regex_str_dcc, re.IGNORECASE)
    
        # regex matching DCC category and number within a larger string
        self._regex_dcc_mixed_string = re.compile(".*?" + self._regex_str_dcc + ".*?", re.IGNORECASE)
        
        # regex matching DCC category, number and version in strings of the form "T0000000-v5"
        self._regex_full_dcc_string = re.compile(self._regex_str_full_dcc, re.IGNORECASE)
        
        # regex matching DCC category, number and version within a larger string
        self._regex_full_dcc_mixed_string = re.compile(".*?" + self._regex_str_full_dcc + ".*?", re.IGNORECASE)
    
    def get_dcc_number_from_string(self, string, mixed=True, require_version=False):
        """Extracts the DCC number from a string and returns a DccNumber object
        
        :param string: string to match DCC number in
        :param mixed: whether to allow match in a larger string
        :param require_version: whether to require that a version is designated in the match
        """
        
        if mixed:
            # match pattern within a larger string
            pattern = self._regex_full_dcc_mixed_string
        else:
            # match exact pattern
            pattern = self._regex_full_dcc_string
        
        # search for matches and pass them to another function to validate and create the object; return this object
        return self._dcc_number_from_search(pattern.search(string), require_version=require_version)

    def is_dcc_number(self, dcc_str):
        """Checks if the specified string is a valid DCC number
        
        :param dcc_str: the string to check
        """
        
        # search for an exact DCC number, catching a non-match
        try:
            self.get_dcc_number_from_string(dcc_str, mixed=False)
        catch InvalidDccNumberException as e:
            # exception is thrown for a non-match, so return false
            return False
        
        return True
    
    def _dcc_number_from_search(self, regex_search, require_version=False):
        """Validates the matched values in a regular expression search for a DCC number in a string
        
        :param regex_search: search results object from regular expression
        :param require_version: whether to require that a version is specified in the matched string
        """
        
        # if the regex search is NoneType, that means no valid values were found
        if regex_search is None:
            raise DccNumberNotFoundException()
        
        # extract group
        group = regex_search.groups()
        
        # first match is the category
        category_letter = group[0]
        
        # second match is the number
        dcc_numeric = group[1]
        
        # check category is valid
        if not self.is_category_letter(category_letter):
            raise InvalidDccNumberException()
        
        # check number is valid
        if not self.is_dcc_numeric(dcc_numeric):
            raise InvalidDccNumberException()
        
        # find version, if present
        # group[2] is the matched "-v1" string, but we want the actual number, which is the fourth match
        version = group[3]
        
        # if the version is NoneType, and we require it, then throw an exception
        if require_version and version is None:
            raise VersionNotFoundInSearch()
        
        # try to parse the version if it was matched
        if version is not None:
            # check if version number is valid
            if not self.is_dcc_version(version):
                raise InvalidVersionException()
        
        # return a new DccNumber object representing the matched information
        return record.DccNumber(category_letter, dcc_numeric, version)
    
    @classmethod
    def is_category_letter(cls, letter):
        """Checks if the specified category letter is valid
        
        :param letter: category letter to check
        """
        
        # check if letter is in list of valid letters
        return letter in cls.document_type_letters.keys()
    
    @classmethod
    def is_dcc_numeric(cls, numeric):
        """Checks if the specified number is a valid DCC numeral
        
        :param numeric: DCC numeral to check
        """
        
        # for now, just check if the number is a positive integer
        # TODO: any other constraints to check, e.g. length?
        return int(numeric) > 0
    
    @classmethod
    def is_dcc_version(cls, version):
        """Checks if the specified version number is valid
        
        :param version: version to check
        """
        
        return int(version) >= 0

class DccNumberNotFoundException(Exception):
    """Exception for when a DCC number is not found"""
    pass

class InvalidDccNumberException(Exception):
    """Exception for when a DCC number is invalid"""
    pass

class VersionNotFoundInSearch(Exception):
    """Exception for when a version is not found"""
    pass

class InvalidVersionException(Exception):
    """Exception for when a version is invalid"""
    pass