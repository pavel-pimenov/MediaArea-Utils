#!/usr/bin/env python
# -*- coding: utf-8 -*-

import MySQLdb
import subprocess
import argparse
import fnmatch
import time
import sys
import os
import Repo

import xml.etree.ElementTree as ElementTree


print "\n========================================================"
print "Handle_OBS_results.py"
print "Copyright (c) MediaArea.net SARL. All Rights Reserved."
print "Use of this source code is governed by a BSD-style"
print "license that can be found in the License.txt file in the"
print "root of the source tree."
print "========================================================\n"

##################################################################
class mysql:

    def __init__(self):
        self.running = True
        try:
            self.sql = MySQLdb.connect(
                    host=Config["MySQL_host"],
                    user=Config["MySQL_user"],
                    passwd=Config["MySQL_passwd"],
                    db=Config["MySQL_db"])
        except MySQLdb.Error, e:
            self.running = True
            print "*** MySQL Error %d: %s ***" % (e.args[0], e.args[1])
            print "*** FATAL: quitting ***"
            sys.exit(1)

    def close(self):
        if self.open:
            self.sql.commit()
            return self.cursor.close()
        else:
            print "*** close: No DB cursor is open! ***"
            return 0

    def execute(self, query):
        print "---------------- SQL QUERY ----------------"
        print query
        print "-------------------------------------------"
        self.cursor = self.sql.cursor()
        self.cursor.execute(query)
        self.sql.commit()
        self.open = True

    def rowcount(self):
        if self.open:
            return self.cursor.rowcount
        else:
            print "*** rowcount: No DB cursor is open! ***"
            return 0

    def fetchone(self):
        if self.open:
            return self.cursor.fetchone()
        else:
            print "*** fetchone: No DB cursor is open! ***"
            return 0

    def fetchall(self):
        if self.open:
            return self.cursor.fetchall()
        else:
            print "*** fetchall: No DB cursor is open! ***"
            return 0

##################################################################
def Initialize_DB():

    # If the tables doesn’t exist, create it
    Cursor.execute("SELECT * FROM information_schema.tables WHERE table_schema = '" + Config["MySQL_db"] + "' AND table_name = '" + Table + "';")
    Result = 0
    Result = Cursor.rowcount()
    if Result == 0:
        Cursor.execute("CREATE TABLE IF NOT EXISTS " + Table
                        + """
                            (
                                distrib varchar(50),
                                arch varchar(10),
                                state tinyint(4)
                            )
                            DEFAULT CHARACTER SET utf8
                            DEFAULT COLLATE utf8_general_ci;
                        """)

    if Release == True:
        Cursor.execute("SELECT * FROM information_schema.tables WHERE table_schema = '" + Config["MySQL_db"] + "' AND table_name = '" + DL_pages_table + "';")
        Result = 0
        Result = Cursor.rowcount()
        if Result == 0:
            Cursor.execute("CREATE TABLE IF NOT EXISTS " + DL_pages_table
                            + "("
                            + DB_structure
                            + ") DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci;")
        else:
            # Update table schema to add doc package name
            if Project_kind == "lib":
                Cursor.execute("SELECT * FROM information_schema.columns WHERE table_schema = '" + Config["MySQL_db"] \
                               + "' AND table_name = '" + DL_pages_table + "' AND column_name = 'libnamedoc';")
                if Cursor.rowcount() == 0:
                    Cursor.execute("ALTER TABLE `" + DL_pages_table + "` ADD `libnamedoc` VARCHAR(120) DEFAULT '';")

    # Ensure that all the distribs in the dictionary are presents
    # in the DB

    for Distrib_name in Distribs:

        for Arch in Distribs[Distrib_name]:

            Cursor.execute("SELECT * FROM `" + Table + "` WHERE distrib = '" + Distrib_name + "' AND arch = '" + Arch + "';")
            Result = 0
            Result = Cursor.rowcount()
            # If the couple (Distrib_name, Arch) isn't already
            # in the table, we insert it
            if Result == 0:
                Cursor.execute("INSERT INTO `" + Table + "` (distrib, arch) VALUES ('" + Distrib_name + "', '" + Arch + "');")

    # Ensure that the DB doesn’t keep distribs the distros which
    # are no longer in the dictionary. The DL_pages_table is not
    # affected since a distrib can be removed from builds but still
    # wanted in the download tables.

    if not Rebuild:
        Cursor.execute("SELECT * FROM `" + Table + "`")
        DB_distribs = Cursor.fetchall()

        for DB_dist in DB_distribs:
            DB_distrib_name = DB_dist[0]
            DB_arch = DB_dist[1]
            if DB_distrib_name in Distribs:
                # If the distrib is present, but this arch has been
                # removed
                if Distribs[DB_distrib_name].count(DB_arch) == 0:
                    Cursor.execute("DELETE FROM `" + Table + "` WHERE distrib = '" + DB_distrib_name + "' AND arch = '" + DB_arch + "';")
            else:
                Cursor.execute("DELETE FROM `" + Table + "` WHERE distrib = '" + DB_distrib_name + "' AND arch = '" + DB_arch + "';")

