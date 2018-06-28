from math import pi, exp, cos, sin
from os.path import basename

from svgpathtools import Line, svg2paths, Path, parse_path
from svgwrite import Drawing, rgb

from svgpathtools.svg2paths import combine_transforms, transform_path
from utils import calc_overall_bbox, get_paletton
import argparse
import xml.dom.minidom

parser = argparse.ArgumentParser(
    description='Generate a fabric pattern by doing a cairo tiling of another SVG')
parser.add_argument('--filename', type=str,
                    help='The filename of the svg to be tiled.')


def cexp(x):
    return pow(exp(1), x)


def c(a):
    return cos(a * pi / 180.)


def s(a):
    return sin(a * pi / 180.)


def rotate_transform(angle):
    return c(angle), s(angle), -s(angle), c(angle), 0, 0

args = parser.parse_args()
all_paths, attributes = svg2paths(args.filename)

# we want a pentagon with the interior angles 120, 90, 120, 120, 90 interior angles
#     1
# 5        2
#    4  3
angle1 = 120.0
angle2 = 90.0
length1 = 300
# length
# start with the top corner at 0, 0
points = [0, None, None, None, None]
points[1] = points[0] + length1 * cexp(1j * 0.5 * angle1 * pi / 180.0)
points[4] = points[0] + length1 * cexp(-1j * 0.5 * angle1 * pi / 180.0)
angle23 = (180 - angle1 * 0.5 - 90)
points[2] = points[1] + length1 * cexp(-1j * angle23 * pi / 180.0)
points[3] = points[4] + length1 * cexp(1j * angle23 * pi / 180.0)

def new_pent():
    # what is the interior angle between 543?
    return Path(*[Line(start=points[i-1], end=points[i]) for i in range(len(points))])

dwg = Drawing("single_new_pent().svg", profile='tiny')
dwg.add(dwg.path(**{'d': new_pent().d(), 'fill': "none", 'stroke-width': 4,
                                'stroke': rgb(0, 0, 0)}))

bbox = calc_overall_bbox(new_pent())
width, height = abs(bbox[1] - bbox[0]), abs(bbox[3] - bbox[2])
dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), width, height)
dwg.save()

pent_width, pent_height = width, height
path_filename = "path_clip_{}.svg".format(basename(args.filename).replace(".svg", ""))
dwg = Drawing(path_filename)
all_paths, attributes = svg2paths(args.filename)
image_bbox = calc_overall_bbox(all_paths)

transform = "translate(0, 0)"
dx = min(bbox[0], bbox[1]) - min(image_bbox[0], image_bbox[1])
dy = min(bbox[2], bbox[3]) - min(image_bbox[2], image_bbox[3])
dwg.add(dwg.path(**{"d": new_pent().d(), "fill": "none", 'stroke-width': 4,
                    'stroke': rgb(0, 0, 0)}))
clip_path = dwg.defs.add(dwg.clipPath(id="pent_path",
                                      transform="translate({}, {})".format(-dx, -dy)
    ))
clip_path.add(dwg.path(d=new_pent().d()))
group = dwg.add(dwg.g(clip_path="url(#pent_path)",
                      transform="translate({}, {})".format(dx, dy), id="clippedpath"))
for i, path in enumerate(all_paths):
    group.add(dwg.path(d=path.d(), style=attributes[i].get('style'), id=attributes[i]['id']))
dwg.add(dwg.use("#clippedpath", transform="transform(100, 100)"))

dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), width, height)
dwg.save()

# now generate the tiling

xml = xml.dom.minidom.parse(path_filename)
open(path_filename, "w").write(xml.toprettyxml())

dwg = Drawing("tiling2.svg", profile="tiny")
transforms = [[0, 0]]
pents = [new_pent()]
# point 2 of pentagon 2 needs to be attached to point 2 of pentagon 1
pents.append(transform_path(rotate_transform(90), new_pent()))
diff = pents[0][1].end - pents[1][1].end
transforms.append([90, diff])
pents[1] = pents[1].translated(diff)
pents.append(transform_path(rotate_transform(180), new_pent()))
# point 4 of pentagon 3 needs to be attached to point 3 of pentagon 1
diff = pents[0][2].end - pents[2][3].end
transforms.append([180, diff])
pents[2] = pents[2].translated(diff)
pents.append(transform_path(rotate_transform(-90), new_pent()))
# point 5 of pentagon 4 needs to be attached to point 2 of pentagon 1
diff = pents[0][4].end - pents[3][4].end
transforms.append([-90, diff])
pents[3] = pents[3].translated(diff)

colors = get_paletton("workspace/paletton.txt")
num_across = 6
num_down = 3
current_color = 0
bottom_length = abs(points[2]-points[3])
rep_spacing = pent_width*2 + bottom_length
row_spacing = pent_height*2 + bottom_length
column_offset = pents[0][0].end - pents[1][2].end
for y in range(num_down):
    transform = "translate({}, {})".format(0, rep_spacing*y)
    dgroup = dwg.add(dwg.g(transform=transform))
    for x in range(num_across):
        # if x is odd, point 1 of pent 1 needs to be attached to point 3 of pent 2
        if x % 2 == 1:
            dx = int(x/2)*rep_spacing+pent_width*2+column_offset.real
            transform = "translate({}, {})".format(dx, column_offset.imag)
        else:
            transform = "translate({}, {})".format(int(x/2)*rep_spacing, 0)
        group = dgroup.add(dwg.g(transform=transform))
        for pent in pents:
            group.add(dwg.path(**{'d': pent.d(), 'fill': colors[current_color % len(colors)],
                                  'stroke-width': 4, 'stroke': rgb(0, 0, 0)}))
            current_color += 1
bbox = calc_overall_bbox(pents)

width, height = pent_width*2*num_across, pent_height*2*num_down
dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), width, height)
dwg.save(pretty=True)


dwg = Drawing("snake_tiling_m.svg")
# pents_group is a group of 4 pentagons
pents_group = dwg.add(dwg.g())
current_color = 0


def format_transform(angle, diff):
    transform1 = rotate_transform(angle)
    transform2 = 1, 0, 0, 1, diff.real, diff.imag
    transform = combine_transforms(transform2, transform1)
    return "matrix({},{},{},{},{},{})".format(*transform)


def add_pentagon(group, transform, current_color):
    pent_group = group.add(dwg.g(transform=format_transform(*transform))) # id="pentagon{}".format(current_color
    pent_group.add(dwg.path(**{'d': new_pent().d(), 'fill': colors[current_color % len(colors)],
                               'stroke-width': 4, 'stroke': rgb(0, 0, 0)}))
    return pent_group


bottom_length = abs(points[2]-points[3])
for y in range(num_down):
    transform = "translate({}, {})".format(0, rep_spacing*y)
    dgroup = dwg.add(dwg.g(transform=transform))
    for x in range(num_across):
        # if x is odd, point 1 of pent 1 needs to be attached to point 3 of pent 2
        if x % 2 == 1:
            dx = int(x/2)*rep_spacing+pent_width*2+column_offset.real
            diff = dx + column_offset.imag*1j
            transform = "translate({}, {})".format(dx, column_offset.imag)
        else:
            diff = int(x/2)*rep_spacing
            transform = "translate({}, {})".format(diff, 0)
        for i in range(4):
            pent_group = add_pentagon(dgroup, (transforms[i][0], transforms[i][1]+diff), current_color)
            for i, path in enumerate(all_paths):
                pent_group.add(dwg.path(**{'d':path.d(), 'style':attributes[i].get('style'),
                                   'id':attributes[i]['id']}))
            current_color += 1

dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), width, height)
dwg.save(pretty=True)