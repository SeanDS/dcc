"""DCC exceptions."""


class NotLoggedInError(Exception):
    """Error due to user not being logged in."""

    def __init__(self, *args, **kwargs):
        super().__init__("You are not logged in to the DCC.", *args, **kwargs)


class UnrecognisedDCCRecordError(Exception):
    """Error for when a page is not recognised by the DCC server."""

    def __init__(self, *args, **kwargs):
        super().__init__(
            "The retrieved page was not recognised as a valid record.", *args, **kwargs
        )


class UnauthorisedError(Exception):
    """Error for when a document is not available to the user to be viewed."""

    def __init__(self, *args, **kwargs):
        super().__init__(
            "You do not have permission to view this record.", *args, **kwargs
        )


class UnknownError(Exception):
    """Error for when an unknown error is reported by the DCC."""

    def __init__(self, *args, **kwargs):
        super().__init__(
            "An unknown error occurred; please report this to the developers.",
            *args,
            **kwargs
        )


class NoVersionError(Exception):
    """Exception for when a DCC number has not got a version specified."""

    def __init__(self, *args, **kwargs):
        super().__init__("The DCC number has no specified version.", *args, **kwargs)


class DryRun(Exception):
    """A dry run has taken place."""