##################################################################
def Waiting_loop():

    Count = 0

    # We wait for max 9h (600*20)+(1200*17)
    while Count < 38:

        Count = Count + 1

        # At first, check every 10mn during 3h20
        if Count < 20:
            if Count == 1:
                print "Wait 10mn..."
            else:
                print "All builds aren’t finished yet, wait another 10mn..."
            time.sleep(600)

        # Past 3h30, trigger rebuilds
        else:
            print "All builds aren’t finished yet, trigger rebuild(s) if there are still distribs in scheduled state, and wait 20mn..."
            for Distrib_name in Distribs:
                for Arch in Distribs[Distrib_name]:
                    Params = "osc results " + MA_project \
                           + " |grep " + Distrib_name \
                           + " |grep " + Arch \
                           + " |awk '{print $3}' |sed 's/*//'"
                    Result = subprocess.check_output(Params, shell=True).strip()
                    if Result == "scheduled":
                        print "Trigger rebuild for " + Distrib_name + " (" + Arch + ")"
                        subprocess.call(["osc", "rebuild", MA_project, Distrib_name, Arch])
            time.sleep(1200)

        # Check if the builds are done on OBS
        Params = "osc results 2>&1 " + MA_project \
               + " |awk '{print $3}' |sed 's/*//' |grep -v 'excluded\|disabled\|broken\|unresolvable\|failed\|succeeded' |wc -l"
        Result = subprocess.check_output(Params, shell=True).strip()
        # When all the distros are build, Result will equal 0
        if Result == "0":
            break

        # If Result ≠ 0 and Count = 37, then we have wait for 9h
        # and all the distros aren’t build. This while loop will
        # exit at the next iteration, and in the error mail we’ll
        # specify that the timeout was reached.
        Timeout = False
        if Count == 37:
            Timeout = True

##################################################################
def Update_DB():

    # We update the table with the results of the build
    for Distrib_name in Distribs:
        for Arch in Distribs[Distrib_name]:
            # We take "grep 'Distrib_name '" instead of "grep Distrib_name"
            # because the name of a distrib can be included in the
            # names of another distribs (ie SLE_11 and SLE_11_SPx)
            Params = "osc results " + MA_project \
                   + " |grep '" + Distrib_name + " '"\
                   + " |grep " + Arch \
                   + " |awk '{print $3}' |sed 's/*//'"
            Result = subprocess.check_output(Params, shell=True).strip()
            # First case : if the state is disabled, excluded or
            # unknown
            State = "0"
            if Result == "succeeded":
                State = "1"
            elif Result == "broken" or Result == "unresolvable" or Result == "failed" or Result == "blocked" or Result == "scheduled" or Result == "building" or Result == "finished":
                State = "2"
            elif Result == "":
                State = "3"
            Cursor.execute("UPDATE `" + Table + "` SET state= '" + State + "' WHERE distrib = '" + Distrib_name + "' AND arch = '" + Arch + "';")

##################################################################
def Trigger_rebuild():
    for Distrib in Distribs:
        for Arch in Distribs[Distrib]:
            print "Trigger rebuild for %s/%s"% (Distrib, Arch)
            subprocess.call(["osc", "rebuild", MA_project, Distrib, Arch])

##################################################################
def Get_package(Name, Distrib_name, Arch, Revision, Package_type, Package_infos, Destination):

    # We pass Package_infos as argument even if is global because it locally modified by the calling function

    # The wanted name for the package, under the form:
    # name[_|-]version[-1][_|.]Arch.[deb|rpm|pkg.tar.xz]
    Name_wanted = Name \
                + Package_infos[Package_type]["dash"] + Version \
                + Revision \
                + Package_infos[Package_type]["separator"] + Package_infos[Package_type][Arch] \
                + "." + Distrib_name \
                + "." + Package_type
    Name_final = os.path.join(Destination, Name_wanted)

    Name_obs_side = "0"
    # Fetch the name of the package on OBS
    # We take “ deb" ” to avoid the *.debian.txz files
    Params = "osc api /build/" \
           + OBS_project \
           + "/" + Distrib_name \
           + "/" + Arch \
           + "/" + OBS_package \
           + " |grep 'rpm\"\|deb\"\|pkg.tar.xz\"'" \
           + " |grep " + Name + Package_infos[Package_type]["dash"] + Version \
           + " |grep -v src |awk -F '\"' '{print $2}'"

    print "Name of the package on OBS:"
    print Params
    Name_obs_side = subprocess.check_output(Params, shell=True).strip()

    # If the bin package is build
    if len(Name_obs_side) > 1:
        Params_getpackage = "osc api /build/" + OBS_project \
                          + "/" + Distrib_name \
                          + "/" + Arch \
                          + "/" + OBS_package \
                          + "/" + Name_obs_side \
                          + " > " + Name_final

        print "Command to fetch the package:"
        print Params_getpackage
        print
        if os.path.isfile(Name_final):
            os.remove(Name_final)
        subprocess.call(Params_getpackage, shell=True)

        if os.path.isfile(Name_final):
            if Config["Enable_repo"]:
                if Package_type == "rpm":
                    print "Export package %s to repository" % Name_final
                    print
                    Repo.Add_rpm_package(Name_final, Name, Version, Arch, Distrib_name, Release)
                elif Package_type == "deb":
                    print "Export package %s to repository" % Name_final
                    print
                    Repo.Add_deb_package(Name_final, Name, Version, Arch, Distrib_name, Release)
        else:
        # This is potentially a spam tank, but I leave the
        # mails here because:
        # 1. it allows to have the command that have
        # failed = more convenient to understand the issue
        # 2. because of the multiple runs for the
        # multiple OBS repos (Project_debX), the final test
        # can miss some download errors.

        # If the bin package is build, but hasn’t been
        # downloaded for some raison.
            Params = "echo '" \
                   + Distrib_name \
                   + " (" + Arch + "): the package " \
                   + Name_obs_side \
                   + " is build, but hasn’t been downloaded.\n\nThe command line was:\n" \
                   + Params_getpackage + "'" \
                   + " |mailx -s '[BR lin] Problem with " \
                   + OBS_package + "'" \
                   + " " + Config["Email_to"]
            subprocess.call(Params, shell=True)
    else:
        print "ERROR: fail to get the name of the package " + Name + " on OBS."
        print

    return Name_wanted

