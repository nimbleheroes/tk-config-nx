"""
Hook which chooses an environment file to use based on the current context.
"""
import os
from tank import Hook


class PickEnvironment(Hook):
    def execute(self, context, **kwargs):
        """
        The default implementation assumes there are three environments, called shot, asset
        and project, and switches to these based on entity type.
        """

        env = None

        self.logger.debug("context dict: {}".format(context.to_dict()))

        if context.source_entity:
            if context.source_entity["type"] == "Version":
                env = "version"
                self.logger.debug("environment returned: {}".format(env))
                return env
            elif context.source_entity["type"] == "PublishedFile":
                env = "published_file"
                self.logger.debug("environment returned: {}".format(env))
                return env

        if context.project is None:
            # Our context is completely empty. We're going into the site context.
            if os.getenv('NX_ONSITE'):
                # we're accessing SG from an 'onsite' machine
                env = "onsite"
            else:
                # we're accessing SG from 'offsite'
                env = "offsite"
            self.logger.debug("environment returned: {}".format(env))
            return env

        if context.entity is None:
            # We have a project but not an entity.
            env = "project"
            self.logger.debug("environment returned: {}".format(env))
            return env

        if context.entity and context.step is None:
            # We have an entity but no step.
            if context.entity["type"] == "Shot":
                env = "shot"
                self.logger.debug("environment returned: {}".format(env))
                return env
            if context.entity["type"] == "Asset":
                env = "asset"
                self.logger.debug("environment returned: {}".format(env))
                return env
            if context.entity["type"] == "Sequence":
                env = "sequence"
                self.logger.debug("environment returned: {}".format(env))
                return env

        if context.entity and context.step:
            # We have a step and an entity.
            if context.entity["type"] == "Project":
                env = "project_step"
                self.logger.debug("environment returned: {}".format(env))
                return env
            if context.entity["type"] == "Shot":
                env = "shot_step"
                self.logger.debug("environment returned: {}".format(env))
                return env
            if context.entity["type"] == "Asset":
                env = "asset_step"
                self.logger.debug("environment returned: {}".format(env))
                return env
            if context.entity["type"] == "Sequence":
                env = "sequence_step"
                self.logger.debug("environment returned: {}".format(env))
                return env

