#!/usr/bin/python

# Base imports for all integrations, only remove these at your own risk!
import json
from pathlib import Path
import uuid
import sys
import os
import time
from collections import OrderedDict
import requests
from copy import deepcopy
import importlib
import pickle
from IPython.core.magic import (Magics, magics_class, line_magic, cell_magic, line_cell_magic)
from IPython.core.display import HTML
from IPython.display import display_html, display, Javascript, FileLink, FileLinks, Image
import pandas as pd
# Widgets
from ipywidgets import GridspecLayout, widgets


from addon_core import Addon

@magics_class
class Persist(Addon):
    # Static Variables

    magic_name = "persist"
    name_str = "persist"
    custom_evars = ['persist_addon_dir']

    custom_allowed_set_opts = ['persist_purge_days', 'persist_purge_data_only', 'persist_auto_purge', 'persist_addon_dir', 'persist_max_queries', 'persist_query_tz']

    # Option Format: [ Value, Description]
    # The options for both the base and customer integrations are a little obtuse at first.
    # This is because they are designed to be self documenting.
    # Each option item is actually a list of two length.
    # opt['item'][0] is the actual value if opt['item']
    # p[t['item'][1] is a description of the option and it's use for built in description.

    myopts = {}
    myopts['persist_purge_days'] = [60, "Number of days to keep queries before purge events occur"]
    myopts['persist_default_pkl_size'] = ['KB', "Units to show pickle sizes in. Defaults to KB (kilobytes), Supported: B, KB, MB"]
    myopts['persist_purge_data_only'] = [0, "When purging, only purge data, full records of df only, just the data part of queries (retain the query)"]
    myopts['persist_auto_purge'] = [0, "When starting integrations, run a check to automaticall purge old data"]
    myopts['persist_addon_dir'] = ['~/.ipython/integrations/' + name_str, "Directory for sharedmod caching/configs"]
    myopts['persist_max_queries'] = [50, "Max number of quries to allow to be stored"]
    myopts['persist_query_tz'] = ['local', "When showing query time, show as local time or utc (values: local or utc)"]


    # Class Init function - Obtain a reference to the get_ipython()
    # We get the self ipy, we set session to None, and we load base_integration level environ variables.


    def __init__(self, shell, debug=False, *args, **kwargs):
        super(Persist, self).__init__(shell, debug=debug)
        self.debug = debug

        #Add local variables to opts dict
        for k in self.myopts.keys():
            self.opts[k] = self.myopts[k]

        self.load_env(self.custom_evars)
        self.loadPersistedDict()

        shell.user_ns['persist_var'] = self.creation_name


    def listPersisted(self):

        # {"a88167960e644cceb6dfd1531ef2cde0": {"qtime": 1611754956, "pkl_size": 13321, "integration": "Splunk", "instance": "testing", "query": "search myterm='ff', 'notes':'some notes'} # file name is a88167960e644cceb6dfd1531ef2cde0.pkl

        print("Currently Persisted Data: \n")

