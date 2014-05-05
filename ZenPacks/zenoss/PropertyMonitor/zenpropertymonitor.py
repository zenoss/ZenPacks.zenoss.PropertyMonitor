##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Model, event and metric collection for VMware vSphere.
'''

import logging
log = logging.getLogger('zen.PropertyMonitor')

import Globals

import zope.component
import zope.interface

from twisted.internet import defer, task
from twisted.spread import pb

from Products.ZenCollector.daemon import CollectorDaemon

from Products.ZenCollector.interfaces import (
    ICollector,
    ICollectorPreferences,
    IScheduledTask,
    IDataService,
)

from Products.ZenCollector.tasks import (
    BaseTask,
    SimpleTaskFactory,
    SimpleTaskSplitter,
    TaskStates,
)


from ZenPacks.zenoss.PropertyMonitor.services.PropertyMonitorService import (
    PropertyMonitorDataSourceConfig,
    PropertyMonitorValueSpec,
)

pb.setUnjellyableForClass(PropertyMonitorDataSourceConfig, PropertyMonitorDataSourceConfig)


class Preferences(object):
    zope.interface.implements(ICollectorPreferences)

    collectorName = 'zenpropertymonitor'
    configurationService = 'ZenPacks.zenoss.PropertyMonitor.services.PropertyMonitorService'
    cycleInterval = 5 * 60
    configCycleInterval = 60 * 60 * 12
    maxTasks = None

    def buildOptions(self, parser):
        pass

    def postStartup(self):
        pass

class PropertyMonitorCollectorDaemon(CollectorDaemon):
    pass

class IntervalWorker(object):
    workers = {}

    def __init__(self, interval):
        self.interval = interval
        self.name = "IntervalWorker-%d" % (int(interval))
        self._dataService = zope.component.queryUtility(IDataService)
        self._collector = zope.component.queryUtility(ICollector)

        self.pendingSpecs = set()
        self._loopingCall = task.LoopingCall(self)  
        self._running = False  

    @classmethod
    def getWorker(cls, interval):
        if interval not in cls.workers:
            worker = IntervalWorker(interval)

            cls.workers[interval] = worker

        worker = cls.workers[interval]

        # start its loopingCall, if not already running.
        worker.start()

        return worker
           
    @defer.inlineCallbacks
    def start(self):
        if self._loopingCall.running: 
            return

        # Start (or re-start, if it stopped after an error) the loopingcall.
        try:
            log.info("Interval Worker %d LoopingCall starting" % self.interval)
            yield self._loopingCall.start(self.interval)
        except Exception:
            log.exception("Interval Worker %d LoopingCall encountered an error" % self.interval)
        finally:
            log.info("Interval Worker %d LoopingCall exited." % self.interval)

    def addSpec(self, spec):
        log.debug("[%s] addSpec: %s" % (self.name, spec))
        self.pendingSpecs.add(spec)

    def queueSize(self):
        return len(self.pendingSpecs)

    @defer.inlineCallbacks
    def __call__(self):
        pendingSpecs = list(self.pendingSpecs)
        self.pendingSpecs.clear()

        if not pendingSpecs:
            log.info("%s - no pending queries" % (self.name))
            return

        log.info("%s processing %d pending queries" % (self.name, len(pendingSpecs)))

        remoteProxy = self._collector.getRemoteConfigServiceProxy()
        processedSpecs = yield remoteProxy.callRemote('fetch_values', pendingSpecs)

        for spec in processedSpecs:
            log.debug("[%s] processSpec: %s" % (self.name, spec))
            self._dataService.writeRRD(
                spec.rrd.rrdPath,
                spec.value,
                spec.rrd.rrdType,
                rrdCommand=spec.rrd.command,
                cycleTime=self.interval,
                min=spec.rrd.min,
                max=spec.rrd.max,
                timestamp=spec.timestamp
            )


class PropertyMonitorTask(BaseTask):
    zope.interface.implements(IScheduledTask)    

    def __init__(self, taskName, configId, scheduleIntervalSeconds, taskConfig):
        super(PropertyMonitorTask, self).__init__(
            taskName, configId, scheduleIntervalSeconds, taskConfig)

        self.name = taskName
        self.configId = configId
        self.state = TaskStates.STATE_IDLE
        self.interval = scheduleIntervalSeconds
        self.config = taskConfig

    def getWorker(self):
        return IntervalWorker.getWorker(self.interval)

    def doTask(self):
        worker = self.getWorker()
        for dsConfig in self.config.dsConfigs:
            for rrdConfig in dsConfig.rrdConfig.values():
                valueSpec = PropertyMonitorValueSpec(dsConfig.component_path, dsConfig.property_name, rrdConfig, None)

                # Queue this value up to be collected the next time the IntervalWorker for this polling interval runs.        
                worker.addSpec(valueSpec)

        log.debug("Worker %s: Queue size is now %d." % (worker.name, worker.queueSize()))


def main():
    preferences = Preferences()
    task_factory = SimpleTaskFactory(PropertyMonitorTask)
    task_splitter = SimpleTaskSplitter(task_factory)
    daemon = PropertyMonitorCollectorDaemon(preferences, task_splitter)
    daemon.run()


if __name__ == '__main__':
    main()
