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


class LongRequestEvent(object):
    zope.interface.implements(ILongRequestEvent)

    def __init__(self, thread_id, duration, uri, worker_environ, zope_request):
        self.thread_id = thread_id
        self.duration = duration
        self.uri = uri
        self.worker_environ = worker_environ
        self.zope_request = zope_request


class ILongRequestEventOver1(ILongRequestEvent):
    pass


class LongRequestEventOver1(LongRequestEvent):
    zope.interface.implements(ILongRequestEventOver1)


class ILongRequestEventOver2(ILongRequestEvent):
    pass


class LongRequestEventOver2(LongRequestEvent):
    zope.interface.implements(ILongRequestEventOver2)


class ILongRequestEventOver3(ILongRequestEvent):
    pass


class LongRequestEventOver3(LongRequestEvent):
    zope.interface.implements(ILongRequestEventOver3)


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


class LongRequestFinishedEvent(object):
    zope.interface.implements(ILongRequestFinishedEvent)

    def __init__(self, thread_id, duration, uri):
        self.thread_id = thread_id
        self.duration = duration
        self.uri = uri
