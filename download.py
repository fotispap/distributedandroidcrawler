#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
import subprocess
import json
import couchdb
import protobuf_to_dict

from pprint import pprint

from config import *
from googleplay import GooglePlayAPI
from helpers import sizeof_fmt

if (len(sys.argv) < 2):
    print "Usage: %s packagename [filename]"
    print "Download an app."
    print "If filename is not present, will write to packagename.apk."
    sys.exit(0)
# Arguments only for testing, normally it will take package name from search results
packagename = sys.argv[1]

if (len(sys.argv) == 3):
    filename = sys.argv[2]
else:
    filename = packagename + ".apk"

# Connect
api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)

# Get the version code and the offer type from the app details
m = api.details(packagename) # This API call returns all the medata we need in google's protobuf format
prot = m.docV2 # protobuf
#f = open("./results/" + filename + ".details", "wb")
#print >> f, prot 

details = protobuf_to_dict.protobuf_to_dict(prot.details) # This serializes google's protobuf to JSON
rating = protobuf_to_dict.protobuf_to_dict(prot.aggregateRating)
description = prot.descriptionHtml
metadata = { 'docid': prot.docid, 'creator': prot.creator, 'title': prot.title, 'details': details['appDetails'], 'rating': rating }
print metadata
#sa = doc.annotations.sectionRelated.listUrl
#print sa
#resp = api.browse(sa)
#print resp

#Open couchdb connection
couch = couchdb.Server()
db = couch['decompiled']
#db.save(metadata)

#print m
print "================================"
#print doc
vc = prot.details.appDetails.versionCode
ot = prot.offer[0].offerType

# Download (in ./apks/ folder for DroidBroker to find them)
print "Downloading %s..." % sizeof_fmt(prot.details.appDetails.installationSize),
data = api.download(packagename, vc, ot) # Download :D
open("./apks/" + filename, "wb").write(data)
print "Done"
print "Running DroidBroker Tool"

#Run Droid Broker 
args = ['apktool','d',  packagename + '.apk','-f']
args1 = ['java','-jar', 'DroidBroker.jar', '-P']
subprocess.call(args1)

json_filename=("./results/" + packagename + '.json')

broker_results = open("./results/" + packagename + '.json')
broker_json = json.load(broker_results)
#pprint(broker_json)
db_doc = { 'metadata': metadata, 'decompiled': broker_json }
db.save(db_doc)
