"""Public synthetic regressions for corpus-qualified scalar boundaries."""
import asyncio
import hashlib
import json
import random
import time
from pathlib import Path
import os
import sys

import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from ras_commander_mcp.adapter import metadata_api_present


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_randomized_stdio_requests_are_isolated_and_recoverable(tmp_path,mode):
    project=tmp_path/'project'; project.mkdir(); private=tmp_path/'private'; private.mkdir()
    content={
      'english.prj':b'Proj Title=English\nEnglish Units\nPlan File=../../outside.p01\nGeom File=secret.g01\n',
      'metric.prj':b'Proj Title=Metric\nSI Units\nPlan File=plan.p01\n',
      'conflict.prj':b'Proj Title=Conflict\nSI Units\nEnglish Units\n',
      'plan.p01':b'Plan Title=First=Retained\nPlan Title=Second\nSimulation Date=01JAN2020,2400,02JAN2020,2400\nComputation Interval=0.5SEC\nGeom File=secret.g01\nBEGIN DESCRIPTION:\nActual narrative.\nEND DESCRIPTION:\n',
      'secret.g01':b'NEVER OPEN GEOMETRY', 'secret.dss':b'NEVER OPEN DSS',
      'results.p01.hdf':b'NEVER OPEN RESULTS',
      'nul.p01':b'Plan Title=not eligible\0',
      'large.p01':b'X'*1048577,
    }
    for name,blob in content.items():(project/name).write_bytes(blob)
    before={name:hashlib.sha256(blob).hexdigest() for name,blob in content.items()}
    # Sentinel audit is independent of the server: every process denies non-text reads/project writes.
    (private/'sitecustomize.py').write_text('''import os,sys\nroot=os.environ['RAS_REGRESSION_ROOT']\nreal=os.open\ndef check(path,flags):\n p=os.path.abspath(os.fsdecode(path))\n if p.startswith(root+os.sep):\n  if flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):raise RuntimeError('project write forbidden')\n  if os.path.isfile(p) and not (p.endswith('.prj') or p.endswith('.p01')):raise RuntimeError('binary read forbidden')\ndef hook(event,args):\n if event=='open' and isinstance(args[0],(str,bytes)):check(args[0],args[2] or 0)\nsys.addaudithook(hook)\ndef wrapped(path,flags,mode=0o777,*,dir_fd=None):\n p=os.fsdecode(path)\n if dir_fd is not None and not os.path.isabs(p) and os.name=='posix':p=os.path.join(os.readlink('/proc/self/fd/'+str(dir_fd)),p)\n check(p,flags)\n return real(path,flags,mode,dir_fd=dir_fd)\nos.open=wrapped\n''')
    env=dict(os.environ); env.update(RAS_MCP_ALLOWED_ROOTS=json.dumps([str(project)]),RAS_REGRESSION_ROOT=str(project),PYTHONPATH=str(private)+os.pathsep+env.get('PYTHONPATH',''))
    cases=[('project_units','english.prj','ft'),('project_units','metric.prj','m'),('project_units','conflict.prj','m'),('plan_description','plan.p01','Actual narrative.')]
    random.Random(20261004).shuffle(cases)
    async def run():
      with (private/'stderr.log').open('w') as errors:
       async with Client(StdioServerParameters(command=sys.executable,args=['-m','ras_commander_mcp'],env=env),mode=mode) as client:
        for _ in range(3):
          for tool,name,expected in cases:
            for bad in ['../../outside.prj','secret.g01','secret.dss','results.p01.hdf','nul.p01','large.p01']:
                response=await client.call_tool('plan_description',{'request':{'root':str(project),'file':bad}}); assert response.is_error
            response=await client.call_tool(tool,{'request':{'root':str(project),'file':name}}); assert not response.is_error
            value=response.structured_content; assert value['source']['sha256']==before[name]
            assert value['units']==expected if tool=='project_units' else value['records'][0]['value']==expected
        if metadata_api_present():
          response=await client.call_tool('plan_configuration',{'request':{'root':str(project),'file':'plan.p01','fields':['Plan Title','Simulation Date','Computation Interval','Geom File'],'limit':1}})
          records=[]; rounds=0
          while True:
            assert not response.is_error; value=response.structured_content; records+=value['records']; rounds+=1
            if value['next_offset'] is None:break
            response=await client.call_tool('plan_configuration',{'request':{'root':str(project),'file':'plan.p01','fields':['Plan Title','Simulation Date','Computation Interval','Geom File'],'limit':1,'offset':value['next_offset']}})
          assert rounds==5 and len(records)==5
          assert [(r['value'],r['occurrence']) for r in records if r['field']=='Plan Title']==[('First=Retained',0),('Second',1)]
          assert next(r['value'] for r in records if r['field']=='Simulation Date')=='01JAN2020,2400,02JAN2020,2400'
          response=await client.call_tool('project_metadata',{'request':{'root':str(project),'file':'conflict.prj','fields':['Units','Unsteady File']}})
          assert response.structured_content['units'] is None
          assert response.structured_content['missing_fields']==['Unsteady File']
    asyncio.run(run())
    assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in project.iterdir()}==before
