##############################################################################
#
# Copyright (c) Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
""" """

from __future__ import absolute_import

import ConfigParser
import copy
import logging
import threading
import time
import pprint
import re

from cipher.background.thread import BackgroundWorkerThread
from cipher.background.contextmanagers import (ZopeInteraction, ZopeTransaction)
from paste.request import construct_url
from paste.util.converters import asbool
from zope.event import notify
from zope.component import adapter

from cipher.longrequest import interfaces


LOG = logging.getLogger("cipher.longrequest")

INITIAL_DELAY = 1  # sec
TICK = 1  # sec

THREAD = None
THREADPOOL = None

DURATION_LEVEL_1 = 2  # sec
DURATION_LEVEL_2 = 10  # sec
DURATION_LEVEL_3 = 30  # sec
FINISHED_LOG_LEVEL = logging.INFO
VERBOSE_LOG = False

ZOPE_THREAD_REQUESTS = {}

LOG_TEMPLATE = """Long running request detected
%(info)s
%(others)s"""

THREAD_TEMPLATE = """thread_id:%(thread_id)s
duration:%(duration)s sec
URL:%(uri)s
threads in use:%(threadsused)s
environment:%(worker_environ)s
username:%(username)s
form:%(form)s"""

IGNORE_URLS = []

NOW = time.time  # testing hook


class RequestCheckerThread(BackgroundWorkerThread):

    description = "cipher.longrequest checker thread"

    log = LOG  # override default logger in BackgroundWorkerThread

    running = True

    maxRequestTime = 0
    maxThreadsUsed = 0

    def __init__(self, *args, **kw):
        super(RequestCheckerThread, self).__init__(*args, **kw)
        self.notified = {}
        self.lastDuration = {}

    def run(self):
        if INITIAL_DELAY:
            time.sleep(INITIAL_DELAY)  # give it some initial delay
            LOG.info(
                "RequestCheckerThread %s initial delay spent, now working..." %
                self.site_name)
        if self.site_db is None:
            self.runNoDB()
        else:
            super(RequestCheckerThread, self).run()

    def runNoDB(self):
        """Main loop of the thread."""
        try:
            while self.scheduleNextWork():
                with ZopeInteraction():
                    try:
                        try:
                            with ZopeTransaction(
                                    user=self.user_name,
                                    note=self.getTransactionNote()):
                                self.doWork()
                        finally:
                            # Do the cleanup in a new transaction, as
                            # the current one may be doomed or
                            # something.  Also do it while the site
                            # is available, since we may need to access
                            # local utilities during the cleanup
                            with ZopeTransaction(
                                    user=self.user_name,
                                    note=self.getCleanupNote()):
                                self.doCleanup()
                    except:
                        # Note: log the exception while the ZODB connection
                        # is still open; we may need it for repr() of
                        # objects in various __traceback_info__s.
                        self.log.exception("Exception in %s" % self.name)
        except:
            self.log.exception("Exception in %s, thread terminated" % self.name)

    def scheduleNextWork(self):
        time.sleep(TICK)
        return self.running

    def prevRequestFinished(self, thread_id):
        # notify before the fact gets deleted
        ld = self.lastDuration[thread_id]
        # collect stats
        self.maxRequestTime = max(self.maxRequestTime, ld[0])
        notify(interfaces.LongRequestFinishedEvent(
                thread_id, ld[0], ld[2]))
        del self.lastDuration[thread_id]

    def doWork(self):
        if THREADPOOL is None:
            # no threadpool yet, return ASAP
            return

        LOG.debug("checking request threads")

        now = NOW()

        #allThreadIds = dict([(t.thread_id, 1) for t in THREADPOOL.workers])
        workingThreadIds = dict([(k, 1) for k in THREADPOOL.worker_tracker.keys()])
        self.maxThreadsUsed = max(len(workingThreadIds), self.maxThreadsUsed)

        # THREADPOOL.worker_tracker has ONLY the threads which are
        # doing some work!

        # clean up notification dict, in case threads get killed
        for thread_id in tuple(self.notified.keys()):
            if thread_id not in workingThreadIds:
                del self.notified[thread_id]

        # clean up lastDuration dict, in case threads get killed
        for thread_id in tuple(self.lastDuration.keys()):
            if thread_id not in workingThreadIds:
                self.prevRequestFinished(thread_id)

        # clean up ZOPE_THREAD_REQUESTS dict, in case threads get killed
        for thread_id in tuple(ZOPE_THREAD_REQUESTS.keys()):
            if thread_id not in workingThreadIds:
                del ZOPE_THREAD_REQUESTS[thread_id]

        workers = THREADPOOL.worker_tracker.items()
        for thread_id, (time_started, worker_environ) in workers:
            # make a duplicate of worker_environ ASAP
            worker_environ = copy.copy(worker_environ)

            duration = int(now - time_started)

            # check whether there was a previous request on this thread
            try:
                ld = self.lastDuration[thread_id]
                if ld[0] > duration or worker_environ is None:
                    # there was a previous request that finished
                    self.prevRequestFinished(thread_id)
            except KeyError:
                pass

            if not worker_environ:
                # ignore requests without a worker_environ
                continue

            # check duration against levels
            if DURATION_LEVEL_3 and duration > DURATION_LEVEL_3:
                event = interfaces.LongRequestEventOver3
            elif DURATION_LEVEL_2 and duration > DURATION_LEVEL_2:
                event = interfaces.LongRequestEventOver2
            elif DURATION_LEVEL_1 and duration > DURATION_LEVEL_1:
                event = interfaces.LongRequestEventOver1
            else:
                # duration is under any limits
                continue

            # construct a URL from the request
            uri = getURI(worker_environ)

            # check ignored URLs
            bail = False
            for ignore in IGNORE_URLS:
                if ignore.match(uri):
                    bail = True
                    break
            if bail:
                continue

            worker_environ = self.removeWSGIStuff(worker_environ)

            # mmm, this does not work, I guess wsgi.input is consumed
            #form = parse_formvars(worker_environ)

            try:
                zope_request = ZOPE_THREAD_REQUESTS[thread_id]
            except KeyError:
                zope_request = None

            # remember current duration and URL
            self.lastDuration[thread_id] = (duration, time_started, uri)

            try:
                notifiedEvent, notifiedTime = self.notified[thread_id]
                if event == notifiedEvent and time_started == notifiedTime:
                    # the request / timeout level we just detected was already
                    # notified, be quiet until something else happens
                    continue
            except KeyError:
                pass

            # shoot the event
            notify(event(thread_id, duration, uri, worker_environ, zope_request))

            # remember the event, time_started is a sort of ID for the request
            self.notified[thread_id] = (event, time_started)

    def removeWSGIStuff(self, environ):
        rv = {}
        for k in tuple(environ.keys()):
            if (k.startswith('wsgi.') or k.startswith('paste.')
                or k.startswith('weberror.')):
                continue
            else:
                rv[k] = environ[k]
        return rv

    def getMaxRequestTime(self, clear=False):
        rv = self.maxRequestTime
        if clear:
            self.maxRequestTime = 0
        return rv

    def getMaxThreadsUsed(self, clear=False):
        rv = self.maxThreadsUsed
        if clear:
            self.maxThreadsUsed = 0
        return rv


