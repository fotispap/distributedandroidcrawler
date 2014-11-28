#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
import subprocess
from pprint import pprint

from config import *
from googleplay import GooglePlayAPI
from helpers import sizeof_fmt

if (len(sys.argv) < 2):
    print "Usage: %s packagename [filename]"
    print "Download an app."
    print "If filename is not present, will write to packagename.apk."
    sys.exit(0)

packagename = sys.argv[1]

if (len(sys.argv) == 3):
    filename = sys.argv[2]
else:
    filename = packagename + ".apk"

# Connect
api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)

# Get the version code and the offer type from the app details
m = api.details(packagename)
doc = m.docV2
sa = doc.annotations.sectionRelated.listUrl
print sa
resp = api.browse(sa)
print resp
sa_list = resp.docV2
print sa_list
#print m
print "================================"
#print doc
vc = doc.details.appDetails.versionCode
ot = doc.offer[0].offerType

# Download (in ./apks/ folder for DroidBroker to find them)
print "Downloading %s..." % sizeof_fmt(doc.details.appDetails.installationSize),
#data = api.download(packagename, vc, ot)
#open("./apks/" + filename, "wb").write(data)
print "Done"
print "Running DroidBroker Tool"

#Run Droid Broker 
args = ['apktool','d',  packagename + '.apk','-f']
args1 = ['java','-jar', 'DroidBroker.jar', '-P']
#subprocess.call(args1)


