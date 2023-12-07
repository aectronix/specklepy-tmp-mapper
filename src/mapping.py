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
from specklepy.objects.other import Collection
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
		    branch_name = "window",
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

def hasLine(lines, line):

	for l in lines:
		if (l and
			l.baseCurve['start']['x'] == line['start']['x'] and l.baseCurve['start']['y'] == line['start']['y'] and l.baseCurve['start']['z'] == line['start']['z'] and
			l.baseCurve['end']['x'] == line['end']['x'] and l.baseCurve['end']['y'] == line['end']['y'] and l.baseCurve['end']['z'] == line['end']['z']
			): return True
	return False


# Establish connections
arc = Archicad(arg.port)
spk = Cloud()

# Get contents
# obj2 = spk.retrieve('aeb487f0e6', 'ea9ee1495e')
obj = spk.retrieve(arg.stream, arg.commit)
selection = arc.com.GetSelectedElements()

pidElevationToHome = [arc.utl.GetBuiltInPropertyId('General_TopElevationToHomeStory')]
pidTopLinkStory = [arc.utl.GetBuiltInPropertyId('General_TopLinkStory')]

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

cc = 0
for s in selection:
	# get main info
	guId = str(s.elementId.guid)
	catIds = arc.com.GetTypesOfElements([s])
	catName = catIds[0].typeOfElement.elementType

	cc += 1

	print('processing ' + str(cc) + '/' + str(len(selection)) + '...') #, end='\r')

	if catName == 'Beam':
		for i in range(0, len(obj['@Beam'])):
			if guId.lower() == obj['@Beam'][i]['applicationId'].lower():

				# print(guId)

				bos = BaseObjectSerializer()
				beam = bos.traverse_base(obj['@Beam'][i])[1]

				beam['category'] = 'Structural Framing'
				beam['family'] = 'RLL_Каркас_Горизонтал_Бетон500'
				beam['builtInCategory'] = 'OST_StructuralFraming'
				beam['type'] = 'Custom'

				beam['speckle_type'] = None
				beam['speckle_type'] = 'Objects.BuiltElements.Column:Objects.BuiltElements.Revit.RevitBeam'

				if not hasLevel(obj['@Levels'], beam['level']['index']):
					level = newLevel(beam['level']['index'], beam['level']['name'], beam['level']['elevation'])
					obj['@Levels'].append(level)

				beam['parameters'] = {}
				beam['parameters']['speckle_type'] = 'Base'
				beam['parameters']['applicationId'] = None

				ay, az = 0, 0
				if   beam['anchorPoint'] == 0: ay = 0; az = 0 # left, top
				elif beam['anchorPoint'] == 1: ay = 1; az = 0 # center, top
				elif beam['anchorPoint'] == 2: ay = 3; az = 0 # right, top

				elif beam['anchorPoint'] == 3: ay = 0; az = 1 # left, center
				elif beam['anchorPoint'] == 4: ay = 1; az = 1 # center, center
				elif beam['anchorPoint'] == 5: ay = 3; az = 1 # right, center

				elif beam['anchorPoint'] == 6: ay = 0; az = 3 # left, bottom
				elif beam['anchorPoint'] == 7: ay = 1; az = 3 # center, bottom
				elif beam['anchorPoint'] == 8: ay = 3; az = 3 # right, bottom

				beam['parameters']['Y_JUSTIFICATION'] = {
					'name': 'y Justification',
					'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
					'applicationId': None,
					'applicationInternalName': 'Y_JUSTIFICATION',
					'applicationUnit': None,
					'applicationUnitType': None,
					'isReadOnly': False,
					'isShared': False,
					'isTypeParameter': False,
					'units': None,
					'value': ay
				}

				beam['parameters']['Z_JUSTIFICATION'] = {
					'name': 'z Justification',
					'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
					'applicationId': None,
					'applicationInternalName': 'Z_JUSTIFICATION',
					'applicationUnit': None,
					'applicationUnitType': None,
					'isReadOnly': False,
					'isShared': False,
					'isTypeParameter': False,
					'units': None,
					'value': az
				}

				beam['parameters']['Y_OFFSET_VALUE'] = {
					'name': 'y Offset Value',
					'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
					'applicationId': None,
					'applicationInternalName': 'Y_OFFSET_VALUE',
					'applicationUnit': 'autodesk.unit.unit:meters-1.0.1',
					'applicationUnitType': None,
					'isReadOnly': False,
					'isShared': False,
					'isTypeParameter': False,
					'units': None,
					'value': beam['offset']
				}

				# repack back
				obj['@Beam'][i] = bos.recompose_base(beam)


	if catName == 'Column':
		for i in range(0, len(obj['@Column'])):
			if guId.lower() == obj['@Column'][i]['applicationId'].lower():

				# print(guId)

				bos = BaseObjectSerializer()
				column = bos.traverse_base(obj['@Column'][i])[1]

				# # update schema
				column['category'] = 'Structural Columns'
				column['builtInCategory'] = 'OST_StructuralColumns'

				column['speckle_type'] = None
				column['speckle_type'] = 'Objects.BuiltElements.Column:Objects.BuiltElements.Revit.RevitColumn'

				column['baseOffset'] = column['bottomOffset']
				nHeight = column['segments']['Segment #1']['assemblySegmentData']['nominalHeight']
				nWidth = column['segments']['Segment #1']['assemblySegmentData']['nominalWidth']

				if column['segments']['Segment #1']['assemblySegmentData']['modelElemStructureType'] == 'Complex Profile':
					column['type'] = column['segments']['Segment #1']['assemblySegmentData']['profileAttrName'] + ' ' + str(nHeight) + 'x' + str(nWidth)
				else:
					column['type'] = column['segments']['Segment #1']['assemblySegmentData']['buildingMaterial'] + ' ' + str(nHeight) + 'x' + str(nWidth)

				# # levels
				column['level']['category'] = 'Levels'
				column['level']['builtInCategory'] = 'OST_Levels'
				column['level']['createView'] = True
				column['level']['referenceOnly'] = False
				column['level']['speckle_type'] = None
				column['level']['speckle_type'] = 'Objects.BuiltElements.Level:Objects.BuiltElements.Revit.RevitLevel'

				if not hasLevel(obj['@Levels'], column['level']['index']):
					level = newLevel(column['level']['index'], column['level']['name'], column['level']['elevation'])
					obj['@Levels'].append(level)

				topLinkStory = arc.com.GetPropertyValuesOfElements([s], pidTopLinkStory)
				if topLinkStory and not hasattr(topLinkStory[0].propertyValues[0], 'error'):
					topLink = re.search(r'Home \+ (\d+).*\((.*?)\)', topLinkStory[0].propertyValues[0].propertyValue.value)
					if topLink:
						index = column['level']['index'] + int(topLink.group(1))
						name = topLink.group(2)
						elevation = column['level']['elevation'] + column['bottomOffset'] + column['height'] - column['topOffset'] 

						topLevel = newLevel(index, name, elevation)
						if not hasLevel(obj['@Levels'], index):
							obj['@Levels'].append(topLevel)
							print('added ' + str(index) + '. ' + name + ' (' + str(elevation) + ')')

						if not 'topLevel' in column:
							top = BaseObjectSerializer()
							column['topLevel'] = top.traverse_base(topLevel)[1]

				# repack back
				obj['@Column'][i] = bos.recompose_base(column)

	if catName == 'Wall':
		for i in range(0, len(obj['@Wall'])):
			if guId.lower() == obj['@Wall'][i]['applicationId'].lower():

				# print(guId)

				bos = BaseObjectSerializer()
				wall = bos.traverse_base(obj['@Wall'][i])[1]

				# levels
				wall['level']['category'] = 'Levels'
				wall['level']['builtInCategory'] = 'OST_Levels'
				wall['level']['createView'] = True
				wall['level']['referenceOnly'] = False

				wall['speckle_type'] = None
				wall['speckle_type'] = 'Objects.BuiltElements.Wall:Objects.BuiltElements.Revit.RevitWall'

				if not hasLevel(obj['@Levels'], wall['level']['index']):
					level = newLevel(wall['level']['index'], wall['level']['name'], wall['level']['elevation'])
					obj['@Levels'].append(level)

				topLinkStory = arc.com.GetPropertyValuesOfElements([s], pidTopLinkStory)
				if topLinkStory and not hasattr(topLinkStory[0].propertyValues[0], 'error'):
					topLink = re.search(r'Home \+ (\d+).*\((.*?)\)', topLinkStory[0].propertyValues[0].propertyValue.value)
					if topLink:
						index = wall['level']['index'] + int(topLink.group(1))
						name = topLink.group(2)
						elevation = wall['level']['elevation'] + wall['baseOffset'] + wall['height'] - wall['topOffset'] 

						topLevel = newLevel(index, name, elevation)
						if not hasLevel(obj['@Levels'], index):
							obj['@Levels'].append(topLevel)
							print('added ' + str(index) + '. ' + name + ' (' + str(elevation) + ')')

						if not 'topLevel' in wall:
							top = BaseObjectSerializer()
							wall['topLevel'] = top.traverse_base(topLevel)[1]
				
				# update schema
				wall['category'] = 'Walls'
				wall['builtInCategory'] = 'OST_Walls'
				wall['family'] = 'Basic Wall'

				if wall['structure'] == 'Basic':
					wall['type'] =  str(wall['thickness']) + ' ' + wall['buildingMaterialName']
				elif wall['structure'] == 'Composite':
					wall['type'] = wall['compositeName']

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
				out = 0
				if wall['offsetFromOutside']:
					out = wall['offsetFromOutside']
				off = 0
				if wall['referenceLineOffset']:
					off = wall['referenceLineOffset']

				if wall['referenceLineLocation'] == 'Center':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 0
				elif wall['referenceLineLocation'] == 'Core Center':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 1

				elif wall['referenceLineLocation'] == 'Outside':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 2
				elif wall['referenceLineLocation'] == 'Core Outside':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 4

				elif wall['referenceLineLocation'] == 'Inside':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 3
				elif wall['referenceLineLocation'] == 'Core Inside':
					wall['parameters']['WALL_KEY_REF_PARAM']['value'] = 5

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
				vw2 = math.sqrt((dx*1000) ** 2 + (dy*1000) ** 2)/1000
				#print('vector: (' + str(vx) + ',' + str(vy) + '), weight: ' + str(vw))

				# vector unit
				ux = vx/vw
				uy = vy/vw

				ux2 = dx/vw2
				uy2 = dy/vw2
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

					if wall['referenceLineStartIndex'] == -1:
						out = out
					if wall['referenceLineStartIndex'] == -3:
						out = t - out
					if wall['referenceLineStartIndex'] == 3:
						out = t - out

					# temp
					if off != 0:
						if wall['referenceLineStartIndex'] == -1:
							off = 0
						if wall['referenceLineStartIndex'] == -3:
							off = 0

					start['x'] = sx + (ux * mod) - (ux * out) - (ux * off)
					end['x'] = ex + (ux * mod) - (ux * out) - (ux * off)
					start['y'] = sy + (uy * mod) - (uy * out) - (uy * off)
					end['y'] = ey + (uy * mod) - (uy * out) - (uy * off)
					
				wall['baseLine']['start']['x'] = start['x']
				wall['baseLine']['end']['x'] = end['x']
				wall['baseLine']['start']['y'] = start['y']
				wall['baseLine']['end']['y'] = end['y']

				# openings
				if wall['elements'] and wall['hasDoor'] == True:

					doors  = arc.com.GetElementsByType('Door')

					for d in doors:

						guId = str(d.elementId.guid)
						for j in range(0, len(wall['elements'])):
							if guId.lower() == wall['elements'][j]['applicationId'].lower():

								door = wall['elements'][j]

								# definition, parameters
								door['category'] = 'Doors'
								door['type'] = door['libraryPart'] + ' - ' + str(door['width']*1000) + 'x' + str(door['height']*1000)
								door['builtInCategory'] = 'OST_Doors'
								door['speckle_type'] = 'Objects.Other.Revit.RevitInstance'

								door['level'] = wall['level']

								door['units'] = 'm'

								door['definition'] = {
									'units': 'm',
									'type': door['type'],
									'category': 'Doors',
									'speckle_type': 'Objects.BuiltElements.Revit.RevitElementType:Objects.BuiltElements.Revit.RevitSymbolElementType',
									'placementType': 'OneLevelBasedHosted',
									'builtInCategory': 'OST_Doors',
								}

								door['transform'] = {
									'units': 'm',
									'speckle_type': 'Objects.Other.Transform',
									'matrix': [
										ux2, 0, 0, 	0 + wall['baseLine']['start']['x'] + door['objLoc'],
										0, uy2, 0, 	0 + wall['baseLine']['start']['y'] - door['objLoc'],
										0, 0, 1,	0 + wall['baseLine']['start']['z'] + door['lower'],

										0, 0, 0,	1
									]
								}

								# door['parameters'] = door2['parameters']

								door['parameters'] = {}
								door['parameters']['speckle_type'] = 'Base'
								door['parameters']['applicationId'] = None

								door['parameters']['MountGap_BM'] = {
									'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
									'applicationId': None,
									'applicationInternalName': 'MountGap_BM',
									'applicationUnit': None,
									'applicationUnitType': 'autodesk.unit.unit:meters-1.0.1',
									'isReadOnly': False,
									'isShared': False,
									'isTypeParameter': False,
									'name': 'MountGap_BM',
									'units': 'm',
									'value': 0
								}

								door['parameters']['MountGap_LTRT'] = {
									'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
									'applicationId': None,
									'applicationInternalName': 'MountGap_LTRT',
									'applicationUnit': None,
									'applicationUnitType': 'autodesk.unit.unit:meters-1.0.1',
									'isReadOnly': False,
									'isShared': False,
									'isTypeParameter': False,
									'name': 'MountGap_LTRT',
									'units': 'm',
									'value': 0
								}

								door['parameters']['MountGap_TP'] = {
									'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
									'applicationId': None,
									'applicationInternalName': 'MountGap_TP',
									'applicationUnit': None,
									'applicationUnitType': 'autodesk.unit.unit:meters-1.0.1',
									'isReadOnly': False,
									'isShared': False,
									'isTypeParameter': False,
									'name': 'MountGap_TP',
									'units': 'm',
									'value': 0
								}

								door['parameters']['TMP_A_Offset'] = {
									'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
									'applicationId': None,
									'applicationInternalName': 'TMP_A_Offset',
									'applicationUnit': None,
									'applicationUnitType': 'autodesk.unit.unit:meters-1.0.1',
									'isReadOnly': False,
									'isShared': False,
									'isTypeParameter': False,
									'name': 'TMP_A_Offset',
									'units': 'm',
									'value': door['revealDepthFromSide']
								}



								wall['elements'][j] = None
								wall['elements'][j] = door


				if wall['elements'] and wall['hasWindow'] == True:

					windows  = arc.com.GetElementsByType('Window')

					for w in windows:

						guId = str(w.elementId.guid)
						for k in range(0, len(wall['elements'])):
							if guId.lower() == wall['elements'][k]['applicationId'].lower():

								window = wall['elements'][k]

								# definition, parameters
								window['category'] = 'Windows'
								window['type'] = window['libraryPart'] + ' - ' + str(window['width']*1000) + 'x' + str(window['height']*1000)
								window['builtInCategory'] = 'OST_Windows'
								window['speckle_type'] = 'Objects.Other.Revit.RevitInstance'

								window['level'] = wall['level']

								window['units'] = 'm'

								window['definition'] = {
									'units': 'm',
									'type': window['type'],
									'category': 'Windows',
									'speckle_type': 'Objects.BuiltElements.Revit.RevitElementType:Objects.BuiltElements.Revit.RevitSymbolElementType',
									'placementType': 'OneLevelBasedHosted',
									'builtInCategory': 'OST_Windows',
								}

								ov = -1 if window['oSide'] == True else 1

								window['transform'] = {
									'units': 'm',
									'speckle_type': 'Objects.Other.Transform',
									'matrix': [
										ux2, 0, 0, 	0 + wall['baseLine']['start']['x'] + window['objLoc'] * ux2,
										0, uy2, 0, 	0 + wall['baseLine']['start']['y'] + window['objLoc'] * uy2,
										0, 0, 1,	0 + wall['baseLine']['start']['z'] + window['lower'],

										0, 0, 0,	1
									]
								}

								window['parameters'] = {}
								window['parameters']['speckle_type'] = 'Base'
								window['parameters']['applicationId'] = None

								window['parameters']['Глубина_вставки_окна'] = {
									'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
									'applicationId': None,
									'applicationInternalName': 'Глубина_вставки_окна',
									'applicationUnit': None,
									'applicationUnitType': 'autodesk.unit.unit:meters-1.0.1',
									'isReadOnly': False,
									'isShared': False,
									'isTypeParameter': False,
									'name': 'Глубина_вставки_окна',
									'units': 'm',
									'value': window['revealDepthFromSide']
								}

								wall['elements'][k] = None
								wall['elements'][k] = window


				# repack back
				obj['@Wall'][i] = bos.recompose_base(wall)


	if catName == 'Slab':
		for i in range(0, len(obj['@Slab'])):
			if guId.lower() == obj['@Slab'][i]['applicationId'].lower():

				# print(guId)

				bos = BaseObjectSerializer()
				slab = bos.traverse_base(obj['@Slab'][i])[1]

				# update schema
				slab['category'] = 'Floors'
				slab['family'] = 'Floor'
				slab['type'] = 'User Custom'
				slab['builtInCategory'] = 'OST_Floors'

				slab['speckle_type'] = None
				slab['speckle_type'] = 'Objects.BuiltElements.Floor:Objects.BuiltElements.Revit.RevitFloor'

				if slab['structure'] == 'Basic':
					slab['type'] =  str(slab['thickness']) + ' ' + slab['buildingMaterialName']
				elif slab['structure'] == 'Composite':
					slab['type'] = slab['compositeName']

				# levels
				slab['level']['category'] = 'Levels'
				slab['level']['builtInCategory'] = 'OST_Levels'
				slab['level']['createView'] = True
				slab['level']['referenceOnly'] = False
				slab['level']['speckle_type'] = None
				slab['level']['speckle_type'] = 'Objects.BuiltElements.Level:Objects.BuiltElements.Revit.RevitLevel'

				if not hasLevel(obj['@Levels'], slab['level']['index']):
					level = newLevel(slab['level']['index'], slab['level']['name'], slab['level']['elevation'])
					obj['@Levels'].append(level)

				# top elevation to home story
				elevationHome = arc.com.GetPropertyValuesOfElements([s], pidElevationToHome)
				elevation = elevationHome[0].propertyValues[0].propertyValue.value
				slab['TopElevationToHomeStory'] = elevation

				slab['parameters'] = {}
				slab['parameters']['speckle_type'] = 'Base'
				slab['parameters']['applicationId'] = None

				slab['parameters']['FLOOR_HEIGHTABOVELEVEL_PARAM'] = {
					'speckle_type': 'Objects.BuiltElements.Revit.Parameter',
					'applicationId': None,
					'applicationInternalName': 'FLOOR_HEIGHTABOVELEVEL_PARAM',
					'applicationUnit': 'autodesk.unit.unit:meters-1.0.1',
					'applicationUnitType': None,
					'isReadOnly': False,
					'isShared': False,
					'isTypeParameter': False,
					'name': 'Height Offset From Level',
					'units': 'm',
					'value': elevation
				}

				# fix position via segments
				for segment in slab['outline']['segments']:
					segment['start']['z'] = slab['level']['elevation'] + elevation
					segment['end']['z'] = slab['level']['elevation'] + elevation

				# repack back
				obj['@Slab'][i] = bos.recompose_base(slab)


	if catName == 'Zone':
		for i in range(0, len(obj['@Zone'])):
			if guId.lower() == obj['@Zone'][i]['applicationId'].lower():

				# print(guId)

				bos = BaseObjectSerializer()
				zone = bos.traverse_base(obj['@Zone'][i])[1]

				zone['type'] = 'Room'
				zone['category'] = 'Rooms'

				if not hasLevel(obj['@Levels'], zone['level']['index']):
					level = newLevel(zone['level']['index'], zone['level']['name'], zone['level']['elevation'])
					obj['@Levels'].append(level)

				# repack back
				obj['@Zone'][i] = bos.recompose_base(zone)

				for segment in zone['outline']['segments']:

					# if not hasLine(obj['@elements'][0]['elements'], segment):
					bbs = BaseObjectSerializer()
					boundry = bbs.traverse_base(Base())[1]

					boundry['level'] = zone['level']
					boundry['units'] = 'm'
					boundry['baseCurve'] = segment
					boundry['speckle_type'] = 'Objects.BuiltElements.Revit.Curve.RoomBoundaryLine'

					obj['@elements'][0]['elements'].append(bbs.recompose_base(boundry))


# reorder levels
obj['@Levels'].sort(key=lambda l: l.index)

# comitting
spk.update(obj, 'window 1a1')

print("\n%s sec" % (time.time() - start_time))