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

import zope.interface
import zope.schema


class ILongRequestEvent(zope.interface.Interface):
    thread_id = zope.schema.Int(
            title=u'Thread ID',
            required=True)

    duration = zope.schema.Int(
            title=u'Duration (seconds)',
            required=True)

    uri = zope.schema.TextLine(
            title=u'URI',
            required=False)

    # BIG FAT WARNING:
    # this is the request environment passed in as a reference
    # so it can CHANGE easily, even go away
    # (remember, the request is running in a thread)
    worker_environ = zope.schema.Field(
            title=u'Worker environment',
            description=u'',
            required=False)

    # BIG FAT WARNING:
    # the same applies as for worker_environ
    # is None if not determinable
    zope_request = zope.schema.Field(
            title=u'zope.publisher request',
            description=u'',
            required=False)


@zope.interface.implementer(ILongRequestEvent)
class LongRequestEvent(object):

    def __init__(self, thread_id, duration, uri, worker_environ, zope_request):
        self.thread_id = thread_id
        self.duration = duration
        self.uri = uri
        self.worker_environ = worker_environ
        self.zope_request = zope_request


class ILongRequestEventOver1(ILongRequestEvent):
    pass


@zope.interface.implementer(ILongRequestEventOver1)
class LongRequestEventOver1(LongRequestEvent):
    pass


class ILongRequestEventOver2(ILongRequestEvent):
    pass


@zope.interface.implementer(ILongRequestEventOver2)
class LongRequestEventOver2(LongRequestEvent):
    pass


class ILongRequestEventOver3(ILongRequestEvent):
    pass


@zope.interface.implementer(ILongRequestEventOver3)
class LongRequestEventOver3(LongRequestEvent):
    pass


class ILongRequestFinishedEvent(zope.interface.Interface):
    thread_id = zope.schema.Int(
            title=u'Thread ID',
            required=True)

    duration = zope.schema.Int(
            title=u'Duration (seconds)',
            required=True)

    uri = zope.schema.TextLine(
            title=u'URI',
            required=False)


@zope.interface.implementer(ILongRequestFinishedEvent)
class LongRequestFinishedEvent(object):

    def __init__(self, thread_id, duration, uri):
        self.thread_id = thread_id
        self.duration = duration
        self.uri = uri


class ILongRequestTickEvent(zope.interface.Interface):
    """An hook for additional processing of the thread pool

    Can be used for things like monitoring the number of busy threads.
    """

    thread_pool = zope.interface.Attribute("Thread pool")


@zope.interface.implementer(ILongRequestTickEvent)
class LongRequestTickEvent(object):

    def __init__(self, thread_pool):
        self.thread_pool = thread_pool
