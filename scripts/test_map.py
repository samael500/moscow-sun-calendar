"""Check offline geometry, region membership and the antimeridian seam."""
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from build_map import ROOT, build, projectors

class MapTests(unittest.TestCase):
    def test_all_points_and_region_bounds(self):
        cities=json.loads((ROOT/'data/cities.json').read_text())
        meta=json.loads((ROOT/'web/map-projection.json').read_text())
        self.assertEqual({c['id'] for c in cities},set(meta['points']))
        self.assertEqual(len(cities),116)
        memberships=[i for k,ids in meta['regions'].items() if k!='all' for i in ids]
        self.assertEqual(sorted(memberships),sorted(meta['points']))
        project=projectors('conic')
        for city in cities:
            self.assertEqual(list(project(city['longitude'],city['latitude'])),meta['points'][city['id']])
        for region,ids in meta['regions'].items():
            x0,y0,x1,y1=meta['bounds'][region]
            for name in ids:
                x,y=meta['points'][name]
                self.assertTrue(x0<=x<=x1 and y0<=y<=y1)
    def test_antimeridian_is_continuous(self):
        project=projectors('conic')
        for latitude in [40,55,66,82]:
            a=project(179.999,latitude);b=project(-179.999,latitude)
            self.assertLess(math.dist(a,b),.03) # <300m across 0.002°
            self.assertLess(math.dist(b,project(180.001,latitude)),1e-9)
    def test_assets_reproduce_offline(self):
        with TemporaryDirectory() as tmp:
            build(Path(tmp),'conic')
            for name in ['map.svg','map-projection.json']:
                self.assertEqual((Path(tmp)/name).read_bytes(),(ROOT/'web'/name).read_bytes())

if __name__=='__main__':unittest.main()
