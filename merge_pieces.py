from svgpathtools import svg2paths, Path, Line
from svgwrite import Drawing, rgb
import argparse
from math import atan, asin, sin, cos, pi
from numpy import argmin

parser = argparse.ArgumentParser(
    description='Generate a merged piece from two pieces by stretching the pattern piece along an edge')
parser.add_argument('--filename', type=str,
                    help='The filename of the svg with at least two pattern pieces.')


class Intersection(object):
    def __init__(self, point=1.0+1.0*1j, diff=0.0):
        self.point = point
        self.diff = diff


class PathClip(object):
    def __init__(self, index=0, t=0.0, target=1.0+1.0*1j):
        self.index = index
        self.t = t
        self.target = target


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
            overall_bbox = [xmin, xmax, ymin, ymax]
        else:
            overall_bbox = [min(xmin, overall_bbox[0]), max(xmax, overall_bbox[1]),
                            min(ymin, overall_bbox[2]), max(ymax, overall_bbox[3])]
    return overall_bbox


def flatten_shape(i, all_paths, merge_paths):
    dwg = Drawing("merge_output%s.svg" % i, profile='tiny')

    def draw_line(start, end, offset=0.0):
        start += offset
        end += offset
        dwg.add(dwg.line(start=(start.real, start.imag), end=(end.real, end.imag),
                         stroke_width=4, stroke=rgb(255, 0, 0)))

    dwg.add(dwg.path(**{'d': all_paths[i].d(), 'fill': "none", 'stroke-width': 4,
                        'stroke': rgb(0, 0, 0)}))
    dwg.add(dwg.path(**{'d': merge_paths[i].d(), 'fill': "none", 'stroke-width': 4,
                        'stroke': rgb(255, 0, 0)}))
    bbox = calc_overall_bbox(all_paths[i])
    width, height = abs(bbox[1] - bbox[0]), abs(bbox[3] - bbox[2])
    margin = 40
    lower = min(bbox[2], bbox[3]) + height+margin
    left = min(bbox[0], bbox[1]) + margin

    def draw_marker(loc, col=rgb(255, 0, 0), offset=(left, lower)):
        dwg.add(dwg.circle(center=(loc.real + offset[0], loc.imag + offset[1]), r=4,
                           fill=col))

    max_axis = max(width, height)
    num_lines = 10
    points = [merge_paths[i].point(j / num_lines) for j in range(num_lines)] + [
        merge_paths[i].point(1.0)]
    angles = [
        asin((points[j + 1].imag - points[j].imag) / abs(points[j + 1] - points[j]))
        for j in range(num_lines)]

    ends = [max_axis * (sin(angle) + cos(angle) * 1j) for angle in
            angles]
    intersection_clips = []
    for j, end in enumerate(ends):
        end_point = end + points[j]
        intersections = other_paths[i].intersect(Line(start=points[j], end=end_point))

        for intersection in intersections[0]:
            intersection_point = intersection[1].point(intersection[2])
            target = merge_paths[i].length()*(1-j/num_lines) + abs(intersection_point - points[j])*1j
            intersection_clips.append(PathClip(index=other_paths[i].index(intersection[1]),
                                               t=intersection[2],
                                               target=target))
            if j % 10 == 0:
                draw_line(points[j], intersection_point)
                draw_marker(intersection_point, rgb(0, 255, 0), (0, 0))
            break

    # make the flexed points by chopping the chunks of the other paths out, then
    # translating and rotating them such that their end points line up with the diff lines
    def transform_side(sides, targets, angle_offset=0):
        def angle(point1, point2):
            diff = point1-point2
            if diff.real == 0:
                return 90.0
            return atan(diff.imag / diff.real)*180.0/pi
        # change this so that it has two targets
        transformed_side = Path(*sides)
        source_angle = angle(transformed_side.end, transformed_side.start) - \
                       angle(targets[0], targets[1])
        transformed_side = transformed_side.rotated(-source_angle+angle_offset)
        source = transformed_side.end if angle_offset == 0 else transformed_side.start
        diff = targets[1] - source
        transformed_side = transformed_side.translated(diff)
        draw_marker(targets[0], rgb(0, 200, 200))
        draw_marker(targets[1], rgb(0, 255, 255))
        transformed_diff = abs(transformed_side.start - transformed_side.end)
        targets_diff = abs(targets[0]-targets[1])
        if transformed_diff < targets_diff :
            transformed_side.insert(0, Line(start=targets[0],
                                            end=transformed_side.start))
        elif transformed_diff > targets_diff:
            # pop elements off until the transformed diff is smaller
            while transformed_diff > targets_diff:
                transformed_side.pop(0)
                transformed_diff = abs(transformed_side.start - transformed_side.end)
            print("path", transformed_side)
            print("path is longer", transformed_diff-targets_diff)
        return transformed_side

    start_index = 0
    curr_t = 0
    flexed_path = []
    t_resolution = 0.01
    if intersection_clips[0].index > intersection_clips[-1].index or \
        (intersection_clips[0].index == intersection_clips[-1].index and
         intersection_clips[0].t > intersection_clips[-1].t):
        intersection_clips.reverse()
    # add the end of the shape to the intersection clips
    intersection_clips.append(PathClip(index=len(other_paths[i])-1, t=1.0,
                                       target=merge_paths[i].length()))
    last_target = 0
    for clip in intersection_clips:
        sides = []
        print("boundaries", start_index, clip.index, curr_t, clip.t)
        upper_t = clip.t if start_index == clip.index else 1.0
        while start_index <= clip.index and curr_t < upper_t:
            curr_seg = other_paths[i][start_index]
            while curr_t < upper_t:
                max_t = curr_t + t_resolution if curr_t+t_resolution < clip.t else clip.t
                sides.append(Line(start=curr_seg.point(curr_t),
                                  end=curr_seg.point(max_t)))
                curr_t += t_resolution
            curr_t = upper_t
            if start_index != clip.index:
                curr_t = 0.0
            if upper_t == 1.0:
                start_index += 1
                upper_t = clip.t if start_index == clip.index else 1.0
        if len(sides) != 0:
            flexed_path.append(transform_side(sides, [last_target, clip.target]))
        last_target = clip.target

    straight_path = [Line(start=0, end=merge_paths[i].length())]
    for p in flexed_path:
        p = p.translated(left+lower*1j)
        dwg.add(dwg.path(d=p.d(), fill="none", stroke_width=4,
                         stroke=rgb(255, 0, 0)))

    transformed_path = flexed_path + straight_path
    transformed_path = Path(*transformed_path).translated(left + lower*1j)
    dwg.add(dwg.path(d=transformed_path.d(), fill="none", stroke_width=4,
                     stroke=rgb(0, 0, 0)))
    bbox = calc_overall_bbox(list(all_paths[i]) + list(transformed_path))

    width, height = abs(bbox[1] - bbox[0]), abs(bbox[3] - bbox[2])
    dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), width, height)
    dwg.save()
    return flexed_path


