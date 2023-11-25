import argparse
import json
import math
import time

from specklepy.api import operations
from specklepy.api.client import SpeckleClient
from specklepy.api.credentials import get_default_account
from specklepy.api.credentials import get_local_accounts
from specklepy.objects.base import Base
from specklepy.objects.geometry import Point
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
		    branch_name = "wall",
		    message=message
		)

		print('commit "' + message + '" sent')



# Establish connections
arc = Archicad(arg.port)
spk = Cloud()

# Get contents
obj = spk.retrieve(arg.stream, arg.commit)
selection = arc.com.GetSelectedElements()

# print(obj['elements'][0]['elements'][0])

# bos = BaseObjectSerializer()
# wall = bos.traverse_base(obj['elements'][0]['elements'][0])[1]
# print(wall['parameters'])

# Add level structure
obj['@Levels'] = []

for s in selection:
	# get main info
	guId = str(s.elementId.guid)
	catIds = arc.com.GetTypesOfElements([s])
	catName = catIds[0].typeOfElement.elementType

	if catName == 'Wall':
		for i in range(0, len(obj['@Wall'])):
			if guId.lower() == obj['@Wall'][i]['applicationId'].lower():

				print(guId)

				bos = BaseObjectSerializer()
				wall = bos.traverse_base(obj['@Wall'][i])[1]
				# wall = obj['@Wall'][i]

				# update schema
				wall['category'] = 'Walls'
				wall['family'] = 'Basic Wall'
				wall['type'] = wall['structure'] + ' Structure'

				wall['parameters'] = {}
				wall['parameters']['speckle_type'] = 'Base'
				wall['parameters']['applicationId'] = None

				# levels
				wall['level']['category'] = 'Levels'
				wall['level']['builtInCategory'] = 'OST_Levels'
				wall['level']['createView'] = True
				wall['level']['referenceOnly'] = False

				if not any(level.id == wall['level']['id'] for level in obj['@Levels']):

					print('added ' + wall['level']['name'] + ' story')

					level_bos = BaseObjectSerializer()
					level = level_bos.traverse_base(Base())[1]

					level['id'] = wall['level']['id']
					level['name'] = wall['level']['name']
					level['index'] = wall['level']['index']
					level['units'] = wall['level']['units']
					level['category'] = 'Levels'
					level['elevation'] = wall['level']['elevation']
					level['createView'] = True
					level['speckle_type'] = 'Objects.BuiltElements.Level:Objects.BuiltElements.Revit.RevitLevel'
					level['referenceOnly'] = False
					level['builtInCategory'] = 'OST_Levels'

					obj['@Levels'].append(level_bos.recompose_base(level))


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
				out = 0
				if wall['offsetFromOutside']:
					out = wall['offsetFromOutside']
				# out = t/2 - wall['offsetFromOutside']
				off = 0
				if wall['referenceLineOffset']:
					off = wall['referenceLineOffset']
					# off = wall['referenceLineOffset']

				print(wall['referenceLineLocation'])
				print(wall['referenceLineStartIndex'])
				print(wall['referenceLineOffset'])

				if wall['referenceLineLocation'] == 'Center':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 0

				elif wall['referenceLineLocation'] == 'Outside':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 2

				elif wall['referenceLineLocation'] == 'Inside':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 3

				# try to get a vector
				#print('line: (' + str(wall['baseLine']['start']['x']) + ',' + str(wall['baseLine']['start']['y']) + ') -> (' + str(wall['baseLine']['end']['x']) + ',' + str(wall['baseLine']['end']['y']) + ')')

				start = { 'x': sx, 'y': sy }
				end = { 'x': ex, 'y': ey }

				# vector deltas
				dx = ex - sx
				dy = ey - sy
				#print('delta: (' + str(dx) + ',' + str(dy) + ')')

				# vector
				vx = -dy
				vy = dx

				# vector weight
				vw = math.sqrt((vx*1000) ** 2 + (vy*1000) ** 2)/1000
				#print('vector: (' + str(vx) + ',' + str(vy) + '), weight: ' + str(vw))

				# vector unit
				ux = vx/vw
				uy = vy/vw
				#print('unitv: (' + str(ux) + ',' + str(uy) + ')')

				# Regular basic walls
				if wall['structure'] == 'Basic' and not wall['referenceLineLocation'] == 'Center':

					if wall['referenceLineLocation'] == 'Inside' and wall['referenceLineStartIndex'] == -1:
						mod = -mod
						off = -off
					if wall['referenceLineLocation'] == 'Outside' and wall['referenceLineStartIndex'] == 3:
						mod = -mod
						off = -off

					if wall['referenceLineLocation'] == 'Outside' and wall['referenceLineStartIndex'] == -3:
						if off > 0:
							off = t - off
						elif off < 0:
							off = 1 * (t - off)

					# if not wall['referenceLineLocation'] == 'Center':
					start['x'] = sx + (ux * mod) - (ux * off)
					end['x'] = ex + (ux * mod) - (ux * off)
					start['y'] = sy + (uy * mod) - (uy * off)
					end['y'] = ey + (uy * mod) - (uy * off)

				# Composite cases
				if wall['structure'] == 'Composite' and not wall['referenceLineLocation'] == 'Center':

					if wall['referenceLineLocation'] == 'Core Center':

						if wall['referenceLineStartIndex'] == -1:
							out = out
						if wall['referenceLineStartIndex'] == -3:
							out = t - out

					# if wall['referenceLineLocation'] == 'Inside' and wall['referenceLineStartIndex'] == -1:
					# 	mod = -mod
					# if wall['referenceLineLocation'] == 'Outside' and wall['referenceLineStartIndex'] == 3:
					# 	mod = -mod

					# if wall['referenceLineStartIndex'] == -1:
					# 	out = -out
					# if wall['referenceLineStartIndex'] == 3:
					# 	out = -out

					# if wall['referenceLineLocation'] == 'Outside':
					# 	out = -out # strange but works

					if wall['referenceLineLocation'] == 'Inside' or wall['referenceLineLocation'] == 'Core Inside':
						off = 0
					elif wall['referenceLineLocation'] == 'Outside' or wall['referenceLineLocation'] == 'Core Outside':
						off = 0

					start['x'] = sx + (ux * mod) - (ux * out)
					end['x'] = ex + (ux * mod) - (ux * out)
					start['y'] = sy + (uy * mod) - (uy * out)
					end['y'] = ey + (uy * mod) - (uy * out)

					# start['x'] = sx - (ux * out) - (ux * off)
					# end['x'] = ex - (ux * out) - (ux * off)
					# start['y'] = sy - (uy * out) - (uy * off)
					# end['y'] = ey - (uy * out) - (uy * off)
					

				wall['baseLine']['start']['x'] = start['x']
				wall['baseLine']['end']['x'] = end['x']
				wall['baseLine']['start']['y'] = start['y']
				wall['baseLine']['end']['y'] = end['y']

				# print('result: (' + str(wall['baseLine']['start']['x']) + ',' + str(wall['baseLine']['start']['y']) + ') -> (' + str(wall['baseLine']['end']['x']) + ',' + str(wall['baseLine']['end']['y']) + ')')

				# repack back
				# obj['@Wall'][i] = wall
				obj['@Wall'][i] = bos.recompose_base(wall)

	# if catName == 'Slab':
	# 	for i in range(0, len(obj['@Slab'])):
	# 		if guId.lower() == obj['@Slab'][i]['applicationId'].lower():

	# 			print(guId)

	# 			bos = BaseObjectSerializer()
	# 			slab = bos.traverse_base(obj['@Slab'][i])[1]
	# 			# wall = obj['@Wall'][i]

	# 			# update schema
	# 			slab['category'] = 'Floors'
	# 			slab['family'] = 'Floor'
	# 			slab['type'] = 'User Custom'

	# 			# levels
	# 			slab['level']['category'] = 'Levels'
	# 			slab['level']['builtInCategory'] = 'OST_Levels'
	# 			slab['level']['createView'] = True
	# 			slab['level']['referenceOnly'] = False

	# 			for s in range(0, len(slab['outline']['segments'])):
	# 				slab['outline']['segments'][s]['start']['z'] = 2
	# 				slab['outline']['segments'][s]['end']['z'] = 2


	# 			# repack back
	# 			obj['@Slab'][i] = bos.recompose_base(slab)

# comitting
spk.update(obj, 'w 1a9')
