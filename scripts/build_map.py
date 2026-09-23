"""Reproducible offline atlas assets. No calendar/astronomy changes."""
import argparse
import hashlib
import json
from pathlib import Path

from pyproj import CRS, Transformer
from shapely.affinity import translate
from shapely.geometry import box, shape
from shapely import make_valid, unary_union

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = box(-35, 5, 235, 88)
CRS_TEXT = '+proj=lcc +lat_1=45 +lat_2=65 +lat_0=55 +lon_0=100 +datum=WGS84 +units=m +no_defs'


def projectors(kind):
    if kind == 'linear':
        return lambda lon, lat: ((lon - 19) / 162 * 1100, (82 - lat) / 41 * 420)
    transformer = Transformer.from_crs('EPSG:4326', CRS.from_proj4(CRS_TEXT), always_xy=True)
    def project(lon, lat):
        x, y = transformer.transform(lon, lat)
        return x / 10000, -y / 10000
    return project


def bounds(points):
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs), max(ys)]


def pieces(geometry):
    # Natural Earth splits features at ±180°. Duplicate the western half into
    # 180..192 before clipping, rather than drawing a segment across the world.
    for shift in (0, 360, -360):
        clipped = translate(make_valid(geometry), xoff=shift).intersection(DOMAIN)
        if not clipped.is_empty:
            yield clipped.segmentize(.5)


def path_data(geometry, project):
    def line(coords, close=False):
        return 'M' + 'L'.join(f'{x:.3f},{y:.3f}' for x, y in (project(*p[:2]) for p in coords)) + ('Z' if close else '')
    if geometry.geom_type == 'Polygon':
        return line(geometry.exterior.coords, True) + ''.join(line(r.coords, True) for r in geometry.interiors)
    if geometry.geom_type in ('LineString', 'LinearRing'):
        return line(geometry.coords)
    if hasattr(geometry, 'geoms'):
        return ''.join(path_data(g, project) for g in geometry.geoms)
    return ''


def build(output, kind):
    project = projectors(kind)
    cities = json.loads((ROOT / 'data/cities.json').read_text())
    points = {c['id']: list(project(c['longitude'], c['latitude'])) for c in cities}
    regions = {'all': [c['id'] for c in cities]}
    for key, name in [('west', 'Запад'), ('south', 'Юг'), ('center', 'Центр'), ('east', 'Восток')]:
        regions[key] = [c['id'] for c in cities if c.get('region') == name or name in c.get('search_terms', '')]
    meta = {'projection': kind, 'crs': CRS_TEXT if kind == 'conic' else 'legacy equirectangular',
            'points': points, 'regions': regions,
            'bounds': {key: bounds([points[i] for i in ids]) for key, ids in regions.items()},
            'source_sha256': {}, 'layers': {}}
    paths = []
    for name in ['land', 'lakes', 'rivers']:
        raw = (ROOT / f'data/{name}.geojson').read_bytes()
        meta['source_sha256'][name] = hashlib.sha256(raw).hexdigest()
        features = json.loads(raw)['features']
        geometries = [g for f in features for g in pieces(shape(f['geometry']))]
        # Rejoin adjacent land pieces at 180° so the split is not a false coast.
        if name == 'land':
            geometries = [unary_union(geometries)]
        data = ''.join(path_data(g, project) for g in geometries)
        paths.append(f'<path class="{name}" d="{data}"/>')
        meta['layers'][name] = len(features)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Карта городов, суши и крупных водоёмов"><g data-terrain="true">' + ''.join(paths) + '</g></svg>'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'map.svg').write_text(svg)
    (output / 'map-projection.json').write_text(json.dumps(meta, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(kind, len(points), 'cities', meta['layers'], 'bounds', meta['bounds']['all'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection', choices=['conic', 'linear'], default='conic')
    parser.add_argument('--output', type=Path, default=ROOT / 'web')
    args = parser.parse_args()
    build(args.output, args.projection)