def startRequestHandler(event):
    try:
        thread = threading.currentThread()
        ZOPE_THREAD_REQUESTS[thread.thread_id] = event.request
    except:
        pass


def endRequestHandler(event):
    try:
        thread = threading.currentThread()
        del ZOPE_THREAD_REQUESTS[thread.thread_id]
    except:
        pass


def getURI(worker_environ):
    # worker_environ can go away anytime, protect against that
    try:
        uri = worker_environ['HTTP_X_FORWARDED_FOR']
    except:
        try:
            uri = construct_url(worker_environ)
        except:
            uri = 'n/a'
    return uri


def getAllThreadInfo(omitThreads=()):
    now = NOW()

    infos = []
    workers = THREADPOOL.worker_tracker.items()
    for thread_id, (time_started, worker_environ) in workers:
        if thread_id in omitThreads or not worker_environ:
            continue

        duration = int(now - time_started)
        uri = getURI(worker_environ)

        try:
            zope_request = ZOPE_THREAD_REQUESTS[thread_id]
        except KeyError:
            zope_request = None

        dummyevent = interfaces.LongRequestEvent(thread_id, duration, uri,
                                                 worker_environ, zope_request)

        infos.append(getFormattedThreadinfo(dummyevent))

    return infos


def getFormattedThreadinfo(event):
    username = ''
    form = ''
    if event.zope_request is not None:
        try:
            username = event.zope_request.principal.id
        except:
            pass
        try:
            form = event.zope_request.form
            form = pprint.pformat(form)
        except:
            pass
    try:
        worker_environ = pprint.pformat(event.worker_environ)
    except:
        worker_environ = event.worker_environ
    data = dict(thread_id=event.thread_id,
                duration=event.duration,
                uri=event.uri,
                worker_environ=worker_environ,
                username=username,
                form=form,
                threadsused=getThreadsUsed())
    threadinfo = THREAD_TEMPLATE % data
    return threadinfo


def addLogEntry(event, level):
    threadinfo = getFormattedThreadinfo(event)
    if VERBOSE_LOG:
        others = '\n--\n'.join(
            ['', 'Other threads:'] +  # spacing an header
            getAllThreadInfo(omitThreads=(event.thread_id,)))
    else:
        others = ''
    LOG.log(level, LOG_TEMPLATE % dict(info=threadinfo, others=others))


