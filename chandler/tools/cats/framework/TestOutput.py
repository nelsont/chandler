"""TestOutput class for cats 0.2

This is a module contains on major class, TestOutput,
which is used for string output, timeing, and report->action->test->suite
encapsulation.
"""
__author__ =  'Mikeal Rogers <mikeal@osafoundation.org>'
__version__=  '0.2'

from datetime import datetime as dtime
import copy

class datetime(dtime):
    """Class for overriding datetime's normal string method"""
    def __str__(self):
        """Method to return more parsable datetime string"""
        return '%s:%s:%s:%s' % (self.hour, self.minute, self.second, self.microsecond)

class TestOutput:
    """
    Test output and timing class.
    """
    def __init__(self, logname=None, debug=0, mask=0, stdout=None):
        """Instantiation method
        
        Keyword Arguments:
        logname: str  -- Name of the logfile
        debug:   int  -- Debug level
        mask:    int  -- Masking level
        stdout   bool -- Switch to turn on stdout output
        """
        self.debug = debug
        self.mask = mask
        self.suiteList = []
        self.testList = []
        self.actionList = []
        self.performanceActionList = []
        self.currentSuite = {}
        self.currentTest = {}
        self.currentAction = {}
        self.currentPerformanceAction = {}
        self.inAction = False
        self.inTest = False
        self.inSuite = False
        
        if stdout is True:
           import sys
           self.stdout = sys.__stdout__
        else:
           self.stdout = None
        
        if logname is not None:
            self.f = file(logname, 'w')
        else:
            self.f = None
            
    def startSuite(self, name, comment=None):
        """Method to begin test Suite.
        
        Required Argument:
        name: str -- Name of Suite
        
        Keyword Argument:
        comment: str -- Comment string
        """
        
        self.currentSuite = {}
        self.testList = []
        self.currentSuite = {'name':name, 'comment':comment, 'starttime':datetime.now(), 'result':None}
        self.printOut('Starting Suite %s :: StartTime %s' % (name, self.currentSuite['starttime']), level=3) 
        self.inSuite = True
        
    def endSuite(self):
        """Method to end current running suite.
        
        Encapsulates test list."""
            
        self.currentSuite['endtime'] = datetime.now()
        self.currentSuite['totaltime'] = self.currentSuite['endtime'] - self.currentSuite['starttime']
        self.printOut('Ending Suite ""%s"" :: EndTime %s :: Total Time %s' % (self.currentSuite['name'], self.currentSuite['endtime'], self.currentSuite['totaltime']), level=3)
        self.currentSuite['testlist'] = copy.copy(self.testList)
        self.suiteList.append(copy.copy(self.currentSuite))
        self.inSuite = False
        
    def startTest(self, name, comment=None):
        """Method to begin individual test class run.
        
        Required Argument:
        name: str -- Name of Test
        
        Keyword Argument:
        comment: -- Comment string"""
        
        self.currentTest = {}
        self.actionList = []
        self.currentTest = {'name':name, 'comment':comment, 'starttime':datetime.now(), 'result':None}
        self.printOut('Starting Test ""%s"" :: StartTime %s' % (name, self.currentTest['starttime']), level=2)
        self.inTest = True
        
    def endTest(self, comment=None):
        """Method to end individual test class run.
        
        Encapsulates action list."""
        self.currentTest['endtime'] = datetime.now()
        self.currentTest['totaltime'] = self.currentTest['endtime'] - self.currentTest['starttime']
        self.currentTest['comment'] = '%s\n%s' % (self.currentTest['comment'], comment)
        self.printOut('Ending Test ""%s"" :: EndTime %s :: Total Time %s' % (self.currentTest['name'], self.currentTest['endtime'], self.currentTest['totaltime']), level=2)
        self.currentTest['actionlist'] = copy.copy(self.actionList)
        self.testList.append(copy.copy(self.currentTest))
        self.inTest = False
        
    def startAction(self, name, comment=None):
        """Method to being action inside of test class run.
        
        Required Argument:
        name: str -- Name of action
        
        Keyword Argument:
        comment: str -- Comment string"""
        self.currentAction = {}
        self.currentReportList = []
        self.currentAction = {'name':name, 'comment':comment, 'starttime':datetime.now(), 'result':None}
        self.printOut('Starting Action ""%s"" :: StartTime %s' % (name, self.currentAction['starttime']), level=1)
        self.inAction = True
                       
    def endAction(self, result=True, comment=None):
        """Method to end current action.
        
        Keyword Arguments:
        result:  bool -- User signalled result of action. Shortcut to call report() at end of action.
        comment: str  -- Comment string
        """
        if self.inAction is False:
            self.printOut("ENDACTION HAS BEEN CALLED OUTSIDE OF ACTION", level=1, result=False)
            return False
        self.currentAction['endtime'] = datetime.now()
        self.currentAction['totaltime'] = self.currentAction['endtime'] - self.currentAction['starttime']
        self.report(result, comment)
        self.currentAction['reportlist'] = copy.copy(self.currentReportList)
        self.actionList.append(copy.copy(self.currentAction))
        self.inAction = False
        
    def startPerformanceAction(self, name, comment=None):
        """Method to being performance action timer.
        
        This starts and stops it's own timer and isn't encapsulated in the normal output datastructure.
        
        Required Argument:
        name: str -- Name of action you wish to time.
        
        Keyword Argument:
        comment: str -- Comment string.
        """
        self.currentPerformanceAction = {}
        self.currentPerformanceAction = {'name':name, 'comment':comment, 'starttime':datetime.now()}
        self.printOut('Performance Starting Action ""%s"" :: StartTime %s' % (name, self.currentPerformanceAction['starttime']), level=1)

    def endPerformanceAction(self):
        """Method to end preformance action timer."""
        self.currentPerformanceAction['endtime'] = datetime.now()
        self.currentPerformanceAction['totaltime'] = self.currentPerformanceAction['endtime'] - self.currentPerformanceAction['starttime']
        self.performanceActionList.append(copy.copy(self.currentPerformanceAction))
        
    def addComment(self, string):
        """Method to insert comment in to current action or test.
        
        Required Argument:
        string: str -- Comment string."""
        string = '[%s] %s' % (datetime.now(), string)
        
        if self.inAction is True:
            self.currentAction['comment'] = '%s :: %s' % (self.currentAction['comment'], string)
            self.printOut('CommentAdd :: %s' % string, level=0, result=True)
        elif self.inAction is False:
            self.currentTest['comment'] = '%s :: %s' % (self.currentTest['comment'], string)
            self.printOut('CommentAdd :: %s' % string, level=1, result=True)
    
    def report(self, result, name=None, comment=None):
        """Method to report PASS/FAIL within test or action.
        
        Required Argument:
        result: bool -- PASS=True, FAIL=False
        
        Keyword Arguments:
        name:    str -- Name of report being called. If not inside action name is REQUIRED.
        comment: str -- Comment string.
        """
        # check state
        if self.inAction is True:
            self.currentReportList.append((result, name, comment))
        elif self.inAction is False:
            if name is None:
                x = datetime.now()
                self.printOut('UNNAMED REPORT CANNOT BE CALLED OUTSIDE OF ACTION %s:%s:%s:%s' % (x.hour, x.minute, x.second, x.microsecond), level=0, result=False)
                return
            elif name is not None:
                if comment is None: comment = 'Action created by framework for report call'
                self.startAction(name=name, comment=comment)
                self.endAction(result, comment=comment)
                return
        
        if name is not None: comment = '%s :: %s' % (name, comment)
        
        if result is True:
            self.printOut('Success in action.%s.report:: %s' % (self.currentAction['name'], comment), level=0, result=True)
        else:
            self.printOut('Failure in action.%s.report :: %s' % (self.currentAction['name'], comment), level=0, result=False)
        
    def write(self, string):
        """Method to allow TestOutput to be used like a file object.
        
        Required Argument:
        string: str -- String you wish to write."""
        self._write(string)    

    def _write(self, string):
        """Internal method for writing to log/stdout when enabled.
        
        Required Argument:
        string: str -- String you wish to write."""
        if self.f is not None:
            self.f.write(string)
            self.f.flush()
        
        if self.stdout is not None:
            self.stdout.write(string)
            self.stdout.flush()
 
    def printOut(self, string, level=0, result=True):
        """Method to print using self._write but observe debug and mask settings.
        
        Required Argument:
        string: str -- String you wish to print.
        
        Keyword Arguments:
        level:  int  -- Level at which the output came; report=0, action=1, test=2, suite=3.
        result: boot -- Result for output. Necessary for masking passes.
        """
        #Prepend + for true and - for false to the beginning of each string 
        if result is True:
            leadchar = '+'
        else:
            leadchar = '-'
        #Each line should be prepended with the amount of characters for that level, this shows the encapsulation.
        string = '%s%s\n' % (leadchar * (4 - level), string)
        
        if isinstance(string, unicode):
            string = string.encode('utf8')

        if self.debug > 2:
            self._write(string)
            return
        if self.debug > 1:
            if level >= self.mask:
                self._write(string)
                return
        if self.debug > 0:
            if result is False:
                self._write(string)
                return
        if self.debug == 0:
            if result is False:
                if level >= self.mask:
                    self._write(string)
                    return

