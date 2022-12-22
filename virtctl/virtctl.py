#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
import subprocess
import os
import ipaddress
import json
import yaml
from xml.etree import ElementTree
from pprint import pprint


IMAGE_PATH = "/opt/virtctl/images/"
DATA_PATH = "/opt/virtctl/datas/"
VM_NETWORK = "192.168.122.0/24"
VIRTCTL_USER = 'ubuntu'
VIRTCTL_PASSWD = 'ubuntu'
BASE_CLOUD_INIT = {
    'hostname': 'hoge',
    'user': VIRTCTL_USER,
    'password': VIRTCTL_PASSWD,
    'chpasswd': {'expire': False},
    'ssh_pwauth': True,
    }
BASE_CLOUD_INIT_NW = {
    'version': 2,
    'ethernets': {
        'eth0': {
            'dhcp4': 'false',
            'dhcp6': 'false',
            'addresses': [''],
            'gateway4': '',
            'nameservers': {
                'addresses': ['8.8.8.8', '8.8.4.4']
                }
            }
        }
    }


class VirtCtl:

    def __init__(self):
        pass

    def res_cmd(self, cmd, check=False):
        return subprocess.run(
            cmd, stdout=subprocess.PIPE,
            check=check, shell=True, text=True).stdout

    def res_cmd_lfeed(self, cmd, check=False):
        return subprocess.run(
            cmd, stdout=subprocess.PIPE,
            check=check, shell=True, text=True).stdout.split('\n')

    def yes_no_input(self):
        while True:
            if sys.version_info[0] == 3:
                choice = input("Please respond with 'yes' or 'no' [y/N]: ").lower()
            else:
                choice = raw_input("Please respond with 'yes' or 'no' [y/N]: ").lower()
            if choice in ['y', 'ye', 'yes']:
                return True
            elif choice in ['n', 'no']:
                return False

    def virtctl_init(self):
        os.makedirs(IMAGE_PATH, exist_ok=True)
        os.makedirs(DATA_PATH, exist_ok=True)

    def cmd_virsh_list(self):
        cmd = "virsh list --all"
        return self.res_cmd(cmd)

    def cmd_virsh_dumpxml(self, vm_name):
        cmd = "virsh dumpxml %s" % vm_name
        return self.res_cmd(cmd)

    def get_vm_list(self, ip=False):
        cmd = "virsh list --all"
        res_vms = self.res_cmd_lfeed(cmd)
        vms = [x.split()[1] for x in res_vms[2:] if x]
        states = [x.split()[2] for x in res_vms[2:] if x]
        if not vms:
            return {}
        ret_vms = {}
        for i, vm in enumerate(vms):
            ret_vms[vm] = {}
            ret_vms[vm]['status'] = states[i]
            net_list = self.get_net_list()
            for net in net_list:
                if net_list[net]['vm_name'] == vm:
                    if ip:
                        ret_vms[vm]['ip'] = net
        return ret_vms

    def get_vm_macaddr(self, vm_name):
        dumpxml = self.cmd_virsh_dumpxml(vm_name)
        vm_info = ElementTree.fromstring(dumpxml)
        return vm_info.find("devices/interface/mac").get("address")

    def read_ipam(self):
        try:
            with open("%sipam.json" % DATA_PATH, 'r') as f:
                res = json.load(f)
                return res if res else {}
        except:
            return {}

    def get_net_list(self):
        return self.read_ipam()

    def write_ipam(self, ipam):
        try:
            with open("%sipam.json" % DATA_PATH, 'w') as f:
                f.write(json.dumps(ipam))
            return True
        except:
            return False

    def get_ip_assign(self, vm_name):
        ipam = self.read_ipam()
        for ip in ipam:
            if vm_name == ipam[ip]["vm_name"]:
                return ip

    def ipam_ip_assign(self, vm_name, req_ip):
        ipam = self.read_ipam()
        if req_ip:
            if not ipaddress.ip_address(req_ip) in ipaddress.ip_network(VM_NETWORK):
                print("%s is out of range %s" % (req_ip, VM_NETWORK))
                exit(1)
            if req_ip in ipam:
                print("%s is already assigned!" % req_ip)
                exit(1)
            ipam[req_ip] = {}
            ipam[req_ip]["vm_name"] = vm_name
            self.write_ipam(ipam)
            return req_ip
        for ip in ipaddress.ip_network(VM_NETWORK):
            if ip in [ipaddress.ip_network(VM_NETWORK)[0],
                      ipaddress.ip_network(VM_NETWORK)[1],
                      ipaddress.ip_network(VM_NETWORK)[-1]]:
                continue
            if format(ip) in ipam:
                continue
            ipam[format(ip)] = {}
            ipam[format(ip)]["vm_name"] = vm_name
            break
        self.write_ipam(ipam)
        return ip

    def ipam_ip_unassign(self, vm_name):
        ipam = self.read_ipam()
        for ip in ipam:
            if vm_name == ipam[ip]["vm_name"]:
                ipam.pop(ip)
                break
        self.write_ipam(ipam)
        return ip

    def vm_dhcp_regist(self, vm_name):
        mac_addr = self.get_vm_macaddr(vm_name)
        ip_addr = self.get_ip_assign(vm_name)
        cmd = "virsh net-update default add ip-dhcp-host '<host mac=\"%(mac_addr)s\" name=\"%(vm_name)s\" ip=\"%(ip_addr)s\"/>' --live" % {'mac_addr': mac_addr, 'vm_name': vm_name, 'ip_addr': ip_addr}
        self.res_cmd(cmd)
        return ip_addr

    def vm_dhcp_unregist(self, vm_name):
        mac_addr = self.get_vm_macaddr(vm_name)
        ip_addr = self.get_ip_assign(vm_name)
        cmd = "virsh net-update default delete ip-dhcp-host '<host mac=\"%(mac_addr)s\" name=\"%(vm_name)s\" ip=\"%(ip_addr)s\"/>' --live" % {'mac_addr': mac_addr, 'vm_name': vm_name, 'ip_addr': ip_addr}
        self.res_cmd(cmd)
        return 

    def vm_exists(self, vm_name):
        vms = self.get_vm_list()
        if vm_name in vms:
            return True
        return False

    def vm_image_exists(self, vm_name):
        return os.path.exists("%s%s.qcow2" % (IMAGE_PATH, vm_name))

    def create_cloudinit_image(self, vm_name, ip_addr=''):
        cloud_config = BASE_CLOUD_INIT
        cloud_config['hostname'] = vm_name
        network_config = {}
        if ip_addr:
            network_config = BASE_CLOUD_INIT_NW

            ip_addr_with_cidr = str(ip_addr) + '/' + str(ipaddress.ip_network(VM_NETWORK).prefixlen)
            gateway = str(ipaddress.ip_network(VM_NETWORK)[1])
            network_config['ethernets']['eth0']['addresses'][0] = ip_addr_with_cidr
            network_config['ethernets']['eth0']['gateway4'] = gateway
        try:
            with open("/tmp/userdata", 'w') as f:
                f.write("#cloud-config\n")
                f.write(yaml.safe_dump(cloud_config, sort_keys=False))
            with open("/tmp/network-config", 'w') as f:
                f.write(yaml.safe_dump(network_config, sort_keys=False))
        except:
            raise
        cmd = "cloud-localds --network-config=/tmp/network-config %(image_path)s%(vm_name)s.img /tmp/userdata" % {'image_path': IMAGE_PATH, 'vm_name': vm_name}
        self.res_cmd(cmd)
        return "%(image_path)s%(vm_name)s.img" % {'image_path': IMAGE_PATH, 'vm_name': vm_name}

    def delete_cloudinit_image(self, vm_name):
        os.remove("%(path)s%(vm_name)s.img" % {'path': IMAGE_PATH, 'vm_name': vm_name})

    def _create_vm_image(self, vm_name, size, force=False, backing_file=''):
        if self.vm_image_exists(vm_name):
            if not force:
                print("ERROR: Already exists VM image %s" % vm_name)
                exit(1)
            else:
                return
        if not backing_file:
            backing_file = '%(path)svmbase.qcow2' % {'path': IMAGE_PATH}
        if not os.path.exists(backing_file):
            print("ERROR: Backing file %s not found" % backing_file)
            exit(1)
        cmd = "qemu-img create -f qcow2 -b %(backing_file)s %(path)s%(vm_name)s.qcow2 %(size)dG" % {'backing_file': backing_file, 'path': IMAGE_PATH, 'vm_name': vm_name, 'size': size}
        self.res_cmd(cmd)

    def create_vm(self, vm_name, cpu=2, mem=2048, disk=10, ip='', backing_file='', force=False):
        if self.vm_exists(vm_name):
            print("ERROR: Already exists VM %s" % vm_name)
            exit(1)
        ip_addr = self.ipam_ip_assign(vm_name, ip)
        self._create_vm_image(vm_name, disk, force=force, backing_file=backing_file)
        print("VM %s assigned %s" % (vm_name, ip_addr))
        cloudinit_path = self.create_cloudinit_image(vm_name, ip_addr=ip_addr)
        cmd = "virt-install --name %(vm_name)s --memory %(mem)d --vcpus %(cpu)d --disk %(path)s%(vm_name)s.qcow2,bus=virtio --disk %(cloudinit_path)s,device=cdrom --network bridge=virbr0,model=virtio --import --nographics --noautoconsole" % {'vm_name': vm_name, 'mem': mem, 'cpu': cpu, 'path': IMAGE_PATH, 'cloudinit_path': cloudinit_path}
        self.res_cmd(cmd, check=True)
        self.vm_dhcp_regist(vm_name)
        print("VM %s created!" % vm_name)

    def start_vm(self, vm_name):
        if not self.vm_exists(vm_name):
            print("ERROR: VM %s not found" % vm_name)
            exit(1)
        cmd = "virsh start %s" % vm_name
        self.res_cmd(cmd, check=True)
        print("VM %s started!" % vm_name)

    def stop_vm(self, vm_name):
        if not self.vm_exists(vm_name):
            print("ERROR: VM %s not found" % vm_name)
            exit(1)
        cmd = "virsh destroy %s" % vm_name
        self.res_cmd(cmd)
        print("VM %s stopped!" % vm_name)

    def _delete_vm_image(self, vm_name):
        if not self.vm_image_exists(vm_name):
            return
        os.remove("%(path)s%(vm_name)s.qcow2" % {'path': IMAGE_PATH, 'vm_name': vm_name})

    def delete_vm(self, vm_name, force=False):
        if not self.vm_exists(vm_name):
            print("ERROR: VM %s not found" % vm_name)
            exit(1)
        if not force:
            print("Are you sure you want to delete this VM %s?" % vm_name)
        if force or self.yes_no_input():
            self.stop_vm(vm_name)
            self.vm_dhcp_unregist(vm_name)
            ip_addr = self.ipam_ip_unassign(vm_name)
            print("VM %s unassigned %s" % (vm_name, ip_addr))
            cmd = "virsh undefine %s" % vm_name
            self.res_cmd(cmd, check=True)
            self.delete_cloudinit_image(vm_name)
            self._delete_vm_image(vm_name)
            print("VM %s deleted!" % vm_name)
        else:
            exit(0)


