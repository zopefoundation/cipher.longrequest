import doctest
import os
import time

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
        longrequest.addLogEntryError, adapts=(interfaces.ILongRequestEventOver3,))

    zope.component.provideHandler(
        longrequest.addLogEntryWarn, adapts=(interfaces.ILongRequestEventOver2,))

    zope.component.provideHandler(
        longrequest.addLogEntryInfo, adapts=(interfaces.ILongRequestEventOver1,))

    zope.component.provideHandler(
        longrequest.addLogEntryFinishedInfo,
        adapts=(interfaces.ILongRequestFinishedEvent,))

    logger = loggingsupport.InstalledHandler('cipher.longrequest')
    return logger


def doctest_ThreadpoolCatcher():
    """
    test for ThreadpoolCatcher

        >>> print longrequest.THREADPOOL
        None

        >>> app = DummyApplication()
        >>> tc = longrequest.ThreadpoolCatcher(app)

    A request without a threadpool:

        >>> req = makeRequest()
        >>> tc(req.environ, None)

        >>> print longrequest.THREADPOOL
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
    """
    test for RequestCheckerThread, no threadpool available

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> rct.doWork()

        >>> print logger
        <BLANKLINE>
        >>> logger.clear()

        >>> longrequest.THREADPOOL = DummyThreadPool()

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        >>> logger.clear()

        >>> logger.uninstall()

    """


def doctest_RequestCheckerThread_over3():
    """
    test for RequestCheckerThread, duration over DURATION_LEVEL_3

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = time.time()
        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 40, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest ERROR
          Long running request detected
        thread_id:142
        duration:40 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        >>> logger.clear()

    Well unless DURATION_LEVEL_3 is None, it falls back to level 2

        >>> longrequest.DURATION_LEVEL_3 = None

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:40 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:

        >>> logger.uninstall()
        >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_over2():
    """
    test for RequestCheckerThread, duration over DURATION_LEVEL_2

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = time.time()
        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 15, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:15 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:

        >>> logger.uninstall()
        >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_over1():
    """
    test for RequestCheckerThread, duration over DURATION_LEVEL_1

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = time.time()
        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:142
        duration:7 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:

        >>> logger.uninstall()
        >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_single_notification():
    """
    test for RequestCheckerThread, ensure that a request shoots events only
    ONCE per timeout level exceeded

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> saveNOW = longrequest.RequestCheckerThread.NOW

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = 130000000
        >>> longrequest.RequestCheckerThread.NOW = lambda self: now
        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:142
        duration:7 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        >>> logger.clear()

        >>> now = 130000001
        >>> rct.doWork()
        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        >>> logger.clear()

        >>> now = 130000002
        >>> rct.doWork()
        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        >>> logger.clear()

        >>> now = 130000020
        >>> rct.doWork()
        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:27 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        >>> logger.clear()

        >>> logger.uninstall()
        >>> longrequest.RequestCheckerThread.NOW = saveNOW
        >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_final_event():
    """
    test for RequestCheckerThread, check that LongRequestFinishedEvent
    gets fired

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> saveNOW = longrequest.RequestCheckerThread.NOW

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = 130000000
        >>> longrequest.RequestCheckerThread.NOW = lambda self: now

    Case 1, the current request finishes

        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:142
        duration:7 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        >>> logger.clear()

        >>> now = 130000020
        >>> rct.doWork()
        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:27 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        >>> logger.clear()

        >>> now = 130000021

    Here the request finishes

        >>> longrequest.THREADPOOL.worker_tracker[142] = (now, None)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request finished thread_id:142 duration:27 sec
        http://localhost
        >>> logger.clear()


    Case 2, there is a new request served by the same thread

        >>> now = 130001022

        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:142
        duration:7 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        >>> logger.clear()

        >>> now = 130001042
        >>> rct.doWork()
        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:27 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        >>> logger.clear()

        >>> now = 130001044

    Here is the new request

        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now-1, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request finished thread_id:142 duration:27 sec
        http://localhost
        >>> logger.clear()


        >>> del longrequest.THREADPOOL.worker_tracker[142]


    Case 3, thread gets killed

        >>> now = 130002022

        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[389] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:389
        duration:7 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        >>> logger.clear()

        >>> now = 130002042
        >>> rct.doWork()
        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:389
        duration:27 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:
        form:
        >>> logger.clear()

        >>> now = 130002044

        >>> del longrequest.THREADPOOL.worker_tracker[389]

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request finished thread_id:389 duration:27 sec
        http://localhost
        >>> logger.clear()


        >>> logger.uninstall()
        >>> longrequest.RequestCheckerThread.NOW = saveNOW
        >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_all_levels_none():
    """
    test for RequestCheckerThread, all levels set to none

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

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads

        >>> logger.uninstall()
        >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_no_env():
    """
    test for RequestCheckerThread, no environ in the worker

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = time.time()
        >>> req = makeRequest()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 7, {})

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads

        >>> logger.uninstall()
        >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_uri():
    """
    test for RequestCheckerThread, URI determination

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = time.time()
        >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/foobar',
        ...     'QUERY_STRING': 'bar=42', 'SERVER_PORT': '443'}
        >>> req = makeRequest(kw)
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 15, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:15 sec
        URL:https://localhost/foobar?bar=42
        environment:{'PATH_INFO': '/foobar',
         'QUERY_STRING': 'bar=42',
         'REMOTE_ADDR': '1.1.1.1',
         'SERVER_NAME': 'localhost',
         'SERVER_PORT': '443'}
        username:
        form:
        >>> logger.clear()

    Check now HTTP_X_FORWARDED_FOR

        >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/foobar',
        ...     'QUERY_STRING': 'bar=42', 'SERVER_PORT': '443',
        ...     'HTTP_X_FORWARDED_FOR': 'https://foo.bar.com/bar'}
        >>> req = makeRequest(kw)
        >>> now = time.time()
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 15, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest WARNING
          Long running request detected
        thread_id:142
        duration:15 sec
        URL:https://foo.bar.com/bar
        environment:{'HTTP_X_FORWARDED_FOR': 'https://foo.bar.com/bar',
         'PATH_INFO': '/foobar',
         'QUERY_STRING': 'bar=42',
         'REMOTE_ADDR': '1.1.1.1',
         'SERVER_NAME': 'localhost',
         'SERVER_PORT': '443'}
        username:
        form:


        >>> logger.uninstall()
        >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_zope_request():
    """
    test for RequestCheckerThread, when a zope request is around

        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)

        >>> logger = addSubscribers()

        >>> longrequest.THREADPOOL = DummyThreadPool()
        >>> now = time.time()
        >>> req = makeRequest()
        >>> zope_request = DummyZopeRequest(username='foo.admin')
        >>> longrequest.ZOPE_THREAD_REQUESTS[142] = zope_request
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 40, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest ERROR
          Long running request detected
        thread_id:142
        duration:40 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:foo.admin
        form:{}
        >>> logger.clear()


        >>> rct = longrequest.RequestCheckerThread(None, None, None, None)
        >>> zope_request = DummyZopeRequest(username='foo.admin', form={'foobar':'42'})

        >>> longrequest.ZOPE_THREAD_REQUESTS[142] = zope_request
        >>> longrequest.THREADPOOL.worker_tracker[142] = (now - 40, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest ERROR
          Long running request detected
        thread_id:142
        duration:40 sec
        URL:http://localhost
        environment:{'REMOTE_ADDR': '1.1.1.1', 'SERVER_NAME': 'localhost', 'SERVER_PORT': '80'}
        username:foo.admin
        form:{'foobar': '42'}
        >>> logger.clear()


        >>> logger.uninstall()
        >>> longrequest.THREADPOOL = None

    """


def doctest_RequestCheckerThread_ignore_urls():
    """
    test for RequestCheckerThread, check ignore URLs

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

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        >>> logger.clear()

        >>> now = time.time()
        >>> kw = {'wsgi.url_scheme': 'https', 'PATH_INFO': '/customer/dashboard',
        ...     'SERVER_PORT': '443'}
        >>> req = makeRequest(kw)
        >>> longrequest.THREADPOOL.worker_tracker[143] = (now - 7, req.environ)

        >>> rct.doWork()

        >>> print logger
        cipher.longrequest DEBUG
          checking request threads
        cipher.longrequest INFO
          Long running request detected
        thread_id:143
        duration:7 sec
        URL:https://localhost/customer/dashboard
        environment:{'PATH_INFO': '/customer/dashboard',
         'REMOTE_ADDR': '1.1.1.1',
         'SERVER_NAME': 'localhost',
         'SERVER_PORT': '443'}
        username:
        form:

        >>> logger.uninstall()
        >>> longrequest.THREADPOOL = None

    """


def doctest_make_filter():
    """
    test for make_filter

        >>> here = os.path.dirname(__file__)
        >>> cfg = os.path.join(here, 'testing', 'paster.ini')

        >>> global_conf = {'__file__': cfg, 'here': here}

        >>> longrequest.make_filter(None, global_conf)
        <ThreadpoolCatcher>

        >>> print longrequest.DURATION_LEVEL_1
        3
        >>> print longrequest.DURATION_LEVEL_2
        7
        >>> print longrequest.DURATION_LEVEL_3
        42

        >>> print longrequest.INITIAL_DELAY
        11
        >>> print longrequest.TICK
        5

        >>> [p.pattern for p in longrequest.IGNORE_URLS]
        ['.*/rest/.*', '.*/admin/.*']


    """


def setUp(test=None):
    PlacelessSetup().setUp()

    longrequest.DURATION_LEVEL_1 = 2
    longrequest.DURATION_LEVEL_2 = 10
    longrequest.DURATION_LEVEL_3 = 30

    longrequest.IGNORE_URLS = []


def tearDown(test=None):
    PlacelessSetup().tearDown()

    longrequest.DURATION_LEVEL_1 = 2
    longrequest.DURATION_LEVEL_2 = 10
    longrequest.DURATION_LEVEL_3 = 30

    longrequest.INITIAL_DELAY = 1
    longrequest.TICK = 1

    longrequest.IGNORE_URLS = []


def test_suite():
    return doctest.DocTestSuite(setUp=setUp, tearDown=tearDown)
