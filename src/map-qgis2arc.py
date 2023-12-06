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
		    branch_name = "map",
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
	level['speckle_type'] = 'Objects.BuiltElements.Level:Objects.BuiltElements.Archicad.ArchicadLevel'

	return bos.recompose_base(level)

def newSegment(start_x, start_y, start_z, end_x, end_y, end_z):

	bos = BaseObjectSerializer()
	segment = bos.traverse_base(Base())[1]
	segment['start'] = {
		'x': start_x,
		'y': start_y,
		'z': start_z,
		'units': 'm',
		'speckle_type': 'Objects.Geometry.Point'
	}
	segment['end'] = {
		'x': end_x,
		'y': end_y,
		'z': end_z,
		'units': 'm',
		'speckle_type': 'Objects.Geometry.Point'
	}
	segment['units'] = 'm'
	segment['speckle_type'] = 'Objects.Geometry.Line'

	return bos.recompose_base(segment)

def newPolySegment(start_x, start_y, start_z, end_x, end_y, end_z):

	bos = BaseObjectSerializer()
	segment = bos.traverse_base(Base())[1]
	segment['arcAngle'] = 0
	segment['startPoint'] = {
		'x': start_x,
		'y': start_y,
		'z': start_z,
		'units': 'm',
		'speckle_type': 'Objects.Geometry.Point'
	}
	segment['endPoint'] = {
		'x': end_x,
		'y': end_y,
		'z': end_z,
		'units': 'm',
		'speckle_type': 'Objects.Geometry.Point'
	}
	segment['units'] = 'm'
	segment['speckle_type'] = 'Objects.BuiltElements.Archicad.ElementShape+PolylineSegment'

	return bos.recompose_base(segment)

def newSlab(thickness):

	bos = BaseObjectSerializer()
	slab = bos.traverse_base(Base())[1]

	slab['level'] = {}
	slab['units'] = 'm'
	slab['structure'] = 'Basic'
	slab['thickness'] = thickness
	slab['elementType'] = 'Slab'
	slab['speckle_type'] = 'Objects.BuiltElements.Floor:Objects.BuiltElements.Archicad.ArchicadFloor'
	slab['useFloorFill'] = False
	slab['edgeAngleType'] = 'Perpendicular'
	slab['buildingMaterialName'] = 'GENERIC - INTERNAL CLADDING'
	slab['referencePlaneLocation'] = 'Bottom'
	slab['outline'] = {
		'units': 'm',
		'closed': True,
		'speckle_type': 'Objects.Geometry.Polycurve',
		'segments': []
	}
	slab['shape'] = {
		'speckle_type': 'Objects.BuiltElements.Archicad.ElementShape',
		'contourPolyline': {
			'units': 'm',
			'speckle_type': 'Objects.BuiltElements.Archicad.ElementShape+Polyline',
			'polylineSegments': []
		}

	}

	return bos.recompose_base(slab)



# Establish connections
arc = Archicad(arg.port)
spk = Cloud()

print('retrieving commit data... ', end=' ', flush=True)
obj = spk.retrieve(arg.stream, arg.commit)
print(str(len(obj['elements'][0]['elements'])) + ' polygon objects found')
obj['@Slab'] = []

# temporary offset
off_x = 323700
off_y = 6659600

for i in range(0, len(obj['elements'][0]['elements'])):
	# if i < 1:

	print('processing ' + str(i) + '/' + str(len(obj['elements'][0]['elements'])) + '...', end='\r')

	bos = BaseObjectSerializer()
	poly = bos.traverse_base(obj['elements'][0]['elements'][i])[1]

	if poly:
		if poly['geometry'][0]['displayValue']:
			vertices = poly['geometry'][0]['displayValue'][0]['vertices']
		if poly['attributes']:
			attributes = poly['attributes']

	z_min = attributes['H_DTM_MIN']

	slab = newSlab(attributes['H_DSM_MAX'] - attributes['H_DTM_MIN'])
	slab['level'] = newLevel(0, 'Ground Floor', 0)
	if poly and poly['geometry'][0]['displayValue']:
		slab['displayValue'] = poly['geometry'][0]['displayValue']
		slab['height'] = attributes['H_DSM_MAX'] - attributes['H_DTM_MIN']

	pointsBase = []
	points = []
	unique = set()

	# take only base
	for v in range(0, len(vertices), 3):
		if vertices[v+2] == 0:
			pointsBase.append({'x': vertices[v], 'y': vertices[v+1], 'z': vertices[v+2]})

	# filter out duplicated points
	for point in pointsBase:
		p = (point['x'], point['y'], point['z'])
		if p not in unique:
			unique.add(p)
			points.append({'x': point['x']-off_x, 'y': point['y']-off_y, 'z': point['z']})

	# build segments
	for p in range(0, len(points)-1):
		slab['outline']['segments'].append(newSegment(points[p]['x'], points[p]['y'], z_min,	points[p+1]['x'], points[p+1]['y'], z_min))
		slab['shape']['contourPolyline']['polylineSegments'].append(newPolySegment(points[p]['x'], points[p]['y'], z_min,	points[p+1]['x'], points[p+1]['y'], z_min))

	slab['outline']['segments'].append(newSegment(points[-1]['x'], points[-1]['y'], points[-1]['z'],	points[0]['x'], points[0]['y'], points[0]['z']))
	slab['shape']['contourPolyline']['polylineSegments'].append(newPolySegment(points[-1]['x'], points[-1]['y'], z_min,	points[0]['x'], points[0]['y'], z_min))

	bos = BaseObjectSerializer()
	slab = bos.traverse_base(slab)[1]
	slab = (bos.recompose_base(slab))

	del pointsBase
	del points
	del unique

	obj['@Slab'].append(slab)


# erase
obj['elements'] = None

# comitting
spk.update(obj, 'oostende')

print("\n%s sec" % (time.time() - start_time))