if __name__ == "__main__":
    args = parser.parse_args()
    all_paths, attributes = svg2paths(args.filename)
    # how do we figure out what sections of the path are linked?
    diffs = [[abs(i.start - j.start) for j in all_paths[0]] for i in
             all_paths[1]]
    # get the location of the lowest value of the diffs - this will tell us the offset
    diff_min = [argmin(diff) for diff in diffs]
    offset_diffs = [diff_min[i + 1] - diff_min[i] for i in range(len(diff_min) - 1)]
    # pull out the longest contiguous section of 1s
    start_one = offset_diffs.index(1)
    end_one = offset_diffs[::-1].index(1)
    # for each of the shapes, construct a new shape where the section in the merge paths
    # is straight
    merge_paths = [Path(*list(all_paths[i])[start_one:end_one]) for i in range(0, 2)]
    other_paths = [Path(*list(all_paths[i])[end_one:]+list(all_paths[i])[0:start_one])
                   for i in range(0, 2)]
    flexed_paths = [flatten_shape(i, all_paths, merge_paths) for i in range(0, 2)]
    dwg = Drawing("flexed_sides.svg", profile="tiny")
    upper_sizes = [0, 0]
    for i, path_list in enumerate(flexed_paths):
        bbox = calc_overall_bbox(path_list)
        if i == 0:
            upper_sizes = [max(bbox[0], bbox[1]), abs(bbox[3] - bbox[2])]
        transform = "scale(1, {})".format(-1 if i == 0 else 1)
        group = dwg.add(dwg.g(transform=transform))
        for path in path_list:
            path = path.translated(-min(bbox[2], bbox[3])*1j)
            group.add(dwg.path(**{'d': path.d(), 'fill': "none", 'stroke-width': 4,
                                'stroke': rgb(0, 0, 0)}))
    bbox = calc_overall_bbox(flexed_paths[1])
    dwg.viewbox(min(bbox[0], bbox[1]), -upper_sizes[1],
                abs(min(bbox[0], bbox[1]) -max(bbox[0], bbox[1], upper_sizes[0])),
                abs(bbox[3] - bbox[2])+upper_sizes[1])
    dwg.save()
    # render the shapes selected
    dwg = Drawing("merge_output.svg", profile='tiny')
    for path in all_paths:
        dwg.add(dwg.path(
            **{'d': path.d(), 'fill': "none", 'stroke-width': 4, 'stroke': rgb(0, 0, 0)}))
    dwg.add(dwg.path(**{'d': merge_paths[0].d(), 'fill': "none", 'stroke-width': 4,
                        'stroke': rgb(255, 0, 0)}))
    dwg.add(dwg.path(**{'d': merge_paths[1].d(), 'fill': "none", 'stroke-width': 4,
                        'stroke': rgb(0, 255, 0)}))
    bbox = calc_overall_bbox([x for x in all_paths[0]] + [x for x in all_paths[1]])
    dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), abs(bbox[1] - bbox[0]),
                abs(bbox[3] - bbox[2]))
    dwg.save()
