from __future__ import print_function
import collections
import doctest
import sys
import time
import traceback

import mock

import zope.component
# HACK to make sure basicmost event subscriber is installed
import zope.component.event
from zope.testing import loggingsupport
from zope.testing.cleanup import CleanUp as PlacelessSetup

from cipher.longrequest import interfaces, longrequest


class DummyRequest:
    def __init__(self, environ):
        self.environ = environ
        self.callbacks = []

    def add_response_callback(self, callback):
        self.callbacks.append(callback)


def makeRequest(kw=None):
    environ = {'wsgi.version': (1, 0),
               'wsgi.url_scheme': 'http',
               'SERVER_PORT': '80'}
    if kw is not None:
        environ.update(kw)
    environ['REMOTE_ADDR'] = '1.1.1.1'
    environ['SERVER_NAME'] = 'localhost'
    return DummyRequest(environ)


class DummyPrincipal:
    id = None


class DummyZopeRequest:
    def __init__(self, username=None, form={}):
        self.principal = DummyPrincipal()
        self.principal.id = username
        self.form = form


class DummyThreadPool:
    def __init__(self):
        self.worker_tracker = {}


class DummyApplication:
    def __call__(self, environ, start_response):
        pass


def addSubscribers():
    zope.component.provideHandler(
        longrequest.addLogEntryError,
        adapts=(interfaces.ILongRequestEventOver3,))

    zope.component.provideHandler(
        longrequest.addLogEntryWarn,
        adapts=(interfaces.ILongRequestEventOver2,))

    zope.component.provideHandler(
        longrequest.addLogEntryInfo,
        adapts=(interfaces.ILongRequestEventOver1,))

    zope.component.provideHandler(
        longrequest.addLogEntryFinishedInfo,
        adapts=(interfaces.ILongRequestFinishedEvent,))

    logger = loggingsupport.InstalledHandler('cipher.longrequest')
    return logger


def doctest_ThreadpoolCatcher():
    """Test for ThreadpoolCatcher

        >>> print(longrequest.THREADPOOL)
        None

        >>> app = DummyApplication()
        >>> tc = longrequest.ThreadpoolCatcher(app)

    A request without a threadpool:

        >>> req = makeRequest()
        >>> tc(req.environ, None)

        >>> print(longrequest.THREADPOOL)
        None


    Let's add the threadpool:

        >>> tpool = DummyThreadPool()
        >>> req.environ['paste.httpserver.thread_pool'] = tpool

        >>> tc(req.environ, None)

        >>> longrequest.THREADPOOL is tpool
        True

    Once set, it stays forever:

        >>> req.environ['paste.httpserver.thread_pool'] = 42
        >>> tc(req.environ, None)

        >>> longrequest.THREADPOOL is tpool
        True

    Cleanup:

        >>> longrequest.THREADPOOL = None
    """


