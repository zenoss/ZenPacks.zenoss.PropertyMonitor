##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""ZenPacks.zenoss.PropertyMonitor

This module contains initialization code for the ZenPack. Everything in
the module scope will be executed at startup by all Zenoss Python
processes.

The initialization order for ZenPacks is defined by
$ZENHOME/ZenPacks/easy-install.pth.

"""

import logging
LOG = logging.getLogger('zen.PropertyMonitor')

from . import zenpacklib

CFG = zenpacklib.ZenPackSpec(
    name=__name__,
    zProperties={
        'DEFAULTS': {'category': 'Property Monitor'},
        'zPropertyMonitorInterval': {'type': 'int', 'default': 300},
    },

    classes={},
    class_relationships={}
)

CFG.create()
