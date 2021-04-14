#!/usr/bin/python

# Base imports for all integrations, only remove these at your own risk!
import json
import sys
import os
import time
from pathlib import Path
from collections import OrderedDict
import requests
from copy import deepcopy
import importlib
import pickle
from IPython.core.magic import (Magics, magics_class, line_magic, cell_magic, line_cell_magic)
from IPython.core.display import HTML
from IPython.display import display_html, display, Markdown, Javascript, FileLink, FileLinks, Image

# Widgets
from ipywidgets import GridspecLayout, widgets


# nameing code
import traceback, threading, time
# end naming code

class InstanceCreationError(Exception):
    pass

#@magics_class
class Addon(Magics):
    # Static Variables
    ipy = None              # IPython variable for updating and interacting with the User's notebook
    debug = False           # Enable debug mode

    magic_name = "addon"
    name_str = "addon"
    env_pre = "JUPYTER_"

    # Variables users are allowed to set
    base_allowed_set_opts = ['m_replace_a0_20', 'm_replace_crlf_lf']

    # Option Format: [ Value, Description]
    # The options for both the base and customer integrations are a little obtuse at first.
    # This is because they are designed to be self documenting.
    # Each option item is actually a list of two length.
    # opt['item'][0] is the actual value if opt['item']
    # p[t['item'][1] is a description of the option and it's use for built in description.

    #addon_evars = []
    global_evars = ['proxy_host', 'proxy_user']
    addon_evars = ['_' + i for i in global_evars]

    opts = {}
    opts['m_replace_a0_20'] = [False, 'Replace hex(a0) with space (hex(20)) on magic submission - On lines and cells']
    opts['m_replace_crlf_lf'] = [True, 'Replace crlf with lf (convert windows to unix line endings) on magic submission - Only on cells, not lines']

    # The Main Display Grid (dg)
    dg = None

    # Class Init function - Obtain a reference to the get_ipython()
    # We get the self ipy, we set session to None, and we load base_integration level environ variables.

    def __init__(self, shell, debug=False, *args, **kwargs):
        self.debug = debug
        super(Addon, self).__init__(shell)
        self.ipy = shell
        self.load_env(self.global_evars)
        if 'jupyter_loaded_addons' not in shell.user_ns:
            shell.user_ns['jupyter_loaded_addons'] = [self.magic_name]
        else:
            shell.user_ns['jupyter_loaded_addons'].append(self.magic_name)

        # Begin Know your own name Name Code
        for frame, line in traceback.walk_stack(None):
            varnames = frame.f_code.co_varnames
            if varnames == ():
                break
            if frame.f_locals[varnames[0]] not in (self, self.__class__):
                break
                # if the frame is inside a method of this instance,
                # the first argument usually contains either the instance or
                #  its class
                # we want to find the first frame, where this is not the case
        else:
            raise InstanceCreationError("No suitable outer frame found.")
        self._outer_frame = frame
        self.creation_module = frame.f_globals["__name__"]
        self.creation_file, self.creation_line, self.creation_function, \
            self.creation_text = \
            traceback.extract_stack(frame, 1)[0]
        self.creation_name = self.creation_text.split("=")[0].strip()
        threading.Thread(target=self._check_existence_after_creation).start()


    def _check_existence_after_creation(self):
        while self._outer_frame.f_lineno == self.creation_line:
            time.sleep(0.01)
        # this is executed as soon as the line number changes
        # now we can be sure the instance was actually created
        error = InstanceCreationError(
                "\nCreation name not found in creation frame.\ncreation_file: "
                "%s \ncreation_line: %s \ncreation_text: %s\ncreation_name ("
                "might be wrong): %s" % (
                    self.creation_file, self.creation_line, self.creation_text,
                    self.creation_name))
        nameparts = self.creation_name.split(".")
        try:
            var = self._outer_frame.f_locals[nameparts[0]]
        except KeyError:
            raise error
        finally:
            del self._outer_frame
        # make sure we have no permament inter frame reference
        # which could hinder garbage collection
        try:
            for name in nameparts[1:]: var = getattr(var, name)
        except AttributeError:
            raise error
        if var is not self: raise error

    def print_creation_info(self):
        print(self.creation_name, self.creation_module, self.creation_function,
                self.creation_line, self.creation_text, sep=", ")