##################################################################
def Get_packages_on_OBS():
    global FS_filter

    Cursor.execute("SELECT * FROM `" + Table + "`" + DB_filter)
    DB_distribs = Cursor.fetchall()

    for DB_dist in DB_distribs:

        Distrib_name = DB_dist[0]
        Arch = DB_dist[1]
        State = DB_dist[2]

        # State == 1 if build succeeded
        if State == 1:

            print
            print "API commands for " + Distrib_name + " (" + Arch + ")"
            print

            # Initialization depending on the distrib’s family
            Revision = ""
            if fnmatch.fnmatch(Distrib_name, "Debian*") or \
               fnmatch.fnmatch(Distrib_name, "*Ubuntu*"):
                Package_type = "deb"
                Revision = "-1"
            if fnmatch.fnmatch(Distrib_name, "RHEL*") or \
                    fnmatch.fnmatch(Distrib_name, "CentOS*") or \
                    fnmatch.fnmatch(Distrib_name, "Fedora*"):
                Package_type = "rpm"
                # We must reassign even if it’s the default value, in case SLE/openSUSE/Mageia came
                # before and assign it to i586
                Package_infos[Package_type]["i586"] = "i686"
            if fnmatch.fnmatch(Distrib_name, "SLE*") or \
                    fnmatch.fnmatch(Distrib_name, "openSUSE*") or \
                    fnmatch.fnmatch(Distrib_name, "Mageia*"):
                Package_type = "rpm"
                Package_infos[Package_type]["i586"] = "i586"
            if fnmatch.fnmatch(Distrib_name, "Arch*"):
                Package_type = "pkg.tar.xz"


            # Handle libzen and libmediainfo without 0 ending and Debian 9/Ubuntu 15.10+ 0v5 ending
            Bin_or_lib_name = Bin_name
            if Project_kind == "lib":
                if (fnmatch.fnmatch(Distrib_name, "RHEL*") and Distrib_name != "RHEL_5") or \
                   (fnmatch.fnmatch(Distrib_name, "CentOS*") and Distrib_name != "CentOS_5") or \
                   fnmatch.fnmatch(Distrib_name, "Fedora*") or \
                   fnmatch.fnmatch(Distrib_name, "Arch*"):
                    Bin_or_lib_name = Devel_name
                elif (fnmatch.fnmatch(Distrib_name, "xUbuntu*") and Distrib_name > "xUbuntu_15.04") \
                     or Distrib_name == "Ubuntu_Next_standard" \
                     or Distrib_name == "Debian_Next_ga" :
                    Bin_or_lib_name = Bin_name + "v5"

            ### Bin package ###
            Bin_name_wanted = Get_package(Bin_or_lib_name, Distrib_name, Arch, Revision, Package_type, Package_infos, Destination)

            ### Debug package ###
            if not fnmatch.fnmatch(Distrib_name, "Arch*") and \
               not Distrib_name == "RHEL_5" and \
               not Distrib_name == "CentOS_5":
                Debug_name_wanted = Get_package(Bin_or_lib_name + Package_infos[Package_type]["debugsuffix"], Distrib_name, Arch, Revision, Package_type, Package_infos, Destination)
            else:
                Debug_name_wanted = ''

            ### Dev package ###
            # Arch devel dependencies usually come with the library itself
            if Project_kind == "lib" and not fnmatch.fnmatch(Distrib_name, "Arch*"):
                Dev_name_wanted =  Get_package(Devel_name + Package_infos[Package_type]["devsuffix"], Distrib_name, Arch, Revision, Package_type, Package_infos, Destination)
            else:
                Dev_name_wanted = ''

            ### Doc package ###
            # No doc packages for Arch at this time, doc packages aren’t generated for Debian_6.0
            if Project_kind == "lib" and not fnmatch.fnmatch(Distrib_name, "Arch*") and not Distrib_name == "Debian_6.0":
                Doc_name_wanted = Get_package(Devel_name + "-doc", Distrib_name, Arch, Revision, Package_type, Package_infos, Destination)
            else:
                Doc_name_wanted = ''

            ### GUI package ###
            if Project_kind == "gui" and not Bin_name == "qctools" and \
                                        (not Bin_name == "mediaconch" or \
                                        (not fnmatch.fnmatch(Distrib_name, "CentOS*") and \
                                         not fnmatch.fnmatch(Distrib_name, "RHEL*") and \
                                         not fnmatch.fnmatch(Distrib_name, "SLE_11*") and \
                                         not fnmatch.fnmatch(Distrib_name, "openSUSE_11*"))):
                Gui_name_wanted = Get_package(Bin_name + "-gui", Distrib_name, Arch, Revision, Package_type, Package_infos, Destination_gui)

                # GUI debug package
                if not fnmatch.fnmatch(Distrib_name, "Arch*") and not Distrib_name == "RHEL_5" and not Distrib_name == "CentOS_5":
                    if Package_type == "deb" \
                       or fnmatch.fnmatch(Distrib_name, "openSUSE_*") \
                       or (fnmatch.fnmatch(Distrib_name, "SLE_*") and not fnmatch.fnmatch(Distrib_name, "SLE_11*")):
                        Gui_debug_name_wanted = Get_package(Bin_name + "-gui" + Package_infos[Package_type]["debugsuffix"], Distrib_name, Arch, Revision, Package_type, Package_infos, Destination_gui)
                    else:
                        Gui_debug_name_wanted = Get_package(Bin_name + Package_infos[Package_type]["debugsuffix"], Distrib_name, Arch, Revision, Package_type, Package_infos, Destination_gui)
                else:
                        Gui_debug_name_wanted = ''
            else:
                Gui_name_wanted = ''
                Gui_debug_name_wanted = ''

            ##################
            # Server package #
            ##################

            if Bin_name == "mediaconch" and (not Distrib_name == "CentOS_5" and \
                                             not Distrib_name == "CentOS_6" and \
                                             not fnmatch.fnmatch(Distrib_name, "RHEL_*") and \
                                             not fnmatch.fnmatch(Distrib_name, "SLE_11*") and \
                                             not fnmatch.fnmatch(Distrib_name, "openSUSE_11*")):
                Server_name_wanted = Get_package(Bin_name + "-server", Distrib_name, Arch, Revision, Package_type, Package_infos, Destination_server)

                # Server debug package
                if not fnmatch.fnmatch(Distrib_name, "Arch*"):
                    if Package_type == "deb" or fnmatch.fnmatch(Distrib_name, "openSUSE_*") or fnmatch.fnmatch(Distrib_name, "SLE_*"):
                        Server_debug_name_wanted = Get_package(Bin_name + "-server" + Package_infos[Package_type]["debugsuffix"], Distrib_name, Arch, Revision, Package_type, Package_infos, Destination_server)
                    else:
                        Server_debug_name_wanted = Get_package(Bin_name + Package_infos[Package_type]["debugsuffix"], Distrib_name, Arch, Revision, Package_type, Package_infos, Destination_server)
                else:
                    Server_debug_name_wanted = ''
            else :
                Server_name_wanted = ''
                Server_debug_name_wanted = ''

            if Rebuild:
                FS_filter += "\|" if FS_filter else ""
                FS_filter += "%s\.%s" % (Package_infos[Package_type][Arch], Distrib_name)

            ###########################
            # Put the filenames in DB #
            ###########################

            # If we run for a release
            if Release == True:

                # First, ensure that all the succeeded distribs are
                # presents in the DB
                Cursor.execute("SELECT * FROM `" + DL_pages_table + "` WHERE platform = '" + Distrib_name + "' AND arch = '" + Arch + "';")
                Result = 0
                Result = Cursor.rowcount()
                if Result == 0:
                    Cursor.execute("INSERT INTO `" + DL_pages_table + "` (platform, arch) VALUES ('" + Distrib_name + "', '" + Arch + "');")

                # For the libs
                if Project_kind == "lib":
                    Cursor.execute("UPDATE `" + DL_pages_table + "` SET"\
                            + " version = '" + Version + "'," \
                            + " libname = '" + Bin_name_wanted + "'," \
                            + " libnamedbg = '" + Debug_name_wanted + "'," \
                            + " libnamedev = '" + Dev_name_wanted + "'," \
                            + " libnamedoc = '" + Doc_name_wanted + "'"
                            + " WHERE platform = '" + Distrib_name + "'" \
                            + " AND arch = '" + Arch + "';")

                # For MC
                if Bin_name == "mediaconch":
                    Cursor.execute("UPDATE `" + DL_pages_table + "` SET"\
                            + " version = '" + Version + "'," \
                            + " cliname = '" + Bin_name_wanted + "'," \
                            + " clinamedbg = '" + Debug_name_wanted + "'," \
                            + " servername = '" + Server_name_wanted + "'," \
                            + " servernamedbg = '" + Server_debug_name_wanted + "'," \
                            + " guiname = '" + Gui_name_wanted + "'," \
                            + " guinamedbg = '" + Gui_debug_name_wanted + "'" \
                            + " WHERE platform = '" + Distrib_name + "'" \
                            + " AND arch = '" + Arch + "';")

                # For MI, DA, AM, BM
                if Bin_name == "mediainfo" or Bin_name == "dvanalyzer" or \
                   Bin_name == "avimetaedit" or Bin_name == "bwfmetaedit":
                    Cursor.execute("UPDATE `" + DL_pages_table + "` SET"\
                            + " version = '" + Version + "'," \
                            + " cliname = '" + Bin_name_wanted + "'," \
                            + " clinamedbg = '" + Debug_name_wanted + "'," \
                            + " guiname = '" + Gui_name_wanted + "'," \
                            + " guinamedbg = '" + Gui_debug_name_wanted + "'" \
                            + " WHERE platform = '" + Distrib_name + "'" \
                            + " AND arch = '" + Arch + "';")

                # For QC
                if Bin_name == "qctools":
                    Cursor.execute("UPDATE `" + DL_pages_table + "` SET"\
                            + " version = '" + Version + "'," \
                            + " cliname = ''," \
                            + " clinamedbg = ''," \
                            + " guiname = '" + Bin_name_wanted + "'," \
                            + " guinamedbg = '" + Debug_name_wanted + "'" \
                            + " WHERE platform = '" + Distrib_name + "'" \
                            + " AND arch = '" + Arch + "';")

            print "-----------------------"

