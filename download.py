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
import socket
from pprint import pprint
from redis import WatchError
from config import *
from googleplay import GooglePlayAPI
from helpers import sizeof_fmt


offset = None
# Authenticating to Google Play
api = GooglePlayAPI(ANDROID_ID)
api.login(GOOGLE_LOGIN, GOOGLE_PASSWORD, AUTH_TOKEN)
# Establishing redis & gearman connections
global SERVER_HOST
global HOSTNAME
global total_apps
total_apps =0
HOSTNAME=socket.gethostname()
SERVER_HOST= "127.0.0.1"
gm_worker = gearman.GearmanWorker([SERVER_HOST+':4730'])
redis_conn = redis.Redis(host=SERVER_HOST, port=6379, db=0)
print "Registered and waiting for work"
def task_listener_reverse(gearman_worker, gearman_job):
	
	search_term = gearman_job.data
	print HOSTNAME
	print "Will search for: " + search_term
	nb_res = 50
	print nb_res
	#print "NB_RES:" + nb_res
	try:
		message = api.search(search_term, nb_results=nb_res)
	except:
		print "Error: something went wrong. Maybe the nb_res you specified was too big?"
		sys.exit(1)
	doc = message.doc[0]

	for c in doc.child:
		time_total_start = time.time()
		#print time_total_start
		print c.docid
		print c.title

		packagename = c.docid
		try:
			m = api.details(packagename) # This API call returns all the medata we need in google's protobuf format
		except:
			print "Error getting details from API"
		prot = m.docV2 # protobuf

		# Check if apk has already been processed
		try:
			pipe = redis_conn.pipeline()
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
		#print "I reach here"
		#Open couchdb connection
		print SERVER_HOST
		db_host = "http://" + SERVER_HOST + ":5984"
		print db_host
		try:
			couch = couchdb.Server("http://" + SERVER_HOST + ":5984")
		except:
			print "Error connecting to db"
		db = couch['decompiled']
		#db.save(metadata)
	 	app_type = prot.offer[0].formattedAmount
		#print "I reach here as well"
		if app_type != "Free":
			db[packagename] = metadata
			print "App is not free. Adding only metadata"
			continue
		#print m
		#print "================================"
		#print doc
		vc = prot.details.appDetails.versionCode
		ot = prot.offer[0].offerType

		# Download (in ./apks/ folder for DroidBroker to find them)
		print "Downloading %s..." % sizeof_fmt(prot.details.appDetails.installationSize),
		download_start = time.time()
		try:
			data = api.download(packagename, vc, ot) # Download :D
		except:
			print "Problem"
		download_finish = time.time()
		total_download_time = download_finish - download_start
		print "DOWNLOAD TIME: " + str(total_download_time)
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
		print "DECOMPILE TIME: " + str(time_to_decompile)
		broker_results = open("./results/" + packagename + '.json')
		broker_json = json.load(broker_results)
		#pprint(broker_json)
		broker_results.close()

		print "I REACH HEREEEEEEEEEEE"
		try:
			db_doc = { 'metadata': metadata, 'decompiled': broker_json }
			db_time_start = time.time()
			db[packagename] = db_doc
			db_time_stop = time.time()
			db_total = db_time_stop - db_time_start
			print "DB_TIME:" + str(db_total)
		except:
			print "DB_PROBLEMS"
		#total_network_time = total_network_time + db_time
		print "Removing files..."
		try:
			shutil.rmtree("./results/")
			print "Removing files..."
			os.remove("./apks/" + filename)
		except:
			print "Failed to remove files"
		#total_apps +=1
		end = time.time()
		total_time = end- time_total_start
		print "Total time:" + str(end - time_total_start)
		db_stats = couch['statistics']
		db_statistics = db_stats.get(HOSTNAME)
		try:
			if db_statistics is None:
				statistics = { 'total_apps': 1, 'time_db': db_total, 'time_decompile': time_to_decompile, "time_download": total_download_time, 'total_time': total_time }
				db_stats[HOSTNAME] = statistics
			else:
				db_statistics['total_apps'] += 1
				db_statistics['time_db'] += db_total
				db_statistics['time_decompile'] += time_to_decompile
				db_statistics['time_download'] += total_download_time
				db_statistics['total_time'] += total_time
				db_stats[HOSTNAME] = db_statistics
		except:
			print "DB PROBLEM"

		# print "Total time for this app: " + time_total
		
	return gearman_job.data + str(os.getpid())
	
# gm_worker.set_client_id is optional
#gm_worker.set_client_id('python-worker')
gm_worker.register_task('reverse', task_listener_reverse)
print "I am goint to start working now"
# Enter our work loop and call gm_worker.after_poll() after each time we timeout/see socket activity
gm_worker.work()
