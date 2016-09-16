import re
import record

class DccPatterns(object):
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
    
    # DCC category and number regex string
    _regex_str_dcc = "([a-z])(\\d+)"
    
    # DCC category, number and version regex string (optional version string)
    # version strings on the DCC are either -vX where X is an integer > 0, or -x0
    _regex_str_full_dcc = "([a-z])(\\d+)(-[vx](\\d+))?"
    
    def __init__(self):
        # DCC number, of the form "X0000000"
        self._regex_dcc_string = re.compile(self._regex_str_dcc, re.IGNORECASE)
    
        # DCC number with whitespace either side, of the form "blah-X0000000-blah"
        self._regex_dcc_mixed_string = re.compile(".*?" + self._regex_str_dcc + ".*?", re.IGNORECASE)
        
        # DCC number with version, of the form "X0000000-v1"
        self._regex_full_dcc_string = re.compile(self._regex_str_full_dcc, re.IGNORECASE)
        
        # DCC number with version, with whitespace either side, of the form "blah-X0000000-blah"
        self._regex_full_dcc_mixed_string = re.compile(".*?" + self._regex_str_full_dcc + ".*?", re.IGNORECASE)
    
    def get_dcc_number_from_string(self, string, mixed=True, require_version=False):
        if mixed:
            pattern = self._regex_full_dcc_mixed_string
        else:
            pattern = self._regex_full_dcc_string
        
        return self._dcc_number_from_search(pattern.search(string), require_version=require_version)

    def is_dcc_number(self, dcc_str):
        # match both type and number
        search = self._regex_dcc_string.search(dcc_str)
        
        try:
            self._dcc_number_from_search(search)
        except DccNumberNotFoundException as e:
            return False
        
        return True
    
    def _dcc_number_from_search(self, regex_search, require_version=False):        
        # NoneType indicates no matches
        if regex_search is None:
            raise DccNumberNotFoundException()
        
        # extract group
        group = regex_search.groups()
        
        category_letter = group[0]
        dcc_numeric = group[1]
        
        # validate letter designator
        if not self.is_category_letter(category_letter):
            raise InvalidDccNumberException()
        
        # validate numeric
        if not self.is_dcc_numeric(dcc_numeric):
            raise InvalidDccNumberException()
        
        # find optional version
        # group[2] is the matched -v1 string, but we want the 4th match representing the version number itself
        version = group[3]
        
        # check if version is required
        if require_version and version is None:
            raise VersionNotFoundInSearch()
        
        if version is not None:
            # validate version since it was found
            if not self.is_dcc_version(version):
                raise InvalidVersionException()
        
        return record.DccNumber(category_letter, dcc_numeric, version)
    
    @classmethod
    def is_category_letter(cls, letter):
        return letter in cls.document_type_letters.keys()
    
    @classmethod
    def is_dcc_numeric(cls, numeric):
        # TODO: add specific constraints
        return int(numeric) > 0
    
    @classmethod
    def is_dcc_version(cls, version):
        return int(version) >= 0

class DccNumberNotFoundException(Exception):
    pass

class InvalidDccNumberException(Exception):
    pass

class VersionNotFoundInSearch(Exception):
    pass

class InvalidVersionException(Exception):
    pass