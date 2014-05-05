



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
    zProperties={},
    classes={},
    class_relationships={}
)

CFG.create()