def doctest_RequestCheckerThread_nowork():
    """Test for RequestCheckerThread, no threadpool available

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> logger = addSubscribers()

    >>> rct.doWork()

    >>> print(logger)
    <BLANKLINE>
    >>> logger.clear()

    >>> longrequest.THREADPOOL = DummyThreadPool()

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    >>> logger.clear()

    >>> logger.uninstall()
    >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_over3():
    """Test for RequestCheckerThread, duration over DURATION_LEVEL_3

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> logger = addSubscribers()

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> req = makeRequest()
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 40, req.environ)

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    cipher.longrequest ERROR
      Long running request detected
    thread_id:142
    duration:40 sec
    URL:http://localhost
    threads in use:1
    environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
    username:
    form:
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack
    >>> logger.clear()

    Well unless DURATION_LEVEL_3 is None, it falls back to level 2

    >>> longrequest.DURATION_LEVEL_3 = None

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    cipher.longrequest WARNING
      Long running request detected
    thread_id:142
    duration:40 sec
    URL:http://localhost
    threads in use:1
    environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
    username:
    form:
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack

    >>> logger.uninstall()
    >>> longrequest.THREADPOOL = None

    """  # noqa: E501 line too long


def doctest_RequestCheckerThread_over2():
    """Test for RequestCheckerThread, duration over DURATION_LEVEL_2

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> logger = addSubscribers()

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> req = makeRequest()
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 15, req.environ)

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    cipher.longrequest WARNING
      Long running request detected
    thread_id:142
    duration:15 sec
    URL:http://localhost
    threads in use:1
    environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
    username:
    form:
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack

    >>> logger.uninstall()
    >>> longrequest.THREADPOOL = None

    """  # noqa: E501 line too long


def doctest_RequestCheckerThread_over1():
    """Test for RequestCheckerThread, duration over DURATION_LEVEL_1

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> logger = addSubscribers()

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> req = makeRequest()
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    cipher.longrequest INFO
      Long running request detected
    thread_id:142
    duration:7 sec
    URL:http://localhost
    threads in use:1
    environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
    username:
    form:
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack

    >>> logger.uninstall()
    >>> longrequest.THREADPOOL = None

    """  # noqa: E501 line too long


def doctest_RequestCheckerThread_single_notification():
    """
    test for RequestCheckerThread, ensure that a request shoots events only
    ONCE per timeout level exceeded

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> saveNOW = longrequest.NOW

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = 130000000
        >>> longrequest.NOW = lambda: now
        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:142
        duration:7 sec
        URL:http://localhost
        threads in use:1
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        Thread stack:
          File "module.py", line 69, in main
            do_stuff()
          File "submodule.py", line 42, in helper
            endless_loop()
        Top of stack
        >>> logger.clear()

        >>> now = 130000001
        >>> rct.doWork()
        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        >>> logger.clear()

        >>> now = 130000002
        >>> rct.doWork()
        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        >>> logger.clear()

        >>> now = 130000020
        >>> rct.doWork()
        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:27 sec
        URL:http://localhost
        threads in use:1
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        Thread stack:
          File "module.py", line 69, in main
            do_stuff()
          File "submodule.py", line 42, in helper
            endless_loop()
        Top of stack
        >>> logger.clear()

        >>> logger.uninstall()
        >>> longrequest.NOW = saveNOW
        >>> longrequest.THREADPOOL = None

    """  # noqa: E501 line too long


def doctest_RequestCheckerThread_final_event():
    """
    test for RequestCheckerThread, check that LongRequestFinishedEvent
    gets fired

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> saveNOW = longrequest.NOW

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = 130000000
        >>> longrequest.NOW = lambda: now

    Case 1, the current request finishes

        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:142
        duration:7 sec
        URL:http://localhost
        threads in use:1
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        Thread stack:
          File "module.py", line 69, in main
            do_stuff()
          File "submodule.py", line 42, in helper
            endless_loop()
        Top of stack
        >>> logger.clear()

        >>> now = 130000020
        >>> rct.doWork()
        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:27 sec
        URL:http://localhost
        threads in use:1
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        Thread stack:
          File "module.py", line 69, in main
            do_stuff()
          File "submodule.py", line 42, in helper
            endless_loop()
        Top of stack
        >>> logger.clear()

        >>> rct.getMaxRequestTime()
        0

        >>> now = 130000021

    Here the request finishes

        >>> longrequest.THREADPOOL.worker_tracker[142] = (now, None)

        >>> rct.doWork()

        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request finished thread_id:142 duration:27 sec
        http://localhost
        >>> logger.clear()

        >>> rct.getMaxRequestTime()
        27

    Case 2, there is a new request served by the same thread

        >>> now = 130001022

        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:142
        duration:7 sec
        URL:http://localhost
        threads in use:1
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        Thread stack:
          File "module.py", line 69, in main
            do_stuff()
          File "submodule.py", line 42, in helper
            endless_loop()
        Top of stack
        >>> logger.clear()

        >>> now = 130001042
        >>> rct.doWork()
        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:27 sec
        URL:http://localhost
        threads in use:1
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        Thread stack:
          File "module.py", line 69, in main
            do_stuff()
          File "submodule.py", line 42, in helper
            endless_loop()
        Top of stack
        >>> logger.clear()

        >>> now = 130001044

    Here is the new request

        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now-1, req.environ)

        >>> rct.doWork()

        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request finished thread_id:142 duration:27 sec
        http://localhost
        >>> logger.clear()

        >>> rct.getMaxRequestTime()
        27

        >>> del longrequest.THREADPOOL.worker_tracker[142]


    Case 3, thread gets killed

        >>> now = 130002022

        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[389] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:389
        duration:7 sec
        URL:http://localhost
        threads in use:1
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        Thread stack:
          File "module.py", line 69, in main
            do_stuff()
          File "submodule.py", line 42, in helper
            endless_loop()
        Top of stack
        >>> logger.clear()

        >>> now = 130002042
        >>> rct.doWork()
        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:389
        duration:27 sec
        URL:http://localhost
        threads in use:1
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        Thread stack:
          File "module.py", line 69, in main
            do_stuff()
          File "submodule.py", line 42, in helper
            endless_loop()
        Top of stack
        >>> logger.clear()

        >>> now = 130002044

        >>> del longrequest.THREADPOOL.worker_tracker[389]

        >>> rct.doWork()

        >>> print(logger)
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request finished thread_id:389 duration:27 sec
        http://localhost
        >>> logger.clear()

        >>> logger.uninstall()
        >>> longrequest.NOW = saveNOW
        >>> longrequest.THREADPOOL = None

    """  # noqa: E501 line too long


def doctest_RequestCheckerThread_all_levels_none():
    """Test for RequestCheckerThread, all levels set to none

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> logger = addSubscribers()

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> req = makeRequest()
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

    >>> longrequest.DURATION_LEVEL_1 = None
    >>> longrequest.DURATION_LEVEL_2 = None
    >>> longrequest.DURATION_LEVEL_3 = None

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads

    >>> logger.uninstall()
    >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_no_env():
    """Test for RequestCheckerThread, no environ in the worker

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> logger = addSubscribers()

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> req = makeRequest()
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, {})

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads

    >>> logger.uninstall()
    >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_uri():
    """Test for RequestCheckerThread, URI determination

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> logger = addSubscribers()

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/foobar',
    ...     'QUERY_STRING': 'bar=42', 'SERVER_PORT': '443'}
    >>> req = makeRequest(kw)
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 15, req.environ)

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    cipher.longrequest WARNING
      Long running request detected
    thread_id:142
    duration:15 sec
    URL:https://localhost/foobar?bar=42
    threads in use:1
    environment:{'PATH_INFO': '/foobar',
     'QUERY_STRING': 'bar=42',
     'REMOTE_ADDR': '1.1.1.1',
     'SERVER_NAME': 'localhost',
     'SERVER_PORT': '443'}
    username:
    form:
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack
    >>> logger.clear()

    Check now HTTP_X_FORWARDED_FOR:

    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/foobar',
    ...     'QUERY_STRING': 'bar=42', 'SERVER_PORT': '443',
    ...     'HTTP_X_FORWARDED_FOR': 'https://foo.bar.com/bar'}
    >>> req = makeRequest(kw)
    >>> now = time.time()
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 15, req.environ)

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    cipher.longrequest WARNING
      Long running request detected
    thread_id:142
    duration:15 sec
    URL:https://foo.bar.com/bar
    threads in use:1
    environment:{'HTTP_X_FORWARDED_FOR': 'https://foo.bar.com/bar',
     'PATH_INFO': '/foobar',
     'QUERY_STRING': 'bar=42',
     'REMOTE_ADDR': '1.1.1.1',
     'SERVER_NAME': 'localhost',
     'SERVER_PORT': '443'}
    username:
    form:
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack


    >>> logger.uninstall()
    >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_zope_request():
    """Test for RequestCheckerThread, when a zope request is around

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> logger = addSubscribers()

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> req = makeRequest()
    >>> zope_request = DummyZopeRequest(username='foo.admin')
    >>> longrequest.ZOPE_THREAD_REQUESTS[142] = zope_request
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 40, req.environ)

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    cipher.longrequest ERROR
      Long running request detected
    thread_id:142
    duration:40 sec
    URL:http://localhost
    threads in use:1
    environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
    username:foo.admin
    form:{}
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack
    >>> logger.clear()


    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)
    >>> zope_request = DummyZopeRequest(username='foo.admin', form={'foobar':'42'})

    >>> longrequest.ZOPE_THREAD_REQUESTS[142] = zope_request
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 40, req.environ)

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    cipher.longrequest ERROR
      Long running request detected
    thread_id:142
    duration:40 sec
    URL:http://localhost
    threads in use:1
    environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
    username:foo.admin
    form:{'foobar': '42'}
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack
    >>> logger.clear()


    >>> logger.uninstall()
    >>> longrequest.THREADPOOL = None

    """  # noqa: E501 line too long


