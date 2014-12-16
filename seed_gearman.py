#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
import os
import urlparse
import time
from pprint import pprint
import gearman
from config import *
from googleplay import GooglePlayAPI
from helpers import sizeof_fmt, print_header_line, print_result_line

def check_request_status(job_request):
    if job_request.complete:
        print "Job %s finished!  Result: %s - %s" % (job_request.job.unique, job_request.state, job_request.result)
    elif job_request.timed_out:
        print "Job %s timed out!" % job_request.unique
    elif job_request.state == JOB_UNKNOWN:
        print "Job %s connection failed!" % job_request.unique


gm_client = gearman.GearmanClient(['127.0.0.1:4730'])


    

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
			m = api.details(c.docid)
			doc_temp = m.docV2
			vc = doc_temp.details.appDetails.versionCode
			ot = doc_temp.offer[0].offerType
			packagename = c.docid
			string = bytes(packagename)
			print string
			completed_job_request = gm_client.submit_job("randomwalk", string, background=True)
			check_request_status(completed_job_request)

			time.sleep(1)

