#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
 File Name: scripts/config_vm.py
 Author: longhui
 Created Time: 2018-03-07 09:38:18
'''

from optparse import OptionParser
import time
from lib.Log.log import log
from lib.Val.virt_factory import VirtFactory

if __name__ == "__main__":
    usage = """usage: %prog [options] vm_name\n

        config_vm.py vm_name --add-vif=vif_index --device=eth0  [--host=ip --user=user --pwd=passwd]
        config_vm.py vm_name --del-vif=vif_index   [--host=ip --user=user --pwd=passwd]
        config_vm.py vm_name --list-vif            [--host=ip --user=user --pwd=passwd]
        config_vm.py vm_name --list-pif            [--host=ip --user=user --pwd=passwd]
        """

    parser = OptionParser(usage=usage)
    parser.add_option("--host", dest="host", help="IP for host server")
    parser.add_option("-u", "--user", dest="user", help="User name for host server")
    parser.add_option("-p", "--pwd", dest="passwd", help="Passward for host server")

    parser.add_option("--add-vif", dest="vif_index", help="Add a virtual interface device to guest VM")
    parser.add_option("--del-vif", dest="del_index", help="Delete a virtual interface device from guest VM")
    parser.add_option("--device", dest="device", help="The target device which new vif will attach to")
    parser.add_option("--ip", dest="vif_ip", help="The ip assigned to the virtual interface")
    parser.add_option("--netmask", dest="vif_netmsk", help="The netmask for the target virtual interface")
    parser.add_option("--list-vif", dest="list_vif", action="store_true",
                      help="List the virtual interface device in guest VM")
    parser.add_option("--list-pif", dest="list_pif", action="store_true",
                      help="List the interface device in the host")

    (options, args) = parser.parse_args()
    log.debug("options:%s, args:%s", str(options), str(args))

    if options.host is not None and (options.user is None or options.passwd is None):
        log.fail("Please specify a user-name and passward for the given host:%s", options.host)
        exit(1)
    host_name = options.host
    user = options.user if options.user else "root"
    passwd = str(options.passwd).replace('\\', '') if options.passwd else ""

    if not args:
        log.error("Please specify a VM name to config.")
        parser.print_help()
        exit(1)
    if not options.list_vif  and not options.list_pif and \
        (not options.vif_index and not options.del_index):
        parser.print_help()
        exit(1)

    vnet_driver = VirtFactory.get_vnet_driver(host_name, user, passwd)
    inst_name = args[0]

    if options.list_vif:
        vif_list = vnet_driver.get_all_vifs_indexes(inst_name)
        if vif_list:
            log.success("All virtual interface device: %s", sorted(vif_list))
        else:
            log.fail("No virtual interface device found.")

    if options.list_pif:
        pif_list = vnet_driver.get_all_devices()
        if pif_list:
            log.success("All device on the host: %s", sorted(pif_list))
        else:
            log.fail("No device found on the host.")

    if options.vif_index is not None:
        vif_index = options.vif_index
        if options.device is None:
            log.fail("Please specify a device or bridge for the new created virtual interface.")
            exit(1)
        device_name = options.device
        log.info("Start to add a new virtual interface device with index:%s to VM [%s]", vif_index, inst_name)
        new_vif = vnet_driver.create_new_vif(inst_name, device_name, vif_index)
        if new_vif is not None:
            if VirtFactory.get_virt_driver(host_name, user, passwd).is_instance_running(inst_name):
                ret = vnet_driver.attach_vif_to_vm(inst_name, vif_index)
                if ret:
                    log.success("New virtual interface device [%s] attached to VM [%s] successfully.", vif_index, inst_name)
                    exit(0)
            else:
                log.success("New virtual interface device created successfully.")
                exit(0)

        log.fail("New virtual interface device created or attached failed.")
        exit(1)
    elif options.del_index is not None:
        vif_index = options.del_index
        log.info("Start to delete the interface device [%s] from VM [%s].", vif_index, inst_name)
        virt_driver = VirtFactory.get_virt_driver(host_name, user, passwd)
        if virt_driver.is_instance_running(inst_name):
            ret = vnet_driver.detach_vif_from_vm(inst_name, vif_index)
            if not ret:
                log.fail("Failed to unplug the virtual interface device [%s] from VM.", vif_index)
                exit(1)
        ret = vnet_driver.destroy_vif(inst_name, vif_index)
        if ret:
            log.success("Successfully delete the virtual interface device.")
            exit(0)
        else:
            log.fail("Failed to delete the virtual interface device")
            exit(1)