def doctest_RequestCheckerThread_ignore_urls():
    """Test for RequestCheckerThread, check ignore URLs

    >>> import re
    >>> longrequest.IGNORE_URLS = [re.compile('.*/rest/.*'),
    ...     re.compile('.*/admin/.*')]

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> logger = addSubscribers()

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/rest/update-it',
    ...     'QUERY_STRING': 'bar=42', 'SERVER_PORT': '443'}
    >>> req = makeRequest(kw)
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    >>> logger.clear()

    >>> now = time.time()
    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/customer/dashboard',
    ...     'SERVER_PORT': '443'}
    >>> req = makeRequest(kw)
    >>> longrequest.THREADPOOL.worker_tracker[143] = (now - 7, req.environ)

    >>> rct.doWork()

    >>> print(logger)
    cipher.longrequest DEBUG
      checking request threads
    cipher.longrequest INFO
      Long running request detected
    thread_id:143
    duration:7 sec
    URL:https://localhost/customer/dashboard
    threads in use:2
    environment:{'PATH_INFO': '/customer/dashboard',
     'REMOTE_ADDR': '1.1.1.1',
     'SERVER_NAME': 'localhost',
     'SERVER_PORT': '443'}
    username:
    form:
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack

    >>> logger.uninstall()
    >>> longrequest.THREADPOOL = None

    """


