import argparse
import json
import math
import time

from specklepy.api import operations
from specklepy.api.client import SpeckleClient
from specklepy.api.credentials import get_default_account
from specklepy.api.credentials import get_local_accounts
from specklepy.objects.base import Base
from specklepy.transports.server import ServerTransport
from specklepy.serialization.base_object_serializer import BaseObjectSerializer

from archicad import ACConnection
# from archicad.releases.ac26.b3000types import ErrorItem
# from archicad.releases.ac26.b3000types import BuiltInPropertyUserId

start_time = time.time()

cmd = argparse.ArgumentParser()
cmd.add_argument('-s', '--stream', required=False, help='stream id')
cmd.add_argument('-c', '--commit', required=False, help='commit id')
cmd.add_argument('-p', '--port', required=False, help='ac port')
arg = cmd.parse_args()


class Archicad():

	def __init__(self, port=19723):

		self.port = 19723 if not port else port
		self.com = None
		self.utl = None

		self.connect()

	def connect(self):

		con = ACConnection.connect(int(self.port))
		commands = con.commands
		utils = con.utilities
		if commands.IsAlive():
			print('Archicad' + str(commands.GetProductInfo()))
			self.com = commands
			self.utl = utils
		else: print('no archicad connection')


class Cloud():

	def __init__(self):

		self.client = None
		self.transport = None

		self.connect()

	def connect(self):

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
		    branch_name = "map",
		    message=message
		)

		print('commit "' + message + '" sent')


# Establish connections
arc = Archicad(arg.port)
spk = Cloud()
bos = BaseObjectSerializer()

# Get contents
obj = spk.retrieve(arg.stream, arg.commit)
selection = arc.com.GetSelectedElements()

for s in selection:
	# get main info
	guId = str(s.elementId.guid)
	catIds = arc.com.GetTypesOfElements([s])
	catName = catIds[0].typeOfElement.elementType

	if catName == 'Wall':
		for i in range(0, len(obj['@Wall'])):
			if guId.lower() == obj['@Wall'][i]['applicationId'].lower():

				print(guId)
				# wall = bos.traverse_base(obj['@Wall'][i])[1]
				wall = obj['@Wall'][i]

				# update schema
				wall['category'] = 'Walls'
				wall['family'] = 'Basic Wall'
				wall['type'] = 'User Custom'

				wall['parameters'] = {}
				wall['parameters']['speckle_type'] = 'Base'
				wall['parameters']['applicationId'] = None

				# insert location line parameter
				wall['parameters']['WALL_KEY_REF_PARAM'] = {}
				wall['parameters']['WALL_KEY_REF_PARAM'] = {
					'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
					'applicationId': None,
					'applicationInternalName': 'WALL_KEY_REF_PARAM',
					'applicationUnit': None,
					'applicationUnitType': None,
					'isReadOnly': False,
					'isShared': False,
					'isTypeParameter': False,
					'name': 'Location Line',
					'units': None,
					'value': 0
				}

				# get baseline geometry
				t  = wall['thickness']
				sx = wall['baseLine']['start']['x']
				sy = wall['baseLine']['start']['y']
				sz = wall['baseLine']['start']['z']
				ex = wall['baseLine']['end']['x']
				ey = wall['baseLine']['end']['y']
				ez = wall['baseLine']['end']['z']
				mod = t/2

				if wall['referenceLineLocation'] == 'Inside' and wall['referenceLineStartIndex'] == -1:
					mod = -mod

				if wall['referenceLineLocation'] == 'Outside' and wall['referenceLineStartIndex'] == 3:
					mod = -mod

				print(wall['referenceLineLocation'])
				print(wall['referenceLineStartIndex'])

				if wall['referenceLineLocation'] == 'Center':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 0

				elif wall['referenceLineLocation'] == 'Outside':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 2

				elif wall['referenceLineLocation'] == 'Inside':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 3

				# try to get a vector
				print('line: (' + str(wall['baseLine']['start']['x']) + ',' + str(wall['baseLine']['start']['y']) + ') -> (' + str(wall['baseLine']['end']['x']) + ',' + str(wall['baseLine']['end']['y']) + ')')

				# vector deltas
				dx = ex - sx
				dy = ey - sy
				print('delta: (' + str(dx) + ',' + str(dy) + ')')

				vx = -dy
				vy = dx

				vw = math.sqrt((vx*1000) ** 2 + (vy*1000) ** 2)/1000
				print('vector: (' + str(vx) + ',' + str(vy) + '), weight: ' + str(vw))

				ux = vx/vw
				uy = vy/vw
				print('unitv: (' + str(ux) + ',' + str(uy) + ')')

				line = bos.traverse_base(obj['@Wall'][i]['baseLine'])[1]
				if not wall['referenceLineLocation'] == 'Center':
					# wall['baseLine']['start']['x'] = sx + 1
					# wall['baseLine']['end']['x'] = ex + 1
					# wall['baseLine']['start']['y'] = sy
					# wall['baseLine']['end']['y'] = ey

					# line['start']['x'] = sx + (ux * mod)
					# line['end']['x'] = ex + (ux * mod)
					# line['start']['y'] = sy + (uy * mod)
					# line['end']['y'] = ey + (uy * mod)

					line['start']['x'] = sx + 1
					line['end']['x'] = ex + 1
					line['start']['y'] = sy + 1
					line['end']['y'] = ey + 1

				wall['baseLine'] = bos.recompose_base(line)

				print('result: (' + str(wall['baseLine']['start']['x']) + ',' + str(wall['baseLine']['start']['y']) + ') -> (' + str(wall['baseLine']['end']['x']) + ',' + str(wall['baseLine']['end']['y']) + ')')

				# repack back
				# obj['@Wall'][i] = bos.recompose_base(wall)

# comitting
spk.update(obj, '001c1')