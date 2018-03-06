#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
 File Name: vnet_driver_xen.py
 Author: longhui
 Created Time: 2018-03-05 14:06:59
 Descriptions:
 host_metrics    PIF_metrics               VIF_metrics    VM_metrics
      |              |                           |            |
     host <-----    PIF    ----->network<-----  VIF----->    VM
'''

import time
from lib.Log.log import log
from lib.Val.vnet_driver import VnetDriver
from lib.Val.Xen import XenAPI

API_VERSION_1_1 = '1.1'


class XenVnetDriver(VnetDriver):
    '''
    '''

    def __init__(self, hostname=None, user="root", passwd=""):
        VnetDriver.__init__(self, hostname, user, passwd)
        self._hypervisor_handler = None

        self._hypervisor_handler = self.get_handler()

    def __del__(self):
        try:
            if self._hypervisor_handler is not None:
                self._hypervisor_handler.xenapi.session.logout()
                self._hypervisor_handler = None
        except Exception, error:
            log.debug(error)

    def get_handler(self):
        '''
        return the handler of the virt_driver
        '''
        if self._hypervisor_handler is not None:
            return self._hypervisor_handler

        if self.hostname is None:
            self._hypervisor_handler = XenAPI.xapi_local()  #no __nonzero__, can not use if/not for bool test
        else:
            log.debug("connecting to %s with user:%s,passwd:%s", "http://" + str(self.hostname), self.user, self.passwd)
            self._hypervisor_handler = XenAPI.Session("http://" + str(self.hostname))
        try:
            self._hypervisor_handler.xenapi.login_with_password(self.user, self.passwd, API_VERSION_1_1, 'XenVirtDriver')
        except Exception, error:
            log.exception("Exception raised:%s when get handler.", error)
            return None

        return self._hypervisor_handler

    def delete_handler(self):
        '''
        release the session
        '''
        try:
            if self._hypervisor_handler is not None:
                self._hypervisor_handler.xenapi.session.logout()
                self._hypervisor_handler = None
        except Exception, error:
            log.debug(error)

    def get_vswitch_list(self):
        """
        """
        pass

    def get_PIF_by_device(self, device_name):
        """
        @param device_name: interface name in Host, eg, eth0,etc
        """
        if self._hypervisor_handler is None:
            self._hypervisor_handler = self.get_handler()

        all_pifs = self._hypervisor_handler.xenapi.PIF.get_all()
        for pif in all_pifs:
            if device_name == self._hypervisor_handler.xenapi.PIF.get_device(pif):
                return pif
        log.error("No PIF found corresponding with device name [%s].", device_name)
        return None

    def get_all_devices(self):
        """
        @return: return a dict with key is the interface name and value is PIF_ref
        """
        if self._hypervisor_handler is None:
            self._hypervisor_handler = self.get_handler()
        try:
            all_pifs = self._hypervisor_handler.xenapi.PIF.get_all()
            return [self._hypervisor_handler.xenapi.PIF.get_device(pif) for pif in all_pifs]
        except Exception, error:
            log.exception(error)
            return []

    def get_device_infor(self, pif_ref=None, device_name=None):
        """
        @param pif_ref: reference to a PIF object
        @param device_name: name of interface in host
        @return: return a dict with key: DNS,IP,MTU,MAC,netmask,gateway,network, etc.
        """
        if self._hypervisor_handler is None:
            self._hypervisor_handler = self.get_handler()

        if pif_ref is not None:
            return self._hypervisor_handler.xenapi.PIF.get_record(pif_ref)
        elif device_name is not None:
            pif_ref = self.get_PIF_by_device(device_name)
            if not pif_ref:
                log.error("Can not get device infor with given device name:%s.", device_name)
                return {}
            return self._hypervisor_handler.xenapi.PIF.get_record(pif_ref)
        else:
            log.error("Please specify a device name to get device infor.")
            return {}

    def get_network_by_PIF(self, pif_ref):
        """
        @param pif_ref:
        @return: a reference to network
        """
        if self._hypervisor_handler is None:
            self._hypervisor_handler = self.get_handler()

        all_pifs = self._hypervisor_handler.xenapi.PIF.get_all()
        if pif_ref not in all_pifs:
            log.error("Invalid reference to PIF: %s", pif_ref)
            return None

        return self._hypervisor_handler.xenapi.PIF.get_network(pif_ref)

    def create_new_vif(self, vm_ref, network_ref, device_index):
        """
        @param vm_ref: reference to the guest VM
        @param network_ref: reference to the network
        @param device_index: index of interface in guest VM
        """
        record = {'MAC': '',
                 'MAC_autogenerated': True,
                 'MTU': '0',
                 'other_config': {},
                 'qos_algorithm_params': {},
                 'qos_algorithm_type': ''}
        record['VM'] = vm_ref
        record['network'] = network_ref
        record['device'] = str(device_index)
        log.debug("create new vif with record:%s", str(record))
        handler = self.get_handler()
        new_vif = handler.xenapi.VIF.create(record)
        return new_vif

    def attach_vif_to_vm(self, vif_ref):
        """
        Hotplug the specified VIF, dynamically attaching it to the running VM
        @param vif_ref: virtual interface reference
        """
        if self._hypervisor_handler is None:
            self._hypervisor_handler = self.get_handler()

        vm_ref = self._hypervisor_handler.xenapi.VIF.get_VM(vif_ref)
        if self._hypervisor_handler.xenapi.VM.get_record(vm_ref)['power_state'] != 'Running':
            log.error("Only a running VM supports hot-plug a VIF.")
            return False

        try:
            self._hypervisor_handler.xenapi.VIF.plug(vif_ref)
        except Exception, error:
            log.error("Only a running VM supports hot-plug a VIF:%s.", error)
            return False
        return True

    def detach_vif_from_vm(self, vif_ref):
        """
        Hot-unplug the specified VIF, dynamically unattaching it from the running VM
        @param vif_ref: virtual interface reference
        @note It should check the power_state before use this API
        """
        if self._hypervisor_handler is None:
            self._hypervisor_handler = self.get_handler()

        vm_ref = self._hypervisor_handler.xenapi.VIF.get_VM(vif_ref)
        if self._hypervisor_handler.xenapi.VM.get_record(vm_ref)['power_state'] != 'Running':
            log.error("Only a running VM supports hot-unplug a VIF.")
            return False
        try:
            self._hypervisor_handler.xenapi.VIF.unplug(vif_ref)
        except Exception, error:
            log.exception("Only a running VM supports hot-unplug a VIF:%s", error)
            return False
        return True

