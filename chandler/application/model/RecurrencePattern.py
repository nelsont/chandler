#!bin/env python

"""Model object representing recurring time based items.

Currently a placeholder, we haven't done the full schema yet for this class.
"""

__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2002 Open Source Applications Foundation"
__license__ = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

from persistence.dict import PersistentDict

from RdfObject import RdfObject
from RdfRestriction import RdfRestriction

from RdfNamespace import chandler

class RecurrencePattern(RdfObject):
    """RecurrencePattern"""

    # Define the schema for RecurrencePattern
    # ---------------------------------------

    rdfs = PersistentDict()

    def __init__(self):
        RdfObject.__init__(self)

