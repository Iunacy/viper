import sys,platform,os,subprocess,json,pathlib,hashlib,shutil,importlib.metadata
root=pathlib.Path.cwd(); base='5c66c95ec48c101a2d4af55df8d917ff5a72bcac'
def git(*args): return subprocess.check_output(['git',*args],text=True).strip()
changed=git('diff','--name-only',base).splitlines()
evidence_paths=[p for p in git('ls-tree','-r','--name-only',base).splitlines() if any(x in p for x in ('/results/','/evidence/','/qualification/')) or p.endswith(('results.csv','STATUS.txt','UPSTREAM.txt','SHA256SUMS'))]
verified={}
for name in evidence_paths:
    original=subprocess.check_output(['git','show',base+':'+name]); path=root/name
    assert path.is_file() and path.read_bytes()==original, name
    verified[name]=hashlib.sha256(original).hexdigest()
report={'audited_main_sha':base,'head':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),'platform':platform.platform(),'os_release':pathlib.Path('/etc/os-release').read_text(),'python':sys.version,'executable':sys.executable,'cpu_count':os.cpu_count(),'available_cpu_cores':len(os.sched_getaffinity(0)),'disk':dict(zip(('total','used','free'),shutil.disk_usage(root))),'memory':{line.split(':')[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))},'gpu_read_only':subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total,memory.free','--format=csv,noheader'],text=True).strip(),'package_versions':{n:importlib.metadata.version(n) for n in ('torch','numpy','transformers','safetensors','torchcodec','pyarrow','pillow','pandas','av')},'changed_tracked_paths':changed,'preserved_historical_evidence_sha256':verified}
for name in ('GR00T','IsaacLab'):
    source=pathlib.Path('/home/iris/.local/share/viper-cloud-ubuntu/sources')/name
    report[name]={'sha':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),'dirty':subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip()}
print(json.dumps(report,indent=2))
