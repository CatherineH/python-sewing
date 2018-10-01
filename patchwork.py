import argparse
from pdfrw import PdfReader
from re import match
from svgwrite import Drawing, rgb
from svgwrite.container import Group
from svgpathtools import Path, parse_path

parser = argparse.ArgumentParser(
    description='Generate new pattern pieces from existing patterns')
parser.add_argument('--filename', type=str, help='The filename of the pdf pattern.')
parser.add_argument('--size', type=str, help="The size of the pattern to analyze.")

point_separator = ","


def cmyk(c, m, y, k):
    """
    this was taken from https://stackoverflow.com/questions/14088375/how-can-i-convert-rgb-to-cmyk-and-vice-versa-in-python
    """
    rgb_scale = 1.0
    cmyk_scale = 1.0
    r = rgb_scale * (1.0 - (c + k) / float(cmyk_scale))
    g = rgb_scale * (1.0 - (m + k) / float(cmyk_scale))
    b = rgb_scale * (1.0 - (y + k) / float(cmyk_scale))
    return r, g, b


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
        try:
            point = [float(p) for p in parts]
        except ValueError:
            raise ValueError("invalid parts {}".format(parts))
        return transform_point(point, matrix, format="str")


def endswith(line, ending):
    if len(line) == len(ending):
        return line == ending
    if line.find(ending) < 0:
        return False
    return len(line) - len(ending) == line.find(ending)


def parse_shape(shape, i, gstates):
    # see https://www.adobe.com/content/dam/acom/en/devnet/acrobat/pdfs/PDF32000_2008.pdf
    output_filename = "page%s.svg" % i
    dwg = Drawing(output_filename, profile='tiny')
    fill = "none"
    stroke = rgb(0, 0, 0)
    stroke_width = 4
    stroke_dasharray = None
    stroke_miterlimit = None
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
        if endswith(line, 'BDC'):
            continue
        elif endswith(line, 'Tj'):
            text = ' '.join(parts[:-1])
            text = text.split('Tj')[0]
            group = Group(transform="matrix({})".format(' '.join([str(d) for d in transform])))
            group.add(dwg.text(text))
            shapes_stack.append(group)
        elif endswith(line, 'Tc'):
            pass # not yet implemented
        elif endswith(line, 'Tm'):
            for i, part in enumerate(parts):
                if part == 'Tm':
                    transform = [float(d) for d in parts[i-6: i]]
                if part == 'Tw':
                    word_spacing = parts[i-1]
                if part == 'Tc':
                    char_spacing = parts[i-1]
        elif endswith(line, 'q'):
            # q - start stack
            continue
        elif endswith(line, 're'):
            # rectangle
            vals = {'insert': (nums[0], nums[1]), 'size': (nums[2], nums[3])}
            if fill:
                vals['fill'] = fill
            if stroke:
                vals['stroke'] = stroke
            shapes_stack.append(dwg.rect(**vals))
        elif endswith(line, 'n'):
            # - clipping path
            continue
        elif endswith(line, 'RG'):
            # set stroke color
            stroke = rgb(*nums[0:3])
        elif endswith(line, 'K'):
            stroke = rgb(*cmyk(*nums[0:4]))
        elif endswith(line, 'J'):
            # not sure how to implement cap styles
            continue
        elif endswith(line, 'cm'):
            # current transformation matrix
            transform = nums[0:6]
        elif endswith(line, 'F') or endswith(line, 'f'):
            # fill
            fill = rgb(*nums[0:3])
        elif endswith(line, 'm'):
            # move to
            d += " M " + format_pointstr(parts[0:2])
        elif endswith(line, ' c'):
            # curve
            d += " C " + format_pointstr(parts[0:6])
        elif endswith(line, 'v'):
            # append to bezier curve
            d += " S " + format_pointstr(parts[0:4])
        elif endswith(line, 'y'):
            d += " C " + format_pointstr(parts[0:4])+" "+format_pointstr(parts[2:4])
        elif endswith(line, 'l'):
            # line to
            d += " L " + format_pointstr(parts[0:2])
        elif endswith(line, 'h'):
            # make sure it's a closed path
            continue
        elif endswith(line, 'S'):
            # stroke to 4-unit width
            continue
        elif endswith(line, 'Q'):
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
                if stroke_dasharray:
                    vals['stroke-dasharray'] = stroke_dasharray
                if stroke_miterlimit:
                    vals['stroke-miterlimit'] = stroke_miterlimit
                dwg.add(dwg.path(**vals))
            d = ''
            shapes_stack = []
        elif endswith(line, 'gs'):
            key = parts[0]
            if key not in gstates:
                print("could not find state %s in dictionary")
            state = gstates[key]
            # color blending not yet implemented
            pass
        elif endswith(line, 'w'):
            stroke_width = nums[0]
        elif endswith(line, 'd'):
            fullstring = " ".join(parts[:-1])
            parsed = match('([\w\s\d]+)\[([\d\s]+)\](\d)', fullstring)
            if parsed:
                line_props = parsed.group(1)
                if line_props.find('M') >= 0:
                    m_part = line_props.split('M')[0].split(' ')[-2]
                    stroke_miterlimit = float(m_part)
                if line_props.find('w') >= 0:
                    m_part = line_props.split('w')[0].split(' ')[-2]
                    stroke_width = float(m_part)

                stroke_dasharray = parsed.group(2)
                offset = float(parsed.group(3)) # throw away the offset, it doesn't
                # convert nicely to svg
        elif endswith(line, 'M'):
            stroke_miterlimit = nums[0]
        else:
            print("not sure what to do with %s" % line)
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
