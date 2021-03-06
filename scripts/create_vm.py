#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
 File Name: create_vm.py
 Author: longhui
 Created Time: 2018-03-01 13:20:26
'''
from optparse import OptionParser
from lib.Log.log import log
from lib.Utils.vm_utils import VirtHostDomain


if __name__ == "__main__":
    usage = """usage: %prog [options] arg1 arg2\n
        create_vm.py -c new_vm_name -t template
        create_vm.py -c new_vm_name -t template [--memory=size --cpu-max=cores] [--host=ip --user=user --pwd=passwd]
        create_vm.py -c new_vm_name -t template [--vif=vif_index --ip=ip [--device=eth0]] [--host=ip --user=user --pwd=passwd]
        create_vm.py --list-vm       [--host=ip --user=user --pwd=passwd]
        create_vm.py --list-templ    [--host=ip --user=user --pwd=passwd]
        create_vm.py --list-network  [--host=ip --user=user --pwd=passwd]
        create_vm.py --list-SR       [--host=ip --user=user --pwd=passwd]
        """
    parser = OptionParser(usage=usage)
    parser.add_option("--host", dest="host", help="IP for host server")
    parser.add_option("-u", "--user", dest="user", help="User name for host server")
    parser.add_option("-p", "--pwd", dest="passwd", help="Password for host server")

    parser.add_option("-c", "--create", dest="vm_name",
                      help="Create a new VM with a template.")
    parser.add_option("-t", "--templ", dest="template",
                      help="Template used to create a new VM.")

    parser.add_option("--memory", dest="memory_size", help="Config the target memory size in GB.")
    parser.add_option("--min-mem", dest="min_memory", help="Config the min static memory size in GB.")
    parser.add_option("--max-mem", dest="max_memory", help="Config the max static memory size in GB.")
    parser.add_option("--cpu-max", dest="max_cores", help="Config the max VCPU cores.")

    parser.add_option("--vif", dest="vif_index", help="Configure on a virtual interface device")
    parser.add_option("--device", dest="device",
                      help="The target physic NIC name with an associated network vif attach(ed) to")
    parser.add_option("--network", dest="network",
                      help="The target network(in xen, it is same as bridge) which vif connect(ed) to")
    parser.add_option("--bridge", dest="bridge", help="The target bridge which vif connect(ed) to")

    parser.add_option("--ip", dest="vif_ip", help="The ip assigned to the virtual interface")
    parser.add_option("--netmask", dest="vif_netmask", help="The netmask for the target virtual interface")

    parser.add_option("--add-disk", dest="disk_size", help="The disk size(GB) add to the VM")
    parser.add_option("--storage", dest="storage_name", help="The storage location where the virtual disk put")

    parser.add_option("--list-vm", dest="list_vm", action="store_true",
                      help="List all the vms in server.")
    parser.add_option("--list-templ", dest="list_templ", action="store_true",
                      help="List all the templates in the server.")
    parser.add_option("--list-network", dest="list_network", action="store_true",
                      help="List the network in the host(in Xenserver, it is same as bridge)")
    parser.add_option("--list-bridge", dest="list_bridge", action="store_true",
                      help="List the bridge/switch names in the host")
    parser.add_option("--list-SR", dest="list_sr", action="store_true",
                      help="List the storage repository infor in the host")

    (options, args) = parser.parse_args()
    log.debug("options:%s, args:%s", str(options), str(args))

    if options.host is not None and (options.user is None or options.passwd is None):
        log.fail("Please specify a user-name and passward for the given host:%s", options.host)
        exit(1)

    host_name = options.host
    user = options.user if options.user else "root"
    passwd = str(options.passwd).replace('\\', '') if options.passwd else ""

    virthost = VirtHostDomain(host_name, user, passwd)
    if not virthost:
        log.fail("Can not connect to virtual driver or DB driver, initial VirtHostDomain failed.")
        exit(1)

    vnet_driver = virthost.vnet_driver
    virt_driver = virthost.virt_driver

    if options.list_vm:
        all_vms = virthost.get_vm_list()
        if all_vms:
            log.info(str(sorted(all_vms)))
        else:
            log.info("No VMs.")

    elif options.list_templ:
        all_templs = virthost.get_templates_list()
        str_templ = "All templates are:\n" + "\n".join(sorted(all_templs))
        if all_templs:
            log.info(str_templ)
        else:
            log.info("No templates.")

    elif options.list_network:
        all_networks = virthost.get_network_list()
        if all_networks:
            log.info(str(sorted(all_networks)))
        else:
            log.info("No network found.")

    elif options.list_bridge:
        all_bridges = virthost.get_bridge_list()
        if all_bridges:
            log.info(str(sorted(all_bridges)))
        else:
            log.info("No bridges found.")
    elif options.list_sr:
        log.info("All SR information:")
        infor_formate = "%-20s\t%s"
        log.info(infor_formate, "Storage_name", "Free_size(GB)")
        storage = virthost.get_host_all_storage_info()
        for k, v in storage.iteritems():
            log.info(infor_formate, k, v[1])

    elif options.vm_name is not None:
        if options.template is None:
            log.fail("A template must be suppulied to create a new VM.")
            exit(1)
        new_vm_name, template_name = options.vm_name, options.template

        if virt_driver.is_instance_exists(new_vm_name):
            log.fail("There is already one VM named [%s]", new_vm_name)
            exit(1)
        if template_name not in virt_driver.get_templates_list():
            log.fail("No template named: %s", template_name)
            exit(1)

        # parse memory and vcpu config
        max_cores, memory_size, min_memory, max_memory = None, None, None, None
        try:
            if options.max_cores is not None:
                max_cores = int(options.max_cores)
            if options.memory_size is not None:
                memory_size = float(options.memory_size)
            if options.min_memory is not None:
                min_memory = float(options.min_memory)
            if options.max_memory is not None:
                max_memory = float(options.max_memory)
        except ValueError:
            log.fail("Please input a integer for cpu cores or a number for memory size.")
            exit(1)
        #  min_memory <= memory_size <= max_memory
        if memory_size and min_memory and memory_size < min_memory:
            log.fail("Invalid input memory params, memory size should be larger than min memory.")
            exit(1)
        if memory_size and max_memory and memory_size > max_memory:
            log.fail("Invalid input memory params, memory size should be smaller than max memory.")
            exit(1)
        if max_memory and min_memory and min_memory > max_memory:
            log.fail("Invalid input memory params, min_memory should be smaller than max memory.")
            exit(1)

        # parse ip config
        if options.vif_ip is not None:  # if an IP is specify, please specify a device, vif_index
            if not options.vif_index:
                log.fail("Please specify an VIF for configuring the IP.")
                exit(1)
            device_name = options.device
            if device_name is not None and device_name not in virthost.get_all_devices():
                log.fail("Invalid device name:[%s].", device_name)
                exit(1)
            network = options.network
            if network is not None and network not in virthost.get_network_list():
                log.fail("No network named: [%s].", network)
                exit(1)
            bridge = options.bridge
            if bridge is not None and bridge not in virthost.get_bridge_list():
                log.fail("No bridge named: [%s].", bridge)
                exit(1)

            if options.device is None and options.network is None and options.bridge is None:
                options.device = virthost.get_default_device()
                if not options.device:
                    log.fail("Failed to get default device. "
                             "Please specify a NIC or network for the new created virtual interface.")
                    exit(1)

            if not virthost.is_IP_available(options.vif_ip, vif_netmask=options.vif_netmask, device=options.device,
                                            network=options.network, bridge=options.bridge):
                log.fail("IP check failed.")
                exit(1)

        # parse disk config
        if options.disk_size is not None:
            if not options.storage_name:
                options.storage_name = virthost.get_max_free_size_storage()
                if not options.storage_name:
                    log.fail("Failed to get default SR, please specify a storage name for the new virtual disk.")
                    exit(1)
            try:
                size = int(options.disk_size)
            except ValueError:
                log.fail("Wrong input of disk size, please input a integer number.")
                exit(1)

            storage_info = virt_driver.get_host_storage_info(storage_name=options.storage_name)
            if not storage_info:
                log.fail("Fail to get infor about storage [%s]", options.storage_name)
                exit(1)
            if size >= storage_info['size_free'] - 1:
                log.fail("No enough volume on storage:[%s], at most [%s] GB is available",
                         options.storage_name, storage_info['size_free'] - 1)
                exit(1)

        # 1. create VM
        ret = virthost.create_vm(new_vm_name, template_name)
        if not ret:
            log.fail("Failed to create VM [%s].Exiting....", new_vm_name)
            exit(1)
        log.info("New instance [%s] created successfully.", new_vm_name)

        # 2. config cpu cores and memory
        ret = virthost.config_vcpus(new_vm_name, vcpu_max=max_cores)
        if not ret:
            log.warn("Config VCPU cores failed, keep same as before...")

        log.debug("memory_size:%s, min_memory:%s, max_memory:%s", memory_size, min_memory, max_memory)
        if max_memory:
            ret = virthost.config_max_memory(new_vm_name, static_max=max_memory)
            if not ret:
                log.warning("Configure max memory size failed, keep same as before...")
        if min_memory:
            ret = virthost.config_min_memory(new_vm_name, static_min=min_memory)
            if not ret:
                log.warn("Config min memory size failed, keep same as before...")
        if memory_size:
            ret = virthost.config_memory(new_vm_name, dynamic_min=memory_size, dynamic_max=memory_size)
            if not ret:
                log.warn("Config target memory size failed, keep same as before...")

        # 3. config VM IP
        if options.vif_ip is not None:
            config_ret = virthost.config_vif(new_vm_name, options.vif_index, options.device, options.network,
                                             options.bridge, options.vif_ip)
            if not config_ret:
                log.warn("Vif configure failed.")
            else:
                log.info("Successfully configured the virtual interface device [%s] to VM [%s].",
                         options.vif_index, new_vm_name)
        # 4. config VM disk
        if options.disk_size is not None:
            ret = virthost.add_vm_disk(new_vm_name, storage_name=options.storage_name, size=size)
            if ret:
                log.info("Successfully add a new disk with size [%s]GB to VM [%s].", size, new_vm_name)
            else:
                log.warn("Failed to add a new disk with size [%s]GB to VM [%s].", size, new_vm_name)

        # 5. power on VM
        ret = virthost.power_on_vm(new_vm_name)
        if ret:
            log.success("Create VM [%s] and power on successfully.", new_vm_name)
            exit(0)
        else:
            log.fail("VM [%s] created, but power on failed.", new_vm_name)
            exit(1)
    else:
        parser.print_help()
        exit(1)
