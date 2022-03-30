#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class VirtCtl:

    def __init__(self):
        pass


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
