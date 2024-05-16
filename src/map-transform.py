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
		    branch_name = "test",
		    message=message
		)

		print('commit "' + message + '" sent')


def newLevel(index, name, elevation):

	bos = BaseObjectSerializer()
	level = bos.traverse_base(Base())[1]

	level['index'] = index
	level['name'] = name
	level['elevation'] = elevation
	level['units'] = 'm'
	level['category'] = 'Levels'
	level['createView'] = True
	level['speckle_type'] = 'Objects.BuiltElements.Level:Objects.BuiltElements.Revit.RevitLevel'
	level['referenceOnly'] = False
	level['builtInCategory'] = 'OST_Levels'

	return bos.recompose_base(level)

def hasLevel(levels, index):

	for l in levels:
		if l and l.index == index:
			return True
	return False


# Establish connections
arc = Archicad(arg.port)
spk = Cloud()

# Get contents
# obj2 = spk.retrieve('aeb487f0e6', 'ea9ee1495e')
obj = spk.retrieve(arg.stream, arg.commit)
selection = arc.com.GetSelectedElements()

pidElementID = [arc.utl.GetBuiltInPropertyId('General_ElementID')]
pidParentID = [arc.utl.GetBuiltInPropertyId('IdAndCategories_ParentId')]
pidElevationToHome = [arc.utl.GetBuiltInPropertyId('General_TopElevationToHomeStory')]
pidTopLinkStory = [arc.utl.GetBuiltInPropertyId('General_TopLinkStory')]
pidHeight = [arc.utl.GetBuiltInPropertyId('General_Height')]
pidThickness = [arc.utl.GetBuiltInPropertyId('Geometry_OpeningTotalThickness')]
pidBottomELevation = [arc.utl.GetBuiltInPropertyId('General_BottomElevationToHomeStory')]

pidTemp = [arc.utl.GetBuiltInPropertyId('IdAndCategories_ParentId')]

obj['@Levels'] = []
obj['@elements'] = []

# separator lines
bos = BaseObjectSerializer()
lines = bos.traverse_base(Base())[1]
lines['name'] = 'Room Separation Lines'
lines['speckle_type'] = 'Speckle.Core.Models.Collection'
lines['applicationId'] = 'Room Separation Lines'
lines['collectionType'] = 'Revit Category'
lines['elements'] = []

obj['@elements'].append(bos.recompose_base(lines))

# openings
bos = BaseObjectSerializer()
shafts = bos.traverse_base(Base())[1]
shafts['name'] = 'Shaft Opening'
shafts['speckle_type'] = 'Speckle.Core.Models.Collection'
shafts['applicationId'] = 'Shaft Opening'
shafts['collectionType'] = 'Revit Category'
shafts['elements'] = []

obj['@elements'].append(bos.recompose_base(shafts))


# openings  = arc.com.GetElementsByType('Opening')
# print(openings)

doors  = arc.com.GetElementsByType('Door')
windows  = arc.com.GetElementsByType('Window')
openings  = arc.com.GetElementsByType('Opening')

cc = 0

catIds = arc.com.GetTypesOfElements(selection)

for s in catIds:
	# get main info
	# guId = str(s.elementId.guid)
	print(s)
# 	catIds = arc.com.GetTypesOfElements([s])
# 	catName = catIds[0].typeOfElement.elementType

# 	cc += 1

# 	print('processing ' + str(cc) + '/' + str(len(selection)) + '...', end='\r')


# 	if catName == 'Wall':
# 		for i in range(0, len(obj['@Wall'])):
# 			if guId.lower() == obj['@Wall'][i]['applicationId'].lower():

# 				# print(guId)

# 				bos = BaseObjectSerializer()
# 				wall = bos.traverse_base(obj['@Wall'][i])[1]

# 				# levels
# 				wall['level']['category'] = 'Levels'
# 				wall['level']['builtInCategory'] = 'OST_Levels'
# 				wall['level']['createView'] = True
# 				wall['level']['referenceOnly'] = False