##################################################################
def Verify_states_and_files():
    Filter = " |grep '%s'" % FS_filter if Rebuild else ""

    Cursor.execute("SELECT * FROM `" + Table + "`" + DB_filter)
    DB_distribs = Cursor.fetchall()

    Number_succeeded = 0
    Number_bin_wanted = 0
    Number_dev_wanted = 0
    Number_gui_wanted = 0
    Number_srv_wanted = 0
    Number_doc_wanted = 0
    Number_dbg_wanted = 0
    Dists_failed = []

    for DB_dist in DB_distribs:

        Distrib_name = DB_dist[0]
        Arch = DB_dist[1]
        State = DB_dist[2]

        # State == 1 if build succeeded
        if State == 1:
            Number_succeeded = Number_succeeded + 1
            Number_bin_wanted = Number_bin_wanted + 1

            if Project_kind == "lib" and not fnmatch.fnmatch(Distrib_name, "Arch*"):
                Number_dev_wanted = Number_dev_wanted + 1
                # Doc packages aren’t generated for Debian_6.0
                if not Distrib_name == "Debian_6.0":
                    Number_doc_wanted = Number_doc_wanted + 1
            elif Project_kind == "gui" and (not fnmatch.fnmatch(OBS_package, "MediaConch*") and \
                                            not fnmatch.fnmatch(OBS_package, "QCTools*") or \
                                           (not fnmatch.fnmatch(Distrib_name, "CentOS*") and \
                                            not fnmatch.fnmatch(Distrib_name, "RHEL*") and \
                                            not fnmatch.fnmatch(Distrib_name, "SLE_11*") and \
                                            not fnmatch.fnmatch(Distrib_name, "openSUSE_11*"))):
                Number_gui_wanted = Number_gui_wanted + 1

            if fnmatch.fnmatch(OBS_package, "MediaConch*") and \
               (not Distrib_name == "CentOS_5" and \
                not Distrib_name == "CentOS_6" and \
                not fnmatch.fnmatch(Distrib_name, "RHEL_*") and \
                not fnmatch.fnmatch(Distrib_name, "SLE_11*") and \
                not fnmatch.fnmatch(Distrib_name, "openSUSE_11*")):
                Number_srv_wanted = Number_srv_wanted + 1

            # Neither MediaInfo nor MediaInfoLib provides debuginfo package
            if not fnmatch.fnmatch(OBS_package, "MediaInfo*") and not fnmatch.fnmatch(Distrib_name, "Arch*"):
                Number_dbg_wanted = Number_dbg_wanted + 1

        # State == 2 if build failed
        if State == 2:
            Dists_failed.append(DB_dist + ("Build failed",))
        elif State == 3:
            Dists_failed.append(DB_dist + ("OBS error",))

    print "(In case the mails can’t be send:)"
    print "succeeded: " + str(Number_succeeded)

    ################
    # Bin packages #
    ################

    # Careful: if multiple instances run at the same time (debX)
    # and one of them doesn’t download its packages, the problem
    # may not be detected. Because the packages downloaded by other
    # instances will be counted in Number_bin.

    Number_bin = 0
    Params = "ls " + Destination + "/" + Devel_name + "*" + Version + "*" \
           + " |grep 'rpm\|deb\|pkg.tar.xz'" \
           + " |grep -v 'dbg\|debug\|dev\|devel\|doc'" \
           + Filter \
           + " |wc -l"
    Result = subprocess.check_output(Params, shell=True).strip()
    Number_bin = int(Result)

    # It’s not a good idea to put it before the previous line, as
    # in some case Result is an int, and other time it’s a str…
    print "bin: " + str(Number_bin)

    if Number_bin < Number_bin_wanted:
        Params = \
               "echo 'OBS project: " + OBS_project + "\n" \
               + "OBS package: " + OBS_package + "\n" \
               + "Version: " + Version + "\n\n" \
               + "The number of downloaded bin packages is lower than the number of succeeded bin packages on OBS:\n" \
               + str(Number_succeeded) + " succeeded and " + str(Number_bin) + " downloaded.'" \
               + " |mailx -s '[BR lin] Problem with " + OBS_package + "'" \
               + " " + Config["Email_to"]
        subprocess.call(Params, shell=True)

    ##################
    # Debug packages #
    ##################

    Number_debug = 0
    Params = "ls " + Destination + "/" + Devel_name + "*" \
           + " |grep 'rpm\|deb\|pkg.tar.xz'" \
           + " |grep 'dbg\|debug'" \
           + Filter \
           + " |wc -l"
    Result = subprocess.check_output(Params, shell=True).strip()
    Number_debug = int(Result)

    print "dbg: " + str(Number_debug)

    # Debug packages aren’t perfectly handled on OBS
    #if Number_debug < Number_dbg_wanted:
    #    Params = \
    #           "echo 'OBS project: " + OBS_project + "\n" \
    #           + "OBS package: " + OBS_package + "\n" \
    #           + "Version: " + Version + "\n\n" \
    #           "The number of downloaded debug packages is lower than the number of succeeded debug packages on OBS:\n" \
    #           + str(Number_succeeded) + " succeeded and " + str(Number_debug) + " downloaded.'" \
    #           + " |mailx -s '[BR lin] Problem with " + OBS_package + "'"
    #           + " " + Config["Email_to"]
    #    subprocess.call(Params, shell=True)

    ################
    # Dev packages #
    ################

    if Project_kind == "lib":
        Number_dev = 0
        Params = "ls " + Destination + "/" + Devel_name + "*" \
               + " |grep 'rpm\|deb\|pkg.tar.xz'" \
               + " |grep 'dev\|devel'" \
               + Filter \
               + " |wc -l"
        Result = subprocess.check_output(Params, shell=True).strip()
        Number_dev = int(Result)

        print "dev: " + str(Number_dev)

        if Number_dev < Number_dev_wanted:
            Params = \
                   "echo 'OBS project: " + OBS_project + "\n" \
                   + "OBS package: " + OBS_package + "\n" \
                   + "Version: " + Version + "\n\n" \
                   "The number of downloaded dev packages is lower than the number of succeeded dev packages on OBS:\n" \
                   + str(Number_succeeded) + " succeeded and " + str(Number_dev) + " downloaded.'" \
                   + " |mailx -s '[BR lin] Problem with " + OBS_package + "'" \
                   + " " + Config["Email_to"]
            subprocess.call(Params, shell=True)

        ################
        # Doc packages #
        ################

        Number_doc = 0
        Params = "ls " + Destination + "/" + Devel_name + "-doc*" \
               + " |grep 'rpm\|deb\|pkg.tar.xz'" \
               + Filter \
               + " |wc -l"
        Result = subprocess.check_output(Params, shell=True).strip()
        Number_doc = int(Result)

        print "doc: " + str(Number_doc)

        if Number_doc < Number_doc_wanted:
            Params = \
                   "echo 'OBS project: " + OBS_project + "\n" \
                   + "OBS package: " + OBS_package + "\n" \
                   + "Version: " + Version + "\n\n" \
                   "The number of downloaded doc packages is lower than the number of succeeded doc packages on OBS:\n" \
                   + str(Number_succeeded) + " succeeded and " + str(Number_doc) + " downloaded.'" \
                   + " |mailx -s '[BR lin] Problem with " + OBS_package + "'" \
                   + " " + Config["Email_to"]
            subprocess.call(Params, shell=True)

    ###################
    # Server packages #
    ###################

    if Bin_name == "mediaconch":
        Number_server = 0
        Params = "ls " + Destination_server + "/" + Bin_name + "-server" + "?" + Version + "*" \
               + " |grep 'rpm\|deb\|pkg.tar.xz'" \
               + Filter \
               + " |wc -l"
        Result = subprocess.check_output(Params, shell=True).strip()
        Number_server = int(Result)

        print "server: " + str(Number_server)

        if Number_server < Number_srv_wanted:
            Params = \
                   "echo 'OBS project: " + OBS_project + "\n" \
                   + "OBS package: " + OBS_package + "\n" \
                   + "Version: " + Version + "\n\n" \
                   "The number of downloaded server packages is lower than the number of succeeded server packages on OBS:\n" \
                   + str(Number_succeeded) + " succeeded and " + str(Number_server) + " downloaded.'" \
                   + " |mailx -s '[BR lin] Problem with " + OBS_package + "'" \
                   + " " + Config["Email_to"]
            subprocess.call(Params, shell=True)

    ################
    # GUI packages #
    ################

    if Project_kind == "gui" and Bin_name != "qctools":
        Number_gui = 0
        Params = "ls " + Destination_gui + "/" + Bin_name + "-gui" + "?" + Version + "*" \
               + " |grep 'rpm\|deb\|pkg.tar.xz'" \
               + Filter \
               + " |wc -l"
        Result = subprocess.check_output(Params, shell=True).strip()
        Number_gui = int(Result)

        print "gui: " + str(Number_gui)

        if Number_gui < Number_gui_wanted:
            Params = \
                   "echo 'OBS project: " + OBS_project + "\n" \
                   + "OBS package: " + OBS_package + "\n" \
                   + "Version: " + Version + "\n\n" \
                   "The number of downloaded gui packages is lower than the number of succeeded gui packages on OBS:\n" \
                   + str(Number_succeeded) + " succeeded and " + str(Number_gui) + " downloaded.'" \
                   + " |mailx -s '[BR lin] Problem with " + OBS_package + "'" \
                   + " " + Config["Email_to"]
            subprocess.call(Params, shell=True)

    ###################
    # Failed packages #
    ###################

    if len(Dists_failed) > 0:

        Failed_list = ""
        for Dist in Dists_failed:
            Distrib_name = Dist[0]
            Arch = Dist[1]
            Reason = Dist[3]
            Failed_list = Failed_list + "* %s (%s) Reason: %s\n" % (str(Distrib_name), str(Arch), str(Reason))

        print "\nFailed:\n" + Failed_list

        Timeout_message = ""
        if Timeout:
            Timeout_message = "After more than 9 hours, the builds weren’t over. The script will download whatever is available.\n\n"

        Params = \
               "echo 'OBS project: " + OBS_project + "\n" \
               + "OBS package: " + OBS_package + "\n" \
               + "Version: " + Version + "\n\n" \
               + Timeout_message \
               + "These packages fail on OBS for:\n" + Failed_list + "'" \
               + " |mailx -s '[BR lin] Problem with " + OBS_package + "'" \
               + " " + Config["Email_to"]
        subprocess.call(Params, shell=True)

    # Confirmation mails

    Quotient, Seconds = divmod(time.time()-Time_start, 60)
    Hours, Minutes = divmod(Quotient, 60)
    if Hours < 10:
        Total_time = "0" + str("%d" % Hours)
    else:
        Total_time = str("%d" % Hours)
    Total_time = Total_time + ":"
    if Minutes < 10:
        Total_time = Total_time + "0" + str("%d" % Minutes)
    else:
        Total_time = Total_time + str("%d" % Minutes)
    Total_time = Total_time + ":"
    if Seconds < 10:
        Total_time = Total_time + "0" + str("%d" % Seconds)
    else:
        Total_time = Total_time + str("%d" % Seconds)

    print "\nHandle_OBS_results.py has run during: " + Total_time

    # Don’t send a confirmation mail for the debX repos
    if Project_kind == "lib":
        # We use >= and not ==, because there may be other repos
        # which have ran into the same directory (Project_debX).
        if len(Dists_failed) == 0 and Number_bin >= Number_bin_wanted and Number_dev >= Number_dev_wanted and Number_doc >= Number_doc_wanted:
            Params = \
                   "echo 'OBS project: " + OBS_project + "\n" \
                   + "OBS package: " + OBS_package + "\n" \
                   + "Version: " + Version + "\n\n" \
                   + "SUCCESS\n\n" \
                   + "* " + str(Number_succeeded) + " builds succeeded;\n" \
                   + "* " + str(Number_bin) + " bin (" + Bin_name + ") packages downloaded;\n" \
                   + "* " + str(Number_dev) + " dev packages downloaded;\n" \
                   + "* " + str(Number_debug) + " debug packages downloaded (debug packages aren’t perfectly handled on OBS);\n" \
                   + "* " + str(Number_doc) + " doc packages downloaded.\n\n" \
                   + "Handle_OBS_results.py has run during: " + Total_time + "'" \
                   + " |mailx -s '[BR lin] OK for " + OBS_package + "'" \
                   + " " + Config["Email_to"]
            subprocess.call(Params, shell=True)

    if Project_kind == "gui":
        if len(Dists_failed) == 0 and Number_bin >= Number_bin_wanted and Number_gui >= Number_gui_wanted:
            Params = \
                   "echo 'OBS project: " + OBS_project + "\n" \
                   + "OBS package: " + OBS_package + "\n" \
                   + "Version: " + Version + "\n\n" \
                   + "SUCCESS\n\n" \
                   + "* " + str(Number_succeeded) + " builds succeeded;\n" \
                   + "* " + str(Number_bin) + " bin (CLI) packages downloaded;\n" \
                   + "* " + str(Number_debug) + " debug packages downloaded (debug packages aren’t perfectly handled on OBS);\n" \
                   + "* " + str(Number_gui) + " gui packages downloaded.\n\n" \
                   + "Handle_OBS_results.py has run during: " + Total_time + "'" \
                   + " |mailx -s '[BR lin] OK for " + OBS_package + "'" \
                   + " " + Config["Email_to"]
            subprocess.call(Params, shell=True)

