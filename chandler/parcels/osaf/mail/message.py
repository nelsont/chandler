__revision__  = "$Revision$"
__date__      = "$Date$"
__copyright__ = "Copyright (c) 2004 Open Source Applications Foundation"
__license__   = "http://osafoundation.org/Chandler_0.1_license_terms.htm"

import osaf.contentmodel.mail.Mail as Mail
import repository.util.UUID as UUID
import repository.persistence.XMLRepositoryView as XMLRepositoryView
import mx.DateTime as DateTime
import email as email
import email.Message as Message
import email.Utils as Utils
import re as re
import common as common
import logging as logging

__exp = "\w+((-\w+)|(\.\w+)|(\_\w+))*\@[A-Za-z2-9]+((\.|-)[A-Za-z0-9]+)*\.[A-Za-z]{2,5}"


def isValidEmailAddress(emailAddress):
    """
    This method tests an email address for valid syntax as defined RFC 822
    ***Warning*** This method  will return False if Name and Address is past
    i.e. John Jones <john@jones.com>. The method only validates against the actual
    email address i.e. john@jones.com

    @param emailAddress: A string containing a email address to validate. Please see ***Warning*** for more
                         details
    @type addr: C{String}
    @return: C{Boolean}
    """
    if not __isString(emailAddress):
        return False

    emailAddress = emailAddress.strip()

    #XXX: Test id the address is in the form John test <john@test.com and handle it>
    #emailAddress = Utils.parseaddr(emailAddress)[1]
    if len(emailAddress) > 3:
        if re.match("\w+((-\w+)|(\.\w+)|(\_\w+))*\@[A-Za-z0-9]+((\.|-)[A-Za-z0-9]+)*\.[A-Za-z]{2,5}", emailAddress) is not None:
            return True

    return False

def emailAddressesAreEqual(emailAddressOne, emailAddressTwo):
    """
    This method tests whether two email addresses are the same.
    Addresses can be in the form john@jones.com or John Jones <john@jones.com>.
    The method strips off the username and <> brakets if they exist and just compares
    the actual email addresses for equality. It will not look to see if each
    address is RFC 822 compliant only that the strings match. Use C{message.isValidEmailAddress}
    to test for validity.

    @param emailAddressOne: A string containing a email address to compare.
    @type emailAddressOne: C{String}
    @param emailAddressTwo: A string containing a email address to compare.
    @type emailAddressTwo: C{String}
    @return: C{Boolean}
    """

    #XXX: There are bugs here because of the weakness of the parseaddr API
    if not __isString(emailAddressOne) or not __isString(emailAddressTwo):
        return False

    emailAddressOne = Utils.parseaddr(emailAddressOne)[1]
    emailAddressTwo = Utils.parseaddr(emailAddressTwo)[1]

    return emailAddressOne.lower() == emailAddressTwo.lower()

def dateTimeToRFC2882Date(dateTime):
    return Utils.formatdate(dateTime.ticks(), True)

def format_addr(emailAddress):
    if not isinstance(emailAddress, Mail.EmailAddress):
        return None

    if hasValue(emailAddress.fullName):
        return emailAddress.fullName + " <" + emailAddress.emailAddress + ">"

    return emailAddress.emailAddress

def createMessageID():
    return Utils.make_msgid()

def hasValue(value):
    """
    This method determines if a String has one or more non-whitespace characters.
    This is useful in checking that a Subject or To address field was filled in with
    a useable value

    @param value: The String value to check against. The value can be None
    @type value: C{String}
    @return: C{Boolean}
    """
    if __isString(value):
        test = value.strip()
        if len(test) > 0:
            return True

    return False

def isPlainTextContentType(contentType):
    if __isString(contentType):
        contentType = contentType.lower().strip()

        if contentType == common.MIME_TEXT_PLAIN:
            return True

    return False

def createChandlerHeader(postfix):
    if not hasValue(postfix):
        return None

    return common.CHANDLER_HEADER_PREFIX + postfix

def isChandlerHeader(header):
    if not hasValue(header):
        return False

    if header.startswith(common.CHANDLER_HEADER_PREFIX):
        return True

    return False

def messageTextToKind(messageText):
    """
    This method converts a email message string to
    a Chandler C{Mail.MailMessage} object

    @param messageText: A string representation of a mail message
    @type messageText: string
    @return: C{Mail.MailMessage}
    """

    if not isinstance(messageText, str):
        raise TypeError("messageText must be a String")

    return messageObjectToKind(email.message_from_string(messageText), messageText)

