# Chandler blueprint for new build process

"""
Notes:
Start() is responsible for capturing all pertinent output to the open file
object, log.  True is returned if a new build was created, False is returned
if no code has changed, and an exception is raised if there are problems.
"""

# To appease older Pythons:
True = 1
False = 0


import os, hardhatutil, hardhatlib, sys, re

path = os.environ.get('PATH', os.environ.get('path'))
whereAmI = os.path.dirname(os.path.abspath(hardhatlib.__file__))
cvsProgram = hardhatutil.findInPath(path, "cvs")
treeName = "Chandler"
mainModule = 'chandler'
logPath = 'hardhat.log'

def Start(hardhatScript, workingDir, cvsVintage, buildVersion, clobber, log):

    global buildenv

    try:
        buildenv = hardhatlib.defaults
        buildenv['root'] = workingDir
        buildenv['hardhatroot'] = whereAmI
        hardhatlib.init(buildenv)
    
    except hardhatlib.HardHatMissingCompilerError:
        print "Could not locate compiler.  Exiting."
        sys.exit(1)
    
    except hardhatlib.HardHatUnknownPlatformError:
        print "Unsupported platform, '" + os.name + "'.  Exiting."
        sys.exit(1)
    
    except hardhatlib.HardHatRegistryError:
        print
        print "Sorry, I am not able to read the windows registry to find" 
        print "the necessary VisualStudio complier settings.  Most likely you"
        print "are running the Cygwin python, which will hopefully be supported"
        print "soon.  Please download a windows version of python from:\n"
        print "http://www.python.org/download/"
        print
        sys.exit(1)
    
    except Exception, e:
        print "Could not initialize hardhat environment.  Exiting."
        print "Exception:", e
        traceback.print_exc()
        raise e
        sys.exit(1)
    
    # make sure workingDir is absolute
    workingDir = os.path.abspath(workingDir)
    chanDir = os.path.join(workingDir, mainModule)
    # test if we've been thruough the loop at least once
    if clobber == 1:
        if os.path.exists(chanDir):
            hardhatutil.rmdirRecursive(chanDir)
            
    os.chdir(workingDir)

    # remove outputDir and create it
    outputDir = os.path.join(workingDir, "output")
    if os.path.exists(outputDir):
        hardhatutil.rmdirRecursive(outputDir)
    os.mkdir(outputDir)
    
    if not os.path.exists(chanDir):
        # Initialize sources
        print "Setup source tree..."
        log.write("- - - - tree setup - - - - - - -\n")
        
        outputList = hardhatutil.executeCommandReturnOutputRetry(
         [cvsProgram, "-q", "checkout", cvsVintage, "chandler"])
        hardhatutil.dumpOutputList(outputList, log)
    
        # hack for linux until we fix things    
        if buildenv['os'] == 'posix':
            if not os.path.exists("Chandler"):
                os.symlink(chanDir, "Chandler")
    
        os.chdir(chanDir)
    
        for releaseMode in ('debug', 'release'):
    
            doInstall(releaseMode, workingDir, log)
            ret = Do(hardhatScript, releaseMode, workingDir, outputDir, 
              cvsVintage, buildVersion, log)
            CopyLog(os.path.join(workingDir, logPath), log)
    else:
        os.chdir(chanDir)
    
        print "Checking CVS for updates"
        log.write("Checking CVS for updates\n")
        buildVersionEscaped = "\'" + buildVersion + "\'"
        buildVersionEscaped = buildVersionEscaped.replace(" ", "|")
        
        if changesInCVS(chanDir, workingDir, cvsVintage, log):
            log.write("Changes in CVS, do an install\n")
            changes = "-changes"
        else:
            log.write("No changes, install skipped\n")
            changes = "-nochanges"

        # do tests after checking CVS
        for releaseMode in ('debug', 'release'):
    
            if changes == "-changes":
                doInstall(releaseMode, workingDir, log)
                makeDistrib(hardhatScript, releaseMode, outputDir, buildVersion, log)
    
            ret = Do(hardhatScript, releaseMode, workingDir, outputDir, 
              cvsVintage, buildVersion, log)
            CopyLog(os.path.join(workingDir, logPath), log)

    return ret + changes 


# These modules are the ones to check out of CVS
cvsModules = (
    'chandler',
)