##################################################################
# Main

Time_start = time.time()

#
# Arguments
#
# 1 $OBS_project (home:MediaArea_net[:snapshots])
# 2 $OBS_package (ZenLib, MediaInfoLib, …)
# 3 Version
# 4 Destination for the packages
# For MC: 5 Destination for the server packages and 6 for the GUI
# For MI: 5 Destination for the GUI packages

#
# Handle the variables
#

Args_parser = argparse.ArgumentParser()
Args_parser.add_argument("--filter", help="filter distributions/archs")
Args_parser.add_argument("project")
Args_parser.add_argument("package")
Args_parser.add_argument("version")
Args_parser.add_argument("destination", nargs="+")
Args = Args_parser.parse_args()

OBS_project = Args.project
OBS_package = Args.package
Version = Args.version
Destination = Args.destination[0]
# The directory from where the python script is executed
Script_emplacement = os.path.dirname(os.path.realpath(__file__))

MA_project = OBS_project + "/" + OBS_package

Config = {}
execfile( os.path.join( Script_emplacement, "Handle_OBS_results.conf"), Config)

Package_infos = Config["Package_infos"]

# Various initializations
DL_pages_table = "0"
DB_structure = ""
Release = False
Timeout = False
Count = 0
Result = 0

if OBS_package == "ZenLib":
    Project_kind = "lib"
    Bin_name = "libzen0"
    Devel_name = "libzen"
    if fnmatch.fnmatch(OBS_project, "*:snapshots"):
        Table = "snapshots_obs_zl"
    else:
        DL_pages_table = "releases_dlpages_zl"
        DB_structure = """
            platform varchar(50),
            arch varchar(10),
            version varchar(18),
            libname varchar(120),
            libnamedbg varchar(120),
            libnamedev varchar(120),
            libnamedoc varchar(120)"""
        Table = "releases_obs_zl"