def messageObjectToKind(messageObject, messageText=None):
    """
    This method converts a email message string to
    a Chandler C{Mail.MailMessage} object

    @param messageObject: A C{email.Message} object representation of a mail message
    @type messageObject: C{email.Message}
    @return: C{Mail.MailMessage}
    """

    if not isinstance(messageObject, Message.Message):
        raise TypeError("messageObject must be a Python email.Message.Message instance")

    m = Mail.MailMessage()

    if messageText is None or type(messageText) != str:
        messageText = messageObject.as_string()

    # Save the original message text in a text blob
    m.rfc2822Message = strToText(m, "rfc2822Message", messageText)

    # XXX: Will ned to manually extract the received header and references

    if m is None:
        raise TypeError("Repository returned a MailMessage that was None")

    date = messageObject['Date']

    if date is not None:
        m.dateSent = DateTime.mktime(Utils.parsedate(date))
        m.dateSentString = date
        del messageObject['Date']

    #XXX: Will this fail at the Repository level
    else:
        m.dateSent = None

    m.dateReceived = DateTime.now()

    __assignToKind(m, messageObject, 'Subject', 'String', 'subject')
    __assignToKind(m, messageObject, 'Content-Type', 'String', 'contentType')
    __assignToKind(m, messageObject, 'Content-Length', 'String', 'contentLength')
    __assignToKind(m, messageObject, 'Content-Transfer-Encoding', 'String', 'contentTransferEncoding')
    __assignToKind(m, messageObject, 'Mime-Version', 'String', 'mimeVersion')
    __assignToKind(m, messageObject, 'Message-ID', 'String', 'messageId')
    __assignToKind(m, messageObject, 'Return-Path', 'String', 'returnPath')
    __assignToKind(m, messageObject, 'In-Reply-To', 'String', 'inReplyTo')
    __assignToKind(m, messageObject, 'From', 'EmailAddress', 'fromAddress')
    __assignToKind(m, messageObject, 'Reply-To', 'EmailAddress', 'replyToAddress')
    __assignToKind(m.toAddress, messageObject, 'To', 'EmailAddressList')
    __assignToKind(m.ccAddress, messageObject, 'Cc', 'EmailAddressList')
    __assignToKind(m.bccAddress, messageObject, 'Bcc', 'EmailAddressList')
    __assignToKind(m.references, messageObject, 'References', 'StringList')
    __assignToKind(m.received, messageObject, 'Received', 'StringList')

    m.chandlerHeaders = {}
    m.additionalHeaders = {}

    for (key, val) in messageObject.items():

        if isChandlerHeader(key):
            m.chandlerHeaders[key] =  val

        else:
            m.additionalHeaders[key] = val

        try:
            del messageObject[key]

        except KeyError:
            logging.error("in osaf.mail.message.messageObjectToKind: KEY ERROR")

    if messageObject.is_multipart():
        mimeParts = messageObject.get_payload()
        found = False
        m.hasMimeParts = True
        m.mimeParts = []

        for mimePart in mimeParts:
            if isPlainTextContentType(mimePart.get_content_type()):
                m.body = strToText(m, "body",  mimePart.get_payload())
                found = True



        if not found:
            m.body = strToText(m, "body", common.ATTACHMENT_BODY_WARNING)

    else:
        m.body = strToText(m, "body", messageObject.get_payload())

    return m

