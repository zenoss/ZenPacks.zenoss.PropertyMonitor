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
import json

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
    SubConfigurationTaskSplitter,
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
    def buildOptions(self):
        super(PropertyMonitorCollectorDaemon, self).buildOptions()

        self.parser.add_option('--querychunksize',
                               dest="querychunksize", type="int", default=256,
                               help="Number of properties to include in each zenhub query (default=256)")

    def getDevicePingIssues(result):
        # we don't care about device connectivity issues, since all
        # data is pulled from zenhub anyway.
        return defer.succeed([])


class TaskSplitter(SubConfigurationTaskSplitter):
    subconfigName = 'dsConfigs'

    def makeConfigKey(self, config, subconfig):
        return (config.id, str(subconfig.cycletime))


class IntervalWorker(object):
    workers = {}

    def __init__(self, interval):
        self.interval = int(interval)
        self.name = "IntervalWorker-%d" % self.interval
        self._dataService = zope.component.queryUtility(IDataService)
        self._collector = zope.component.queryUtility(ICollector)

        self.pendingSpecs = set()
        self._loopingCall = task.LoopingCall(self)
        self._running = False
        self.writeMetricWithMetadata = hasattr(
            self._dataService, 'writeMetricWithMetadata')
        self.metricExtraTags = getattr(
            self._dataService, "metricExtraTags", False)

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
            log.info("IntervalWorker-%d LoopingCall starting" % self.interval)
            yield self._loopingCall.start(self.interval)
        except Exception:
            log.exception("IntervalWorker-%d LoopingCall encountered an error" % self.interval)
        finally:
            log.info("IntervalWorker-%d LoopingCall exited." % self.interval)

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
        chunksize = self._collector.preferences.options.querychunksize

        for specs_chunk in self.chunk(pendingSpecs, chunksize):
            processedSpecs = yield remoteProxy.callRemote('fetch_values', specs_chunk)

            for spec in processedSpecs:
                tags = getattr(spec.rrd, "tags", None)
                if tags and self.metricExtraTags:
                    write_kwargs = {"extraTags": tags}
                else:
                    write_kwargs = {}
                log.debug("[%s] processSpec: %s" % (self.name, spec))
                try:
                    if self.writeMetricWithMetadata:
                        metadata, metric = self.extract_metadata(spec.rrd.rrdPath)
                        yield defer.maybeDeferred(
                            self._dataService.writeMetricWithMetadata,
                            metric,
                            spec.value,
                            spec.rrd.rrdType,
                            timestamp=spec.timestamp,
                            min=spec.rrd.min,
                            max=spec.rrd.max,
                            metadata=metadata,
                            **write_kwargs)
                    else:
                        yield defer.maybeDeferred(
                            self._dataService.writeRRD,
                            spec.rrd.rrdPath,
                            spec.value,
                            spec.rrd.rrdType,
                            rrdCommand=spec.rrd.command,
                            cycleTime=self.interval,
                            min=spec.rrd.min,
                            max=spec.rrd.max)

                except Exception as e:
                    log.exception("An exception occurred during write metric call for datapoint - {}. "
                                  "Exception message: {}".format(spec.rrd.dpName, e))

    def chunk(self, lst, n):
        """
        Break lst into n-sized chunks
        """
        return [lst[i:i + n] for i in xrange(0, len(lst), n)]

    def extract_metadata(self, path):
        """
        Extracts metadata from datapoint's RRD Path.
        """
        metricinfo, metric = path.rsplit("/", 1)
        if "METRIC_DATA" not in str(metricinfo):
            raise Exception(
                "Unable to write Metric with given path { %s } "
                "please see the rrdpath method" % (metricinfo,)
            )

        metadata = json.loads(metricinfo)
        return metadata, metric


class PropertyMonitorTask(BaseTask):
    zope.interface.implements(IScheduledTask)

    def __init__(self, taskName, configId, scheduleIntervalSeconds, taskConfig):
        super(PropertyMonitorTask, self).__init__(
            taskName, configId, scheduleIntervalSeconds, taskConfig)

        self.name = taskName
        self.configId = configId
        self.state = TaskStates.STATE_IDLE
        self.interval = int(scheduleIntervalSeconds)
        self.config = taskConfig

    def getWorker(self):
        return IntervalWorker.getWorker(self.interval)

    def doTask(self):
        worker = self.getWorker()
        for dsConfig in self.config.dsConfigs:
            for rrdConfig in dsConfig.rrdConfig.values():
                valueSpec = PropertyMonitorValueSpec(dsConfig.component_path, dsConfig.property_name, rrdConfig, None)

                # Queue this value up to be collected the next time the
                # IntervalWorker for this polling interval runs.
                worker.addSpec(valueSpec)

        log.debug("Worker %s: Queue size is now %d." % (worker.name, worker.queueSize()))


def main():
    preferences = Preferences()
    task_factory = SimpleTaskFactory(PropertyMonitorTask)
    task_splitter = TaskSplitter(task_factory)
    daemon = PropertyMonitorCollectorDaemon(preferences, task_splitter)
    daemon.run()


if __name__ == '__main__':
    main()
