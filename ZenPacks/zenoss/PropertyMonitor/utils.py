

import logging
LOG = logging.getLogger('ZenPacks.zenoss.PropertyMonitor.utils')


def add_local_lib_path():
    '''
    Helper to add the ZenPack's lib directory to sys.path.
    '''
    import os
    import site

    site.addsitedir(os.path.join(os.path.dirname(__file__), 'lib'))

add_local_lib_path()


def get_all_subclasses(class_):
	subclasses = []

	for subclass in class_.__subclasses__():
		subclasses.append(subclass)
		subclasses.extend(get_all_subclasses(subclass))

	return subclasses