#    def displaySummary(self):
#        
#        for test in self.testList:
#            if test['comment'] == 'None\nNone':
#                self.printOut( "%s %s %s" % ( test['name'] , 'PASS',  test['totaltime'] ), 4)
#            else:
#                self.printOut ("%s %s %s" % ( test['name'] , 'FAIL',  test['totaltime'] ), 4) 
#                self.printOut (test['comment'].replace('\n','') )
#        self.printOut('\n--Suite Summary-- There were %s passed tests and %s failed with a combined %s passed actions and %s failed actions, with %s passed reports and %s failed reports.' % (self.passedTests, self.failedTests, self.passedActions, self.failedActions, self.passedReports,self.failedReports))
        

    def traceback(self):
        """Method to handle python traceback exception."""
        import sys, traceback
        type, value, stack = sys.exc_info()
        
        #Print the exception
        if self.f is not None:
            traceback.print_exception(type, value, stack, None, self.f)
        if self.stdout is not None:
            traceback.print_exception(type, value, stack, None, self.stdout)
        if self.stdout is None and self.f is None:
            traceback.print_exception(type, value, stack, None, self.stderr)
        
        #Clean up logger state
        if self.inAction is True:
            self.endAction(result=False, comment='Action Failure due to traceback')
        if self.inTest is True:
            self.endTest(comment='Test Failure due to traceback')
            
    def _parse_results(self):
        """Method to parse through the result output datastructure to bubble up encapsulated failures"""
        for suite_dict in self.suiteList:
            for test_dict in suite_dict['testlist']:
                for action_dict in test_dict['actionlist']:
                    for report_tuple in action_dict['reportlist']:
                        if report_tuple[0] is False:
                            action_dict['result'] = False
                    if action_dict['result'] is False:
                        test_dict['result'] = False
                if test_dict['result'] is False:
                    suite_dict['result'] = False
            
    def summary(self):
        """Method to calculate and print summary and report"""
        suites_ran = 0
        suites_failed = 0
        tests_ran = 0
        tests_failed = 0
        actions_ran = 0
        actions_failed = 0
        reports_ran = 0
        reports_failed = 0
        
        self._parse_results()
        #Parse through finalized suiteList for failures
        
        self._write('Failure Report;')
        for suite_dict in self.suiteList:
            if suite_dict['result'] is False:
                self._write('*Suite ""%s"" Failed :: Total Time ""%s"" :: Comment ""%s""\n' % (suite_dict['name'], suite_dict['totaltime'], suite_dict['comment']))
                suites_failed = suites_failed + 1
                for test_dict in suite_dict['testlist']:
                    if test_dict['result'] is False:
                        self._write('**Test ""%s"" Failed :: Total Time ""%s"" :: Comment ""%s""\n' % (test_dict['name'], test_dict['totaltime'], test_dict['comment']))
                        tests_failed = tests_failed + 1
                        for action_dict in test_dict['actionlist']:
                            if action_dict['result'] is False:
                                self._write('***Action ""%s"" Failed :: Total Time ""%s"" :: Comment ""%s""\n' % (action_dict['name'], action_dict['totaltime'], action_dict['comment']))
                                actions_failed = actions_failed + 1
                                for report_tuple in action_dict['reportlist']:
                                    if report_tuple[0] is False:
                                        self._write('****Report ""%s"" Failed :: Comment ""%s""\n' % (report_tuple[1], report_tuple[2]))
                                        reports_failed = reports_failed + 1

        #Calculate number ran
        for suite in self.suiteList:
            suites_ran = suites_ran + 1
            for test in suite['testlist']:
                tests_ran = tests_ran + 1
                for action in test['actionlist']:
                    actions_ran = actions_ran + 1
                    for report in action['reportlist']:
                        reports_ran = reports_ran + 1
        
        self._write('$Suites run=%s, pass=%s, fail=%s :: Tests run=%s, pass=%s, fail=%s :: Actions run=%s, pass=%s, fail=%s :: Reports run=%s, pass=%s, fail=%s \n' % 
                    (suites_ran, suites_ran - suites_failed, suites_failed, tests_ran, tests_ran - tests_failed, tests_failed, actions_ran, 
                     actions_ran - actions_failed, actions_failed, reports_ran, reports_ran - reports_failed, reports_failed))                                
           
        
        
    ### All the methods below will be removed pre 0.2-cats-release. They are only there for reverse compatability in old test so that those tests don't fail in Python.    
        
    def Start(self, string):
        
        self.printOut('DEPRICATED LOGGER FUNCTION', level=0, result=False)
        
    def Stop(self):
        
        self.printOut('DEPRICATED LOGGER FUNCTION', level=0, result=False)
        
    def Print(self, string):
        
        self.printOut('DEPRICATED LOGGER FUNCTION', level=0, result=False)
        
    def Report(self, string):
        
        self.printOut('DEPRICATED LOGGER FUNCTION', level=0, result=False)
        
    def ReportPass(self, string):
        
        self.printOut('DEPRICATED LOGGER FUNCTION', level=0, result=False)
        
    def ReportFailure(self, string):
        
        self.printOut('DEPRICATED LOGGER FUNCTION', level=0, result=False)
        
    def SetChecked(self, string):
        
        self.printOut('DEPRICATED LOGGER FUNCTION', level=0, result=False)   
        
    def Close(self):
        
        self.printOut('DEPRICATED LOGGER FUNCTION', level=0, result=False)
        
    def calculateReport(self, reportList):
        
        result = True #keeping track of pass/fail
        
        for report in reportList:
            if report[0] is False:
                result = False
       #     self.printOut(report[1], level = 0, result = report[0])
        return result
                
        
