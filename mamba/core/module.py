# -*- test-case-name: mamba.core.test.test_module -*-
# Copyright (c) 2012 Oscar Campos <oscar.campos@member.fsf.org>
# Ses LICENSE for more details

"""
Module base class
"""

import re
from collections import OrderedDict

from zope.interface import implements
from twisted.internet import inotify
from twisted.python._inotify import INotifyError
from twisted.python import filepath

from mamba.core import inotifier
from mamba.utils import filevariables



class ModuleError(Exception):
    """ModuleError Exception"""

    pass


class ModuleManager(object):
    """
    Every module manager class inherits from me
    """
    implements(inotifier.INotifier)

    def __init__(self):
        # Initialize the ExtensionLoader parent object
        super(ModuleManager, self).__init__()

        self._modules = OrderedDict()

        # Create and setup the Linux iNotify mechanism
        self.notifier = inotify.INotify()
        self.notifier.startReading()
        try:
            self.notifier.watch(
                filepath.FilePath(self._module_store),
                callbacks=[self._notify]
            )
            self._watching = True
        except INotifyError:
            self._watching = False

        # Start the loading process
        self.setup()

    def setup(self):
        """
        Setup the loader and load the Mamba plugins
        """

        try:
            files = filepath.listdir(self._module_store)
            pattern = re.compile('[^_?]\.py$', re.IGNORECASE)
            for file in filter(pattern.search, files):
                if self.is_valid_file(file):
                    self.load(file)
        except OSError:
            pass

    def load(self, filename):
        """
        Loads a Mamba module
        """

        module_name = filepath.splitext(filepath.basename(filename))[0]
        module_path = '%s.%s' % (self._module_store, module_name)
        if module_name in self._modules:
            self._reload(module_name)

        objs = [module_name]
        temp_module = __import__(module_path, globals(), locals(), objs)
        # instance the object
        temp_object = getattr(temp_module, objs[0])()
        temp_object.loaded = True

        self._modules.update({
            module_name: {
                'object': temp_object,
                'module': temp_module,
                'module_path': module_path
            }
        })

    def reload(self, module):
        """
        Reload a controller module
        """

        temp_object = self.lookup(module)
        if not temp_object or not temp_object.get('object').loaded:
            raise ModuleError('Tried to reload %s that is not yet loaded' %
                module
            )

        reload(temp_object.get('module'))
        del self._controllers[module]['object']
        self._controllers[module]['object'] = getattr(
            temp_object.get('module'), temp_object.get('module_path'))()

    def lookup(self, module):
        """
        Find and return a controller from the pool
        """

        return self._modules.get(module, dict())

    def lenght(self):
        """
        Returns the controller pool length
        """

        return len(self._modules)

    def _notify(self, wd, file_path, mask):
        """
        Notifies the changes on resources file_path
        """

        if mask is inotify.IN_MODIFY:
            if not self.is_valid_file(file_path):
                return

            module = filepath.splitext(file_path.basename())[0]
            if module in self._modules:
                self.reload(module)

        if mask is inotify.IN_CREATE:
            if file_path.exists():
                if self.is_valid_file(file_path):
                    self.load(file_path)

    def __valid_file(self, file_path, file_type):
        """
        Check if a file is a valid Mamba file
        """

        basename = filepath.basename(file_path)
        if filepath.splitext(basename)[1] == self._extension:
            fv = filevariables.FileVariables(file_path)
            if fv.get_value('mamba-file-type') == file_type:
                return True

        return False


__all__ = [
    'ModuleError', 'ModuleManager'
]