##### This is the base addon for line magic (single %), it handles the common items, and if the magic isn't common, it sends back to the custom addon to handle
    def handleLine(self, line):
        if self.opts['m_replace_a0_20'][0] == True:
            line = line.replace("\xa0", " ")

        bMischiefManaged = False
        # Handle all common line items or return back to the custom integration
        if line == "" or line.lower().find("help") == 0:
            bMischiefManaged = True
            self.displayMD(self.retHelp())
        elif line.lower() == "status":
            bMischiefManaged = True
            self.displayMD(self.retStatus())
        elif line.lower() == "debug":
            print("Toggling Debug from %s to %s" % (self.debug, not self.debug))
            self.debug = not self.debug
            bMischiefManaged = True
        elif line.lower().find('set ') == 0:
            self.setvar(line)
            bMischiefManaged = True
        else:
            pass
        return bMischiefManaged

    def getHome(self):
        home = ""
        if "HOME" in os.environ:
            if self.debug:
                print("HOME Found")
            home = os.environ["HOME"]
        elif "USERPROFILE" in os.environ:
            if self.debug:
                print("USERPROFILE Found")
            home = os.environ["USERPROFILE"]
        else:
            print("Home not found - Defaulting to ''")
        if home[-1] == "/" or home[-1] == "\\":
            home = home[0:-1]
        if self.debug:
            print("Home: %s" % home)
        return home

    def displayMD(self, md):
        display(Markdown(md))

#### retStatus should not be altered this should only exist in the base integration
    def retStatus(self):
        n = self.name_str
        mn = self.magic_name
        m = "%" + mn
        mq = "%" + m


        table_header = "| Variable | Value | Description |\n"
        table_header += "| -------- | ----- | ----------- |\n"

        out = ""
        out += "# Current State of %s Interface\n" % self.name_str
        out += "---------------------\n"
        out += "\n"
        out += "## Addon Base Properties\n"
        out += table_header
        out += "| debug | %s | Sets verbose out with %s debug |\n" % (self.debug, m)

        for k, v in self.opts.items():
            if k.find("m_") == 0:
                desc = v[1]
                if v[0] is None:
                    val = "None"
                else:
                    val = v[0]

                out += "| %s | %s | %s |\n" % (k, val, desc) 

        out += "\n\n"
        out += "## %s Properties\n" % n
        out += table_header
        for k, v in self.opts.items():
            if k.find(self.name_str + "_") == 0:
                if v[0] is None:
                    val = "None"
                else:
                    val = str(v[0])
                desc = v[1]
                out += "| %s | %s | %s |\n" % (k, val, desc)

        out += "\n\n"
        out += self.customStatus()
        return out

# This customStatus function should be overridden in the Addon. If it is not, nothing will happen. 

    def customStatus(self):
        return ""


    def retHelp(self):
        n = self.name_str
        mn = self.magic_name
        m = "%" + mn
        mq = "%" + m
        table_header = "| Magic | Description |\n"
        table_header += "| -------- | ----- |\n"


        out = ""
        out += "# %s - Jupyter Integrations Addon Help System\n" % m
        out += "------------------\n"
        out += self.retCustomDesc() + "\n\n"
        out += "## %s line magic \n" % (m)
        out += "---------------------\n"
        out += "### Standard Addon Line Magics\n"
        out += table_header
        out += "| %s | This Help Screen |\n" % m
        out += "| %s | Show the status of the %s addon, including variables used for config |\n" % (m + " status", m)
        out += "| %s | Sets the internal debug flag - Used to see more verbose info on addon functionality |\n" % (m + " debug")
        out += "| %s | Sets a the 'variable' provided to the 'value' provided |\n" % (m + " set 'variable' 'value'")
        out += "\n\n"
        out = self.customHelp(out)

        return out

    def retCustomDesc(self):
        return "Standard Addon for as Part of Jupyter Integrations"

#### This is the default custom help and should be overridden
    def customHelp(self, curout):
        out = curout
        out += "Added Custom Addon Help"
        return out
#### displayAddonHelp this is just a default help for Addons

    def displayAddonHelp(self):
        n = self.name_str
        mn = self.magic_name
        m = "%" + mn
        mq = "%" + m

        output = ""
        output += "The %s addon is a interface that allows you to use the magic function %s to interact with your data/analysis\n" % (n, m)
        output += "\n"
        output += "%s functions available\n" % (m)
        output += "###############################################################################################\n"
        output += "\n"
        output += "Standard Base Functions\n"
        output += "{: <35} {: <80}\n".format(*[m, "This help screen"])
        output += "{: <35} {: <80}\n".format(*[m + " status", "Print the status of the %s addon  and variables used for output" % m])
        output += "{: <35} {: <80}\n".format(*[m + " debug", "Sets an internal debug variable to True (False by default) to see more verbose info about addons"])
        output += "{: <35} {: <80}\n".format(*[m + " set %variable% %value%", "Set the variable %variable% to the value %value%"])
        return output