def kindToMessageObject(mailMessage):
    """
    This method converts a email message string to
    a Chandler C{Mail.MailMessage} object

    @param messageObject: A C{email.Message} object representation of a mail message
    @type messageObject: C{email.Message}
    @return: C{Mail.MailMessage}
    """

    if not isinstance(mailMessage, Mail.MailMessage):
        raise TypeError("mailMessage must be an instance of Kind Mail.MailMessage")

    #XXX: To do figure out in relpy to / recieved  / references logic
    messageObject = Message.Message()

    if hasValue(mailMessage.messageId):
       __populateParam(messageObject, 'Message-ID', mailMessage.messageId)
    else:
        messageObject['Message-ID'] = createMessageID()

    messageObject['User-Agent'] = common.CHANDLER_USERAGENT

    __populateParam(messageObject, 'Date', mailMessage.dateSentString)
    __populateParam(messageObject, 'Subject', mailMessage.subject)
    __populateParam(messageObject, 'Content-Type', mailMessage.contentType)
    __populateParam(messageObject, 'Content-Length', mailMessage.contentLength)
    __populateParam(messageObject, 'Content-Transfer-Encoding', mailMessage.contentTransferEncoding)
    __populateParam(messageObject, 'MIME-Version', mailMessage.mimeVersion)
    __populateParam(messageObject, 'Return-Path', mailMessage.returnPath)
    __populateParam(messageObject, 'In-Reply-To', mailMessage.inReplyTo)

    if len(mailMessage.references) > 0:
        messageObject['References'] = " ".join(mailMessage.references)

    #XXX: This will be a special case because we need multiple received headers
    if len(mailMessage.received) > 0:
        messageObject['Received'] = " ".join(mailMessage.received)

    for (key, val) in mailMessage.chandlerHeaders:
        messageObject[key] = val

    for (key, val) in mailMessage.additionalHeaders:
        messageObject[key] = val

    try:
        payload = mailMessage.body
    except AttributeError:
        payloadStr = ""
    else:
        payloadStr = textToStr(payload)
    messageObject.set_payload(payloadStr)

    __populateParam(messageObject, 'From', mailMessage.fromAddress, 'EmailAddress')
    __populateParam(messageObject, 'Reply-To', mailMessage.replyToAddress, 'EmailAddress')

    to = []

    for address in mailMessage.toAddress:
        if hasValue(address.emailAddress):
            to.append(format_addr(address))

    if len(to) > 0:
        messageObject['To'] = ", ".join(to)

    cc = []

    for address in mailMessage.ccAddress:
        if hasValue(address.emailAddress):
            cc.append(format_addr(address))

    if len(cc) > 0:
        messageObject['Cc'] = ", ".join(cc)

    bcc = []

    for address in mailMessage.bccAddress:
        if hasValue(address.emailAddress):
             bcc.append(format_addr(address))

    if len(bcc) > 0:
        messageObject['Bcc'] = ", ".join(bcc)

    return messageObject


def kindToMessageText(mailMessage):
    """
    This method converts a email message string to
    a Chandler C{Mail.MailMessage} object

    @param messageObject: A C{email.Message} object representation of a mail message
    @type messageObject: C{email.Message}
    @return: C{Mail.MailMessage}
    """

    if not isinstance(mailMessage, Mail.MailMessage):
        raise TypeError("mailMessage must be an instance of Kind Mail.MailMessage")

    messageObject = kindToMessageObject(mailMessage)

    return messageObject.as_string()


def strToText(contentItem, attribute, string):
    if not __isString(string):
        return None

    return contentItem.getAttributeAspect(attribute, 'type').makeValue(string, indexed=False)



def textToStr(text):
    if not isinstance(text, XMLRepositoryView.XMLText):
        return False

    reader = text.getReader()
    string = reader.read()
    reader.close()

    return string

def getMailMessage(UUID):
    if not isinstance(UUID, UUID.UUID):
        return None

    mailMessageKind = Mail.MailParcel.getMailMessageKind()
    return Mail.mailMessageKind.findUUID(UUID)


def __populateParam(messageObject, param, var, type='String'):

    if type == 'String':
        if hasValue(var):
            messageObject[param] = var

    elif(type == 'EmailAddress'):
        if var is not None and hasValue(var.emailAddress):
            messageObject[param] = format_addr(var)


def __assignToKind(kindVar, messageObject, key, type, attr = None):

    if type == "String":
        if messageObject[key] is not None:
            setattr(kindVar, attr, messageObject[key])

    # XXX: This logic will need to be expanded
    elif type == "StringList":
        if messageObject[key] is not None:
            kindVar.append(messageObject[key])

    elif type == "EmailAddress":
        if messageObject[key] is not None:
            addr = Utils.parseaddr(messageObject[key])

            keyArgs = {}
            if hasValue(addr[0]):
                keyArgs['fullName'] = addr[0]

            ea = Mail.EmailAddress.getEmailAddress(addr[1], **keyArgs)

            setattr(kindVar, attr, ea)

    elif type == "EmailAddressList":
        if messageObject[key] is not None:
            for addr in Utils.getaddresses(messageObject.get_all(key, [])):
                keyArgs = {}
                if hasValue(addr[0]):
                    keyArgs['fullName'] = addr[0]

                ea = Mail.EmailAddress.getEmailAddress(addr[1], **keyArgs)
                kindVar.append(ea)
    else:
        logging.error("in osaf.mail.message.__assignToKind: HEADER SLIPPED THROUGH")

    try:
       del messageObject[key]

    except KeyError:
        logging.error("in osaf.mail.message.__assignToKind: KEY ERROR")

def __isString(var):
    if isinstance(var, str) or isinstance(var, unicode):
        return True

    return False

