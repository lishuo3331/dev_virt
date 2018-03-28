#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
 File Name: server_utils.py
 Author: longhui
 Created Time: 2018-03-13 18:41:44
 Descriptions: API to get information about the Server/Host
'''
from lib.Log.log import log
from lib.Val.virt_factory import VirtFactory
from lib.Db.db_factory import DbFactory
from lib.Utils.network_utils import IpCheck, is_IP_pingable


class ServerDomain(object):

    def __init__(self, host_name=None, user="root", passwd=""):
        self.virt_driver = VirtFactory.get_virt_driver(host_name, user, passwd)
        self.vnet_driver = VirtFactory.get_vnet_driver(host_name, user, passwd)
        self.db_driver = DbFactory.get_db_driver("Host")

    def __nonzero__(self):
        if self.virt_driver and self.vnet_driver:
            return True
        else:
            return False

    @property
    def server_name(self):
        """
        The name label of the server, in Xen server, it is same as the name in Xen center.
        if the Hypervisor is KVM, return hostname
        :return:
        """
        name_info = self.virt_driver.get_host_name()
        return name_info[0]

    def print_server_hardware_info(self):
        """
        Display server hardware and platform info
        """
        log.info("General hardware and software information:")

        log.info("\nHost Manufacturer informations:")
        platform_info = self.virt_driver.get_host_plat_info()
        log.info("\tManufacturer: %s", platform_info.get('vendor_name'))
        log.info("\tModel: %s", platform_info.get('product_name'))
        log.info("\tSerial Number: %s", platform_info.get('serial_number'))
        log.info("\tSoftware Version: %s", self.virt_driver.get_host_sw_ver(short_name=False))

        log.info("\nHost CPU informations:")
        cpu_info = self.virt_driver.get_host_cpu_info()
        log.info("\tProcessor Model: %s", cpu_info.get("cpu_model"))
        log.info("\tProcessor Sockets: %s", cpu_info.get("cpu_sockets", 0))
        log.info("\tCores per Socket: %s", cpu_info.get("cores_per_socket", 0))
        log.info("\tThreads per Core: %s", cpu_info.get("thread_per_core", 1))
        log.info("\tLogical Processors: %s", cpu_info.get("cpu_cores"))
        log.info("\tProcessor Speed: %s MHz", cpu_info.get("cpu_speed"))

        log.info("\nHost Memory informations:")
        memory_info = self.virt_driver.get_host_mem_info()
        log.info("\tMemory total: %s GB", memory_info.get("size_total"))
        log.info("\tMemory used: %s GB", memory_info.get("size_used"))
        log.info("\tMemory free: %s GB", memory_info.get("size_free"))

        log.info("\nHost Default Storage informations:")
        storage_info = self.virt_driver.get_host_storage_info()
        log.info("\tStorage Size: %s GB", storage_info.get('size_total', 0))
        log.info("\tStorage Used: %s GB", storage_info.get('size_used', 0))
        log.info("\tStorage Free: %s GB", storage_info.get('size_free', 0))

    def get_host_all_storage_info(self):
        """
        :return:
        """
        storage_info = {}
        sr_list = self.virt_driver.get_host_all_storages()
        for sr in sr_list:
            size = self.virt_driver.get_host_storage_info(storage_name=sr)
            storage_info.setdefault(sr, [size['size_total'], size['size_free']])

        return storage_info

    def get_default_device(self):
        """
        get the host's default network/Interface which has configured an IP;
        :return: Interface name on host, or None
        """
        log.info("Get the host default network with IP configured.")

        devices = self.vnet_driver.get_all_devices()
        for device_name in devices:
            # 'IP': '' or an ip,
            device_info = self.vnet_driver.get_device_infor(device_name=device_name)
            ipstr = device_info.get('IP', '')
            if ipstr:
                return device_name
        else:
            log.error("No device found with an IP configured.")
            return None

    def get_default_storage(self):
        """
        get the default storage repository which has the largest volume for user
        :return: the storage name
        """
        log.info("Get the host default storage name which has the largest free volume.")

        all_sr = self.virt_driver.get_host_all_storages()
        max_volume, target_sr = 0, None
        for sr in all_sr:
            storage_dict = self.virt_driver.get_host_storage_info(storage_name=sr)
            temp = int(storage_dict.get('size_free', 0))
            if temp > max_volume:
                max_volume, target_sr = temp, sr

        log.info("The default storage is '%s' with volume %s GB.", target_sr, max_volume)
        return target_sr

    def check_ip_used(self, ip):
        """
        check the ip from database
        :param ip:
        :return:
        """
        query_data = self.db_driver.query()
        ip_list = [d["first_ip"] for d in query_data]
        ip_list.extend([d['second_ip'] for d in query_data])

        if ip in ip_list:
            return True
        else:
            return False

    def is_IP_available(self, vif_ip=None, vif_netmask=None, device=None):
        """
        check if a IP and Netmask usable
        """
        # No ip , don't need to check
        if not vif_ip:
            return True

        dest_metmask = ""
        dest_gateway = None
        if device is not None:
            try:
                # host_name = kwargs['host']
                # user = kwargs['user'] if kwargs['user'] else "root"
                # passwd = str(kwargs['passwd']).replace('\\', '') if kwargs['passwd'] else ""
                # vnet_driver = VirtFactory.get_vnet_driver(host_name, user, passwd)

                device_info = self.vnet_driver.get_device_infor(device_name=device)
                dest_metmask = device_info["netmask"]
                dest_gateway = device_info['gateway']
            except KeyError, error:
                log.exception(str(error))

        if vif_netmask:
            if dest_metmask and dest_metmask != vif_netmask:
                log.error("Netmask [%s] is not corresponding with the target network.", vif_netmask)
                return False
        else:  # get the netmask on device as the default one
            vif_netmask = dest_metmask
        log.debug("VIF IP is: %s, netmask is: %s", vif_ip, vif_netmask)
        if not vif_netmask:  # No default netmask and no given
            log.error("No netmask given, please specify one.")
            return False

        vif_gateway = dest_gateway if dest_gateway else None
        if not IpCheck.is_valid_ipv4_parameter(vif_ip, vif_netmask, gateway=vif_gateway):
            return False

        if is_IP_pingable(vif_ip):
            log.error("Ipaddress [%s] is already be used(Ping test).", vif_ip)
            return False

        if self.check_ip_used(vif_ip):
            log.error("Ip address [%s] already in used.(Check from database).", vif_ip)
            return False

        return True

    def create_database_info(self):
        """
        :return:
        """
        log.info("Start to create [%s] information to databse.", self.server_name)

        hostname = self.server_name
        if self.db_driver.query(hostname=hostname):
            log.info("The hostname [%s] has exist in database.", hostname)
            return True

        cpu_cores = self.virt_driver.get_host_cpu_info().get('cpu_cores')
        sn = self.virt_driver.get_host_plat_info().get('serial_number')
        memory_size = self.virt_driver.get_host_mem_info().get('size_total')

        disk_num = len(filter(lambda x: int(x[0]) > 10, self.get_host_all_storage_info().values()))
        default_storage = self.virt_driver.get_host_storage_info()  # only write the system disk size
        disk_size = default_storage.get('size_total')

        first_ip = self.vnet_driver.get_host_manage_interface_infor().get('IP')

        ret = self.db_driver.create(hostname=hostname, sn=sn, cpu_cores=cpu_cores, memory_size=int(memory_size),
                                    disk_size=int(disk_size), disk_num=disk_num, first_ip=first_ip)
        if ret:
            log.info("Create server [%s] record to database successfully.", hostname)
        else:
            log.error("Create server [%s] record to database failed.", hostname)

        return ret

    def delete_database_info(self):
        """
        delete from database with this server
        :return:
        """
        log.info("Start to delete [%s] information from database.", self.server_name)

        return self.db_driver.delete(hostname=self.server_name)

    def update_database_info(self):
        """
        This function is used to sync server information, include:cpu_cores, memory_size, disk_num
        :return:
        """
        server_name = self.server_name
        log.info("Start to update [%s] information to databse.", server_name)

        sn = self.virt_driver.get_host_plat_info().get('serial_number')
        if not self.db_driver.query(sn=sn, hostname=server_name):
            log.info("No record found with server name [%s], don't update.", server_name)
            return True

        cpu_cores = self.virt_driver.get_host_cpu_info().get('cpu_cores')
        memory_size = self.virt_driver.get_host_mem_info().get('size_total')

        disk_num = len(filter(lambda x: int(x[0]) > 10, self.get_host_all_storage_info().values()))
        default_storage = self.virt_driver.get_host_storage_info()  # only write the system disk size
        disk_size = default_storage.get('size_total')

        first_ip = self.vnet_driver.get_host_manage_interface_infor().get('IP')
        sync_data = {"cpu_cores": cpu_cores,
                     "memory_size": int(memory_size),
                     "disk_num": int(disk_num),
                     "disk_size": int(disk_size),
                     "first_ip": first_ip
                     }
        try:
            ret = self.db_driver.update(sn=sn, hostname=server_name, data=sync_data)
        except Exception as error:
            log.exception("Exception raise when update vm database: %s", error)
            ret = False
        if not ret:
            log.warn("Update database information with ret: [%s], data: %s", ret, sync_data)

        return ret


if __name__ == "__main__":
    host = ServerDomain(host_name="10.143.248.16", user="root", passwd="Mojiti!906")
    storage =host.get_host_all_storage_info()
    for k, v in storage.iteritems():
        print k, "\t\t", v

    print host.virt_driver.get_host_all_storages()

    print host.get_default_storage()

    print host.get_default_device()
    print host.print_server_hardware_info()
    print host.check_ip_used("192.168.1.100")
    print host.create_database_info()
    print host.update_database_info()
    print host.delete_database_info()
