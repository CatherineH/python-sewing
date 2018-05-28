python-sewing
-------------

My scripts for modifying sewing patterns and generating fabric patterns. Each script is
supposed to be used as an individual script; this is not a python module.

patchwork.py
============

Extract dressforms out of PDFs.

Usage:

```bash
python3 patchwork.py --filename pattern.pdf --size 'M'
```

merge_pieces.py
===============

Merge two dressforms into a single dressform by warping the other sides

Usage:

 - first, copy the dressforms to be merged into a new SVG, and drag them so that they
 line up along the side to be merged together, like this:

![two dressforms lined up along side to merge](to_merge.svg.png)

Then, run:

```bash
python3 merge_pieces.py --filename to_merge.svg
```

