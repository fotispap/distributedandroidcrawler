import gearman
import redis
import os
from redis import WatchError
gm_worker = gearman.GearmanWorker(['127.0.0.1:4730'])
my_server = redis.Redis(host="127.0.0.1", port=6379, db=0)

def task_listener_reverse(gearman_worker, gearman_job):
    #print "Reversing string:"  + gearman_job.data + str(os.getpid())
    pipe = my_server.pipeline(False)
    try:
        pipe.watch(gearman_job.data)
        response = pipe.get(gearman_job.data)
        #print response
       # if response is None:
        pipe.multi()
        pipe.set(gearman_job.data,gearman_job.data[::-1]+str(os.getpid()))
        pipe.execute()

    except WatchError:
        print "error:" + os.getpid() + "encountered collision and did not change"
    finally:
        pipe.reset()
    #print "all done tralala"
    return gearman_job.data[::-1]+str(os.getpid())

# gm_worker.set_client_id is optional
gm_worker.set_client_id('python-worker')
gm_worker.register_task('reverse', task_listener_reverse)

# Enter our work loop and call gm_worker.after_poll() after each time we timeout/see socket activity
gm_worker.work()
