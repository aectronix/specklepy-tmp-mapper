import argparse
import json
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

SCHEMA = {
	'WALL_REF': {
		'Inside': [
			{ 'value': 3, 'name': 'Finish Face: Interior' },
			{ 'value': 5, 'name': 'Core Face: Interior' }
		],
		'Center': [
			{ 'value': 0, 'name': 'Wall Centerline' },
			{ 'value': 1, 'name': 'Core Centerline' }
		],
		'Outside': [
			{ 'value': 2, 'name': 'Finish Face: Exterior' },
			{ 'value': 4, 'name': 'Core Face: Exterior' }
		],
	}
}

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

		bos = BaseObjectSerializer()
		obj = bos.traverse_base(result)

		return obj

	def update(self, obj, message):

		print('preparing and committing ...')
		base = BaseObjectSerializer().recompose_base(obj[1])
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

# Get contents
obj = spk.retrieve(arg.stream, arg.commit)
selection = arc.com.GetSelectedElements()

# print(obj[1]['elements'][0]['elements'][0]['parameters'])

for s in selection:
	# get main info
	guId = str(s.elementId.guid)
	catIds = arc.com.GetTypesOfElements([s])
	catName = catIds[0].typeOfElement.elementType

	if catName == 'Wall':
		i = 0
		for wall in obj[1]['@Wall']:
			appId = wall['applicationId']
			if guId.lower() == appId.lower():
				print(guId)
				# update schema
				obj[1]['@Wall'][i]['category'] = 'Walls'
				obj[1]['@Wall'][i]['family'] = 'Basic Wall'
				obj[1]['@Wall'][i]['type'] = 'Wall - Custom'

				obj[1]['@Wall'][i]['parameters'] = {}
				obj[1]['@Wall'][i]['parameters']['speckle_type'] = 'Base'
				obj[1]['@Wall'][i]['parameters']['applicationId'] = None

				obj[1]['@Wall'][i]['parameters']['WALL_KEY_REF_PARAM'] = {}
				obj[1]['@Wall'][i]['parameters']['WALL_KEY_REF_PARAM'] = {
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
				}

				# retrieve baseline geometry
				t = obj[1]['@Wall'][i]['thickness']
				sx = obj[1]['@Wall'][i]['baseLine']['start']['x']
				sy = obj[1]['@Wall'][i]['baseLine']['start']['y']
				sz = obj[1]['@Wall'][i]['baseLine']['start']['z']
				ex = obj[1]['@Wall'][i]['baseLine']['end']['x']
				ey = obj[1]['@Wall'][i]['baseLine']['end']['y']
				ez = obj[1]['@Wall'][i]['baseLine']['end']['z']
				mod = 0

				# define baseline positions
				if obj[1]['@Wall'][i]['referenceLineLocation'] == 'Inside':
					if obj[1]['@Wall'][i]['referenceLineStartIndex'] == -1:
						obj[1]['@Wall'][i]['parameters']['WALL_KEY_REF_PARAM']['value'] = 4
						mod = t/2
					elif obj[1]['@Wall'][i]['referenceLineStartIndex'] == -3:
						obj[1]['@Wall'][i]['parameters']['WALL_KEY_REF_PARAM']['value'] = 5
						mod = t/2 * -1

				if obj[1]['@Wall'][i]['referenceLineLocation'] == 'Center':
					obj[1]['@Wall'][i]['parameters']['WALL_KEY_REF_PARAM']['value'] = 1

				if obj[1]['@Wall'][i]['referenceLineLocation'] == 'Outside':
					if obj[1]['@Wall'][i]['referenceLineStartIndex'] == 3:
						obj[1]['@Wall'][i]['parameters']['WALL_KEY_REF_PARAM']['value'] = 2
						mod = t/2
					elif obj[1]['@Wall'][i]['referenceLineStartIndex'] == 1:
						mod = t/2 * -1
						obj[1]['@Wall'][i]['parameters']['WALL_KEY_REF_PARAM']['value'] = 4

				# strange workaround:
				# we have to completely delete and recreate endpoints,
				# in other case they will be stuck for some reason...
				del obj[1]['@Wall'][i]['baseLine']['start']
				del obj[1]['@Wall'][i]['baseLine']['end']

				obj[1]['@Wall'][i]['baseLine']['start'] = {
					'x': sx + mod,
					'y': sy,
					'z': sz,
					'speckle_type': 'Objects.Geometry.Point',
					'units': 'm'
				}

				obj[1]['@Wall'][i]['baseLine']['end'] = {
					'x': ex + mod,
					'y': ey,
					'z': ez,
					'speckle_type': 'Objects.Geometry.Point',
					'units': 'm'
				}

			i += 1

spk.update(obj, 'walls 001b1')