#
# -*- coding: utf-8 -*-
# Copyright 2021 UPONU GmbH
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
The nxos spanning_tree class
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.cfg.base import (
    ConfigBase,
)
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.utils import (
    dict_diff,
    to_list,
)
from ansible_collections.cisco.nxos.plugins.module_utils.network.nxos.facts.facts import (
    Facts,
)
from ansible_collections.cisco.nxos.plugins.module_utils.network.nxos.utils.utils import (
    flatten_dict,
    search_obj_in_list,
)


class Spanning_tree(ConfigBase):
    """
    The nxos_spanning_tree class
    """

    gather_subset = ["min"]
    gather_network_resources = ["spanning_tree"]

    def __init__(self, module):
        super(Spanning_tree, self).__init__(module)

    def get_spanning_tree_facts(self, data=None):
        """ Gets the 'facts' (the current configuration)

        :rtype: A dictionary
        :returns: The current configuration as a directory
        """
        if self.state not in self.ACTION_STATES:
            self.gather_subset = ["!all", "!min"]
        facts, _warnings = Facts(self._module).get_facts(
            self.gather_subset, self.gather_network_resources, data=data
        )

        spanning_tree_facts = facts["ansible_network_resources"].get(
            "spanning_tree", []
        )

        platform = facts.get("ansible_net_platform", "")
        return spanning_tree_facts, platform

    def edit_config(self, commands):
        return self._connection.edit_config(commands)

    def execute_module(self):
        """ Execute the module

        :rtype: A dictionary
        :returns: The result form module execution
        """
        result = {"changed": False}
        warnings = list()
        commands = list()

        if self.state in self.ACTION_STATES:
            existing_spanning_tree_facts, platform = (
                self.get_spanning_tree_facts()
            )
        else:
            existing_spanning_tree_facts, platform = [], ""

        if self.state in self.ACTION_STATES or self.state == "rendered":
            commands.extend(
                self.set_config(existing_spanning_tree_facts, platform)
            )

        if commands and self.state in self.ACTION_STATES:
            if not self._module.check_mode:
                self.edit_config(commands)
            result["changed"] = True

        if self.state in self.ACTION_STATES:
            result["commands"] = commands

        if self.state in self.ACTION_STATES or self.state == "gathered":
            changed_spanning_tree_facts, platform = (
                self.get_spanning_tree_facts()
            )

        elif self.state == "rendered":
            result["rendered"] = commands

        elif self.state == "parsed":
            running_config = self._module.params["running_config"]
            if not running_config:
                self._module.fail_json(
                    msg="value of running_config parameter must not be empty for state parsed"
                )
            result["parsed"], platform = self.get_spanning_tree_facts(
                data=running_config
            )

        if self.state in self.ACTION_STATES:
            result["before"] = existing_spanning_tree_facts
            if result["changed"]:
                result["after"] = changed_spanning_tree_facts

        elif self.state == "gathered":
            result["gathered"] = changed_spanning_tree_facts

        result["warnings"] = warnings
        return result

    def set_config(self, existing_spanning_tree_facts, platform):
        """ Collect the configuration from the args passed to the module,
            collect the current configuration (as a dict from facts)

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration
        """
        want = self._module.params["config"]
        have = existing_spanning_tree_facts
        resp = self.set_state(want, have)
        return to_list(resp)

    def set_state(self, want, have):
        """ Select the appropriate function based on the state provided

        :param want: the desired configuration as a dictionary
        :param have: the current configuration as a dictionary
        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration
        """
        state = self._module.params["state"]
        if (
            state in ("overridden", "merged", "replaced", "rendered")
            and not want
        ):
            self._module.fail_json(
                msg="value of config parameter must not be empty for state {0}".format(
                    state
                )
            )

        cmds = list()
        if state == "overridden":
            cmds.extend(self._state_overridden(want, have))
        elif state == "deleted":
            cmds.extend(self._state_deleted(want, have))
        else:
            for w in want:
                if state in ["merged", "rendered"]:
                    cmds.extend(self._state_merged(flatten_dict(w), have))
                elif state == "replaced":
                    cmds.extend(self._state_replaced(flatten_dict(w), have))
        return cmds

    def _state_replaced(self, want, have):
        """ The command generator when state is replaced

        :rtype: A list
        :returns: the commands necessary to migrate the current configuration
                  to the desired configuration
        """
        cmds = []
        obj_in_have = search_obj_in_list(want["name"], have, "name")
        if obj_in_have:
            diff = dict_diff(want, obj_in_have)
        else:
            diff = want
        merged_cmds = self.set_commands(want, have)
        if "name" not in diff:
            diff["name"] = want["name"]

        replaced_cmds = []
        if obj_in_have:
            replaced_cmds = self.del_attribs(diff)
        if replaced_cmds or merged_cmds:
            for cmd in set(replaced_cmds).intersection(set(merged_cmds)):
                merged_cmds.remove(cmd)
            cmds.extend(replaced_cmds)
            cmds.extend(merged_cmds)
        return cmds