def doctest_getMaxThreadsUsed_getThreadsUsed():
    """Test for getMaxThreadsUsed

    >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

    >>> longrequest.getMaxThreadsUsed()
    Traceback (most recent call last):
    ...
    ValueError: No thread running

    >>> longrequest.getThreadsUsed()
    Traceback (most recent call last):
    ...
    ValueError: No threadpool yet!

    >>> longrequest.THREAD = rct

    >>> longrequest.getMaxThreadsUsed()
    0

    >>> longrequest.THREADPOOL = DummyThreadPool()

    >>> longrequest.getMaxThreadsUsed()
    0

    >>> longrequest.getThreadsUsed()
    0

    >>> now = time.time()
    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/rest/update-it',
    ...     'QUERY_STRING': 'bar=42', 'SERVER_PORT': '443'}
    >>> req = makeRequest(kw)
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

    >>> rct.doWork()

    >>> longrequest.getMaxThreadsUsed()
    1

    >>> longrequest.getThreadsUsed()
    1

    >>> longrequest.THREADPOOL.worker_tracker[143] = (now - 7, req.environ)
    >>> rct.doWork()

    >>> longrequest.getMaxThreadsUsed()
    2

    >>> longrequest.getThreadsUsed()
    2

    >>> longrequest.THREADPOOL.worker_tracker.clear()

    >>> longrequest.getThreadsUsed()
    0

    >>> rct.doWork()

    >>> longrequest.getMaxThreadsUsed()
    2

    >>> longrequest.getMaxThreadsUsed(True)
    2

    >>> longrequest.getMaxThreadsUsed()
    0

    >>> longrequest.THREAD = None
    >>> longrequest.THREADPOOL = None
    """


