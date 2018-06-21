# try to transform both using svgpathtools and matrix transformations
from math import cos, sin, pi
from svgpathtools import Line, Path, parse_path
from svgpathtools.svg2paths import combine_transforms, transform_path
from svgwrite import Drawing, rgb

import xml.dom.minidom


width = 100
line = Path(Line(start=0, end=width))
path_filename = "transform_test.svg"
dwg = Drawing(path_filename, profile="full")
angle = 45
translate_y = 1


def c(a):
    return cos(a * pi / 180.)


def s(a):
    return sin(a * pi / 180.)


transform1 = c(angle), s(angle), -s(angle), c(angle), 0, 0
transform2 = 1, 0, 0, 1, 0, translate_y
transform = combine_transforms(transform1, transform2)
transform_m = "matrix({},{},{},{},{},{})".format(*transform)
dg = dwg.add(dwg.g(transform=transform_m))
dg.add(dwg.path(d=line.d(), stroke_width=1, stroke=rgb(255, 0, 0)))
line_transformed = parse_path(transform_path(transform, line.d()))
print(transform_path(transform, line.d()))
print(line_transformed)

dwg.add(dwg.path(d=line_transformed.d(), stroke_width=1, stroke=rgb(0, 255, 0)))
'''
dwg.add(dwg.path(d=line.d(), stroke_width=1, stroke=rgb(0, 0, 255)))
dwg.add(dwg.path(d=line.rotated(-45).d(), stroke_width=1, stroke=rgb(0, 0, 255)))
'''
dwg.save()
xml = xml.dom.minidom.parse(path_filename)
open(path_filename, "w").write(xml.toprettyxml())