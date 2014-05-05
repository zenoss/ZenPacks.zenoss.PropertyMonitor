##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.PropertyMonitor')

from twisted.spread import pb
import time

import Globals

from Products.ZenCollector.services.config import CollectorConfigService
from Products.ZenUtils.Utils import unused
from Products.Zuul.interfaces import IInfo

from ZenPacks.zenoss.PropertyMonitor.datasources.ModelPropertyDataSource import ModelPropertyDataSource

# Make pyflakes happy.
unused(Globals)


class PropertyMonitorService(CollectorConfigService):
    def _createDeviceProxy(self, device):
        proxy = CollectorConfigService._createDeviceProxy(self, device)

        proxy.configCycleInterval = 5 * 60
        proxy.dsConfigs = []
        proxy.thresholds = []

        proxy.thresholds += device.getThresholdInstances(
            ModelPropertyDataSource.sourcetype)

        # We only worry about monitoring templates against components right now.
        for component in device.getMonitoredComponents():
            for template in component.getRRDTemplates():
                for ds in self._getDataSourcesFromTemplate(template):
                    try:
                        dsConfig = PropertyMonitorDataSourceConfig(
                            device, component, template, ds)

                        # Filter out anything that is not applicable to
                        # this component type for some reason.
                        if dsConfig.class_name == component.meta_type:
                            proxy.dsConfigs.append(dsConfig)

                    except Exception, e:
                        log.exception(e)

            proxy.thresholds += component.getThresholdInstances(
                ModelPropertyDataSource.sourcetype)

        return proxy

    def _getDataSourcesFromTemplate(self, template):
        datasources = []

        for ds in template.getRRDDataSources("Modeled Property Value"):
            if not ds.enabled:
                continue
            datasources.append(ds)

        return datasources


    def remote_fetch_values(self, valueSpecs):
        for spec in valueSpecs:
            try:
                obj = self.dmd.getObjByPath(spec.component_path)
                spec.value = getattr(IInfo(obj), spec.property_name, None)
                spec.timestamp = time.time()
                log.debug("%s -> %s = %s", spec.component_path, spec.property_name, spec.value)
            except Exception, e:
                spec.value = None
                log.error("Unable to retrieve %s -> %s (%r)", spec.component_path, spec.property_name, e)

        return valueSpecs


class PropertyMonitorValueSpec(pb.Copyable, pb.RemoteCopy):
    def __init__(self, component_path, property_name, rrd, value):
        self.component_path = component_path
        self.property_name = property_name
        self.rrd = rrd
        self.value = value
        self.timestamp = None

    def __hash__(self):
        return hash(self.rrd.rrdPath)

    def __eq__(self, other):
        if self.component_path == other.component_path and \
           self.property_name == other.property_name and \
           self.rrd == other.rrd and \
           self.value == other.value and \
           self.timestamp == other.timestamp:
            return True
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "PropertyMonitorValueSpec(%s:%s rrdPath=%s, value=%s, timestamp=%s)" % (
            self.component_path,
            self.property_name,
            self.rrd.rrdPath,
            self.value,
            self.timestamp
        )


pb.setUnjellyableForClass(PropertyMonitorValueSpec, PropertyMonitorValueSpec)


class PropertyMonitorDataSourceConfig(pb.Copyable, pb.RemoteCopy):
    """
    Represents a single PropertyMonitor datasource.
    """
    
    def __init__(self, device, component, template, datasource):
        self.device = device.id
        self.datasourceId = datasource.id               
        self.class_name = datasource.class_name
        self.component_path = component.getPrimaryUrlPath()
        self.property_name = datasource.property_name

        self.rrdConfig = {}
        for dp in datasource.datapoints():
            self.rrdConfig[dp.id] = RRDConfig(component, datasource, dp)

pb.setUnjellyableForClass(PropertyMonitorDataSourceConfig, PropertyMonitorDataSourceConfig)    


class RRDConfig(pb.Copyable, pb.RemoteCopy):
    """
    RRD configuration for a datapoint.
    Contains the create command and the min and max 
    values for a datapoint
    """
    def __init__(self, component, datasource, dp):
        self.dpName = dp.name()
        self.command = dp.createCmd
        self.dataPointId = dp.id
        self.min = dp.rrdmin
        self.max = dp.rrdmax
        self.rrdType = dp.rrdtype
        self.rrdPath = '/'.join((component.rrdPath(), dp.name()))


pb.setUnjellyableForClass(RRDConfig, RRDConfig)        