if __name__ == "__main__":
    
    logger = TestOutput(logname='testlog')
   # logger.debug = 1
    logger.startSuite('1st suite', 'comment')
    logger.startTest('1st test')
    logger.startAction('1st action in 1st test will pass')
    logger.endAction(True)
    logger.startAction('2nd action in 1st test will fail')
    logger.endAction(False)
    logger.startAction('3nd action in 1st test will fail')
    logger.endAction(False)
    logger.startAction('4nd action in 1st test will fail')
    logger.endAction(False)
    logger.startAction('5nd action in 1st test will fail')
    logger.endAction(False)
    logger.startAction('6nd action in 1st test will fail')
    logger.endAction(False)
    logger.startAction('7nd action in 1st test will fail')
    logger.endAction(False)
    logger.startAction('8nd action in 1st test will fail')
    logger.endAction(False)
    logger.startAction('9nd action in 1st test will fail')
    logger.endAction(False)
    logger.endTest()
    logger.startTest('2nd test')
    logger.startAction('1st action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('2nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('3rd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('4nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('5nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('6nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('7nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('8nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('9nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('10nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('11nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('12nd action in 2nd test will pass')
    logger.endAction(True)
    logger.startAction('13nd action in 2nd test will pass')
    logger.endAction(True)
    logger.endTest()
    logger.endSuite()
    
   # logger.mask = 1
    logger.calculateSuite(logger.suiteList)