if OBS_package == "MediaInfoLib":
    Project_kind = "lib"
    Bin_name = "libmediainfo0"
    Devel_name = "libmediainfo"
    if fnmatch.fnmatch(OBS_project, "*:snapshots"):
        Table = "snapshots_obs_mil"
    else:
        DL_pages_table = "releases_dlpages_mil"
        DB_structure = """
            platform varchar(50),
            arch varchar(10),
            version varchar(18),
            libname varchar(120),
            libnamedbg varchar(120),
            libnamedev varchar(120),
            libnamedoc varchar(120)"""
        Table = "releases_obs_mil"

if OBS_package == "MediaConch":
    Project_kind = "gui"
    Bin_name = "mediaconch"
    Devel_name = "mediaconch"
    Destination_server = Args.destination[1]
    Destination_gui = Args.destination[2]
    if fnmatch.fnmatch(OBS_project, "*:snapshots"):
        Table = "snapshots_obs_mc"
    else:
        DL_pages_table = "releases_dlpages_mc"
        DB_structure = """
            platform varchar(50),
            arch varchar(10),
            version varchar(18),
            cliname varchar(120),
            clinamedbg varchar(120),
            servername varchar(120),
            servernamedbg varchar(120),
            guiname varchar(120),
            guinamedbg varchar(120)"""
        Table = "releases_obs_mc"