def doctest_make_filter():
    """Test for make_filter

    >>> import os.path
    >>> here = os.path.dirname(__file__)
    >>> cfg = os.path.join(here, 'testing', 'paster.ini')

    >>> global_conf = {'__file__': cfg, 'here': here}

    >>> longrequest.make_filter(None, global_conf)
    <ThreadpoolCatcher>

    >>> print(longrequest.DURATION_LEVEL_1)
    3
    >>> print(longrequest.DURATION_LEVEL_2)
    7
    >>> print(longrequest.DURATION_LEVEL_3)
    42

    >>> print(longrequest.INITIAL_DELAY)
    11
    >>> print(longrequest.TICK)
    5

    >>> [p.pattern for p in longrequest.IGNORE_URLS]
    ['.*/rest/.*', '.*/admin/.*']

    """


def doctest_getAllThreadInfo():
    r"""Test for getAllThreadInfo

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/rest/update-it',
    ...     'QUERY_STRING': 'bar=42', 'SERVER_PORT': '443'}
    >>> req = makeRequest(kw)
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/customer/dashboard',
    ...     'SERVER_PORT': '443'}
    >>> req = makeRequest(kw)
    >>> longrequest.THREADPOOL.worker_tracker[143] = (now - 7, req.environ)

    >>> info = longrequest.getAllThreadInfo()
    >>> print('\n--\n'.join(info))
    thread_id:142
    duration:7 sec
    URL:https://localhost/rest/update-it?bar=42
    threads in use:2
    environment:{'PATH_INFO': '/rest/update-it',
     'QUERY_STRING': 'bar=42',
     'REMOTE_ADDR': '1.1.1.1',
     'SERVER_NAME': 'localhost',
     'SERVER_PORT': '443',
     'wsgi.url_scheme': 'https',
     'wsgi.version': (1, 0)}
    username:foo.admin
    form:{'foobar': '42'}
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack
    --
    thread_id:143
    duration:7 sec
    URL:https://localhost/customer/dashboard
    threads in use:2
    environment:{'PATH_INFO': '/customer/dashboard',
     'REMOTE_ADDR': '1.1.1.1',
     'SERVER_NAME': 'localhost',
     'SERVER_PORT': '443',
     'wsgi.url_scheme': 'https',
     'wsgi.version': (1, 0)}
    username:
    form:
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack

    >>> info = longrequest.getAllThreadInfo(omitThreads=(143,))
    >>> print('\n--\n'.join(info))
    thread_id:142
    duration:7 sec
    URL:https://localhost/rest/update-it?bar=42
    threads in use:2
    environment:{'PATH_INFO': '/rest/update-it',
     'QUERY_STRING': 'bar=42',
     'REMOTE_ADDR': '1.1.1.1',
     'SERVER_NAME': 'localhost',
     'SERVER_PORT': '443',
     'wsgi.url_scheme': 'https',
     'wsgi.version': (1, 0)}
    username:foo.admin
    form:{'foobar': '42'}
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack

    >>> longrequest.THREADPOOL = None
    """


def doctest_getThreadTraceback():
    """Test getThreadTraceback

    Normally, getThreadTraceback returns the traceback for the frame:

        >>> print(longrequest.getThreadTraceback(142))
          File "module.py", line 69, in main
            do_stuff()
          File "submodule.py", line 42, in helper
            endless_loop()

    However, when the thread_id parameter does not match any existing
    thread:

        >>> sys._current_frames.return_value = ret = mock.MagicMock()
        >>> ret.__getitem__.side_effect = KeyError(142)
        >>> sys._current_frames()[142]
        Traceback (most recent call last):
          ...
        KeyError: 142

        >>> longrequest.getThreadTraceback(142)
        '  ???'

    """


