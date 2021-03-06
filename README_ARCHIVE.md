
# The following documentation is outdated and kept in case we need to utilize it in filling out the main docs
-----




Integration Example
```
%%mysql
select * from table
```
- Integrations have instances, including a default instance.
  - In the following ENV examples, INSTANCE and INTEGRATION are replaced by the instance and integration names. 
  - The default instance for integration (if you don't specify instance, it will use this) is specified by the ENV variable JUPYTER_INTEGRATION_CONN_DEFAULT="instance"
  - URLs for instances are specified by JUPYTER_INTEGRATION_CONN_URL_INSTANCE  Instance is upper case here, where it's lower case when you use it (LOCAL in the ENV is local in the default instance)
  - CONN_URL is the connection URL in the format: scheme://user@host:port?variable1=variable1val&variable2=variable2val 
    - Specific variables will be mentioned in the docs for the integrations using this
- Queries results will return to plugable, user defined display table in Jupyter. 
  - Standard dataframe HTML is an option
  - We are going to rely on qgrid by default (https://github.com/quantopian/qgrid) - please install it 
- Query results will ALSO return as a data frame automatically by the name of prev_integration_instance
  - If we had an integration named drill, with an instance name of local,  working with Apache Drill, the variable prev_drill_local would always have the most recent query results, as a data frame
  - If you want to save those results to work with them programatically, assign it to a new variable before your next query. 
- Help for the specfic data integration is custom to that integration
  - Help is currently crude print statements, however, I would like to see it expanded to something that could be provided as part of the integration, but also allow users to add their own per integration help, even describing data sets available etc. 
- Query validation for the specific data integration is custom to that integration
  - Right now query validation is a crude proof of concept. I would like to expand this to allow more custom validation, and company specific validations for tables
  - Validation can take three froms
    - Warning only. The query runs, but a warning is printed for the user
    - Warn, and don't run query - If use submits the SAME query again, this WILL allow the query to run. (The user was warned, and they choose to run it anyhow)
    - Warn and don't allow query no matter what. This is a case where a query is not allowed to run. 
- Settings for your group can be passed in through ENV variables on a per integration basis. The only item that is set here (and it should be customizable, it's not right now) is JUPYTER_ and then the items for your integration can be set later
  - We do allow setting the JUPYTER_PROXY_HOST and JUPYTER_PROXY_USER Variable here, all itegrations that may need user/host for Proxy can access this. 
  - We may want to look through this to solidify it
  - Passwords should NOT be set here, we don't want to encourage setting passwords in ENV variables


### Visualizations
- Basic Visualizations are not included via Plotly.
  - Make sure it's installed
  - %vis will display the widget and auto populate with all dataframes that start with prev_
  - If you want to include a dataframe that exists without prev_ in the name, just call %vis with the dataframe name:
    - %vis mydf


To use: 

```
ipy = get_ipython()
from visualization_core import Visualization
myvis = Visualization(ipy, debug=False)
ipy.register_magics(myvis)

import plotly.graph_objects as go
import plotly.express as px
```

Then use 

```
%vis
```

or

```
%vis mydf
```

### Dataframe visualizaing
-------
- We do dataframe profiling with pandas-profiling


To use: 

```
from profile_core import Profile
myprof = Profile(ipy, debug=False)
ipy.register_magics(myprof)
from pandas_profiling import ProfileReport


Then type:

%profile

In a cell

```
 

### To do/Wishlist Items
----------
- I'd like to have a password safe integration with the base class. 
  - When a notebook is opened, the password safe can be "unlocked" using the master password
  - When unlocked, the custom integrations can access their passwords for individual data stores. 
  - Passwords stored here are encrypted, and only availble as pointers from the store. 
- Basic validation templates to work on based on certain data stores
- Document base (non override) functions better 



### Installation
-----
This module is the requirement for other modules. By itself it doesn't do much, but provide a basis for other integrations


After installing this, to instantiate the module so you can use the magics put this in a cell use the code below. I'd recommend having it in the .jupyter folder startup items do it doesn't have to be in every notebook. 


```
from yourthing_core import Yourthing
ipy = get_ipython()
Yourthing = Yourthing(ipy,  pd_use_beaker=True, other_option=False)
ipy.register_magics(Yourthing)
```


A great way to do this is using the ~/.ipython folder. 

In ~/.ipython/profile_default/startup

I create the following files

10_ipy.py
```
ipy = get_ipython()
```
11_vis.py
```
from visualization_core import Visualization
myvis = Visualization(ipy, debug=False)
ipy.register_magics(myvis)

import plotly.graph_objects as go
import plotly.express as px
```

 Then for each integration I am using,  a file, like if I am using drill and splunk:

12_drill.py
```
from drill_core import Drill
Drill = Drill(ipy, debug=False, pd_display_grid="qgrid")
ipy.register_magics(Drill)
```

13_splunk.py
```
from splunk_core import Splunk
Splunk = Splunk(ipy, debug=False, pd_display_grid="qgrid")
ipy.register_magics(Splunk)
```


    
### Class Documentation 
-------
I tried to include documentation in the actual class as much as possible. Here are the functions you will absolutely need to override in your custom integration

NOTE as of 2020-09-04 this needs updating


#### Class Items to add in a customer integration
---------
- Customize the name_str (for jupyter_drill we use "drill")
- Add any ENV variables you want to check for things like usernames, connection strings to custom_evars.
  - They should be name_str + '_user' in format. (we may actually take the name_str part out, but for now be explicit.
  - With jupyter_drill, [name_str + '_user'] would check an ENV variable named "JUPYTER_DRILL_USER"  and place it here. 
- If your integrations allows users to set more options than the base integration list them in custom_allowed_set_opts
- Add any options to myopts here that are specifc to your integration
  - They will be merged with opts in the base_integration. 

#### Functions to override in customer integrations and their purpose
---------
- init() 
  - Any things that are loaded as part of the instantiation should be moved to the init arguments and handled here. Ensure you include the updating of opts setting opts based on arguments here (we could clean this up)
- connect(self, prompt=False)
  - This is the function that gathers and validates all connection data for a class. It may use get pass to request a password from a user (if required) or if an ENV variable wasn't passed, it may ask a connection string or user. 
  - It can handle weird cases like in jupyter_drill, if it's using embedded_mode, it doesn't do username/password/connection string.  It handles that here. It doesn't actually validate, this just collects and then passes to auth()
- auth(self)
  - auth() is called when all the things are collected. It returns a INT result. If 0, then connect handles it as "this is ok"
- validateQuery(self, query) 
 - This takes the query and validates it from a custom perspective. It's unique to the data store, but we may include "basic" validators in the jupyter_integration_base at a future time.
- customQuery(self, query)
 - This is the function custom to the integration that does the actual querying
- customHelp(self)
 - This is custom help returning section for the integration


#### Functions to NOT overide in the base integration class and their purpose
--------
- load_env(self))
- handleLine(self, line)
- handleCell(self, cell)
- runQuery(self, query)
- displayHelp(self)
- retStatus(self)
- setvar(self, line)