if OBS_package == "MediaInfo":
    Project_kind = "gui"
    Bin_name = "mediainfo"
    Devel_name = "mediainfo"
    Destination_gui = Args.destination[1]
    if fnmatch.fnmatch(OBS_project, "*:snapshots"):
        Table = "snapshots_obs_mi"
    else:
        DL_pages_table = "releases_dlpages_mi"
        DB_structure = """
            platform varchar(50),
            arch varchar(10),
            version varchar(18),
            cliname varchar(120),
            clinamedbg varchar(120),
            guiname varchar(120),
            guinamedbg varchar(120)"""
        Table = "releases_obs_mi"

if OBS_package == "QCTools":
    Project_kind = "gui"
    Bin_name = "qctools"
    Devel_name = "qctools"
    Destination_gui = Destination
    if fnmatch.fnmatch(OBS_project, "*:snapshots"):
        Table = "snapshots_obs_qc"
    else:
        DL_pages_table = "releases_dlpages_qc"
        DB_structure = """
            platform varchar(50),
            arch varchar(10),
            version varchar(18),
            cliname varchar(120),
            clinamedbg varchar(120),
            guiname varchar(120),
            guinamedbg varchar(120)"""
        Table = "releases_obs_qc"

if OBS_package == "DVAnalyzer":
    Project_kind = "gui"
    Bin_name = "dvanalyzer"
    Devel_name = "dvanalyzer"
    Destination_gui = Args.destination[1]
    if fnmatch.fnmatch(OBS_project, "*:snapshots"):
        Table = "snapshots_obs_da"
    else:
        DL_pages_table = "releases_dlpages_da"
        DB_structure = """
            platform varchar(50),
            arch varchar(10),
            version varchar(18),
            cliname varchar(120),
            clinamedbg varchar(120),
            guiname varchar(120),
            guinamedbg varchar(120)"""
        Table = "releases_obs_da"

