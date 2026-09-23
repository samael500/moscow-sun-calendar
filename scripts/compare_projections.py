from playwright.sync_api import sync_playwright
from pathlib import Path
import json, argparse, subprocess, sys
from tempfile import TemporaryDirectory
parser=argparse.ArgumentParser(description='Compare conic and legacy projections using the same interface')
parser.add_argument('--url',default='http://localhost:8790/')
parser.add_argument('--browser')
parser.add_argument('--output',type=Path,default=Path('/tmp/sun-projection-review'))
args=parser.parse_args()
out=args.output;out.mkdir(parents=True,exist_ok=True);report=[]
temporary=TemporaryDirectory();linear=Path(temporary.name)
subprocess.run([sys.executable,str(Path(__file__).with_name('build_map.py')),'--projection','linear','--output',str(linear)],check=True)
with sync_playwright() as p:
 b=p.chromium.launch(**({'executable_path':args.browser} if args.browser else {}))
 for kind in ['conic','linear']:
  for width in [390,1280]:
   page=b.new_page(viewport={'width':width,'height':1000})
   if kind=='linear':
    for name in ['map.svg','map-projection.json']:
     page.route('**/'+name,lambda route,request,name=name:route.fulfill(path=str(linear/name),content_type='image/svg+xml' if name.endswith('svg') else 'application/json'))
   page.goto(args.url,wait_until='networkidle');page.wait_for_selector('.map-target')
   for region in ['all','west']:
    page.locator('[data-view='+region+']').click()
    page.locator('#map').screenshot(path=str(out/f'projection-{kind}-{region}-{width}.png'))
    report.append({'projection':kind,'width':width,'region':region,'targets':page.locator('.map-target').count(),'labels':page.locator('[data-label-for]').count(),'reachable_cities':sum(len(x.split()) for x in page.locator('.map-target').evaluate_all('(els)=>els.map(e=>e.dataset.members)'))})
   page.close()
 b.close()
(out/'projection-comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

temporary.cleanup()
