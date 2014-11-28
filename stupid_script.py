#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
import os
import urlparse
from pprint import pprint

from config import *
from googleplay import GooglePlayAPI
from helpers import sizeof_fmt, print_header_line, print_result_line

if (len(sys.argv) < 2):
    print "Usage: %s category [subcategory] [nb_results] [offset]" % sys.argv[0]
    print "List subcategories and apps within them."
    print "category: To obtain a list of supported catagories, use categories.py"
    print "subcategory: You can get a list of all subcategories available, by supplying a valid category"
    sys.exit(0)

ctr = "apps_topselling_free"
#os.system("./categories.py")
#cat = raw_input("Enter the name of one of the categories above...")
nb_results = None
offset = None

if (len(sys.argv) >= 2):
    nb_results = sys.argv[1]

#print "Arguments are:" + ctr + " " + cat + " " + nb_results

api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)

#print SEPARATOR.join(["ID", "Name"])
response = api.browse()

for l in response.category:
	cat = urlparse.parse_qs(l.dataUrl)['cat'][0]
	print "Downloading top " + nb_results + " apps of category: " + cat
	#print SEPARATOR.join(i.encode('utf8') for i in [urlparse.parse_qs(c.dataUrl)['cat'][0], c.name])

	try:
		message = api.list(cat, ctr, nb_results, offset)
	except:
		print "Error: HTTP 500 - one of the provided parameters is invalid"

	 


	if (ctr is None):
		print SEPARATOR.join(["Subcategory ID", "Name"])
		for doc in message.doc:
			print SEPARATOR.join([doc.docid.encode('utf8'), doc.title.encode('utf8')])
	else:
		print_header_line()
		doc = message.doc[0]
		i = 0
		for c in doc.child:
			#print_result_line(c)
			#print c.creator
			#print c.docid
			m = api.details(c.docid)
			doc_temp = m.docV2
			vc = doc_temp.details.appDetails.versionCode
			ot = doc_temp.offer[0].offerType
			print "Downloading " + c.docid + "(%s)..." % sizeof_fmt(doc_temp.details.appDetails.installationSize)
			data = api.download(c.docid, vc, ot)
			open("./apks/" + c.docid + ".apk", "wb").write(data)
			print "Done"
			#discard = raw_input("Download done, press enter to continue...")
			#parts = string_line.split(',')
			#print parts[1]
print "All done. Chupa meu pau!"

