import libcalamares


def pretty_name():
    return "Preparing this console"


def run():
    libcalamares.globalstorage.insert("rootMountPoint", "/")
    return None
