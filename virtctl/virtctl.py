#!/usr/bin/env python3
# -*- coding: utf-8 -*-


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


class CommandVirtCtl:

    def __init__(self):
        self.vc = VirtCtl()
        

def main():
    if not os.getuid() == 0:
        print("ERROR: You must be root")
        exit(1)
    cmd = CommandVirtCtl()
    cmd.command()

if __name__ == '__main__':
    main()
