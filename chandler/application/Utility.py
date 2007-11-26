#   Copyright (c) 2003-2007 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Application utilities.
"""

import os, sys, logging, logging.config, logging.handlers, string, glob
import i18n, schema
import M2Crypto.Rand as Rand, M2Crypto.threading as m2threading
from optparse import OptionParser
from configobj import ConfigObj
from i18n import ChandlerSafeTranslationMessageFactory as _

from chandlerdb.util.c import UUID, loadUUIDs, Default
from repository.persistence.DBRepository import DBRepository
from repository.persistence.RepositoryError import \
    VersionConflictError, RepositoryPasswordError, RepositoryVersionError, \
    RepositoryRunRecoveryError
from PyICU import ICUtzinfo

import version

# Increment this value whenever the schema changes, and replace the comment
# with your name (and some helpful text). The comment's really there just to
# cause Subversion to warn you of a conflict when you update, in case someone 
# else changes it at the same time you do (that's why it's on the same line).
SCHEMA_VERSION = "465" # rae: multiweek view

logger = None # initialized in initLogging()

def createProfileDir(profileDir):
    """
    Create the profile directory with the right permissions. 
    
    Will raise exception if the directory cannot be created.
    """
    os.makedirs(profileDir, 0700)

def locateProfileDir():
    """
    Locate the Chandler repository.
    The location is determined either by parameters, or if not specified, by
    the presence of a .chandler directory in the users home directory.
    """

    def _makeRandomProfileDir(pattern):
        chars = string.ascii_letters + string.digits
        name = ''.join([chars[ord(c) % len(chars)] for c in os.urandom(8)])
        profileDir = pattern.replace('*', '%s') %(name)
        createProfileDir(profileDir)
        return profileDir

    if os.name == 'nt':
        dataDir = None

        if os.environ.has_key('APPDATA'):
            dataDir = os.environ['APPDATA']
        elif os.environ.has_key('USERPROFILE'):
            dataDir = os.environ['USERPROFILE']
            if os.path.isdir(os.path.join(dataDir, 'Application Data')):
                dataDir = os.path.join(dataDir, 'Application Data')

        if dataDir is None or not os.path.isdir(dataDir):
            if os.environ.has_key('HOMEDRIVE') and \
                os.environ.has_key('HOMEPATH'):
                dataDir = '%s%s' % (os.environ['HOMEDRIVE'],
                                    os.environ['HOMEPATH'])

        if dataDir is None or not os.path.isdir(dataDir):
            dataDir = os.path.expanduser('~')

        profileDir = os.path.join(dataDir,
                                  'Open Source Applications Foundation',
                                  'Chandler')

    elif sys.platform == 'darwin':
        dataDir = os.path.join(os.path.expanduser('~'),
                               'Library',
                               'Application Support')
        profileDir = os.path.join(dataDir,
                                  'Open Source Applications Foundation',
                                  'Chandler')

    else:
        dataDir = os.path.expanduser('~')
        profileDir = os.path.join(dataDir, '.chandler')

    # Deal with the random part
    pattern = '%s%s*.default' % (profileDir, os.sep)
    try:
        profileDir = glob.glob(pattern)[0]
    except IndexError:
        try:
            profileDir = _makeRandomProfileDir(pattern)
        except:
            profileDir = None
    except:
        profileDir = None

    return profileDir

def getDesktopDir():
    """
    Return a reasonable guess at the desktop folder.
    
    On Mac, returns '~/Desktop'; on Linux, it'll return '~/Desktop' if it 
    exists, or just '~' if not.
    """
    if os.name == 'nt':
        if os.environ.has_key('USERPROFILE'):
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
            if os.path.isdir(desktop):
                return desktop
        return os.path.realpath('.')

    # Linux or Mac.
    homeDir = os.path.expanduser('~')
    desktopDir = os.path.join(homeDir, 'Desktop')
    if (sys.platform == 'darwin' or os.path.isdir(desktopDir)):
        return desktopDir
    return homeDir

def getPlatformID():
    """
    Return an identifier string that represents what platform
    Chandler is being run on.
    """
    import platform

    platformID = 'Unknown'

    if os.name == 'nt':
        platformID = 'win'
    elif os.name == 'posix':
        if sys.platform == 'darwin':
            # platform.processor() returns 'i386' or 'powerpc'
            # but we need to also check platform.machine()
            # which returns 'Power Macintosh' or 'i386'
            # to determine if we are running under Rosetta

            if platform.processor() == 'i386' and platform.machine() == 'i386':
                platformID = 'osx-intel'
            else:
                platformID = 'osx-ppc'
        elif sys.platform == 'cygwin':
            platformID = 'win-cygwin'
        else:
            platformID = 'linux'

    return platformID

def getPlatformName():
    """
    Return a plain text string that represents what platform
    Chandler is being run on.
    """
    platformID   = getPlatformID()
    platformName = platformID

    if platformID == 'linux':
        platformName = 'Linux'
    elif platformID == 'win' or platformID == 'win-cygwin':
        platformName = 'Windows'
    elif platformID == 'osx-intel':
        platformName = 'Mac OS X (intel)'
    elif platformID == 'osx-ppc':
        platformName = 'Mac OS X (ppc)'

    return platformName

def getOSName():
    """
    Return the common name for the OS.
    
    OS X:    'vers-platform', e.g. 10.3-Panther, 10.4-Tiger, 10.5-Leopard
    Linux:   'distribution-codename-version', e.g. Ubuntu-feisty-7.04
             (i.e. the contents of /etc/lsb-release) or
    Windows: returns a string created from the platform name
             and version information returned from
             sys.getwindowsversion()

    returns 'Unknown' if unable to determine any useful values
    """
    import platform

    platformName = getPlatformName()
    result       = 'Unknown'

    if platformName.startswith('Mac OS X'):
        release   = platform.release()
        version   = release.split('.')
        platforms = {'7': '10.3-Panther', '8': '10.4-Tiger', '9': '10.5-Leopard'}

        if len(version) == 3:
            result = platforms.get(version[0], version[0])

    elif platformName == 'Linux':
        if os.path.exists('/etc/lsb-release'):
            codename     = ''
            version      = ''
            distribution = ''

            lines = open('/etc/lsb-release', 'r').readlines()
            for line in lines:
                name,value = line.split('=')
                value      = value[:-1]

                if name.startswith('DISTRIB_CODENAME'):
                    codename = value
                elif name.startswith('DISTRIB_ID'):
                    distribution = value
                elif name.startswith('DISTRIB_RELEASE'):
                    version = value

            result = '%s-%s-%s' % (distribution, version, codename)
    else:
        try:
            major,minor,build,plat,text = sys.getwindowsversion()  # (5, 1, 2600, 2, 'Service Pack 2')
            platforms = {0: 'Win32', 1: 'Win98', 2: 'WinNT', 3: 'WinCE'}
            result    = '%d.%d-%s' % (major, minor, platforms.get(plat, 'Unknown'))
        except AttributeError:
            result = 'Unknown'

    return result

def getUserAgent():
    """
    Construct a rfc spec'd UserAgent string from the platform and version information
    
    Examples:
        OS X Intel: Chandler/0.7.2.dev-r15512 (Macintosh; U; 10.4-Tiger; i386; en_US)
        OS X Intel: Chandler/0.7.2.dev-r15512 (Macintosh; U; 10.5-Leopard; i386; en_US)
        WinXP:      Chandler/0.7.2.dev-r15512 (Windows; U; 5.1-WinNT; i386; en_US)
        Linux:      Chandler/0.7.2.dev-r15513 (Linux; U; Ubuntu-7.04-feisty; i386; en_US)
    """
    platformID = getPlatformID()
    locale     = i18n.getLocale().replace(';()', '')
    osname     = getOSName().replace(';()', '')

    if platformID == 'win' or platformID == 'win-cygwin':
        platform = 'Windows'
        cpu      = 'i386'
    elif platformID == 'osx-intel':
        platform = 'Macintosh'
        cpu      = 'i386'
    elif platformID == 'osx-ppc':
        platform = 'Macintosh'
        cpu      = 'PPC'
    else:
        platform = 'Linux'
        cpu      = 'i386'

    return 'Chandler/%s (%s; U; %s; %s; %s)' % (version.version, platform, osname, cpu, locale)

# short opt, long opt, type flag, default value, env var, help text
COMMAND_LINE_OPTIONS = {
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'parcelPath': ('-p', '--parcelPath', 's', None,  'PARCELPATH', _(u'Parcel search path')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'pluginPath': (''  , '--pluginPath', 's', 'plugins',  None, _(u'Plugin search path, relative to CHANDLERHOME')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'webserver':  ('-W', '--webserver',  'v', [], 'CHANDLERWEBSERVER', _(u'Activate the built-in webserver')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'profileDir': ('-P', '--profileDir', 's', '',  'PROFILEDIR', _(u'Location of the Chandler user profile directory (relative to CHANDLERHOME)')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'testScripts':('-t', '--testScripts','b', False, None, _(u'Run all test scripts')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'scriptFile': ('-f', '--scriptFile', 's', None,  None, _(u'Script file to execute after startup')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'chandlerTests': ('', '--chandlerTests', 's', None, None, _(u'file:TestClass,file2:TestClass2 to be executed by new framework')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'chandlerTestSuite': ('-T', '--chandlerTestSuite', 'b', False, None, _(u'Run the functional test suite')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'chandlerTestDebug': ('-D', '--chandlerTestDebug', 's', 0, None, _(u'0=Print Only Failures, 1=Print Pass And Fail, 2=Print Pass and Fail, Check Repository After Each Test')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'recordedTest': ('', '--recordedTest', 's', None, None, _(u'Run a recorded test from the recorded_scripts directory. Use "all" to run full suite.')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'chandlerTestMask': ('-M', '--chandlerTestMask', 's', 3, None, _(u'0=Print All, 1=Hide Reports, 2=Also Hide Actions, 3=Also Hide Test Names')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'chandlerPerformanceTests': ('', '--chandlerPerformanceTests', 's', None, None, _(u'file:TestClass,file2:TestClass2 to be executed by performance new framework')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'chandlerTestLogfile': ('', '--chandlerTestLogfile', 's', None, None, _(u'File for chandlerTests output')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'continueTestsOnFailure': ('-F','--continueTestsOnFailure', 'b', False, None, _(u'Do not stop functional test suite on first failure')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'catsProfile':('',   '--catsProfile','s', None,  None, _(u'File for hotshot profile of script execution')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'catsPerfLog':('',   '--catsPerfLog','s', None,  None, _(u'File to output a performance number')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'stderr':     ('-e', '--stderr',     'b', False, None, _(u'Echo error output to log file')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'create':     ('-c', '--create',     'b', False, "CREATE", _(u'Force creation of a new repository')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'ask':        ('',   '--ask',        'b', False, None, _(u'Give repository options on startup')),
    'ramdb':      ('-m', '--ramdb',      'b', False, None, ''),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'restore':    ('-r', '--restore',    's', None,  None, _(u'Repository backup to restore from before repository open')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'recover':    ('-R', '--recover',    'b', False, None, _(u'Open repository with recovery')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'forceplatform': ('', '--force-platform', 'b', False, None, _(u'Open repository with recovery if platform of env does not match current platform')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'reload':     ('',   '--reload',     's', None, None, _(u'Reload a .chex file, will clear repository first')),
    # --nocatch is deprecated and will be removed soon: use --catch=tests or --catch=never instead
    'nocatch':    ('-n', '--nocatch',    'b', False, 'CHANDLERNOCATCH', ''),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'catch':      ('',   '--catch',      's', 'normal', 'CHANDLERCATCH', _(u'The command "normal" leaves outer and test exception handlers in place (the default); "tests" removes the outer one, and "never" removes both.')),
    'wing':       ('-w', '--wing',       'b', False, None, ''),
    'komodo':     ('-k', '--komodo',     'b', False, None, ''),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'locale':     ('-l', '--locale',     's', None,  None, _(u'Set the default locale')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'expand':      ('',   '--expand',      's', '0', None, _(u'Expands the length of localized strings by the percentage specified between 0 and 100')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'encrypt':    ('-S', '--encrypt',    'b', False, None, _(u'Request prompt for password for repository encryption')),
    'nosplash':   ('-N', '--nosplash',   'b', False, 'CHANDLERNOSPLASH', ''),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'logging':    ('-L', '--logging',    's', 'logging.conf',  'CHANDLERLOGCONFIG', _(u'The logging config file')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'verbose':    ('-v', '--verbose',    'b', False, None, _(u'Verbosity option (currently just for run_tests.py)')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'quiet':      ('-q', '--quiet',      'b', False, None, _(u'Quiet option (currently just for run_tests.py)')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'offline':    ('', '--offline',    'b', False, 'CHANDLEROFFLINE', _(u'Takes the Chandler mail service offline')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'verify':     ('-V', '--verify-assignments', 'b', False, None, _(u'Verify attribute assignments against schema')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'debugOn':    ('-d', '--debugOn', 's', None,  None, _(u'Enter PDB upon this exception being raised')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'appParcel':  ('-a', '--app-parcel', 's', "osaf.app",  None, _(u'Parcel that defines the core application')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'nonexclusive':  ('', '--nonexclusive', 'b', False, 'CHANDLERNONEXCLUSIVEREPO', _(u'Enable non-exclusive repository access')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'memorylog':  ('', '--memorylog', 's', None, None, _(u'Specify a buffer size (in MB) for in-memory transaction logs')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'logdir':     ('', '--logdir', 's', None, None, _(u'Specify a directory for transaction logs (relative to the __repository__ directory')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'datadir':    ('', '--datadir', 's', None, None, _(u'Specify a directory for database files (relative to the __repository__ directory')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'repodir':    ('', '--repodir', 's', None, None, _(u"Specify a home directory for the __repository__ directory (relative to the profile directory)")),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'nodeferdelete':   ('', '--nodeferdelete','b', False, None, _(u'Do not defer item deletions in all views by default')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'indexer':    ('-i', '--indexer',    's', '90', None, _(u'Run Lucene indexing in the background every 90s, in the foreground or none')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'checkpoints': ('', '--checkpoints', 's', '10', None, _(u'Checkpoint the repository in the background every 10min, or none')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'uuids':      ('-U', '--uuids',      's', None, None, _(u'Use a file containing a bunch of pre-generated UUIDs')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'undo':       ('',   '--undo',       's', None, None, _(u'Undo -<n> versions or until version <n> or until <check> or <repair> pass or until <start> succeeds')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'backup':     ('',   '--backup',     'b', False, None, _(u'Backup repository before start')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'backupDir':  ('',   '--backup-dir', 's', None, None, _(u'Backup repository before startup into directory')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'repair':     ('',   '--repair',     'b', False, None, _(u'Repair repository before start (currently repairs broken indices)')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'resetIndex': ('',   '--reset-index','b', False, None, _(u'Re-create full-text index database and reset indexer to reindex from earliest version')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'mvcc':       ('',   '--mvcc',       'b', True, 'MVCC', _(u'Run repository multi version concurrency control')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'nomvcc':     ('',   '--nomvcc',     'b', False, 'NOMVCC', _(u'Run repository without multi version concurrency control')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'prune':      ('',   '--prune',      's', '10000', None, _(u'Number of items in a view to prune to after each commit')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'version':    ('',   '--at',         's', None, None, _(u'Version to open repository at')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'timezone':   ('',   '--tz',         's', None, None, _(u'Timezone to initialize repository with if creating a new repository')),
    # L10N: The description of a Chandler command line argument printed to the stdout / console
    'prefs':      ('',   '--prefs',      's', 'chandler.prefs', None, _(u'Path to prefs file that contains defaults for command line options, relative to profile directory')),
}

def initDefaults(**kwds):
    """
    Return a default command line options object from
    COMMAND_LINE_OPTIONS dict, optional env vars and optional kwd args
    """

    class _options(object): pass
    options = _options()

    for name, (x, x, optionType, defaultValue, environName,
               x) in COMMAND_LINE_OPTIONS.iteritems():
        if environName and environName in os.environ:
            if optionType == 'b':
                defaultValue = True
            else:
                defaultValue = os.environ[environName]
        setattr(options, name, defaultValue)
    options.__dict__.update(kwds)

    return options


def varArgsCallback(option, opt, value, parser, default):
    value = []
    rargs = parser.rargs
    while rargs:
        arg = rargs[0]
        # Stop if we hit an arg like "--foo", "-a", "-fx", "--file=f", etc.
        # (Taken verbatim from Python docs)
        if ((arg[:2] == "--" and len(arg) > 2) or
            (arg[:1] == "-" and len(arg) > 1 and arg[1] != "-")):
            break
        else:
            value.append(arg)
            del rargs[0]
    if not value:
        value.extend(default)
    setattr(parser.values, option.dest, value)


def initOptions(**kwds):
    """
    Load and parse the command line options, with overrides in **kwds.
    Returns options
    """
    #XXX i18n parcelPath, profileDir could have non-ascii paths

    # %prog expands to os.path.basename(sys.argv[0])
    usage  = "usage: %prog [options]"
    parser = OptionParser(usage=usage, version="%prog")

    for name, (shortCmd, longCmd, optionType, defaultValue,
               environName, helpText) in COMMAND_LINE_OPTIONS.iteritems():

        if environName and environName in os.environ:


            if optionType == 'b':
                defaultValue = True

            elif optionType =='v':
                # If a type 'v' (variable # of args) flag is set via envvar,
                # treat this as a regular string type, except make the envvar
                # value a list.  The problem with this is that if the command
                # line also has this flag, it doesn't go through the var-args
                # callback, and therefore must have one and only one arg.
                optionType = 's'
                defaultValue = [os.environ[environName]]

            else:
                defaultValue = os.environ[environName]

        if optionType == 'b':
            parser.add_option(shortCmd,
                              longCmd,
                              dest=name,
                              action='store_true',
                              default=defaultValue,
                              help=helpText)

        elif optionType =='v':
            # use the above varArgsCallback to handle flags with zero or
            # more arguments.  defaultValue needs to be a list
            parser.add_option(shortCmd,
                              longCmd,
                              dest=name,
                              action="callback",
                              callback=varArgsCallback,
                              callback_args=(defaultValue,),
                              help=helpText)

        else:
            parser.add_option(shortCmd,
                              longCmd,
                              dest=name,
                              default=defaultValue,
                              help=helpText)

    if sys.platform == 'darwin':
        # [Bug:2464]
        # On the Mac, double-clicked apps are launched with an extra
        # argument, '-psn_x_y', where x & y are unsigned integers. This
        # is used to rendezvous between the launched app and the Window Server.
        #
        # We remove it from parser's arguments because it conflicts with
        # the -p (parcel path) option, overriding the PARCELPATH environment
        # variable if set.
        args = [arg for arg in sys.argv[1:] if not arg.startswith('-psn_')]
        (options, args) = parser.parse_args(args=args)
    else:
        (options, args) = parser.parse_args()
        
    for (opt,val) in kwds.iteritems():
        setattr(options, opt, val)

    # Convert a few options
    if options.chandlerTestSuite:
        options.scriptFile = "tools/cats/Functional/FunctionalTestSuite.py"
    if options.nocatch:
        options.catch = "tests"

    # Ensure a profile directory
    initProfileDir(options)

    # Load prefs and override default options from prefs
    prefs = loadPrefs(options).get('options')
    if prefs:
        for name, (shortCmd, longCmd, optionType, defaultValue,
                   environName, helpText) in COMMAND_LINE_OPTIONS.iteritems():
            if name in prefs and getattr(options, name) == defaultValue:
                if optionType == 'b':
                    value = prefs[name] in ('True', 'true')
                else:
                    value = prefs[name]
                setattr(options, name, value)

    # Resolve pluginPath relative to chandlerDirectory
    chandlerDirectory = locateChandlerDirectory()
    options.pluginPath = [os.path.join(chandlerDirectory, path)
                          for path in options.pluginPath.split(os.pathsep)]
        
    # Store up the remaining args
    options.args = args

    # --reload implies a few other changes:
    if options.reload:
        options.create = True
        options.restore = None

    if options.timezone:
        timezone = ICUtzinfo.getInstance(options.timezone)
        if str(timezone) != options.timezone:
            raise ValueError, ("Invalid timezone", options.timezone)
        options.timezone = timezone

    return options


def initProfileDir(options):
    """
    Ensure we have the profile directory.
    """
    #XXX: i18n a users home directory can be non-ascii path

    # set flag if the profileDir parameter was passed in (default is '')
    # this is used downstream by application.CheckIfUpgraded()
    options.profileDirWasPassedIn = len(options.profileDir) > 0

    if not options.profileDir:
        profileDir = locateProfileDir()
        if profileDir is None:
            profileDir = locateChandlerDirectory()
        options.profileDir = os.path.expanduser(profileDir)
    elif not os.path.isdir(options.profileDir):
        createProfileDir(options.profileDir)


def loadPrefs(options):
    """
    Load the chandler.prefs file as a ConfigObj, in profileDir by default.
    If prefs file doesn't exist, an ConfigObj is returned.
    """
    return ConfigObj(os.path.join(options.profileDir or '.', options.prefs),
                     encoding='utf-8')


def initI18n(options):
    #Will discover locale set if options.locale is None
    i18n._I18nManager.initialize(localeSet=options.locale, expand=options.expand)


class ChandlerRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def doRollover(self):
        self.stream.flush()
        logging.handlers.RotatingFileHandler.doRollover(self)

def initLogging(options):
    global logger

    if logger is None:
        # Make PROFILEDIR available within the logging config file
        logging.PROFILEDIR = options.profileDir

        logConfFile = options.logging
        if os.path.isfile(logConfFile):
            logging.config.fileConfig(options.logging)
        else:
            # Log config file doesn't exist
            #logging.basicConfig(level=logging.WARNING,
            #    format='%(asctime)s %(name)s %(levelname)s: %(message)s',
            #    filename=os.path.join(options.profileDir, 'chandler.log'),
            #    filemode='a')

            logger = logging.getLogger()
            logfile = os.path.join(options.profileDir, 'chandler.log')
            fileHandler = ChandlerRotatingFileHandler(logfile, 'a', 5000000, 5)

            fileFormatter = logging.Formatter(
                '%(asctime)s %(name)s %(levelname)s: %(message)s'
            )

            fileHandler.setFormatter(fileFormatter)

            logger.addHandler(fileHandler)
            logger.setLevel(logging.INFO)

        logger = logging.getLogger(__name__)

        logger.warn('=== logging initialized, Chandler version %s ===' % version.version)

        import twisted.python.log

        def translateLog(eventDict):
            if eventDict.has_key('logLevel'):
                level = eventDict['logLevel']
            elif eventDict['isError']:
                level = logging.ERROR
            elif eventDict.has_key('debug'):
                level = logging.DEBUG
            else:
                level = logging.WARNING
                
            failure = eventDict.get('failure')
            if failure is not None:
                # For failures, log the type & value, as well as
                # the traceback. Note that a try/except/logger.exception()
                # here would log as application.Utility, not the value of
                # 'system'
                format = "Twisted failure: %s %s\n%s"
                args = failure.type, failure.value, failure.getTraceback()
            else:
                msg = eventDict.get('message', None)
                
                if msg:
                    format = msg[0]
                    args = msg[1:]
                elif eventDict.has_key('format'):
                    format = eventDict['format']
                    args = eventDict
                else:
                    format = "UNFORMATTABLE: %s"
                    args = (eventDict,)
                

            system = eventDict.get('system', '-')
            lineno = eventDict.get('lineno', None)
            exc_info = None
                
            logRecord = logging.LogRecord("twisted", level, system, lineno, format, args, exc_info, None)
            logRecord.created = eventDict['time']
            logger.handle(logRecord)

        # We want startLoggingWithObserver here to override the
        # twisted logger, since that would write to stdio, I think.
        twisted.python.log.startLoggingWithObserver(translateLog, setStdout=0)

def getLoggingLevel():
    return logging.getLogger().getEffectiveLevel()

def setLoggingLevel(level):
    logging.getLogger().setLevel(level)

def locateChandlerDirectory():
    """
    Find the directory that Chandler lives in by looking up the file that
    the application module lives in.
    """
    return os.path.dirname(os.path.dirname(__file__))


def locateRepositoryDirectory(profileDir, options):
    if options.repodir:
        return os.path.join(options.repodir, '__repository__')
    if profileDir:
        path = os.path.join(profileDir, '__repository__')
    else:
        path = '__repository__'
    return path


def initRepository(directory, options, allowSchemaView=False):

    if options.uuids:
        input = file(options.uuids)
        loadUUIDs([UUID(uuid.strip()) for uuid in input if len(uuid) > 1])
        input.close()

    if options.checkpoints == 'none':
        options.checkpoints = None
    else:
        options.checkpoints = int(options.checkpoints) # minutes

    repository = DBRepository(directory)

    kwds = { 'stderr': options.stderr,
             'ramdb': options.ramdb,
             'create': True,
             'recover': options.recover,
             'forceplatform': options.forceplatform,
             'exclusive': not options.nonexclusive,
             'memorylog': options.memorylog,
             'mvcc': options.mvcc and not options.nomvcc,
             'prune': int(options.prune),
             'logdir': options.logdir,
             'datadir': options.datadir,
             'nodeferdelete': options.nodeferdelete,
             'refcounted': True,
             'checkpoints': options.checkpoints,
             'logged': not not options.logging,
             'timezone': options.timezone or ICUtzinfo.default,
             'ontzchange': lambda view, newtz: view.logger.warning("%s: timezone changed to %s", view, newtz),
             'verify': options.verify or __debug__ }

    if options.restore:
        kwds['restore'] = options.restore

    while True:
        try:
            if options.encrypt:
                kwds['password'] = options.getPassword
            else:
                kwds.pop('password', None)

            if options.create:
                repository.create(**kwds)
            else:
                repository.open(**kwds)
        except RepositoryPasswordError, e:
            options.encrypt = e.args[0]
            continue
        except RepositoryVersionError:
            repository.close()
            raise
        except RepositoryRunRecoveryError, e:
            if not (options.recover or e.args[0]):
                repository.logger.warning("reopening repository with recovery")
                kwds['recover'] = True
                continue
            raise
        else:
            del kwds
            break

    if options.backupDir:
        dbHome = repository.backup(os.path.join(options.backupDir,
                                                '__repository__'))
        repository.logger.info("Repository was backed up into %s", dbHome)
    elif options.backup:
        dbHome = repository.backup()
        repository.logger.info("Repository was backed up into %s", dbHome)

    version = long(options.version) if options.version else None

    if options.repair:
        view = repository.createView(version=version, timezone=Default)
        schema.initRepository(view)
        if view.check(True):
            view.commit()
        view.closeView()

    if options.undo:
        view = repository.createView(version=version, timezone=Default)
        if options.undo in ('check', 'repair'):
            repair = options.undo == 'repair'
            while view.itsVersion > 0L:
                schema.initRepository(view)
                if view.check(repair):
                    if repair:
                        view.commit()
                    break

                repository.logger.info('Undoing version %d', view.itsVersion)
                view.closeView()
                repository.undo()
                view.openView()
        else:
            version = repository.store.getVersion()
            if options.undo == 'start':
                nVersions = 1
            elif options.undo.startswith('-'):
                nVersions = -long(options.undo)
            else:
                nVersions = version - long(options.undo)
            if version > nVersions:
                version -= nVersions
                repository.undo(version)
        view.closeView()

    # delay timezone change until schema API is initialized
    if repository.isNew():
        view = repository.createView(version=version, timezone=None)
    else:
        view = repository.createView(version=version, timezone=Default)

    schema.initRepository(view)

    if options.resetIndex:
        # re-create Lucene index database
        # indexer, if set to run, to start again from earliest version
        repository.resetIndex()

    if options.indexer == 'foreground':
        # do nothing, indexing happens during commit
        pass

    elif options.indexer == 'none':
        # don't run full-text indexing in the main view
        view.setBackgroundIndexed(True)
        # don't start an indexer

    else:
        if options.indexer == 'background':  # backwards compat
            options.indexer = 60
        else:
            options.indexer = int(options.indexer) # seconds

        if options.indexer:
            # don't run full-text indexing in the main view
            view.setBackgroundIndexed(True)
            # but in the repository's background indexer
            repository.startIndexer(options.indexer)
        else:
            # no interval == foreground
            pass

    if options.debugOn:
        debugOn = view.classLoader.loadClass(options.debugOn)
        view.debugOn(debugOn)

    return view


def stopRepository(view, commit=True):

    if view.repository.isOpen():
        try:
            if commit:
                try:
                    if view.isOpen():
                        view.commit()
                except VersionConflictError, e:
                    logger.exception(e)
        finally:
            view.repository.close()


def verifySchema(view):

    # Fetch the top-level parcel item to check schema version info
    parcelRoot = view.getRoot('parcels')
    version = getattr(parcelRoot, 'version', None)

    if parcelRoot is not None and version != SCHEMA_VERSION:
        logger.error("Schema version of repository (%s) doesn't match application's (%s)", version, SCHEMA_VERSION)
        return False, version, SCHEMA_VERSION

    return True, version, SCHEMA_VERSION


def initParcelEnv(options, chandlerDirectory):
    """
    PARCEL_IMPORT defines the import directory containing parcels
    relative to chandlerDirectory where os separators are replaced
    with "." just as in the syntax of the import statement.
    """
    PARCEL_IMPORT = 'parcels'

    """
    Load the parcels which are contained in the PARCEL_IMPORT directory.
    It's necessary to add the "parcels" directory to sys.path in order
    to import parcels. Making sure we modify the path as early as possible
    in the initialization as possible minimizes the risk of bugs.
    """
    parcelPath = []
    parcelPath.append(os.path.join(chandlerDirectory,
                      PARCEL_IMPORT.replace('.', os.sep)))

    """
    If PARCELPATH env var is set, append those directories to the
    list of places to look for parcels.
    """
    if options.parcelPath:
        for directory in options.parcelPath.split(os.pathsep):
            if os.path.isdir(directory):
                parcelPath.append(directory)
            else:
                logger.warning("'%s' not a directory; skipping" % directory)

    insertionPoint = 1
    for directory in parcelPath:
        #Convert the directory unicode or str path to the OS's filesystem 
        #charset encoding
        if directory not in sys.path:
            sys.path.insert(insertionPoint, directory)
            insertionPoint += 1

    logger.info("Using PARCELPATH %s" % parcelPath)
    return parcelPath


def initPluginEnv(options, path):

    from pkg_resources import working_set, Environment

    # if options is passed in, use prefs to determine what to bypass
    # otherwise all plugins are added to the working_set

    if options is not None:
        prefs = loadPrefs(options)
        pluginPrefs = prefs.get('plugins', None)
    else:
        prefs = None
        pluginPrefs = None
    
    plugin_env = Environment(path)
    eggs = []

    # remove uninstalled plugins from prefs
    if pluginPrefs is not None:
        for project_name in pluginPrefs.keys():
            if project_name not in plugin_env:
                del prefs['plugins'][project_name]
        prefs.write()

    # add active plugins to working set
    for project_name in sorted(plugin_env):
        if pluginPrefs is not None:
            if pluginPrefs.get(project_name) == 'inactive':
                continue
        for egg in plugin_env[project_name]:
            working_set.add(egg)
            eggs.append(egg)
            break

    return plugin_env, eggs


def initParcels(options, view, path, namespaces=None):
    
    # Delayed so as not to trigger early loading of schema.py
    from Parcel import Manager

    Manager.get(view, path=path).loadParcels(namespaces)

    # Record the current schema version into the repository
    parcelRoot = view.getRoot("parcels")
    if getattr(parcelRoot, 'version', None) != SCHEMA_VERSION:
        parcelRoot.version = SCHEMA_VERSION
    

def initPlugins(options, view, plugin_env, eggs):

    # Delayed so as not to trigger early loading of schema.py
    from Parcel import load_parcel_from_entrypoint
    from pkg_resources import ResolutionError

    # if options is passed-in save which plugins are active in prefs
    if options is not None:
        prefs = loadPrefs(options)
        if 'plugins' not in prefs:
            prefs['plugins'] = {}
    else:
        prefs = None

    for egg in eggs:
        for entrypoint in egg.get_entry_map('chandler.parcels').values():
            try:
                entrypoint.require(plugin_env)
            except ResolutionError:
                pass
            else:
                load_parcel_from_entrypoint(view, entrypoint)
                if prefs is not None:
                    prefs['plugins'][egg.key] = 'active'
                        
    if prefs is not None:
        prefs.write()

    return prefs


def initTimezone(options, view):

    from osaf.pim.calendar.TimeZone import TimeZoneInfo, ontzchange

    repository = view.repository

    view.tzinfo.ontzchange = ontzchange
    if repository is not None:
        repository.ontzchange = ontzchange

    default = options.timezone or TimeZoneInfo.get(view).default
    if default != view.tzinfo.floating:
        view.tzinfo.default = default
        if repository is not None:
            repository.timezone = default


def _randpoolPath(profileDir):
    # Return the absolute path for the file that we use to load
    # initial entropy from in startup/store entropy into in
    # shutdown.
    return os.path.join(profileDir, 'randpool.dat')


def initCrypto(profileDir):
    """
    Initialize the cryptographic services before doing any other
    cryptographic operations.
    
    @param profileDir: The profile directory. Additional entropy will be
                       loaded from a file in this directory. It is not a
                       fatal error if the file does not exist.
    @return:           The number of bytes read from file.
    """
    m2threading.init()
    return Rand.load_file(_randpoolPath(profileDir), -1)


def stopCrypto(profileDir):
    """
    Shut down the cryptographic services. You must call startup()
    before doing cryptographic operations again.
    
    @param profileDir: The profile directory. A snapshot of current entropy
                       state will be saved into a file in this directory. 
                       It is not a fatal error if the file cannot be created.
    @return:           The number of bytes saved to file.
    """
    from osaf.framework.certstore import utils
    ret = 0
    if utils.entropyInitialized:
        ret = Rand.save_file(_randpoolPath(profileDir))
    m2threading.cleanup()
    return ret


class CertificateVerificationError(Exception):
    """
    An error that will be raised when, as part of an SSL/TLS connection
    attempt, the X.509 certificate returned by the peer does not verify.
    """
    def __init__(self, host, code, message, untrustedCertificates):
        """
        Inialize.
        
        @param host:                  Host we think we are connected to.
        @param code:                  The error code.
        @param message:               The error string. 
        @param untrustedCertificates: List of untrusted certificates in PEM
                                      format.
        """
        Exception.__init__(self, code, message)
        self.host = host
        self.untrustedCertificates = untrustedCertificates
        

def initTwisted(view, options=None):
    from osaf.startup import run_reactor

    # options.webserver can be:
    # - None (don't start webserver)
    # - a port number string (happens when env var is set but is overridden)
    # - empty list (start with default port)
    # - list of port number strings (start using the first one in list)
    if options and options.webserver:
        if isinstance(options.webserver, list):
            port = int(options.webserver[0])
        else:
            port = int(options.webserver)
        schema.ns('osaf.app', view).mainServer.port = port
        # Commit so twisted thread can see the change
        view.commit()

    run_reactor()

def stopTwisted():
    from osaf.startup import stop_reactor
    stop_reactor()

def initWakeup(view):
    from osaf.startup import run_startup
    run_startup(view)


def stopWakeup():
    pass


def initOnlineStatus(view, options):
    if options.offline: # offline specified on command line; persist value
        schema.ns('osaf.app', view).prefs.isOnline = False
    else: # not specified on command line; inherit persisted value
        options.offline = not schema.ns('osaf.app', view).prefs.isOnline


class SchemaMismatchError(Exception):
    """
    The schema version in the repository doesn't match the application.
    """
    pass

def openRepository(options, repoDir):
    """
    Helper to open repository, checks for schema error as well.
    
    @return: Repository view
    """
    view = initRepository(repoDir, options)
    verify, repoVersion, schemaVersion = verifySchema(view)
    if not verify:
        raise SchemaMismatchError, (repoVersion, schemaVersion)
    return view

def openRepositoryOrBackup(app, options):
    """
    Open repository, or if that fails due to schema mismatch, open backup.chex,
    or if that does not exist, then display a manual migration dialog.
    
    @param app:     The application object.
    @param options: Options.
    @return:        view, repoDir, newRepo
    """
    from application.dialogs.GetPasswordDialog import getPassword
    options.getPassword = getPassword
    from application.dialogs.UpgradeDialog import MigrationDialog

    repoDir = locateRepositoryDirectory(options.profileDir, options)
    newRepo = not os.path.isdir(repoDir)
    view = None

    try:
        detectOldProfiles(options, repoDir)

        view = openRepository(options, repoDir)
    except (RepositoryVersionError, SchemaMismatchError), err:
        newRepo = False
        
        logger.info('Repository open failed with ' + str(err))
        if view is not None:
            view.repository.close()
            view = None
        
        import wx

        backup = os.path.join(options.profileDir, 'backup.chex')
        if os.path.isfile(backup):
            ret = MigrationDialog.run(backup)
            if ret == wx.YES:
                logger.info('Reloading backup')
                options.reload = backup
                options.create = True
                view = initRepository(repoDir, options)
            elif ret == wx.OK:
                options.create = True
                view = initRepository(repoDir, options)
            else:
                app.exitValue = 1
        else:
            if MigrationDialog.run() == wx.OK:
                options.create = True
                view = initRepository(repoDir, options)
            else:
                app.exitValue = 1
            
    return view, repoDir, newRepo

def detectOldProfiles(options, repoDir):
    """
    If we find old profiles that cannot be automatically migrated, this will
    raise SchemaMismatchError.
    """
    if not (options.profileDirWasPassedIn or
            os.path.isdir(repoDir) or
            options.create):
        if glob.glob(os.path.join(options.profileDir, '..', '0.*')):
            # So now we know we are migrating from incompatibe release. 0.7.1
            # or earlier repository can not be automatically migrated to 0.7.2
            # or later. So let's raise a schema error, since we deal with that
            # the same way.
            raise SchemaMismatchError('Found old profiles that cannot be automatically migrated')
