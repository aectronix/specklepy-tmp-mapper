import argparse
import json
import math
import re
import time

from specklepy.api import operations
from specklepy.api.client import SpeckleClient
from specklepy.api.credentials import get_default_account
from specklepy.api.credentials import get_local_accounts
from specklepy.objects.base import Base
from specklepy.objects.other import Collection, Transform
from specklepy.transports.server import ServerTransport
from specklepy.serialization.base_object_serializer import BaseObjectSerializer

start_time = time.time()

cmd = argparse.ArgumentParser()
cmd.add_argument('-s', '--stream', required=False, help='stream id')
cmd.add_argument('-c', '--commit', required=False, help='commit id')
cmd.add_argument('-p', '--port', required=False, help='ac port')
arg = cmd.parse_args()


class Cloud():

	def __init__(self):

		self.client = None
		self.transport = None

		self.connect()

	def connect(self):

		# client = SpeckleClient(host='https://app.speckle.systems/')
		client = SpeckleClient(host='https://speckle.xyz')
		account = get_default_account()
		client.authenticate_with_account(account)
		if client:
			print(client)
			self.client = client
		else: print('no speckle connection')

	def retrieve(self, stream, commit, branch=None):

		content = self.client.commit.get(stream, commit)
		self.transport = ServerTransport(client=self.client, stream_id=stream)
		result = operations.receive(content.referencedObject, self.transport)

		# bos = BaseObjectSerializer()
		# obj = bos.traverse_base(result)

		# return obj
		return result

	def update(self, obj, message):

		print('preparing and committing ...')
		bos = BaseObjectSerializer()
		# base = bos.recompose_base(obj)
		base = obj
		obj_upd = operations.send(base, [self.transport])

		commit = self.client.commit.create(
		    arg.stream,
		    obj_upd,
		    branch_name = "main",
		    message=message
		)

		print('commit "' + message + '" sent')

import random

spk = Cloud()
obj = spk.retrieve(arg.stream, arg.commit)
stars = obj['@Data']

for i in range(0,637):
	star = stars['@{0;0;0;' + str(i) + '}']
	star[0]['test_val'] = random.randint(1, 100)

# # comitting
spk.update(obj, 'stars upd 01')

print("\n%s sec" % (time.time() - start_time))