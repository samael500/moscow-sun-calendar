"""Reduce verified Natural Earth 1:50m files to the atlas water layers.
Input files must match the downloaded snapshots; no network is used.
"""
import argparse
import hashlib
import json
from pathlib import Path
from shapely.geometry import box, shape
ROOT = Path(__file__).resolve().parents[1]
HASHES = {'rivers':'f286e0ce978fde999ca2d7a78c764be08542e19b63cded52b05c12d5173ccc51', 'lakes':'d350b75978b26fe839b797c2c529b2fb8f47fb3983c03f4964e36d5df9378a52'}
RIVERS = {'Amur','Anadyr’','Angara','Daugava','Dnepre','Dniester','Dnipro','Don','Ertis','Ertix','Heilong Jiang','Indigirka','Irtysh','Kama','Kamchatka','Kolyma','Lena','Neva','Ob','Pechora','Severnaya Dvina','Sukhona','Ural','Verkhniy Yenisey','Volga','Yenisey'}


def prepare(name, source, output):
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=HASHES[name]:
        raise ValueError('Source snapshot changed; review it before updating the hash')
    selected=[]
    for feature in json.loads(raw)['features']:
        p=feature['properties'];g=shape(feature['geometry'])
        include = p['name'] in RIVERS if name=='rivers' else (g.intersects(box(12,32,192,86)) and g.area>=.35 and p['featurecla']!='Reservoir' and 'Res.' not in (p['name'] or ''))
        if include:
            selected.append({'type':'Feature','properties':{'name':p['name'],'source':'Natural Earth 1:50m','ne_id':p.get('ne_id')},'geometry':feature['geometry']})
    output.mkdir(parents=True,exist_ok=True)
    (output/(name+'.geojson')).write_text(json.dumps({'type':'FeatureCollection','features':selected},ensure_ascii=False,separators=(',',':'))+'\n')
    print(name,len(selected))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rivers',type=Path,required=True)
    parser.add_argument('--lakes',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'data')
    args=parser.parse_args()
    for name in HASHES:prepare(name,getattr(args,name),args.output)