#        curoutput += "{: <35} {: <80}\n".format(*["", "id:abc - abc is the id to of the data to load (required)"])

        print("{: <10} {: <20} {: <15} {: <15}".format(*['ID', 'Save Ts', 'Saved Size', 'Int/Inst']))
        for x in self.persist_dict.keys():
            d = self.persist_dict[x]
            mytime = self.retHumanTime(d['qtime'])
            mysize = self.dispSize(d['pkl_size'])
            myquery = d['query']
            mynotes = d['notes']
            myid = str(x)
            print("-------------------------------------------------------------")
            print("{: <10} {: <20} {: <15} {: <15}".format(*[myid[0:8], mytime, str(mysize) + ' ' + self.opts['persist_default_pkl_size'][0], d['integration'] + '/' + d['instance']]))
            print("")
            print("Query:\n%s" % myquery)
            print("")
            print("Notes: %s" % mynotes)
            print("")



    def checkDirs(self):
        if not os.path.isdir(self.persist_dir):
            os.makedirs(self.persist_dir)
        if not os.path.isdir(self.persisted_data_dir):
            os.makedirs(self.persisted_data_dir)


    def dispSize(self, size):
        retsize = 0
        psize = self.opts['persist_default_pkl_size'][0]
        if psize not in ['B', 'KB', 'MB']:
            print("persist_default_pkl size must be B, KB, or MB, defaulting to KB")
            psize = 'KB'
        if psize == "B":
            retsize = size
        elif psize == "KB":
            retsize = size / 1000
        elif psize == "MB":
            retsize = size / 1000000
        return retsize

    def retHumanTime(self, etime):
        rettime = ""

        mytime = self.opts['persist_query_tz'][0]
        if mytime != "local" and mytime != "utc":
            print("persist_query_tz not set to local or utc, defaulting to local")
            mytime = "local"
        if mytime == "local":
            rettime = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime(etime))
        elif mytime == "utc":
            rettime = time.strftime("%Y-%m-%d_%H:%M:%S", time.gmtime(etime))
        return rettime


    def savePersisted(self):
        f = open(self.persist_dict_pkl, 'wb')
        pickle.dump(self.persist_dict, f, protocol=pickle.HIGHEST_PROTOCOL)
        f.close()

    def saveData(self, myid, mydf):
        fname = myid + ".pkl"

        sfile = self.persisted_data_dir / fname
        f = open(sfile, 'wb')
        pickle.dump(mydf, f, protocol=pickle.HIGHEST_PROTOCOL)
        f.close()
        mysize = os.path.getsize(sfile)
        return mysize

    def lookupID(self, id):
        retval = id
        for x in self.persist_dict.keys():
            if x.find(id) == 0:
                retval = x
                break
        return retval


    def loadPersistedDF(self, myid):
        mydf = None

        myid = self.lookupID(myid)

        if myid not in self.persist_dict.keys():
            print("The id %s not found in currently persisted data" % myid)
            mydf = None
        else:
            fname = myid + ".pkl"
            r = open(self.persisted_data_dir / fname, 'rb')
            mydf = pickle.load(r)
            r.close()
        return mydf

    def loadPersistedDict(self):

        tstorloc = self.opts['persist_addon_dir'][0]
        if tstorloc[0] == "~":
            myhome = self.getHome()
            thome = tstorloc.replace("~", myhome)
            if self.debug:
                print(thome)
            tpdir = Path(thome)
        else:
            tpdir = Path(tstorloc)
        if self.debug:
            print(tpdir)
        self.persist_dir = tpdir
        self.persisted_data_dir = self.persist_dir / "persisted_data"
        self.persist_dict_pkl = self.persist_dir / "persist_dict.pkl"

        self.checkDirs()

        if os.path.isfile(self.persist_dict_pkl):
            r = open(self.persist_dict_pkl, 'rb')
            self.persist_dict = pickle.load(r)
            r.close()
        else:
            self.persist_dict = {}
        if self.debug:
            print(self.persist_dict)

    def deletePersisted(self, line):
        bConf = False
        tid = line.replace("delete", "").strip()
        tidar = tid.split(" ")
        myid = tidar[0].replace("id:", "").strip()

        if len(tidar) > 1:
            conf = tidar[1].strip()
            if conf == "-conf":
                bConf = True

        myid = self.lookupID(myid)
        if myid not in self.persist_dict.keys():
            print("ID %s does not found in persisted data. Please review %persist list for currrently known persisted data")
        else:
            if not bConf:
                dval = input("Please type the word 'delete' to remove persisted data with ID %s: " % myid)
                if dval.lower().strip() == "delete":
                    bConf = True
            if bConf:
                dfile =  myid + ".pkl"
                os.remove(self.persisted_data_dir / dfile)
                del self.persist_dict[myid]
                self.savePersisted()
                print("Deleted Persisted data with ID %s" % myid)
            else:
                print("Persisted Data removal canceled by not typing delete")
    def purgePersist(self, line):
        bConf = False
        if line.find("-conf") >= 0:
            bConf = True
        if not bConf:
            dval = input("Please type the word 'purge' to confirm purging of all old persisted queries: ")
            if dval.lower().strip() == "purge":
                bConf = True
        if bConf:
            print("This is where we would purge by date! (TODO: Actually Purge stuff)")
        else:
            print("The Purge is canceled")

    def persistDF(self, myline, mycell):
        myid = ""
        mystrdf = ""
        mynotes = ""
        bConf = False

        tline = myline.replace("save", '').strip()
        tar = tline.split(" ")
        mystrdf = tar[0]
        tline = tline.replace(mystrdf, '').strip()
        tar = tline.split(" ")
        if tar[0].find("id:") == 0:
            # This is an ID
            myid = tar[0].replace("id:", '').strip()
            tline = tline.replace(tar[0], '').strip()
        mynotes = mycell.strip()
        if tline.find("-conf") >= 0:
            bConf = True
        if self.debug:
            print("Saving Df: %s" % mystrdf)
            print("Id: %s" % myid)
            print("Notes: %s" % mynotes)
            print("bConf: %s" % bConf)
        if mystrdf in self.ipy.user_ns:
            mydf = self.ipy.user_ns[mystrdf]
        else:
            print("%s variable not found in user namespace, not persisting" % mystrdf)
            return None

        if isinstance(mydf, pd.DataFrame):
            newid = self.persistData(mydf, notes=mynotes, id=myid, confirm=bConf)
            print("Dataframe %s persisted with ID %s" % (mystrdf, newid))
        else:
            print("The variable %s, while it exists, is NOT a dataframe, therefore we will not persist it" % mystrdf)



    def persistData(self, thedata, notes="", integration="", instance="", query="", id="", confirm=False):
        bConf = confirm
        savetime = int(time.time())

        if id != "":
            id = self.lookupID(self.lookupid(id))
            if id in self.persist_dict.keys():
                if not bConf:
                    dval = input("ID %s already exists, please type confirm to confirm overwriting results: " % id)
                    if dval.lower().strip() == "confirm":
                        bConf = True
            else:
                print("id does not exist, and we don't allow custom id - your ID will be ignored")
                id = ""
                cConf = True
        else:
            bConf = True
        if id == "":
            id = self.getUUID()

        if isinstance(thedata, pd.DataFrame):
            if bConf:
                  # {"a88167960e644cceb6dfd1531ef2cde0": {"qtime": 1611754956, "pkl_size": 13321, "integration": "Splunk", "instance": "testing", "query": "search myterm='ff', 'notes':'some notes'} # file name is a88167960e644cceb6dfd1531ef2cde>
                mysize = self.saveData(id, thedata)
                myrec = {"qtime": savetime, "pkl_size": mysize, "integration": integration, "instance": instance, "query": query, "notes": notes}
                self.persist_dict[id] = myrec
                self.savePersisted()
                return id
            else:
                print("We are not going on due to duplicate ids")
        else:
            print("You tried to save a non dataframe, we only allow saving of dataframes")
        return None


    def loadDF(self, line):
        tline = line.replace("load", "").strip()
        tar = tline.split(" ")
        myid = tar[0].replace("id:", "").strip()
        mydfstr = tar[1].strip()

        if self.debug:
            print("ID: %s" % myid)
            print("Var: %s" % mydfstr)

        if mydfstr in self.ipy.user_ns.keys():
            print("Cannot load dataframe as %s because that variable exists in the namespace, please pick another" % mydfstr)
        else:
            self.ipy.user_ns[mydfstr] =  self.loadPersistedDF(myid)



    def getUUID(self):
        return uuid.uuid4().hex

