import pprint
import os
import sgtk
from sgtk.platform.qt import QtCore, QtGui
from datetime import datetime, timedelta
from time import sleep

HookBaseClass = sgtk.get_hook_baseclass()

class PostPhaseHook(HookBaseClass):
    """
    This hook defines methods that are executed after each phase of a publish:
    validation, publish, and finalization. Each method receives the publish
    tree instance being used by the publisher, giving full control to further
    curate the publish tree including the publish items and the tasks attached
    to them. See the :class:`PublishTree` documentation for additional details
    on how to traverse the tree and manipulate it.
    """
    
    def post_publish(self, publish_tree):

        # collect all dispatchers and process them all
        for item  in publish_tree:
            task = item.parent.properties['upstream_scalar']
            if task:
                dispatcher = getattr(task, "dispatcher")

                dispatcher.name = item.parent.properties['publish_name'].split("-")[0] + " Publish"

                # process the task trees within this dispatcher
                result = dispatcher.process()
                self.logger.info('Submitting Scalar Tasks all at once...')
                self.logger.info(str(result))
                break