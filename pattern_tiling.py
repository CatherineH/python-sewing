from math import pi, exp
from svgpathtools import Path, Line
from svgwrite import Drawing, rgb
from utils import calc_overall_bbox, get_paletton


def cexp(x):
    return pow(exp(1), x)


# we want a pentagon with the interior angles 120, 90, 120, 120, 90 interior angles
#     1
# 5        2
#    4  3
angle1 = 120.0
angle2 = 90.0
length1 = 150
# length
# start with the top corner at 0, 0
points = [0, None, None, None, None]
points[1] = points[0] + length1*cexp(1j*0.5*angle1*pi/180.0)
points[4] = points[0] + length1*cexp(-1j*0.5*angle1*pi/180.0)
angle23 = (180-angle1*0.5-90)
points[2] = points[1] + length1*cexp(-1j*angle23*pi/180.0)
points[3] = points[4] + length1*cexp(1j*angle23*pi/180.0)
# what is the interior angle between 543?


pent = Path(*[Line(start=points[i-1], end=points[i]) for i in range(len(points))])
dwg = Drawing("single_pent.svg", profile='tiny')
dwg.add(dwg.path(**{'d': pent.d(), 'fill': "none", 'stroke-width': 4,
                                'stroke': rgb(0, 0, 0)}))

bbox = calc_overall_bbox(pent)
width, height = abs(bbox[1] - bbox[0]), abs(bbox[3] - bbox[2])
dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), width, height)
dwg.save()

pent_width, pent_height = width, height

pents = [pent]
# point 2 of pentagon 2 needs to be attached to point 2 of pentagon 1
pents.append(pent.rotated(90))
diff = pents[0][1].end - pents[1][1].end
pents[1] = pents[1].translated(diff)
pents.append(pent.rotated(180))
# point 4 of pentagon 3 needs to be attached to point 3 of pentagon 1
diff = pents[0][2].end - pents[2][3].end
pents[2] = pents[2].translated(diff)
pents.append(pent.rotated(-90))
# point 5 of pentagon 4 needs to be attached to point 2 of pentagon 1
diff = pents[0][4].end - pents[3][4].end
pents[3] = pents[3].translated(diff)


dwg = Drawing("tiling2.svg", profile="tiny")
colors = get_paletton("workspace/paletton.txt")
num_across = 6
num_down = 3
current_color = 0
bottom_length = abs(points[2]-points[3])
rep_spacing = pent_width*2 + bottom_length
row_spacing = pent_height*2 + bottom_length
for y in range(num_down):
    transform = "translate({}, {})".format(0, rep_spacing*y)
    dgroup = dwg.add(dwg.g(transform=transform))
    for x in range(num_across):
        # if x is odd, point 1 of pent 1 needs to be attached to point 3 of pent 2
        diff = pents[0][0].end - pents[1][2].end
        if x % 2 == 1:
            transform = "translate({}, {})".format(int(x/2)*rep_spacing+pent_width*2+diff.real, diff.imag)
        else:
            transform = "translate({}, {})".format(int(x/2)*rep_spacing, 0)
        group = dgroup.add(dwg.g(transform=transform))
        for pent in pents:
            group.add(dwg.path(**{'d': pent.d(), 'fill': colors[current_color % len(colors)],
                                  'stroke-width': 4,'stroke': rgb(0, 0, 0)}))
            current_color += 1
bbox = calc_overall_bbox(pents)

width, height = pent_width*2*num_across, pent_height*2*num_down
dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), width, height)
dwg.save()