@adapter(interfaces.ILongRequestEvent)
def addLogEntryInfo(event):
    addLogEntry(event, logging.INFO)


@adapter(interfaces.ILongRequestEvent)
def addLogEntryWarn(event):
    addLogEntry(event, logging.WARN)


@adapter(interfaces.ILongRequestEvent)
def addLogEntryError(event):
    addLogEntry(event, logging.ERROR)


@adapter(interfaces.ILongRequestFinishedEvent)
def addLogEntryFinishedInfo(event):
    LOG.log(FINISHED_LOG_LEVEL,
        "Long running request finished thread_id:%s duration:%s sec\n%s",
        event.thread_id, event.duration, event.uri)


def startThread(site_db, site_oid, siteName, user):
    global THREAD
    THREAD = RequestCheckerThread(site_db, site_oid, siteName, user)
    THREAD.start()


def stopThread():
    global THREAD
    THREAD.running = False
    THREAD.join()
    THREAD = None


def getMaxRequestTime(clear=False):
    """Return the MAX time of requests since last cleared"""
    global THREAD
    if THREAD is None:
        raise ValueError("No thread running")
    else:
        return THREAD.getMaxRequestTime(clear)


def getMaxThreadsUsed(clear=False):
    """Return the number MAX of working threads since last cleared"""
    global THREAD
    if THREAD is None:
        raise ValueError("No thread running")
    else:
        return THREAD.getMaxThreadsUsed(clear)


def getThreadsUsed():
    """Return the current number of working threads"""
    global THREADPOOL
    if THREADPOOL is None:
        raise ValueError("No threadpool yet!")
    else:
        return len(THREADPOOL.worker_tracker.keys())


# we need to grab the request --> threadpool from somewhere
# there's no other chance than waiting for the first request
# for this we need a filter

class ThreadpoolCatcher(object):
    """
    This middleware will catch the paster threadpool from the first request.
    """

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        global THREADPOOL
        if THREADPOOL is None:
            THREADPOOL = environ.get('paste.httpserver.thread_pool')
            if THREADPOOL is not None:
                LOG.info("got thread_pool from a request")

        return self.application(environ, start_response)

    def __repr__(self):
        return '<ThreadpoolCatcher>'


def make_filter(app, global_conf, forceStart=False):
    config = ConfigParser.RawConfigParser()
    config.optionxform = str
    config.read(global_conf['__file__'])

    if config.has_option('cipher.longrequest', 'duration-level-1'):
        global DURATION_LEVEL_1
        DURATION_LEVEL_1 = config.getint('cipher.longrequest', 'duration-level-1')

    if config.has_option('cipher.longrequest', 'duration-level-2'):
        global DURATION_LEVEL_2
        DURATION_LEVEL_2 = config.getint('cipher.longrequest', 'duration-level-2')

    if config.has_option('cipher.longrequest', 'duration-level-3'):
        global DURATION_LEVEL_3
        DURATION_LEVEL_3 = config.getint('cipher.longrequest', 'duration-level-3')

    if config.has_option('cipher.longrequest', 'tick'):
        global TICK
        TICK = config.getint('cipher.longrequest', 'tick')

    if config.has_option('cipher.longrequest', 'initial-delay'):
        global INITIAL_DELAY
        INITIAL_DELAY = config.getint('cipher.longrequest', 'initial-delay')

    if config.has_option('cipher.longrequest', 'finished-log-level'):
        global FINISHED_LOG_LEVEL
        value = config.get('cipher.longrequest', 'finished-log-level').lower()
        if value == 'info':
            FINISHED_LOG_LEVEL = logging.INFO
        elif value == 'warn':
            FINISHED_LOG_LEVEL = logging.WARN
        if value == 'error':
            FINISHED_LOG_LEVEL = logging.ERROR

    if config.has_option('cipher.longrequest', 'verbose'):
        global VERBOSE_LOG
        VERBOSE_LOG = asbool(config.get('cipher.longrequest', 'verbose'))

    global IGNORE_URLS
    i = 1
    while config.has_option('cipher.longrequest', 'exclude-url-%i' % i):
        url = config.get('cipher.longrequest', 'exclude-url-%i' % i)
        patt = re.compile(url)  # no flags, use `(?iLmsux)`
        IGNORE_URLS.append(patt)
        i += 1

    start = forceStart
    if not forceStart:
        if config.has_option('cipher.longrequest', 'start-thread'):
            start = config.getboolean('cipher.longrequest', 'start-thread')
    if start:
        startThread(None, None, None, None)
    return ThreadpoolCatcher(app)
