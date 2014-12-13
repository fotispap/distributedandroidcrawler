#!/usr/bin/python

# Do not remove
GOOGLE_LOGIN = GOOGLE_PASSWORD = AUTH_TOKEN = None

import sys
import subprocess
import json
import couchdb
import protobuf_to_dict
import gearman
import redis
import os
import shutil
import time
from pprint import pprint
from redis import WatchError
from config import *
from googleplay import GooglePlayAPI
from helpers import sizeof_fmt


nb_res = 50
offset = None
# Authenticating to Google Play
api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)

# Establishing redis & gearman connections
gm_worker = gearman.GearmanWorker(['5.135.182.108:4730'])
redis_conn = redis.Redis(host="5.135.182.108", port=6379, db=0)
print "Registered and waiting for work"
def task_listener_reverse(gearman_worker, gearman_job):
	
	search_term = gearman_job.data
	print "Will search for: " + search_term
	try:
		message = api.search(search_term, nb_res, offset)
	except:
		print "Error: something went wrong. Maybe the nb_res you specified was too big?"
		sys.exit(1)
	doc = message.doc[0]

	for c in doc.child:
		print c.docid
		print c.title

		packagename = c.docid
		try:
			m = api.details(packagename) # This API call returns all the medata we need in google's protobuf format
		except:
			print "Error getting details from API"
		prot = m.docV2 # protobuf

		# Check if apk has already been processed
		pipe = redis_conn.pipeline()
		try:
			pipe.watch(gearman_job.data)
			rv = redis_conn.get(packagename)
			if rv == None:
				print "Inserting new APK"
				pipe.multi()
				pipe.set(packagename, prot.details.appDetails.versionCode)
				pipe.execute()
			elif rv < prot.details.appDetails.versionCode:
				print "Current version is outdated"
				pipe.multi()
				pipe.set(packagename, prot.details.appDetails.versionCode)
				pipe.execute()
			else:
				print "This app has already be done"
				continue
		except WatchError:
			print "error:" + os.getpid() + "encountered collision and did not change"
			pipe.reset()
			continue
		finally:
			pipe.reset()
		filename = packagename + ".apk"
		details = protobuf_to_dict.protobuf_to_dict(prot.details) # This serializes google's protobuf to JSON
		rating = protobuf_to_dict.protobuf_to_dict(prot.aggregateRating)
		description = prot.descriptionHtml
		metadata = { 'docid': prot.docid, 'creator': prot.creator, 'title': prot.title, 'details': details['appDetails'], 'rating': rating }
		print "I reach here"
		#Open couchdb connection
		try:
			couch = couchdb.Server("http://5.135.182.108:5984")
		except:
			print "Error connecting to db"
		db = couch['decompiled']
		#db.save(metadata)
	 	app_type = prot.offer[0].formattedAmount
		print "I reach here as well"
		if app_type != "Free":
			db[packagename] = metadata
			print "App is not free. Adding only metadata"
			continue
		#print m
		print "================================"
		#print doc
		vc = prot.details.appDetails.versionCode
		ot = prot.offer[0].offerType

		# Download (in ./apks/ folder for DroidBroker to find them)
		print "Downloading %s..." % sizeof_fmt(prot.details.appDetails.installationSize),
		network_start = time.time()
		try:
			data = api.download(packagename, vc, ot) # Download :D
		except:
			print "Problem"
		network_finish = ( time.time() - network_start )
		total_network_time = total_network_time + network_finish
		print total_network_time
		f = open("./apks/" + filename, "wb")
		f.write(data)
		print "Done"
		f.close()
		print "Running DroidBroker Tool"

		#Run Droid Broker 
		args = ['java','-jar', 'DroidBroker.jar', '-P', '-g']
		decompile_start = time.time()
		subprocess.call(args)
		time_to_decompile = (time.time() - decompile_start)
		total_decompile_time = total_decompile_time + time_to_decompile
		
		json_filename=("./results/" + packagename + '.json')

		broker_results = open("./results/" + packagename + '.json')
		broker_json = json.load(broker_results)
		#pprint(broker_json)
		broker_results.close()


		db_doc = { 'metadata': metadata, 'decompiled': broker_json }
		db_time_start = time.time()
		db[packagename] = db_doc
		db_time = time.time() - db_time_start
		total_network_time = total_network_time + db_time
		print "Removing files..."
		print "Timing: Network: " + total_network_time + "Decompiling: " + total_decompile_time
		#DELETE FILES
		try:
			shutil.rmtree("./results/")
			print "Removing files..."
			os.remove("./apks/" + filename)
		except:
			print "Failed to remove files"
	return gearman_job.data + str(os.getpid())
	
# gm_worker.set_client_id is optional
#gm_worker.set_client_id('python-worker')
gm_worker.register_task('reverse', task_listener_reverse)
print "I am goint to start working now"
# Enter our work loop and call gm_worker.after_poll() after each time we timeout/see socket activity
gm_worker.work()
