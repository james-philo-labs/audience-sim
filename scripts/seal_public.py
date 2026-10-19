"""Reseal only after deliberately reviewing the public diff and asset provenance."""
import hashlib,json
from check_public import ROOT,files,main
if main(check_inventory=False):raise SystemExit('Resolve public-content checks before resealing')
manifest={'version':'public-package-0.1','purpose':'Reviewed public file inventory; generated run archives are excluded.','files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files() if p.name!='PUBLIC_ASSETS.json'}}
(ROOT/'PUBLIC_ASSETS.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Reviewed public inventory sealed:',len(manifest['files']),'files')