# 				wall['speckle_type'] = None
# 				wall['speckle_type'] = 'Objects.BuiltElements.Wall:Objects.BuiltElements.Revit.RevitWall'

# 				if not hasLevel(obj['@Levels'], wall['level']['index']):
# 					level = newLevel(wall['level']['index'], wall['level']['name'], wall['level']['elevation'])
# 					obj['@Levels'].append(level)

# 				topLinkStory = arc.com.GetPropertyValuesOfElements([s], pidTopLinkStory)
# 				if topLinkStory and not hasattr(topLinkStory[0].propertyValues[0], 'error'):
# 					topLink = re.search(r'Home \+ (\d+).*\((.*?)\)', topLinkStory[0].propertyValues[0].propertyValue.value)
# 					if topLink:
# 						index = wall['level']['index'] + int(topLink.group(1))
# 						name = topLink.group(2)
# 						elevation = wall['level']['elevation'] + wall['baseOffset'] + wall['height'] - wall['topOffset'] 

# 						topLevel = newLevel(index, name, elevation)
# 						if not hasLevel(obj['@Levels'], index):
# 							obj['@Levels'].append(topLevel)
# 							#print('added ' + str(index) + '. ' + name + ' (' + str(elevation) + ')')

# 						if not 'topLevel' in wall:
# 							top = BaseObjectSerializer()
# 							wall['topLevel'] = top.traverse_base(topLevel)[1]
				
# 				# update schema
# 				wall['category'] = 'Walls'
# 				wall['builtInCategory'] = 'OST_Walls'
# 				wall['family'] = 'Basic Wall'

# 				if wall['structure'] == 'Basic':
# 					wall['type'] =  str(wall['thickness']) + ' ' + wall['buildingMaterialName']
# 				elif wall['structure'] == 'Composite':
# 					wall['type'] = wall['compositeName']

# 				wall['parameters'] = {}
# 				wall['parameters']['speckle_type'] = 'Base'
# 				wall['parameters']['applicationId'] = None

# 				# insert location line parameter
# 				wall['parameters']['WALL_KEY_REF_PARAM'] = {}
# 				wall['parameters']['WALL_KEY_REF_PARAM'] = {
# 					'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
# 					'applicationId': None,
# 					'applicationInternalName': 'WALL_KEY_REF_PARAM',
# 					'applicationUnit': None,
# 					'applicationUnitType': None,
# 					'isReadOnly': False,
# 					'isShared': False,
# 					'isTypeParameter': False,
# 					'name': 'Location Line',
# 					'units': None,
# 					'value': 0
# 				}

# 				transform = Transform()
# 				transform.units = 'm'

# 				matrix = list(range(16))
# 				matrix[0]  = 1
# 				matrix[1]  = 0
# 				matrix[2]  = 0
# 				matrix[3]  = 5
# 				matrix[4]  = 0
# 				matrix[5]  = 0
# 				matrix[6]  = 0
# 				matrix[7]  = 0
# 				matrix[8]  = 0
# 				matrix[9]  = 0
# 				matrix[10] = 0
# 				matrix[11] = 0
# 				matrix[12] = 0
# 				matrix[13] = 0
# 				matrix[14] = 0
# 				matrix[15] = 1

# 				transform.matrix = matrix

# 				tos = BaseObjectSerializer()
# 				tf = tos.traverse_base(transform)[1]
# 				# print(transform)

# 				obj['transform'] = transform

# 				# wall['transform'] = transform
# 				# wall['transform'] = tf
# 				# wall['transform'] = tos.traverse_base(transform)[1]

# 				# repack back
# 				obj['@Wall'][i] = bos.recompose_base(wall)

# 				obj['@Wall'][i]['tranform'] = tos.recompose_base(tf)




# # reorder levels
# obj['@Levels'].sort(key=lambda l: l.index)

# # comitting
# spk.update(obj, 'test 1e')

print("\n%s sec" % (time.time() - start_time))