# Display Help can be customized
    def customHelp(self):
        n = self.name_str
        m = "%" + self.name_str
        mq = "%" + m

        curoutput = self.displayAddonHelp()
        curoutput += "\n"
        curoutput += "Control Functions\n"
        curoutput += "{: <35} {: <80}\n".format(*[m + " list", "List the currently persisted data"])
        curoutput += "{: <35} {: <80}\n".format(*[m + " delete <ID> [-conf]", "Delete a specific <ID> (required) add -conf to auto verify"])
        curoutput += "{: <35} {: <80}\n".format(*[m + " purge [-conf]", "Purge all persisted data older then persist_purge_days add -conf to auto verify"])
        curoutput += "\n"
        curoutput += "Saving Dataframes\n"
        curoutput += "{: <35} {: <80}\n".format(*[mq + " save <df> [id:abc][-conf]", ""])
        curoutput += "{: <35} {: <80}\n".format(*["Notes about your query", ""])

        curoutput += "{: <35} {: <80}\n".format(*["", "df is dataframe to save (required)"])
        curoutput += "{: <35} {: <80}\n".format(*["", "id:abc - abc is the id to overwrite. (This saves over an existing df, this is optional, if none provided, we create a new id"])
        curoutput += "{: <35} {: <80}\n".format(*["", "-conf will auto clobber a previously saved id:"])
        curoutput += "{: <35} {: <80}\n".format(*["", "The next line is the notes about your query"])

        curoutput += "\n"
        curoutput += "Loading Dataframes\n"
        curoutput += "{: <35} {: <80}\n".format(*[m + " load <id:abc> <newvar>", ""])
        curoutput += "{: <35} {: <80}\n".format(*["", "id:abc - abc is the id to of the data to load (required)"])
        curoutput += "{: <35} {: <80}\n".format(*["", "newvar is the name of the new variable to load the dataframe into (required)"])

        return curoutput

    def customStatus(self):
        # Todo put in information about the persisted information
        print("")
        print("Persist addon Subsystem: Installed")
        print("")
        print("Current Persistance Information:")
        print("")
        print("{: <30} {: <80}".format("No. Persited Data:", len(self.persist_dict.keys())))


    # This is the magic name.
    @line_cell_magic
    def persist(self, line, cell=None):
        line = line.replace("\r", "")
        if cell is None:
            line_handled = self.handleLine(line)
            if self.debug:
                print("line: %s" % line)
                print("cell: %s" % cell)
            if not line_handled: # We based on this we can do custom things for integrations. 
                if line.lower().strip() == "list":
                    self.listPersisted()
                elif line.lower().find("delete") == 0:
                    self.deletePersisted(line)
                elif line.lower().find("purge") == 0:
                    self.purgePersist(line)
                elif line.lower().find("save") == 0:
                    self.persistDF(line)
                elif line.lower().find("load") == 0:
                    self.loadDF(line)
                else:
                    print("I am sorry, I don't know what you want to do with your line magic, try just %" + self.name_str + " for help options")
        else: # This is run is the cell is not none, thus it's a cell to process  - For us, that means a query
            if line.lower().find("save") == 0:
                self.persistDF(line, cell)