if OBS_package == "AVIMetaEdit":
    Project_kind = "gui"
    Bin_name = "avimetaedit"
    Devel_name = "avimetaedit"
    Destination_gui = Args.destination[1]
    if fnmatch.fnmatch(OBS_project, "*:snapshots"):
        Table = "snapshots_obs_am"
    else:
        DL_pages_table = "releases_dlpages_am"
        DB_structure = """
            platform varchar(50),
            arch varchar(10),
            version varchar(18),
            cliname varchar(120),
            clinamedbg varchar(120),
            guiname varchar(120),
            guinamedbg varchar(120)"""
        Table = "releases_obs_am"

if OBS_package == "BWFMetaEdit":
    Project_kind = "gui"
    Bin_name = "bwfmetaedit"
    Devel_name = "bwfmetaedit"
    Destination_gui = Args.destination[1]
    if fnmatch.fnmatch(OBS_project, "*:snapshots"):
        Table = "snapshots_obs_bm"
    else:
        DL_pages_table = "releases_dlpages_bm"
        DB_structure = """
            platform varchar(50),
            arch varchar(10),
            version varchar(18),
            cliname varchar(120),
            clinamedbg varchar(120),
            guiname varchar(120),
            guinamedbg varchar(120)"""
        Table = "releases_obs_bm"

if len(DL_pages_table) > 1:
    Release = True

# Build the dictionnary from the active distributions on OBS
Distribs = {}

Params = "osc results --xml " + MA_project
Result = subprocess.check_output(Params, shell=True).strip()

XML_root = ElementTree.fromstring(Result)

for Element in XML_root.iter('result'):
    Distrib = Element.attrib['repository']
    Arch = Element.attrib['arch']
    Distribs[Distrib] = Distribs.get(Distrib, []) + [Arch]

# Filter to cmdline distributions
Rebuild = False
DB_filter = ""
FS_filter = ""
if Args.filter:
    Distribs_filter = {}
    for Element in Args.filter.split(","):
        Distrib = Element.split("/")[0].strip()
        if len(Element.split("/")) > 1:
            Arch = Element.split("/")[1].strip()
            if Arch not in Distribs_filter.get(Distrib, []):
                Distribs_filter[Distrib] = Distribs_filter.get(Distrib, []) + [Arch]
            else:
                Distribs_filter[Distrib] = Distribs.get(Distrib)

    Distribs = Distribs_filter

    for Distrib in Distribs:
        if DB_filter:
            DB_filter += " OR ("
        else:
            DB_filter += " WHERE ("

        DB_filter += "distrib='%s' AND (arch='%s'" % (Distrib, Distribs[Distrib][0])
        for Arch in Distribs[Distrib][1:]:
            DB_filter += " OR arch='%s'" % Arch
        DB_filter += "))"

    Rebuild = True

    Trigger_rebuild()

#
# Handle the directories
#

if not os.path.exists(Destination):
    os.makedirs(Destination)
if Bin_name == "mediaconch":
    if not os.path.exists(Destination_server):
        os.makedirs(Destination_server)
if Project_kind == "gui":
    if not os.path.exists(Destination_gui):
        os.makedirs(Destination_gui)

# Open the access to the DB
Cursor = mysql()

# Ensure that the DB is synchronous with OBS.
Initialize_DB()

# Once the initialisation of this script is done, the first thing
# to do is wait until everything is build on OBS.
Waiting_loop()

# At this point, each enabled distros will be either in succeeded
# or failed state. We can update the DB.
Update_DB()

# Then, fetch the packages.
Get_packages_on_OBS()

# Send a confirmation mail if everything is ok, or else notify when
# a build has failed or a succeeded package has not been downloaded
Verify_states_and_files()

# Close the access to the DB
Cursor.close()

# If we run for MC or MI (no DL pages for ZL and MIL, so we test
# Project_kind), and this is a release
#if Bin_name == "mediaconch" and Release == True:
#    execfile( os.path.join( Script_emplacement, "Generate_DL_pages.py mc linux" ))
#if Bin_name == "mediainfo" and Release == True:
#    execfile( os.path.join( Script_emplacement, "Generate_DL_pages.py mi linux" ))
