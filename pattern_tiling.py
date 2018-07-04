from math import pi, exp, cos, sin
from os.path import basename, isdir

from os import makedirs
import subprocess
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
parser.add_argument('--dx', type=float,
                    help="The x-distance to translate the image (in percentage of the "
                         "total width).")
parser.add_argument('--dy', type=float,
                    help="The y-distance to translate the image (in percentage of the "
                         "total height).")
parser.add_argument('--repetitions', type=float,
                    help="The number of repetitions along each dimension of the tiling.")


def cexp(x):
    return pow(exp(1), x)


def c(a):
    return cos(a * pi / 180.)


def s(a):
    return sin(a * pi / 180.)


def rotate_transform(angle):
    return c(angle), s(angle), -s(angle), c(angle), 0, 0


def format_transform(angle, diff):
    transform1 = rotate_transform(angle)
    transform2 = 1, 0, 0, 1, diff.real, diff.imag
    transform = combine_transforms(transform2, transform1)
    return "matrix({},{},{},{},{},{})".format(*transform)


def prop(property_name, generator):
    def getter(self):
        if not hasattr(self, "_"+property_name):
            self.__getattribute__(generator)()
        return self.__getattribute__("_"+property_name)
    return property(getter)


class CairoTiler(object):
    def __init__(self, filename, dx=None, dy=None, repetitions=3):
        self.filename = filename
        self.dx = dx
        self.dy = dy
        if repetitions is None:
            raise ValueError("got no repetitions")
        self.repetitions = repetitions

        self.output_folder = "output"
        if not isdir(self.output_folder):
            makedirs(self.output_folder)

    bottom_length = prop("bottom_length", "calc_bottom_length")
    cairo_group = prop("cairo_group", "calculate_transforms")
    colors = prop("colors", "init_colors")
    column_offset = prop("column_offset", "calculate_transforms")
    pattern_viewbox = prop("pattern_viewbox", "calc_pattern_viewbox")
    pent_height = prop("pent_height", "calc_pentagon_dimensions")
    pent_width = prop("pent_width", "calc_pentagon_dimensions")
    pent_x = prop("pent_x", "calc_pentagon_dimensions")
    pent_y = prop("pent_y", "calc_pentagon_dimensions")
    points = prop("points", "init_pentagon_points")
    rep_spacing = prop("rep_spacing", "calc_rep_spacing")
    tile_attributes = prop("tile_attributes", "import_tile")
    tile_paths = prop("tile_paths", "import_tile")
    transforms = prop("transforms", "calculate_transforms")

    @property
    def num_down(self):
        return int(1 + self.repetitions)

    @property
    def num_across(self):
        return int(1 + 2 * self.repetitions)

    def calc_rep_spacing(self):
        self._rep_spacing = self.pent_width * 2 + self.bottom_length

    def calc_bottom_length(self):
        self._bottom_length = abs(self.points[2] - self.points[3])

    def calc_pattern_viewbox(self):
        bbox = calc_overall_bbox(self.cairo_group)
        vbwidth = self.cairo_group[1][3].end.real + self.pent_height
        vbheight = self.pent_height * 2
        self._pattern_viewbox = min(bbox[0], bbox[1]) + self.cairo_group[1][2].end.real, \
                                min(bbox[2], bbox[3]), vbwidth * self.repetitions, \
                                vbheight * self.repetitions

    def calc_pentagon_dimensions(self):
        bbox = calc_overall_bbox(self.new_pentagon())
        self._pent_width, self._pent_height = abs(bbox[1] - bbox[0]), abs(
            bbox[3] - bbox[2])
        self._pent_x, self._pent_y = min(bbox[0], bbox[1]), min(bbox[2], bbox[3])

    def calculate_transforms(self):
        self._transforms = [[0, 0]]
        self._cairo_group = [self.new_pentagon()]
        # point 2 of pentagon 2 needs to be attached to point 2 of pentagon 1
        self._cairo_group.append(transform_path(rotate_transform(90), self.new_pentagon()))
        diff = self._cairo_group[0][1].end - self._cairo_group[1][1].end
        self._transforms.append([90, diff])
        self._cairo_group[1] = self._cairo_group[1].translated(diff)
        self._cairo_group.append(transform_path(rotate_transform(180), self.new_pentagon()))
        # point 4 of pentagon 3 needs to be attached to point 3 of pentagon 1
        diff = self._cairo_group[0][2].end - self._cairo_group[2][3].end
        self._transforms.append([180, diff])
        self._cairo_group[2] = self._cairo_group[2].translated(diff)
        self._cairo_group.append(transform_path(rotate_transform(-90), self.new_pentagon()))
        # point 5 of pentagon 4 needs to be attached to point 2 of pentagon 1
        diff = self._cairo_group[0][4].end - self._cairo_group[3][4].end
        self._transforms.append([-90, diff])
        self._cairo_group[3] = self._cairo_group[3].translated(diff)
        self._column_offset = self._cairo_group[0][0].end - self._cairo_group[1][2].end

    def init_pentagon_points(self):
        # we want a pentagon with the interior angles 120, 90, 120, 120, 90 interior
        # angles
        #     1
        # 5        2
        #    4  3
        angle1 = 120.0
        length1 = 300
        # start with the top corner at 0, 0
        self._points = [0, None, None, None, None]
        self._points[1] = self._points[0] + length1 * cexp(1j * 0.5 * angle1 * pi / 180.0)
        self._points[4] = self._points[0] + length1 * cexp(
            -1j * 0.5 * angle1 * pi / 180.0)
        angle23 = (180 - angle1 * 0.5 - 90)
        self._points[2] = self._points[1] + length1 * cexp(-1j * angle23 * pi / 180.0)
        self._points[3] = self._points[4] + length1 * cexp(1j * angle23 * pi / 180.0)

    def init_colors(self):
        self._colors = get_paletton("workspace/paletton.txt")

    def new_pentagon(self):
        return Path(
            *[Line(start=self.points[i - 1], end=self.points[i])
              for i in range(len(self.points))])

    def draw_single_pentagon(self):
        pentagon = self.new_pentagon()
        dwg = Drawing("{}/single_pentagon.svg".format(self.output_folder), profile='tiny')
        dwg.add(dwg.path(**{'d': pentagon.d(), 'fill': "none", 'stroke-width': 4,
                            'stroke': rgb(0, 0, 0)}))
        dwg.viewbox(self.pent_x, self.pent_y, self.pent_width, self.pent_height)
        dwg.save()

    def draw_path_clip(self):
        path_filename = "{}/path_clip_{}.svg".format(self.output_folder,
            basename(self.filename).replace(".svg", ""))
        dwg = Drawing(path_filename)
        image_bbox = calc_overall_bbox(self.tile_paths)

        dx = self.pent_x - min(image_bbox[0], image_bbox[1])
        dy = self.pent_y - min(image_bbox[2], image_bbox[3])
        dwg.add(dwg.path(**{"d": self.new_pentagon().d(), "fill": "none",
                            'stroke-width': 4,
                            'stroke': rgb(0, 0, 0)}))
        neg_transform = "translate({}, {})".format(-dx, -dy)
        transform = "translate({}, {})".format(dx, dy)
        clip_path = dwg.defs.add(dwg.clipPath(id="pent_path", transform=neg_transform))
        clip_path.add(dwg.path(d=self.new_pentagon().d()))
        group = dwg.add(dwg.g(clip_path="url(#pent_path)", transform=transform,
                              id="clippedpath"))
        for i, path in enumerate(self.tile_paths):
            group.add(
                dwg.path(d=path.d(), style=self.tile_attributes[i].get('style'),
                         id=self.tile_attributes[i]['id']))
        dwg.add(dwg.use("#clippedpath", transform="transform(100, 100)"))

        dwg.viewbox(self.pent_x, self.pent_y, self.pent_width, self.pent_height)
        dwg.save()
        xml = xml.dom.minidom.parse(path_filename)
        open(path_filename, "w").write(xml.toprettyxml())

    def import_tile(self):
        self._tile_paths, self._tile_attributes = svg2paths(self.filename)

    def generate_tiling(self):
        dwg = Drawing("{}/tiling2.svg".format(self.output_folder), profile="tiny")

        current_color = 0
        row_spacing = self.pent_height * 2 + self.bottom_length

        for y in range(self.num_down):
            transform = "translate({}, {})".format(0, self.rep_spacing * y)
            dgroup = dwg.add(dwg.g(transform=transform))
            for x in range(self.num_across):
                # if x is odd, point 1 of pent 1 needs to be attached to point 3 of pent 2
                if x % 2 == 1:
                    dx = int(x / 2) * self.rep_spacing + self.pent_width * 2 + self.column_offset.real
                    transform = "translate({}, {})".format(dx, self.column_offset.imag)
                else:
                    transform = "translate({}, {})".format(int(x / 2) * self.rep_spacing, 0)
                group = dgroup.add(dwg.g(transform=transform))
                for pent in self.cairo_group:
                    group.add(
                        dwg.path(**{'d': pent.d(), 'fill': self._colors[current_color % len(self._colors)],
                                    'stroke-width': 4, 'stroke': rgb(0, 0, 0)}))
                    current_color += 1

        dwg.viewbox(*self.pattern_viewbox)
        dwg.save(pretty=True)

    def draw_pattern(self):
        self.output_filename = "{}/snake_tiling_m_{}_{}.svg".format(self.output_folder,
                                                                    self.dx,
                                                           self.dy)
        dwg = Drawing(self.output_filename)
        # add background panel
        background_panel = dwg.rect(insert=(self.pattern_viewbox[0], self.pattern_viewbox[1]),
                     size=('100%', '100%'), fill='#3072a2')
        clip_path = dwg.defs.add(dwg.clipPath(id="background_panel"))
        clip_path.add(background_panel)
        clipped_drawing = dwg.add(dwg.g(clip_path="url(#background_panel)", id="clippedpath"))
        clipped_drawing.add(background_panel)
        current_color = 0

        def add_pentagon(group, transform, current_color, draw_pent=True):
            pent_group = group.add(dwg.g(transform=format_transform(*transform)))
            if draw_pent:
                pent_group.add(
                    dwg.path(
                        **{'d': self.new_pentagon().d(),
                           'fill': self.colors[current_color % len(self.colors)],
                           'stroke-width': 4, 'stroke': rgb(0, 0, 0)}))
            return pent_group

        for y in range(self.num_down):
            transform = "translate({}, {})".format(0, self.rep_spacing * y)
            dgroup = clipped_drawing.add(dwg.g(transform=transform))
            for x in range(self.num_across):
                # if x is odd, point 1 of pent 1 needs to be attached to point 3 of pent 2
                if x % 2 == 1:
                    dx = int(x / 2) * self.rep_spacing + self.pent_width * 2 + self.column_offset.real
                    diff = dx + self.column_offset.imag * 1j
                else:
                    diff = int(x / 2) * self.rep_spacing
                for i in range(4):
                    snake_bbox = calc_overall_bbox(self.tile_paths)
                    snake_width, snake_height = abs(snake_bbox[0] - snake_bbox[1]), \
                                                abs(snake_bbox[2] - snake_bbox[3])
                    pent_group = add_pentagon(dgroup,
                                              (self.transforms[i][0], self.transforms[i][1] + diff),
                                              current_color, draw_pent=False)
                    for i, path in enumerate(self.tile_paths):
                        stransform = 'translate({},{})'.format(snake_width * self.dx,
                                                               snake_height * self.dy)
                        pent_group.add(
                            dwg.path(**{'d': path.d(),
                                        'style': self.tile_attributes[i].get('style'),
                                        'id': self.tile_attributes[i]['id'],
                                        'transform': stransform}))
                    current_color += 1

        dwg.viewbox(*self.pattern_viewbox)
        dwg.save()

    def export_png(self):
        # this step requires that you have imagemagick working.
        # this could be replaced with a python binding to imagemagick, however, these
        # bindings cause python to crash on my computer.
        dpi = 150
        width_inches = 36 # one yard
        size = dpi*width_inches
        subprocess.call(['convert', self.output_filename, '-resize', '{}x{}'.format(size, size),
                         self.output_filename.replace(".svg", ".png")])

    def ranged_diffs(self):
        ds = [0, 0.25, 0.5, 0.75, 1.0]
        for adx in ds:
            self.dx = adx
            for ady in ds:
                self.dy = ady
                self.draw_pattern()


if __name__ == "__main__":
    args = parser.parse_args()
    _tiler = CairoTiler(**vars(args))
    _tiler.draw_pattern()
    _tiler.export_png()