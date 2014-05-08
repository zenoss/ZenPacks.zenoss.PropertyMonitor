##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Datasource type used for monitoring (numeric) model properties from ZODB
'''

from zope.component import adapts
from zope.interface import implements

from Products.ZenModel.RRDDataSource import SimpleRRDDataSource
from Products.ZenModel.ZenPackPersistence import ZenPackPersistence
from Products.ZenUtils.ZenTales import talesEvalStr
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.infos.template import RRDDataSourceInfo
from Products.Zuul.interfaces import IRRDDataSourceInfo
from Products.Zuul.utils import ZuulMessageFactory as _t
from Products.ZenWidgets import messaging

from Products.Zuul.interfaces import ICatalogTool, IInfo
from Products.AdvancedQuery import Eq


class MonitoredPropertyDataSource(ZenPackPersistence, SimpleRRDDataSource):
    '''
    Model class for MonitoredPropertyDataSource.
    '''

    ZENPACKID = 'ZenPacks.zenoss.PropertyMonitor'

    MBP_TYPE = 'Property'

    sourcetypes = (MBP_TYPE,)
    sourcetype = MBP_TYPE

    # SimpleRRDDataSource property overrides.
    cycletime = '${here/zPropertyMonitorInterval}'
    eventClass = '/Ignore'
    severity = 0

    class_name = ''
    property_name = ''

    _properties = tuple([p for p in SimpleRRDDataSource._properties if p['id'] != 'cycletime']) + (
        {'id': 'cycletime', 'type': 'string', 'mode': 'w'},
        {'id': 'class_name', 'type': 'string', 'mode': 'w'},
        {'id': 'property_name', 'type': 'string', 'mode': 'w'},
    )

    def getDescription(self):
        '''
        Return a friendly description of this datasource.
        '''
        if not self.property_name:
            return 'Not Configured'

        return "%s / %s" % (self.class_name, self.property_name)

    def getComponent(self, context):
        return context.id

    def talesEval(self, text, context):
        device = context.device()
        extra = {
            'device': device,
            'dev': device,
            'devname': device.id,
            'datasource': self,
            'ds': self,
            }

        return talesEvalStr(str(text), context, extra=extra)

    def getCycleTime(self, context):
        return int(self.talesEval(self.cycletime, context))

    def testDataSourceAgainstDevice(self, testDevice, REQUEST, write, errorLog):
        """
        Does the majority of the logic for testing a datasource against the device
        @param string testDevice The id of the device we are testing
        @param Dict REQUEST the browers request
        @param Function write The output method we are using to stream the result of the command
        @parma Function errorLog The output method we are using to report errors
        """
        out = REQUEST.RESPONSE
        # Determine which device to execute against
        device = None
        if testDevice:
            # Try to get specified device
            device = self.findDevice(testDevice)
            if not device:
                errorLog(
                    'No device found',
                    'Cannot find device matching %s.' % testDevice,
                    priority=messaging.WARNING
                )
                return self.callZenScreen(REQUEST)
        elif hasattr(self, 'device'):
            # ds defined on a device, use that device
            device = self.device()
        elif hasattr(self, 'getSubDevicesGen'):
            # ds defined on a device class, use any device from the class
            try:
                device = self.getSubDevicesGen().next()
            except StopIteration:
                # No devices in this class, bail out
                pass
        if not device:
            errorLog(
                'No Testable Device',
                'Cannot determine a device against which to test.',
                priority=messaging.WARNING
            )
            return self.callZenScreen(REQUEST)

        ## Execute the datasource

        class_name = REQUEST.get('class_name')
        property_name = REQUEST.get('property_name')
        results = ICatalogTool(device).search(query=Eq('meta_type', class_name))

        if not results.total:
            out.write("0 objects found. No test performed.\n")
            return

        if results.total > 10:
            out.write("%d %s components found, showing first 10<p>\n" % (results.total, class_name))

        for (i, result) in enumerate(results):
            obj = result.getObject()
            info = IInfo(obj)
            property_value = getattr(info, property_name, "ERROR")

            out.write("&nbsp;&nbsp;&nbsp; '%s' %s = %s<br>\n" % (obj.titleOrId(), property_name, property_value))

            if i + 1 == 10:
                break


class IMonitoredPropertyDataSourceInfo(IRRDDataSourceInfo):
    '''
    API Info interface for MonitoredPropertyDataSource.
    '''

    # IRRDDataSourceInfo doesn't define this.
    cycletime = schema.TextLine(title=_t(u'Cycle Time (seconds)'))

    # The xtype for class_name also manages property_name.
    class_name = schema.TextLine(
        title=_t(u'Property'),
        group=_t('Detail'),
        xtype='mbp_property')


class MonitoredPropertyDataSourceInfo(RRDDataSourceInfo):
    '''
    API Info adapter factory for MonitoredPropertyDataSource.
    '''

    implements(IMonitoredPropertyDataSourceInfo)
    adapts(MonitoredPropertyDataSource)

    # RRDDataSourceInfo doesn't define this.
    cycletime = ProxyProperty('cycletime')

    class_name = ProxyProperty('class_name')
    property_name = ProxyProperty('property_name')

    @property
    def testable(self):
        """
        This tells the client if we can test this datasource against a
        specific device.
        """
        return True
