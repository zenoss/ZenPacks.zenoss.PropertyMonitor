##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
API interfaces and default implementations.
'''

import zope.schema
from zope.interface import implements, providedBy

from Products.ZenUtils.Ext import DirectRouter, DirectResponse

from Products import Zuul
from Products.Zuul.facades import ZuulFacade
from Products.Zuul.interfaces import IFacade, IInfo
from Products.Zuul.form.builder import FormBuilder
from Products.ZenModel.DeviceComponent import DeviceComponent
from Products.ZenModel.Device import Device
from .utils import get_all_subclasses


class IPropertyMonitorFacade(IFacade):
    '''
    Python API interface.
    '''

    def getClasses(self, datasourceId=None):
        '''
        Return list of dictionaries of all component classes.
        '''

    def getProperties(self, class_name, datasourceId=None):
        '''
        Return list of dictionaries for all properties in class_name.
        '''


class PropertyMonitorFacade(ZuulFacade):
    '''
    Python API implementation.
    '''

    implements(IPropertyMonitorFacade)

    def getClasses(self, datasourceId=None):
        classes = get_all_subclasses(DeviceComponent) + \
                  get_all_subclasses(Device)

        classnames = [c.meta_type for c in classes if hasattr(c, 'meta_type')]

        return [{'key': c, 'label': c} for c in sorted(set(classnames))]

    def getProperties(self, class_name, datasourceId=None):
        numericTypes = set(['float', 'int', 'long'])
        numericXtypes = set(['numberfield'])

        # Find the class, based on the specified meta_type.
        classes = get_all_subclasses(DeviceComponent) + \
                  get_all_subclasses(Device)
        for c in classes:
            if hasattr(c, 'meta_type') and c.meta_type == class_name:
                obj = c('dummy')
                info = IInfo(obj)

                # We are attempting to show only the numeric fields.  Unfortunately,
                # this is not exactly trivial.   There are two things we can do, however.
                # (note that if we do get it wrong, the impact is minor- this is more
                # about providing a convenient dropdown than about security or anything)

                # 1)  Any fields identified as numeric in the info interface (that is,
                #     from the 'Details' pane in the UI)
                numberfields = set()

                for iface in providedBy(info):
                    f = zope.schema.getFields(iface)
                    numberfields.update(
                        k for k, v in f.iteritems()
                        if getattr(v, 'xtype', None) in numericXtypes)


                # 2) This is fuzzier, but we also include any fields not exposed through the
                #    details pane, but which are still in the info adaptor, and which match
                #    up (name-wise) with known-numeric properties of the object.
                #    This is needed because of the common pattern of exposing via
                #    the UI only a string version of a numeric value, due to
                #    units conversion.
                for field in dir(info):
                    # aha.  A numeric one.  Add it.
                    if obj.getPropertyType(field) in numericTypes:
                        numberfields.add(field)

                return [{'key': x, 'label': x} for x in sorted(numberfields)]
                break

        # Unrecognized meta_type.  No properties for you.
        return []


class PropertyMonitorRouter(DirectRouter):
    '''
    ExtJS DirectRouter API implementation.
    '''

    def _getFacade(self):
        return Zuul.getFacade('propertymonitor', self.context)

    def _getDatasourceId(self, query):
        return query.split('=')[1] if query else None

    def getClasses(self, query):
        """
        @param query: Should contain 'record=' the uid of the applicable datasource
        @returns all of the defined classes, grouped in the form
        {
            'data': [{'key':key, 'label':label}, ...],
            'success': True
        }
        """
        data = self._getFacade().getClasses(
            self._getDatasourceId(query))

        return DirectResponse(success=True, data=data)

    def getProperties(self, query, class_name):
        """
        @param query: Should contain 'record=' the uid of the applicable datasource
        @param class_name: must be a class from getClasses method
        @returns full names all of the properties from this class
        {
            'data': [{'key':key, 'label':label}, ...],
            'success': True
        }
        """
        data = self._getFacade().getProperties(
            class_name, self._getDatasourceId(query))

        return DirectResponse(success=True, data=data)