def doctest_getURI():
    r"""Test for getURI

    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/rest/update-it',
    ...     'QUERY_STRING': 'bar=42', 'SERVER_PORT': '443'}
    >>> req = makeRequest(kw)

    >>> longrequest.getURI(req.environ)
    'https://localhost/rest/update-it?bar=42'

    >>> longrequest.getURI(None)
    'n/a'

    >>> longrequest.getURI({'some': 'crap'})
    'n/a'
    """


def doctest_addLogEntry():
    r"""Test for addLogEntry

    >>> import logging
    >>> saveVERBOSE = longrequest.VERBOSE_LOG
    >>> longrequest.VERBOSE_LOG = True

    >>> longrequest.THREADPOOL = DummyThreadPool()
    >>> now = time.time()
    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/rest/update-it',
    ...     'QUERY_STRING': 'bar=42', 'SERVER_PORT': '443'}
    >>> req = makeRequest(kw)
    >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

    >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/customer/dashboard',
    ...     'SERVER_PORT': '443'}
    >>> req = makeRequest(kw)
    >>> longrequest.THREADPOOL.worker_tracker[143] = (now - 7, req.environ)

    >>> logger = addSubscribers()

    >>> devent = interfaces.LongRequestEvent(143, 7, 'yadayada', kw, None)
    >>> longrequest.addLogEntry(devent, logging.INFO)

    >>> print(logger)
    cipher.longrequest INFO
      Long running request detected
    thread_id:143
    duration:7 sec
    URL:yadayada
    threads in use:2
    environment:{'PATH_INFO': '/customer/dashboard',
     'SERVER_PORT': '443',
     'wsgi.url_scheme': 'https'}
    username:
    form:
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack
    --
    Other threads:
    --
    thread_id:142
    duration:7 sec
    URL:https://localhost/rest/update-it?bar=42
    threads in use:2
    environment:{'PATH_INFO': '/rest/update-it',
     'QUERY_STRING': 'bar=42',
     'REMOTE_ADDR': '1.1.1.1',
     'SERVER_NAME': 'localhost',
     'SERVER_PORT': '443',
     'wsgi.url_scheme': 'https',
     'wsgi.version': (1, 0)}
    username:foo.admin
    form:{'foobar': '42'}
    Thread stack:
      File "module.py", line 69, in main
        do_stuff()
      File "submodule.py", line 42, in helper
        endless_loop()
    Top of stack

    >>> logger.uninstall()

    >>> longrequest.VERBOSE_LOG = saveVERBOSE
    >>> longrequest.THREADPOOL = None
    """


def setUp(test=None):
    PlacelessSetup().setUp()

    longrequest.DURATION_LEVEL_1 = 2
    longrequest.DURATION_LEVEL_2 = 10
    longrequest.DURATION_LEVEL_3 = 30

    longrequest.IGNORE_URLS = []

    test.patcher = mock.patch("sys._current_frames")
    test.patcher2 = mock.patch("traceback.print_stack")
    test.patcher.start()
    test.patcher2.start()
    sys._current_frames.return_value = collections.defaultdict(
        sys._getframe)
    traceback.print_stack = lambda frame, file: file.write(
        '  File "module.py", line 69, in main\n'
        '    do_stuff()\n'
        '  File "submodule.py", line 42, in helper\n'
        '    endless_loop()\n')


def tearDown(test=None):
    test.patcher.stop()
    test.patcher2.stop()

    PlacelessSetup().tearDown()

    longrequest.DURATION_LEVEL_1 = 2
    longrequest.DURATION_LEVEL_2 = 10
    longrequest.DURATION_LEVEL_3 = 30

    longrequest.INITIAL_DELAY = 1
    longrequest.TICK = 1

    longrequest.IGNORE_URLS = []


def test_suite():
    return doctest.DocTestSuite(setUp=setUp, tearDown=tearDown,
                                optionflags=doctest.NORMALIZE_WHITESPACE)
