
__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2002 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import xml.sax, xml.sax.saxutils
import cStringIO

from ItemRef import ItemRef, RefArgs
from ItemRef import Values, References, RefDict
from ItemHandler import ItemHandler

from model.util.UUID import UUID
from model.util.Path import Path
from model.util.LinkedMap import LinkedMap
from model.util.PersistentList import PersistentList
from model.util.PersistentDict import PersistentDict


class Item(object):
    'The root class for all items.'
    
    def __init__(self, name, parent, kind):
        '''Construct an Item.

        All items require a parent item unless they are a repository root in
        which case the parent argument is the repository.
        Kind can be None for schema-less operation.
        Items have two sets of attributes: the regular implementation python
        attributes and the Chandler attributes. The latter are kept in a
        separate dictionary and need to be added first with
        Item.setAttributeValue() before they can be accessed or set with the
        '.' operator.
        When an item is persisted only the Chandler attributes are saved.'''
        
        super(Item, self).__init__()

        self._status = 0
        self._uuid = UUID()

        self._values = Values(self)
        self._references = References(self)
        
        self._name = name or self._uuid.str64()
        self._kind = None
        self._root = None

        self._setParent(parent)
        self._setKind(kind)

    def _fillItem(self, name, parent, kind, **kwds):

        self._uuid = kwds['uuid']
        self._name = name or self._uuid.str64()
        self._kind = None
        self._root = None
        self._status = 0

        kwds['values']._setItem(self)
        self._values = kwds['values']
        
        kwds['references']._setItem(self)
        self._references = kwds['references']

        self._setParent(parent, kwds.get('previous'), kwds.get('next'))
        self._setKind(kind)

    def __iter__(self):

        return self.iterChildren()
    
    def __repr__(self):

        if self._status & Item.RAW:
            return super(Item, self).__repr__()

        if self._status & Item.DELETED:
            return "<%s (deleted): %s %s>" %(type(self).__name__, self._name,
                                             self._uuid.str16())
        else:
            return "<%s: %s %s>" %(type(self).__name__, self._name,
                                   self._uuid.str16())

    def __getattr__(self, name):

        if self._status & Item.DELETED:
            raise ValueError, "item is deleted: %s" %(self)

        return self.getAttributeValue(name)

    def __setattr__(self, name, value):

        if name[0] != '_':
            if self._values.has_key(name):
                return self.setAttributeValue(name, value,
                                              _attrDict=self._values)
            elif self._references.has_key(name):
                return self.setAttributeValue(name, value,
                                              _attrDict=self._references)
            elif self._kind is not None and self._kind.hasAttribute(name):
                return self.setAttributeValue(name, value)

        return super(Item, self).__setattr__(name, value)

    def __delattr__(self, name):

        if self._values.has_key(name):
            self.removeAttributeValue(name, _attrDict=self._values)
        elif self._references.has_key(name):
            self.removeAttributeValue(name, _attrDict=self._references)
        else:
            super(Item, self).__delattr__(name)

    def _otherName(self, name):

        otherName = None
        
        if self._kind is not None:
            attribute = self._kind.getAttribute(name)
            if attribute is not None:
                otherName = attribute.getAspect('otherName')
        else:
            attribute = None

        if otherName is None:
            if attribute is not None:
                raise TypeError, 'Undefined other endpoint for %s.%s' %(self.getItemPath(), name)
            elif name.endswith('__for'):
                otherName = name[:-5]
            else:
                otherName = name + '__for'

        return otherName

    def hasAttributeAspect(self, name, aspect):

        if self._kind is not None:
            attribute = self._kind.getAttribute(name)
            if attribute is not None:
                return attribute.hasAspect(aspect)

        return False

    def getAttributeAspect(self, name, aspect, default=None):

        if self._kind is not None:
            attribute = self._kind.getAttribute(name)
            if attribute is not None:
                return attribute.getAspect(aspect, default)

        return default

    def setAttributeValue(self, name, value=None, _attrDict=None):
        """Create and/or set a Chandler attribute.

        This method is only required when the Chandler attribute doesn't yet
        exist or when there is an ambiguity between a python and a Chandler
        attribute, a situation best avoided."""

        self.setDirty()

        isItem = isinstance(value, Item)
        isRef = not isItem and (isinstance(value, ItemRef) or
                                isinstance(value, RefDict))

        if _attrDict is None:
            if self._values.has_key(name):
                _attrDict = self._values
            elif self._references.has_key(name):
                _attrDict = self._references

        if _attrDict is self._references:
            if not (isItem or isRef):
                del _attrDict[name]
            else:
                old = _attrDict.get(name)

                if isinstance(old, ItemRef):
                    old.reattach(self, name,
                                 old.other(self), value, self._otherName(name))
                    return value
                elif isinstance(old, RefDict):
                    old.clear()
                elif old is not None:
                    raise ValueError, old

        elif (isItem or isRef) and _attrDict is self._values:
            del _attrDict[name]

        if isItem:
            otherName = self._otherName(name)
            card = self.getAttributeAspect(name, 'cardinality', 'single')

            if card == 'single':
                value = ItemRef(self, name, value, otherName)
            else:
                refs = self._refDict(name, otherName)
                value = ItemRef(self, name, value, otherName)
                refs[value._getItem()._refName(name)] = value
                value = refs

            self._references[name] = value

        elif isRef:
            self._references[name] = value

        else:
            self._values[name] = value

        return value

    def getAttributeValue(self, name, _attrDict=None, **kwds):
        """Return the named Chandler attribute value.

        If the attribute is not set then attempt to inherit a value if the
        attribute's inheritFrom aspect is set, attempt to return the value
        of the optional 'default' keyword passed to this method, attempt to
        return the value of its defaultValue aspect if set, or finally raise 
        AttributeError. 
        Calling this method is only required when there is a name ambiguity
        between a python and a Chandler attribute, a situation best avoided."""

        try:
            if (_attrDict is self._values or
                _attrDict is None and self._values.has_key(name)):
                return self._values[name]

            elif (_attrDict is self._references or
                  _attrDict is None and self._references.has_key(name)):
                value = self._references[name]
                if isinstance(value, ItemRef):
                    return value.other(self)
                return value

        except KeyError:
            pass

        inherit = self.getAttributeAspect(name, 'inheritFrom', None)
        if inherit is not None:
            value = self
            for attr in inherit.split('.'):
                value = value.getAttributeValue(attr)

            return value

        elif kwds.has_key('default'):
            return kwds['default']

        elif self.hasAttributeAspect(name, 'defaultValue'):
            return self.getAttributeAspect(name, 'defaultValue')

        raise AttributeError, name

    def removeAttributeValue(self, name, _attrDict=None):
        "Remove a Chandler attribute's value."

        self.setDirty()

        if _attrDict is None:
            if self._values.has_key(name):
                _attrDict = self._values
            elif self._references.has_key(name):
                _attrDict = self._references

        if _attrDict is self._values:
            del _attrDict[name]
        elif _attrDict is self._references:
            value = _attrDict[name]
            del _attrDict[name]

            if isinstance(value, ItemRef):
                value.detach(self, name,
                             value.other(self), self._otherName(name))
            elif isinstance(value, RefDict):
                value.clear()
            else:
                raise ValueError, value

    def hasChild(self, name, load=True):

        return (self.__dict__.has_key('_children') and
                self._children.has_key(name, load))

    def hasChildren(self):

        return (self.__dict__.has_key('_children') and
                self._children._firstKey is not None)

    def placeChild(self, child, after):
        """Place a child after another one in this item's children collection.

        To place a children in first position, pass None for after."""
        
        if (child.getItemParent() is self and
            (after is None or after.getItemParent() is self)):

            key = child.getItemName()
            if after is None:
                afterKey = None
            else:
                afterKey = after.getItemName()

            self._children.place(key, afterKey)

        else:
            raise ValueError, '%s or %s not a %s of %s' %(child, after, self)

    def iterChildren(self, load=True):

        if not load:
            if self.__dict__.has_key('_children'):
                for child in self._children._itervalues():
                    yield child

        elif self.__dict__.has_key('_children'):
            for child in self._children:
                yield child

    def iterAttributes(self, valuesOnly=False, referencesOnly=False):
        """Get a generator of (name, value) tuples for attributes of this item.

        By setting valuesOnly to True, no item references are returned.
        By setting referencesOnly to True, only references are returned."""

        if not referencesOnly:
            for attr in self._values.iteritems():
                yield attr

        if not valuesOnly:
            for ref in self._references.iteritems():
                if isinstance(ref[1], ItemRef):
                    yield (ref[0], ref[1].other(self))
                else:
                    yield ref

    def check(self):

        for key, value in self.iterAttributes(referencesOnly=True):
            if isinstance(value, RefDict) and not value._isTransient():
                l = len(value)
                for other in value:
                    l -= 1
                    if l < 0:
                        break
                if l != 0:
                    raise ValueError, "Iterator on %s.%s doesn't match length (%d left for %d total)" %(self.getItemPath(), key, l, len(value))
        
    def getValue(self, attribute, key, default=None, _attrDict=None):
        'Get a value from a multi-valued attribute.'

        if _attrDict is None:
            value = (self._values.get(attribute, None) or
                     self._references.get(attribute, None))
        else:
            value = _attrDict.get(attribute, None)
            
        if value is None:
            return default

        if isinstance(value, dict):
            return value.get(key, default)

        if isinstance(value, list):
            if len(value) < key:
                return value[key]
            else:
                return default

        raise TypeError, "%s is not multi-valued" %(attribute)

    def setValue(self, attribute, value, key=None, alias=None, _attrDict=None):
        """Set a value for a multi-valued attribute, for an optional key.

        When the cardinality of the attribute is 'list' and its type is a
        literals, key must be an integer.
        When the cardinality of the attribute is 'list' and its values are
        references, key may be an integer or the refName of the item value
        to set."""

        self.setDirty()

        isItem = isinstance(value, Item)
        if isItem and key is None:
            key = value._refName(attribute)

        if _attrDict is None:
            if isItem:
                _attrDict = self._references
            else:
                _attrDict = self._values

        attrValue = _attrDict.get(attribute, None)
            
        if attrValue is None:
            card = self.getAttributeAspect(attribute, 'cardinality', 'single')

            if card == 'dict':
                if isItem:
                    attrValue = self._refDict(attribute)
                else:
                    _attrDict[attribute] = PersistentDict(self, key=value)
                    return

            elif card == 'list':
                if isItem:
                    attrValue = self._refDict(attribute)
                else:
                    _attrDict[attribute] = PersistentList(self, value)
                    return
            else:
                self.setAttributeValue(attribute, value, _attrDict)
                return

            _attrDict[attribute] = attrValue

        if isItem and alias:
            attrValue.__setitem__(key, value, alias=alias)
        else:
            attrValue[key] = value

    def addValue(self, attribute, value, key=None, alias=None, _attrDict=None):
        "Add a value for a multi-valued attribute for a given optional key."

        isItem = isinstance(value, Item)
        if isItem and key is None:
            key = value._refName(attribute)
        
        if _attrDict is None:
            if isItem:
                _attrDict = self._references
            else:
                _attrDict = self._values
                
        attrValue = _attrDict.get(attribute, None)

        if attrValue is None:
            self.setValue(attribute, value, key, alias, _attrDict)

        else:
            self.setDirty()

            if isinstance(attrValue, dict):
                if isItem and alias:
                    attrValue.__setitem__(key, value, alias=alias)
                else:
                    attrValue[key] = value
            elif isinstance(attrValue, list):
                attrValue.append(value)
            else:
                self.setAttributeValue(attribute, value, _attrDict)

    def hasKey(self, attribute, key):
        """Tell where a multi-valued attribute has a value for a given key.

        When the cardinality of the attribute is 'list' and its type is a
        literal, key must be an integer.
        When the cardinality of the attribute is 'list' and its values are
        references, key must be an integer or the refName of the item value
        to remove."""

        value = (self._values.get(attribute, None) or
                 self._references.get(attribute, None))

        if isinstance(value, dict):
            return value.has_key(key)
        elif isinstance(value, list):
            return 0 <= key and key < len(value)
        elif value is not None:
            raise TypeError, "%s is not multi-valued" %(attribute)

        return False

    def hasValue(self, attribute, value, _attrDict=None):
        'Tell whether a multi-valued attribute has a given value.'

        if _attrDict is not None:
            attrValue = _attrDict.get(attribute, None)
        else:
            attrValue = (self._values.get(attribute, None) or
                         self._references.get(attribute, None))

        if isinstance(attrValue, RefDict) or isinstance(attrValue, list):
            return value in attrValue

        elif isinstance(attrValue, dict):
            for v in attrValue.itervalues():
                if v == value:
                    return True

        elif attrValue is not None:
            raise TypeError, "%s is not multi-valued" %(attribute)

        return False

    def removeValue(self, attribute, key=None, value=None, _attrDict=None):
        """Remove the value from a multi-valued attribute for a given key.

        When the cardinality of the attribute is 'list' and its type is a
        literal, key must be an integer and value None.
        When the cardinality of the attribute is 'dict' and its type is a
        literal, key must be an existing key and value is ignored.
        When the cardinality of the attribute is 'list' and its
        values are references, key is ignored and value must be the
        referenced item to remove from the collection."""

        if isinstance(value, Item) and key is None:
            key = value._refName(attribute)
            _attrDict = self._references
        
        if _attrDict is not None:
            value = _attrDict[attribute]
        else:
            value = (self._values.get(attribute, None) or
                     self._references.get(attribute, None))

        if value is not None:
            del value[key]
        else:
            raise KeyError, 'No value for attribute %s' %(attribute)

        self.setDirty()

    def _removeRef(self, name):

        del self._references[name]

    def hasAttributeValue(self, name, _attrDict=None):
        'Check for existence of a value for a given Chandler attribute.'

        if _attrDict is None:
            return (self._values.has_key(name) or
                    self._references.has_key(name))
        else:
            return _attrDict.has_key(name)

    def _isAttaching(self):

        return (self._status & Item.ATTACHING) != 0

    def _setAttaching(self, attaching=True):

        if attaching:
            self._status |= Item.ATTACHING
        else:
            self._status &= ~Item.ATTACHING

    def isDeleting(self):

        return (self._status & Item.DELETING) != 0
    
    def isDeleted(self):

        return (self._status & Item.DELETED) != 0
    
    def isDirty(self):

        return (self._status & Item.DIRTY) != 0

    def setDirty(self, dirty=True):
        """Set the dirty bit on the item so that it gets persisted.

        Returns True if the dirty bit was changed from unset to set.
        Returns False otherwise."""
        
        if dirty:
            if self._status & Item.DIRTY == 0:
                repository = self.getRepository()
                if repository is not None and repository.addTransaction(self):
                    self._status |= Item.DIRTY
                    return True
        else:
            self._status &= ~Item.DIRTY

        return False

    def delete(self, recursive=False):
        """Delete this item and disconnect all its item references.

        If this item has children, they are recursively deleted first if
        'recursive' is True.
        If this item has references to other items and the references delete
        policy is 'cascade' then these other items are deleted last.
        A deleted item is no longer reachable through the repository or other
        items. It is an error to access deleted item reference."""

        if (not (self._status & Item.DELETED) and
            not (self._status & Item.DELETING)):

            if not recursive and self.hasChildren():
                raise ValueError, 'item %s has children, delete must be recursive' %(self)

            self.setDirty()
            self._status |= Item.DELETING
            others = []

            for child in self:
                child.delete(True)

            self._values.clear()

            for name in self._references.keys():
                policy = self.getAttributeAspect(name, 'deletePolicy',
                                                 'remove')
                if policy == 'cascade':
                    value = self._references[name]
                    if value is not None:
                        if isinstance(value, ItemRef):
                            others.append(value.other(self))
                        elif isinstance(value, RefDict):
                            others.extend(value.others())
                    
                self.removeAttributeValue(name, _attrDict=self._references)

            self._parent._removeItem(self)
            self._setRoot(None)

            self._status |= Item.DELETED
            self._status &= ~Item.DELETING

            for other in others:
                if other.refCount() == 0:
                    other.delete()
        
    def getItemName(self):
        '''Return this item's name.

        The item name is used to lookup an item in its parent container and
        construct the item's path in the repository.
        To rename an item use Item.rename().'''

        return self._name

    def getItemDisplayName(self):
        """Return this item's display name.

        By definition, the display name is, in order of precedence, the
        value of the 'displayName' attribute, the value of the attribute
        named by the item's Kind 'displayAttribute' attribute or the item's
        intrinsic name."""

        if self.hasAttributeValue('displayName'):
            return self.displayName

        if self._kind is not None:
            if self._kind.hasAttributeValue('displayAttribute'):
                displayAttribute = self._kind.displayAttribute
                if self.hasAttributeValue(displayAttribute):
                    return self.getAttributeValue(displayAttribute)
                
        return self._name

    def _refName(self, name):
        'deprecated'
        
        return self._uuid

    def refCount(self):
        'Return the total ref count for counted references on this item.'

        count = 0

        if not (self._status & Item.DELETED):
            for name in self._references.iterkeys():
                policy = self.getAttributeAspect(name, 'countPolicy', 'none')
                if policy == 'count':
                    count += self._references[name]._refCount()

        return count

    def getUUID(self):
        'Return the Universally Unique ID for this item.'
        
        return self._uuid

    def getItemPath(self, path=None):
        'Return the path to this item relative to its repository.'

        if path is None:
            path = Path()
            
        self._parent.getItemPath(path)
        path.append(self._name)

        return path

    def getRoot(self):
        '''Return this item's repository root.

        All single-slash rooted paths are expressed relative to this root.'''
        
        return self._root

    def _setRoot(self, root):

        oldRepository = self.getRepository()
        self._root = root
        newRepository = self.getRepository()

        if oldRepository is not newRepository:

            if oldRepository is not None and newRepository is not None:
                raise NotImplementedError, 'changing repositories'

            if oldRepository is not None:
                oldRepository._unregisterItem(self)

            if newRepository is not None:
                newRepository._registerItem(self)

                self.setDirty()

        if root:
            if root.getItemName() == 'Schema':
                self._status |= Item.SCHEMA
            else:
                self._status &= ~Item.SCHEMA

        for child in self.iterChildren(load=False):
            child._setRoot(root)

    def getItemParent(self):
        """Return this item's container parent.

        To change the parent, use Item.move()."""

        return self._parent

    def _setKind(self, kind):

        if self._kind is not None:
            self._kind.detach('items', self)

        self._kind = kind

        if self._kind is not None:
            ref = ItemRef(self, 'kind', self._kind, 'items', 'list', False)
            self._references['kind'] = ref

    def getRepository(self):
        """Return this item's repository.

        The item's repository is defined as the item root's parent."""

        if self._root is None:
            return None
        else:
            return self._root._parent

    def rename(self, name):
        'Rename this item.'
        
        self._parent._removeItem(self)
        self._name = name
        self._parent._addItem(self)

    def move(self, parent, previous=None, next=None):
        'Move this item under another container or make it a root.'

        if self._parent is not parent:
            self._parent._removeItem(self)
            self._setRoot(parent._addItem(self, previous, next))
            self._parent = parent

    def _setParent(self, parent, previous=None, next=None):

        if parent is not None:
            self._parent = parent
            self._setRoot(parent._addItem(self, previous, next))
        else:
            self._parent = None

    def _addItem(self, item, previous=None, next=None):

        name = item._name
        
        if self.__dict__.has_key('_children'):

            loading = self.getRepository().isLoading()
            current = self.getItemChild(name, not loading)
                
            if current is not None:
                if loading:
                    print "Warning, deleting %s while loading" %(current)
                current.delete()

        else:
            self._children = Children(self)

        self._children.__setitem__(name, item, previous, next)

        if '_notChildren' in self.__dict__ and name in self._notChildren:
            del self._notChildren[name]
            
        return self._root

    def _removeItem(self, item):

        del self._children[item.getItemName()]

    def getItemChild(self, name, load=True):
        'Return the child as named or None if not found.'

        child = None
        if self.__dict__.has_key('_children'):
            child = self._children.get(name, None, False)

        if load and child is None:
            hasNot = self.__dict__.has_key('_notChildren')
            if not hasNot or not self._notChildren.has_key(name):
                child = self.getRepository()._loadChild(self, name)
                if child is None:
                    if not hasNot:
                        self._notChildren = { name: name }
                    else:
                        self._notChildren[name] = name

        return child

    def isRemote(self):
        'By default, an item is not remote.'

        return False

    def find(self, spec, _index=0, load=True):
        """Find an item as specified or return None if not found.
        
        Spec can be a Path, a UUID or a string in which case it gets coerced
        into one of the former. If spec is a path, the search is done relative
        to the item unless the path is absolute."""

        if isinstance(spec, Path):
            l = len(spec)

            if l == 0 or _index >= l:
                return None

            if _index == 0:
                if spec[0] == '//':
                    return self.getRepository().find(spec, 1, load)

                elif spec[0] == '/':
                    if self._root is self:
                        return self.find(spec, 1, load)
                    else:
                        return self._root.find(spec, 1, load)

            if spec[_index] == '.':
                if _index == l - 1:
                    return self
                return self.find(spec, _index + 1, load)

            if spec[_index] == '..':
                if _index == l - 1:
                    return self._parent
                return self._parent.find(spec, _index + 1, load)

            child = self.getItemChild(spec[_index], load)
            if child is not None:
                if _index == l - 1:
                    return child
                return child.find(spec, _index + 1, load)

        elif isinstance(spec, UUID):
            return self.getRepository().find(spec, 0, load)

        elif isinstance(spec, str) or isinstance(spec, unicode):
            if (spec[0] != '/' and
                (len(spec) == 36 and spec[8] == '-' or len(spec) == 22)):
                return self.find(UUID(spec), 0, load)

            return self.find(Path(spec), 0, load)

        return None

    def toXML(self):

        out = None
        
        try:
            out = cStringIO.StringIO()
            generator = xml.sax.saxutils.XMLGenerator(out, 'utf-8')
            generator.startDocument()
            self._xmlItem(generator,
                          withSchema = (self._status & Item.SCHEMA) != 0)
            generator.endDocument()

            return out.getvalue()

        finally:
            if out is not None:
                out.close()

    def _saveItem(self, generator):

        self._xmlItem(generator,
                      withSchema = (self._status & Item.SCHEMA) != 0,
                      mode = 'save')

    def _xmlItem(self, generator, withSchema=False, mode='serialize'):

        def xmlTag(tag, attrs, value, generator):

            generator.startElement(tag, attrs)
            generator.characters(value)
            generator.endElement(tag)

        kind = self._kind
        attrs = { 'uuid': self._uuid.str64() }
        if withSchema:
            attrs['withSchema'] = 'True'
        generator.startElement('item', attrs)

        xmlTag('name', {}, self._name, generator)

        if kind is not None:
            xmlTag('kind', { 'type': 'uuid' },
                   kind.getUUID().str64(), generator)

        if (withSchema or kind is None or
            kind.getItemClass() is not type(self)):
            xmlTag('class', { 'module': self.__module__ },
                   type(self).__name__, generator)

        attrs = {}

        if self._root is not self:
            parentID = self._parent.getUUID().str64()

            link = self._parent._children._get(self._name)
            if link._previousKey is not None:
                attrs['previous'] = link._previousKey
            if link._nextKey is not None:
                attrs['next'] = link._nextKey

        else:
            parentID = self.getRepository().ROOT_ID.str64()

        if '_children' in self.__dict__:
            children = self._children
            if children._firstKey is not None:
                attrs['first'] = children._firstKey
            if children._lastKey is not None:
                attrs['last'] = children._lastKey

        xmlTag('container', attrs, parentID, generator)

        self._xmlAttrs(generator, withSchema, mode)
        self._xmlRefs(generator, withSchema, mode)

        generator.endElement('item')

    def _loadItem(self):

        return self

    def _xmlAttrs(self, generator, withSchema, mode):

        for key, value in self._values.iteritems():
            if self.getAttributeAspect(key, 'persist', True):
                attrType = self.getAttributeAspect(key, 'type')
                attrCard = self.getAttributeAspect(key, 'cardinality',
                                                   'single')
                ItemHandler.xmlValue(key, value, 'attribute',
                                     attrType, attrCard, generator,
                                     withSchema)

    def _xmlRefs(self, generator, withSchema, mode):

        for key, value in self._references.iteritems():
            if self.getAttributeAspect(key, 'persist', True):
                value._xmlValue(key, self, generator, withSchema, mode)

    def _refDict(self, name, otherName=None, persist=None):

        if otherName is None:
            otherName = self._otherName(name)
        if persist is None:
            persist = self.getAttributeAspect(name, 'persist', True)

        return self.getRepository().createRefDict(self, name,
                                                  otherName, persist)

    def loadClass(cls, name, module=None):

        if module is None:
            lastDot = name.rindex('.')
            module = name[:lastDot]
            name = name[lastDot+1:]

        m = __import__(module, {}, {}, name)

        try:
            cls = getattr(m, name)
            cls.__module__

            return cls

        except AttributeError:
            raise ImportError, "Module %s has no class %s" %(module, name)

    def __new__(cls, *args, **kwds):

        item = object.__new__(cls, *args, **kwds)
        item._status = Item.RAW

        return item


    loadClass = classmethod(loadClass)
    __new__ = classmethod(__new__)
    
    DELETED   = 0x01
    DIRTY     = 0x02
    DELETING  = 0x04
    RAW       = 0x08
    ATTACHING = 0x10
    SCHEMA    = 0x20


class Children(LinkedMap):

    def __init__(self, item, dictionary=None):

        super(Children, self).__init__(dictionary)
        self._item = item
        
    def linkChanged(self, link, key):

        if key is None:
            self._item.setDirty()
        else:
            link._value.setDirty()
    
    def __repr__(self):

        buffer = None

        try:
            buffer = cStringIO.StringIO()
            buffer.write('{(currenly loaded) ')
            first = True
            for key, value in self._iteritems():
                if not first:
                    buffer.write(', ')
                else:
                    first = False
                buffer.write(key.__repr__())
                buffer.write(': ')
                buffer.write(value.__repr__())
            buffer.write('}')

            return buffer.getvalue()

        finally:
            if buffer is not None:
                buffer.close()

    def _load(self, key):

        if self._item.getRepository()._loadChild(self._item, key) is not None:
            return True

        return False