class CommandVirtCtl:

    def __init__(self):
        self.vc = VirtCtl()
        
    def command(self):
        parser = argparse.ArgumentParser(
            prog='virtctl',
            usage='%(prog)s [-h] [list, create, delete, start, stop, restart, init]',
            description='')
        subparsers = parser.add_subparsers()


        parser_init = subparsers.add_parser('init', help='create image_dir and data_dir`')
        parser_init.set_defaults(handler=self.command_init)

        parser_list = subparsers.add_parser('list', help='see `%(prog)s list -h`')
        parser_list.add_argument('-a', '--all', action='store_true', help='VM info get all')
        parser_list.set_defaults(handler=self.command_list)

        parser_create = subparsers.add_parser('create', help='see `%(prog)s create -h`')
        parser_create.add_argument('vm_name', help='VM name')
        parser_create.add_argument('-m', '--memory', type=int, default=2048, help='VM allocate memory size [MB]')
        parser_create.add_argument('-c', '--cpu', type=int, default=2, help='VM allocate num of cpu')
        parser_create.add_argument('-d', '--disk', type=int, choices=range(4,100), default=10, help='VM allocate disk size [GB]')
        parser_create.add_argument('-i', '--ip', default='', help='IP address')
        parser_create.add_argument('-b', '--backing-file', default='', help='VM backing_file')
        parser_create.add_argument('-f', '--force', action='store_true', help='VM force create')
        parser_create.set_defaults(handler=self.command_create)

        parser_delete = subparsers.add_parser('delete', help='see `%(prog)s delete -h`')
        parser_delete.add_argument('vm_name', help='VM name')
        parser_delete.add_argument('-f', '--force', action='store_true', help='VM force delete')
        parser_delete.set_defaults(handler=self.command_delete)

        parser_start = subparsers.add_parser('start', help='see `%(prog)s start -h`')
        parser_start.add_argument('vm_name', help='VM name')
        parser_start.set_defaults(handler=self.command_start)

        parser_stop = subparsers.add_parser('stop', help='see `%(prog)s stop -h`')
        parser_stop.add_argument('vm_name', help='VM name')
        parser_stop.set_defaults(handler=self.command_stop)

        parser_restart = subparsers.add_parser('restart', help='see `%(prog)s restart -h`')
        parser_restart.add_argument('vm_name', help='VM name')
        parser_restart.set_defaults(handler=self.command_restart)

        parser_net_list = subparsers.add_parser('net-list', help='see `%(prog)s net-list -h`')
        parser_net_list.set_defaults(handler=self.command_net_list)

    def command_init(self, args):
        self.vc.virtctl_init()

    def command_list(self, args):
        if args.all:
            pprint(self.vc.get_vm_list(ip=True))
        else:
            pprint(self.vc.get_vm_list())

    def command_create(self, args):
        self.vc.create_vm(args.vm_name, cpu=args.cpu, mem=args.memory,
            disk=args.disk, ip=args.ip, backing_file=args.backing_file, force=args.force)

    def command_delete(self, args):
        self.vc.delete_vm(args.vm_name, force=args.force)

    def command_start(self, args):
        self.vc.start_vm(args.vm_name)

    def command_stop(self, args):
        self.vc.stop_vm(args.vm_name)

    def command_restart(self, args):
        self.vc.stop_vm(args.vm_name)
        self.vc.start_vm(args.vm_name)

    def command_net_list(self, args):
        pprint(self.vc.get_net_list())


def main():
    if not os.getuid() == 0:
        print("ERROR: You must be root")
        exit(1)
    cmd = CommandVirtCtl()
    cmd.command()

if __name__ == '__main__':
    main()
