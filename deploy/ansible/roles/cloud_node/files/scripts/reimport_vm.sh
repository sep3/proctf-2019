#!/bin/bash -e

vm=${1?Syntax: ./reimport_vm.sh <vm_name>}

if ! [[ $vm =~ ^[a-zA-Z_0-9]+$ ]]; then
  echo "vm name validation error"
  exit 1
fi

vm_path="/home/cloud/${vm}.ova"

if [ ! -f "$vm_path" ]; then
  echo "there is no file ${vm_path}"
  exit 1
fi

while VBoxManage showvminfo "$vm" &>/dev/null; do
  echo "unregister old"
  VBoxManage unregistervm "$vm" --delete
done

VBoxManage import "$vm_path" --vsys 0 --vmname "$vm"
VBoxManage modifyvm "$vm" --cpus=2
VBoxManage modifyvm "$vm" --bridgeadapter1 "eth0"
VBoxManage modifyvm "$vm" --nic1 bridged
VBoxManage modifyvm "$vm" --usbehci off
vboxmanage snapshot "$vm" take initial
