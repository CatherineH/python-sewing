from svgwrite import rgb

def calc_overall_bbox(paths):
    overall_bbox = None
    for path in paths:
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


def get_paletton(filename):
    # extract a list of svgwrite colors from a paletton txt file
    lines = [line.split("=") for line in open(filename, "r").readlines() if len(line.split("=")) > 3]
    rgbs = [line[2].replace("rgb(", "").replace(")", "").split(",") for line in lines]
    return [rgb(*[float(x) for x in _rgb]) for _rgb in rgbs]