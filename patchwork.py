import argparse
from pdfrw import PdfReader
from svgwrite import Drawing, rgb
from svgpathtools import Path, parse_path

parser = argparse.ArgumentParser(
    description='Generate new pattern pieces from existing patterns')
parser.add_argument('--filename', type=str, help='The filename of the pdf pattern.')
parser.add_argument('--size', type=str, help="The size of the pattern to analyze.")

point_separator = ","


def transform_point(point, matrix=(1, 0, 0, 1, 0, 0), format="float", relative=False):
    a, b, c, d, e, f = matrix
    if isinstance(point, list):
        x, y = point
    else:
        point_parts = point.split(',')
        if len(point_parts) >= 2:
            x, y = [float(x) for x in point_parts]
        else:
            # probably got a letter describing the point, i.e., m or z
            return point
    # if the transform is relative, don't apply the translation
    if relative:
        x, y = a * x + c * y, b * x + d * y
    else:
        x, y = a * x + c * y + e, b * x + d * y + f
    if format == "float":
        return x, y
    else:
        return "%s%s%s" % (x, point_separator, y)


def format_pointstr(nums):
    # format an even-length of nums into a1,b1 a2,b2 string list
    return " ".join([point_separator.join(nums[i:i + 2]) for i in range(0, len(nums), 2)])


def transform_str(input, matrix):
    # transform an input string by a matrix
    parts = input.split(",")
    if len(parts) == 1:
        return input
    else:
        point = [float(p) for p in parts]
        return transform_point(point, matrix, format="str")


def parse_shape(shape, i, gstates):
    # see https://www.adobe.com/content/dam/acom/en/devnet/acrobat/pdfs/PDF32000_2008.pdf
    output_filename = "page%s.svg" % i
    dwg = Drawing(output_filename, profile='tiny')
    fill = "none"
    stroke = rgb(0, 0, 0)
    stroke_width = 4
    transform = (1, 0, 0, 1, 0, 0)
    shapes_stack = []
    d = ""
    paths = []
    for line in shape.split("\n"):
        line = line.strip()
        parts = line.split(" ")
        nums = []
        for part in parts:
            try:
                nums.append(float(part))
            except ValueError:
                pass
        operation = parts[-1]
        if operation == 'BDC':
            continue
        elif operation == 'q':
            # q - start stack
            continue
        elif operation == 're':
            # rectangle
            vals = {'insert': (nums[0], nums[1]), 'size': (nums[2], nums[3])}
            if fill:
                vals['fill'] = fill
            if stroke:
                vals['stroke'] = stroke
            shapes_stack.append(dwg.rect(**vals))
        elif operation == 'n':
            # - clipping path
            continue
        elif operation == 'RG':
            # set stroke color
            stroke = rgb(*nums[0:3])
        elif operation == 'J':
            # not sure how to implement cap styles
            continue
        elif operation == 'cm':
            # current transformation matrix
            transform = nums[0:6]
        elif operation == 'F' or operation == 'f':
            # fill
            fill = rgb(*nums[0:3])
        elif operation == 'm':
            # move to
            d += "M " + format_pointstr(parts[0:2])
        elif operation == 'c':
            # curve
            d += " C " + format_pointstr(parts[0:6])
        elif operation == 'v':
            # append to bezier curve
            d += " S " + format_pointstr(parts[0:4])
        elif operation == 'y':
            d += " C " + format_pointstr(parts[0:4])+" "+format_pointstr(parts[2:4])
        elif operation == 'l':
            # line to
            d += " L " + format_pointstr(parts[0:2])
        elif operation == 'h':
            # make sure it's a closed path
            continue
        elif operation == 'S':
            # stroke to 4-unit width
            continue
        elif operation == 'Q':
            # end stack (draw)
            # apply transformation...
            for shape in shapes_stack:
                dwg.add(shape)
            if len(d) > 0:
                paths.append(d + " Z")
                d = " ".join([transform_str(p, transform) for p in d.split(" ")])
                vals = {'d': d}
                vals['stroke-width'] = stroke_width
                if fill:
                    vals['fill'] = fill
                if stroke:
                    vals['stroke'] = stroke

                dwg.add(dwg.path(**vals))
            d = ''
            shapes_stack = []
        elif operation == 'gs':
            key = parts[0]
            if key not in gstates:
                print("could not find state %s in dictionary")
            state = gstates[key]
            # color blending not yet implemented
            pass
        elif operation == 'w':
            stroke_width = nums[0]
        else:
            print("not sure what to do with %s %s" % (operation, line))
    dwg.save()
    return paths


def calc_overall_bbox(paths):
    overall_bbox = None
    for path in paths:
        if isinstance(path, str):
            shape = parse_path(path)
        else:
            shape = path
        bbox = shape.bbox()
        xmin, xmax = min(bbox[0], bbox[1]), max(bbox[0], bbox[1])
        ymin, ymax = min(bbox[2], bbox[3]), max(bbox[2], bbox[3])
        if overall_bbox is None:
            overall_bbox = [xmin,xmax, ymin, ymax]
        else:
            overall_bbox = [min(xmin, overall_bbox[0]), max(xmax, overall_bbox[1]),
                            min(ymin, overall_bbox[2]), max(ymax, overall_bbox[3])]
    return overall_bbox


if __name__ == "__main__":
    args = parser.parse_args()
    x = PdfReader(args.filename, decompress=True)
    name = '(' + args.size + ')'
    shapes = []
    paths = []
    for page_num, page in enumerate(x.pages):
        if '/Resources' not in page:
            continue
        if '/Properties' not in page['/Resources']:
            continue
        oc_keyname = [key for key in page['/Resources']['/Properties']
                      if page['/Resources']['/Properties'][key]['/Name'] == name]
        if len(oc_keyname) == 0:
            continue
        gstates = {}
        if '/ExtGState' in page['/Resources']:
            gstates = page['/Resources']['/ExtGState']
        oc_keyname = oc_keyname[0]
        lines = page.Contents.stream.split('\n')
        start_index = [i for i, l in enumerate(lines) if l.find(oc_keyname) >= 0][0]
        end_index = \
        [i for i, l in enumerate(lines) if l.find('EMC') >= 0 and i > start_index][0]
        shape = "\n".join(lines[start_index:end_index])
        paths += parse_shape(shape, page_num, gstates)
    # all paths
    paths = sorted(list(set(paths)))
    vals = {'fill': 'none', 'stroke': rgb(0, 0, 0), 'stroke-width': 4}
    output_filename = "all_paths.svg"
    dwg = Drawing(output_filename, profile='tiny')
    overall_bbox = calc_overall_bbox(paths)
    print(overall_bbox)
    for path in paths:
        vals['d'] = path
        dwg.add(dwg.path(**vals))
    dwg.viewbox(overall_bbox[0], overall_bbox[2], abs(overall_bbox[1] - overall_bbox[0]),
                abs(overall_bbox[3] - overall_bbox[2]))
    dwg.save()

    # make svgs of all paths
    for i, ds in enumerate(paths):
        output_filename = "path%s.svg" % i
        dwg = Drawing(output_filename, profile='tiny')
        if isinstance(ds, list):
            for d in ds:
                vals['d'] = d,
                dwg.add(dwg.path(**vals))
        else:
            vals['d'] = ds
            shape = parse_path(ds)
            bbox = calc_overall_bbox(shape._segments)
            width = abs(bbox[1] - bbox[0])
            height = abs(bbox[3] - bbox[2])
            if width == 0.0 or height == 0.0:
                continue
            dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), width, height)
            dwg.add(dwg.path(**vals))
        dwg.save()
