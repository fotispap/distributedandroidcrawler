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

def task_listener_randomwalk(gearman_worker, gearman_job):
	attempts = 1 # variables to watch hit ratio
	existed = 0
	print "ACCESSED GEARMAN AGAIN"
	packagename = gearman_job.data

	while True:
		out_of_packages = False
		try:
			details = api.details(packagename) # This API call returns all the medata we need in google's protobuf format
			related_resp = api.executeRequestApi2(details.docV2.annotations.sectionRelated.listUrl)
		except:
			print "API problem"
		doc = related_resp.payload.listResponse.doc[0]
		related_list = []
		for c in doc.child:
			related_list.append(c.docid)

		time_total_start = time.time()
		try:
			m = api.details(packagename) # This API call returns all the medata we need in google's protobuf format
		except:
			print "Error getting details from API"
		prot = m.docV2 # protobuf

		# Check if apk has already been processed
		try:
			pipe = redis_conn.pipeline()
			pipe.watch(packagename)
			rv = redis_conn.get(packagename)
			if rv == None:
				print "Inserting new APK"
				pipe.multi()
				pipe.set(packagename, prot.details.appDetails.versionCode)
				pipe.execute()
				download_flag = True
			elif rv < prot.details.appDetails.versionCode:
				print "Current version is outdated"
				pipe.multi()
				pipe.set(packagename, prot.details.appDetails.versionCode)
				pipe.execute()
				download_flag = True
			else:
				print "This app has already be done: " + packagename
				existed += 1
				download_flag = False

		except WatchError:
			print "error:" + os.getpid() + "encountered collision and did not change"
			pipe.reset()
			download_flag = False
		finally:
				pipe.reset()

		# Gather app metadata

		filename = packagename + ".apk"
		details = protobuf_to_dict.protobuf_to_dict(prot.details) # This serializes google's protobuf to JSON
		rating = protobuf_to_dict.protobuf_to_dict(prot.aggregateRating)
		description = prot.descriptionHtml
		metadata = { 'docid': prot.docid, 'creator': prot.creator, 'title': prot.title, 'details': details['appDetails'], 'rating': rating, 'description': description }

		#Open couchdb connection
		try:
			couch = couchdb.Server("http://" + SERVER_HOST + ":5984")
		except:
			print "Error connecting to db"
		db = couch['decompiled']
		app_type = prot.offer[0].formattedAmount
		if app_type != "Free":
			db[packagename] = metadata
			print "App is not free. Adding only metadata"
			download_flag = False

		# Download (in ./apks/ folder for DroidBroker to find them)
		if download_flag == True:
			vc = prot.details.appDetails.versionCode
			ot = prot.offer[0].offerType
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
			broker_results.close()

			# Upload result to remote storage
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

			# Remove files created
			print "Removing files..."
			try:
				shutil.rmtree("./results/")
				print "Removing files..."
				os.remove("./apks/" + filename)
			except:
				print "Failed to remove files"

			end = time.time()
			total_time = end- time_total_start
			print "Total time:" + str(end - time_total_start)

		# Check the list of related apps to find next target
		have_next_candidate = False
		for next_candidate in related_list:
			try:
				rv = redis_conn.get(next_candidate)
				attempts +=1
				if rv == None:
					packagename = next_candidate
					print "App:" + next_candidate + "is not downloaded. Will download it next..."
					related_list.remove(next_candidate)
					have_next_candidate = True
					break
				elif rv < prot.details.appDetails.versionCode:
					packagename = next_candidate
					print "Current version is outdated"
				else:
					print "App: " + next_candidate + " has already be done"
					existed += 1
			except WatchError:
				print "error:" + os.getpid() + "encountered collision and did not change"
				pipe.reset()
				download_flag = False
			finally:
					pipe.reset()


		# Update database
		db_stats = couch['statistics']
		db_statistics = db_stats.get(HOSTNAME)
		try:
			if db_statistics is None:
				statistics = { 'total_apps': 1, 'time_db': db_total, 'time_decompile': time_to_decompile, "time_download": total_download_time, 'total_time': total_time, 'total_attempts': 1, 'existed': 0 }
				db_stats[HOSTNAME] = statistics
			else:
				db_statistics['total_apps'] += 1
				db_statistics['time_db'] += db_total
				db_statistics['time_decompile'] += time_to_decompile
				db_statistics['time_download'] += total_download_time
				db_statistics['total_time'] += total_time
				db_statistics['total_attempts'] += attempts
				db_statistics['existed'] += existed
				db_stats[HOSTNAME] = db_statistics
		except:
			print "DB PROBLEM"




		if have_next_candidate == False:
			break
		# print "Total time for this app: " + time_total

	return gearman_job.data + str(os.getpid())
	
# gm_worker.set_client_id is optional
#gm_worker.set_client_id('python-worker')
gm_worker.register_task("randomwalk", task_listener_randomwalk)
print "I am going to start working now"
# Enter our work loop and call gm_worker.after_poll() after each time we timeout/see socket activity
gm_worker.work()