def Do(hardhatScript, mode, workingDir, outputDir, cvsVintage, buildVersion, log):

    testDir = os.path.join(workingDir, "chandler")
    os.chdir(testDir)

    if mode == "debug":
        dashT = '-dt'
    else:
        dashT = '-rt'

    try: # test
        print "Testing " + mode
        log.write("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n")
        log.write("Testing " + mode + " ...\n")
        outputList = hardhatutil.executeCommandReturnOutput(
         [hardhatScript, dashT])
        hardhatutil.dumpOutputList(outputList, log)

    except Exception, e:
        print "a testing error"
        log.write("***Error during tests*** " + e.str() + "\n")
        log.write("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n")
        log.write("Tests log:" + "\n")
        hardhatutil.dumpOutputList(outputList, log)
        if os.path.exists(os.path.join(workingDir, logPath)) :
            CopyLog(os.path.join(workingDir, logPath), log)
        log.write("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n")
        return "test_failed"
    else:
        log.write("Tests successful" + "\n")
        log.write("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n")
        log.write("Detailed Tests log:" + "\n")
        if os.path.exists(os.path.join(workingDir, logPath)) :
            CopyLog(os.path.join(workingDir, logPath), log)
        log.write("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n")

    return "success"  # end of Do( )

#   Create end-user, developer distributions
def makeDistrib(hardhatScript, mode, outputDir, buildVersion, log):

    print "Making distribution files for " + mode
    log.write("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n")
    log.write("Making distribution files for " + mode + "\n")
    if mode == "debug":
        distOption = "-dD"
    else:
        distOption = "-D"
        
    outputList = hardhatutil.executeCommandReturnOutput(
     [hardhatScript, "-o", outputDir, distOption, buildVersionEscaped])
    hardhatutil.dumpOutputList(outputList, log)
    
    return

def changesInCVS(moduleDir, workingDir, cvsVintage, log):

    changesAtAll = False
#     print "Examining CVS"
#     log.write("Examining CVS\n")
    for module in cvsModules:
        print module, "..."
        log.write("- - - - " + module + " - - - - - - -\n")
        moduleDir = os.path.join(workingDir, module)
        os.chdir(moduleDir)
        # print "seeing if we need to update", module
        log.write("Seeing if we need to update " + module + "\n")
        outputList = hardhatutil.executeCommandReturnOutputRetry(
         [cvsProgram, "-qn", "update", "-d", cvsVintage])
        # hardhatutil.dumpOutputList(outputList, log)
        if NeedsUpdate(outputList):
            print "" + module + " needs updating"
            changesAtAll = True
            # update it
            print "Getting changed sources"
            log.write("Getting changed sources\n")
            
            outputList = hardhatutil.executeCommandReturnOutputRetry(
            [cvsProgram, "-q", "update", "-Ad"])
            hardhatutil.dumpOutputList(outputList, log)
        
        else:
            # print "NO, unchanged"
            log.write("Module unchanged" + "\n")

    log.write("- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -\n")
    log.write("Done with CVS\n")
    return changesAtAll

def doInstall(buildmode, workingDir, log):
# for our purposes, we do not really do a build
# we will update chandler from CVS, and grab new tarballs when they appear
    if buildmode == "debug":
        dbgStr = "DEBUG=1"
        dashR = '-d'
    else:
        dbgStr = ""
        dashR = '-r'

    moduleDir = os.path.join(workingDir, mainModule)
    os.chdir(moduleDir)
    print "Doing make " + dbgStr + " install\n"
    log.write("Doing make " + dbgStr + " install\n")

    outputList = hardhatutil.executeCommandReturnOutput(
     [buildenv['make'], dbgStr, "install" ])
    hardhatutil.dumpOutputList(outputList, log)


def NeedsUpdate(outputList):
    for line in outputList:
        if line.lower().find("ide scripts") != -1:
            # this hack is for skipping some Mac-specific files that
            # under Windows always appear to be needing an update
            continue
        if line.lower().find("xercessamples") != -1:
            # same type of hack as above
            continue
        if line[0] == "U":
            print "needs update because of", line
            return True
        if line[0] == "P":
            print "needs update because of", line
            return True
        if line[0] == "A":
            print "needs update because of", line
            return True
    return False

def CopyLog(file, fd):
    input = open(file, "r")
    line = input.readline()
    while line:
        fd.write(line)
        line = input.readline()
    input.close()

def getVersion(fileToRead):
    input = open(fileToRead, "r")
    line = input.readline()
    while line:
        if line == "\n":
            line = input.readline()
            continue
        else:
            m=re.match('VERSION=(.*)', line)
            if not m == 'None' or m == 'NoneType':
                version = m.group(1)
                input.close()
                return version

        line = input.readline()
    input.close()
    return 'No Version'

