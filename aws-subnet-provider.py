#!/usr/bin/env python
# this can be used to generate available cidr spaces based on addresses used in aws
# by using separate cache files it can be used as an intermediate source between ansible and terraform
# use as an ansible lookup script via pipe
from netaddr import IPNetwork
import sys
import json
import os
import re
import boto3
from botocore.exceptions import ClientError
import copy
import uuid
import time

entity = json.load(sys.stdin)
if 'prefix' in entity:
	prefix = int(entity['prefix'])
else:
	prefix = 26

global bugout
bugout = ""
if 'bug' in entity:
	bug = True
else:
	bug = False

bugout += "%s\n" % (json.dumps(entity, indent=4))

if 'cache' in entity:
	CACHE = entity['cache']
	bugout += "using cache override: %s\n" % (CACHE)
else:
	CACHE = "./aws-cidr-cli.cache"
	bugout += "Cache override not set, using: %s\n" % (CACHE)

if os.path.isfile(CACHE):
    with open(CACHE) as data_file:
        cachedata = json.load(data_file)
else:
    cachedata = {}

bugout += "phase 1 cache: %s\n" % (json.dumps(cachedata, indent=4))

def writecache(data):
    try:
        with open(CACHE, 'w') as outfile:
                    json.dump(data, outfile)
    except:
        bugout += "ERROR: cache %s creation failed!\n" % CACHE

class AutoVivification(dict):
	'''Implementation of perl's autovivification feature'''
	def __getitem__(self, item):
		try:
			return dict.__getitem__(self, item)
		except KeyError:
			value = self[item] = type(self)()
			return value

def get_aws_subnets():
    # """Get AWS info for vpc and vpc subnets and pack them into a dictionary"""
	try:
	    ec2c = boto3.client('ec2')
	    regions = ec2c.describe_regions()
	    data = AutoVivification()
	    for region in regions['Regions']:
	        ec2 = boto3.resource('ec2', region_name=region['RegionName'])
	        vpcs = ec2.vpcs.all()
	        for vpc in vpcs:
	            nvpc = ec2.Vpc(vpc.id)
	            subnet_iterator = nvpc.subnets.all()
	            for subnet in subnet_iterator:
	                    hastags = False
	                    alltags = "TAGS="
	                    if subnet.tags:
	                        hastags = True
	                        for tag in subnet.tags:
	                            alltags += "%s:%s," % (tag['Key'], tag['Value'])
	                    if hastags:
	                            data[vpc.cidr_block][subnet.cidr_block] = alltags
	                    else:
	                        if subnet.cidr_block not in data.get(vpc.cidr_block, {}):
	                            data[vpc.cidr_block][subnet.cidr_block] = "unset"
	    return data
	except Exception as e:
		print(e)

def get_used_ips(subnets):
	'''Take a list of subnets and return a list of ips in those subnets'''
	x = []
	for cached in cachedata.keys():
		ip = IPNetwork(cachedata[cached])
		x += list(ip)
	for cidr in subnets:
		ip = IPNetwork(cidr)
		x += list(ip)
	return sorted(x)

def next_available(entity, label, bugout):
  '''get the next free subnet in a cidr'''
  # get all the used ranges via AWS api
  awsnets = get_aws_subnets()
  awslist = awsnets[entity['vpc']].keys()
  used = get_used_ips(awslist)
  # calculate all the subnets in the cidr we want space in by prefix
  ss = IPNetwork(entity['vpc'])
  subnets = list(ss.subnet(prefix))
  # get 'range' number of free subnets
  found = False
  for s in subnets:
        ips = IPNetwork(s)
        subnet = list(ips)
        if set(used).isdisjoint(subnet):
            bugout += "## %s not used!!!!!!!!!!\n" % str(s)
            found = str(s)
            break
	# we put found down here because if we go through all the subnets and we still haven't found something
	# we have a problem
  if found:
	used += get_used_ips([found])
	bugout += "%s: %s\n" % (label, found)
	cachedata[label] = found
	bugout += "Use: %s\n" % found
	writecache(cachedata)
	return found
  else:
	sys.exit("ERROR: we might we out of ranges?")

if 'printinfo' in entity:
	print json.dumps(get_aws_subnets(), indent=4, sort_keys=True)
else:
	x = {}
	bugout += "phase 2 cache: %s\n" % (json.dumps(cachedata, indent=4))
	for i in entity['label'].split(","):
		bugout += "proceessing: %s\n" % i
		bugout += "cachedata keys:\n"
		bugout += "%s\n" % (json.dumps(cachedata.keys(), indent=4))
		if i in cachedata.keys():
			bugout += "found cache data for %s\n" % (i)
			r = cachedata[i]
		else:
			bugout += "didn't find cache data for %s, generating..\n" % (i)
			r = next_available(entity, i, bugout)
		x[i] = r
	if bug:
		x['debug'] = bugout
	json.dump(x, sys.stdout)
