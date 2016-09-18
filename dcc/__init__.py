# -*- coding: utf-8 -*-
import logging

# add a null handler to the root to suppress warnings about no handler
logging.getLogger().addHandler(logging.NullHandler())