#!bin/env python

"""Model object representing a group.

Currently a placeholder, we haven't done the full schema yet for this class.
"""

__author__ = "Katie Capps Parlante"
__version__ = "$Revision$"
__date__ = "$Date$"
__copyright__ = "Copyright (c) 2002 Open Source Applications Foundation"
__license__ = "OSAF"

from application.persist import Persist

from RdfObject import RdfObject
from RdfRestriction import RdfRestriction

from EntityItem import EntityItem

class GroupItem(GroupItem):
    """GroupItem"""

    # Define the schema for GroupItem
    # ----------------------------------

    rdfs = Persist.Dict()

    rdfs[chandler.members] = RdfRestriction(EntityItem)

    def __init__(self):
        RdfObject.__init__(self)

    def getMembers(self):
        return self.getRdfAttribute(chandler.members,
                                    GroupItem.rdfs)

    def setMembers(self, members):
        return self.setRdfAttribute(chandler.members,
                                    members,
                                    GroupItem.rdfs)

    members = property(getMembers, setMembers)