##### setvar should only exist in the base_integration
    def setvar(self, line):

        allowed_opts = self.base_allowed_set_opts + self.custom_allowed_set_opts

        tline = line.replace('set ', '')
        ttest = tline.split(' ')[0] # Keys can't have spaces, values can
        tkey = ttest
        tval = tline.replace(tkey + " ", "")
        if tval == "False":
            tval = False
        if tval == "True":
            tval = True
        if tkey in allowed_opts:

            oldval = self.opts[tkey][0]
            try:
                t = int(tval)
            except:
                t = tval
            self.opts[tkey][0] = t
            print("Set Integration Variable %s to %s - Previous Value: %s" % (tkey, t, oldval))
        else:
            print("You tried to set variable: %s - Not in Allowed options!" % tkey)




#### Don't alter this, this loads in ENV variables

    def remove_ev_quotes(self, val):
        retval = ""
        if val[0] == '"' and val[-1] == '"':
            retval = val[1:-1]
        elif val[0] == "'" and val[-1] == "'":
            retval = val[1:-1]
        else:
            retval = val
        return retval

    def load_env(self, evars):
        if self.debug:
            print("Passed Evars: %s" % evars)
            print("Addon_evars: %s" % self.addon_evars)
        for v in [self.name_str + i for i in self.addon_evars] + evars:
            ev = self.env_pre + v.upper()
            if self.debug:
                print("v: %s" % v)
                print("ev: %s" % ev)
            if ev[-1] != "_": # Normal EV - put in options 
                if self.debug:
                    print("Trying to load: %s" % ev)
                if ev in os.environ:
                    tvar = self.remove_ev_quotes(os.environ[ev])
                    if self.debug:
                        print("Loaded %s as %s" % (ev, tvar))
                    bgev = False
                    for gev in self.global_evars:
                        if v.find(gev) >= 0:
                            if v == gev:
                                tset = [tvar, "Jupyter Global value for %s" % gev]
                                self.opts[v] = tset
                                bgev = True
                                break
                            elif v[0] != "_":
                                tset = [tvar, "Integration Global value for %s" % gev]
                                self.opts[v] = tset
                                bgev = True
                                break
                    if not bgev:
                        self.opts[v][0] = tvar
                else:
                    if self.debug:
                        print("Could not load %s" % ev)
            elif ev[-1] == "_":  # This is a per instance variable - must default instances must be specified as default.
                base_var = v[0:-1].replace(self.name_str + "_", "")
                if self.debug:
                    print("base_var: %s" % base_var)
                for e in os.environ:
                    if e.find(ev) == 0:
                        if self.debug:
                            print("Found %s in %s" % (ev, e))
                        tval = self.remove_ev_quotes(os.environ[e])
                        mod = e.replace(ev, "").lower()
                        if base_var == "url":
                            if self.debug:
                                print("filling %s with %s" % (mod, tval))
                            self.fill_mods(mod, tval)





#    def load_env(self, evars):

#        for v in [self.name_str + i for i in self.addon_evars] + evars:
 #           ev = self.env_pre + v.upper()
  #          if ev[-1] != "_": # Normal EV - put in options
   #             if self.debug:
    #                print("Trying to load: %s" % ev)
     #           if ev in os.environ:
      #              tvar = self.remove_ev_quotes(os.environ[ev])
      #              if self.debug:
      #                  print("Loaded %s as %s" % (ev, tvar))
      #              self.opts[v][0] = tvar
      #          else:
      #              if self.debug:
      #                  print("Could not load %s" % ev)
      #      elif ev[-1] == "_":  # This is a per instance variable.
      #          base_var = v[0:-1].replace(self.name_str + "_", "")
      #          for e in os.environ:
      #              if e.find(ev) == 0:
      #                  tval = self.remove_ev_quotes(os.environ[e])
      #                  mod = e.replace(ev, "").lower()
      #                  if base_var == "url":
      #                      self.fill_mods(mod, tval)



