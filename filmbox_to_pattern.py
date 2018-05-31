# install Autodesk FBX python extensions from here:
# https://www.autodesk.com/developer-network/platform-technologies/fbx-sdk-2019-0
from FbxCommon import *
import argparse

# does not work with python >3.3
from math import acos, cos, sin

from svgwrite import Drawing, rgb
from svgpathtools import Path, Line


from utils import calc_overall_bbox

parser = argparse.ArgumentParser(
    description='Generate a sewing pattern from an AutoDesk Filmbox file')
parser.add_argument('--fbx', type=str, help='The filename filmbox file.')


def flatten_scene(pScene):
    lNode = pScene.GetRootNode()

    if not lNode:
        return

    for i in range(lNode.GetChildCount()):

        lChildNode = lNode.GetChild(i)
        if lChildNode.GetNodeAttribute() is None:
            continue
        lAttributeType = (lChildNode.GetNodeAttribute().GetAttributeType())
        if lAttributeType != FbxNodeAttribute.eMesh:
            continue
        lMesh = lChildNode.GetNodeAttribute()
        projected_points = {}
        control_points = lMesh.GetControlPoints()
        start_point = 0
        poly_paths = []
        for polygon_num in range(lMesh.GetPolygonCount()):
            corners = []
            for corner in range(3):
                corners.append(lMesh.GetPolygonVertex(polygon_num, corner))
            # first, check if any of the control points are already projected
            flattened = []
            for j, corner in enumerate(corners):
                if corner in projected_points:
                    flattened.append(projected_points[corner])
                    continue
                target_corner = corners[j-1]
                current_vec = control_points[corner]
                target_vec = control_points[target_corner]
                angle = acos(current_vec.DotProduct(target_vec)/(current_vec.Length()*target_vec.Length()))
                length = current_vec.Distance(target_vec)
                # find where the last point was. If it doesn't exist, use the start point
                start_corner = projected_points[target_corner] \
                    if target_corner in projected_points else start_point
                flattened_corner = start_corner + length*(cos(angle)+1j*sin(angle))
                projected_points[corner] = flattened_corner
                start_point = flattened_corner
                flattened.append(flattened_corner)
            poly_paths.append(Path(*[Line(start=flattened[j], end=flattened[j-1])
                                     for j in range(3)]))

        dwg = Drawing("mesh{}.svg".format(i), profile='tiny')
        for poly_path in poly_paths:
            dwg.add(dwg.path(**{'d': poly_path.d(), 'fill': "none", 'stroke-width': 4,
                            'stroke': rgb(0, 0, 0)}))
        bbox = calc_overall_bbox(poly_paths)
        width, height = abs(bbox[1] - bbox[0]), abs(bbox[3] - bbox[2])
        dwg.viewbox(min(bbox[0], bbox[1]), min(bbox[2], bbox[3]), width, height)
        dwg.save()


if __name__ == "__main__":
    args = parser.parse_args()
    # Prepare the FBX SDK.
    lSdkManager, lScene = InitializeSdkObjects()

    lResult = LoadScene(lSdkManager, lScene, args.fbx)

    if not lResult:
        print("\n\nAn error occurred while loading the scene...")
    else:
        flatten_scene(lScene)
        # Destroy all objects created by the FBX SDK.
    lSdkManager.Destroy()

    sys.exit(0)
