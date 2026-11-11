"""Convert Pascal VOC XML to single-class YOLO with explicit sequence-group splits.

No random-frame split: a CSV must identify the source sequence for every XML.
Use --inventory to generate the CSV template, then fill group_id from source metadata.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
import shutil
import xml.etree.ElementTree as ET


def inventory(root, output):
    files = sorted(root.rglob('*.xml'))
    if not files:
        raise ValueError('No Pascal VOC XML annotations found.')
    with output.open('w',newline='') as stream:
        writer=csv.writer(stream); writer.writerow(['annotation','group_id'])
        for path in files:
            writer.writerow([str(path.relative_to(root)), ''])
    print(f'{len(files)} annotations. Fill every group_id using source-video metadata before conversion.')


def convert(root, output, groups_csv, seed=42):
    root=root.resolve(); output=output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be empty to prevent stale split leakage.')
    with groups_csv.open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    if not rows or any(not row.get('group_id','').strip() or not row.get('annotation') for row in rows):
        raise ValueError('CSV requires annotation and nonempty group_id for each row.')
    if len({r['annotation'] for r in rows}) != len(rows):
        raise ValueError('Duplicate annotations in group manifest.')
    actual={str(p.relative_to(root)) for p in root.rglob('*.xml')}
    if actual != {r['annotation'] for r in rows}:
        raise ValueError('Manifest must cover every XML annotation exactly once.')
    groups=sorted({r['group_id'].strip() for r in rows})
    if len(groups)<3:
        raise ValueError('At least three independent sequence groups are required.')
    random.Random(seed).shuffle(groups)
    n=len(groups); a=max(1,min(n-2,round(n*.7))); b=max(a+1,min(n-1,round(n*.85)))
    assignment={g:('train' if i<a else 'val' if i<b else 'test') for i,g in enumerate(groups)}
    image_index={}
    for path in root.rglob('*'):
        if path.suffix.lower() in {'.jpg','.jpeg','.png'}:
            image_index.setdefault(path.name,[]).append(path)
    records=[]; hashes={}
    for row in rows:
        xml=(root/row['annotation']).resolve()
        if not xml.is_relative_to(root):
            raise ValueError('Annotation paths must be inside dataset root.')
        tree=ET.parse(xml).getroot()
        filename=Path(tree.findtext('filename','')).name
        candidates=image_index.get(filename,[])
        if len(candidates)!=1:
            raise ValueError(f'{xml.name}: image {filename!r} is missing or ambiguous.')
        image=candidates[0]; group=row['group_id'].strip(); split=assignment[group]
        digest=hashlib.sha256(image.read_bytes()).hexdigest()
        if digest in hashes and hashes[digest]!=split:
            raise ValueError('Identical images span splits; correct sequence groups and rerun.')
        hashes[digest]=split
        width=float(tree.findtext('size/width','0')); height=float(tree.findtext('size/height','0'))
        if width<=0 or height<=0:
            raise ValueError(f'Invalid image dimensions: {xml}')
        labels=[]
        for obj in tree.findall('object'):
            box=obj.find('bndbox')
            if box is None:
                raise ValueError(f'Missing bounding box in {xml}')
            # VOC uses one-based inclusive coordinates. Convert to pixel edges.
            x1=max(0,float(box.findtext('xmin'))-1); y1=max(0,float(box.findtext('ymin'))-1)
            x2=min(width,float(box.findtext('xmax'))); y2=min(height,float(box.findtext('ymax')))
            if not 0<=x1<x2<=width or not 0<=y1<y2<=height:
                raise ValueError(f'Invalid bounding box in {xml}')
            labels.append(f'0 {(x1+x2)/(2*width):.8f} {(y1+y2)/(2*height):.8f} {(x2-x1)/width:.8f} {(y2-y1)/height:.8f}')
        key=hashlib.sha256(row['annotation'].encode()).hexdigest()[:20]
        records.append((image,split,key,labels,row['annotation'],group))
    for split in ('train','val','test'):
        (output/'images'/split).mkdir(parents=True,exist_ok=True)
        (output/'labels'/split).mkdir(parents=True,exist_ok=True)
    counts={s:0 for s in ('train','val','test')}
    for image,split,key,labels,_,_ in records:
        shutil.copyfile(image,output/'images'/split/(key+image.suffix.lower()))
        (output/'labels'/split/(key+'.txt')).write_text('\n'.join(labels)+'\n' if labels else '')
        counts[split]+=1
    # JSON string quoting is valid YAML; no unsafe filesystem interpolation.
    (output/'data.yaml').write_text(f'path: {json.dumps(str(output))}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n  0: debris\n')
    (output/'split_manifest.json').write_text(json.dumps({'seed':seed,'counts':counts,'group_splits':assignment,'items':[{'annotation':r[4],'group_id':r[5],'split':r[1],'output_id':r[2]} for r in records]},indent=2))
    return counts

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--inventory',type=Path)
    parser.add_argument('--groups-csv',type=Path)
    parser.add_argument('--output',type=Path,default=Path('datasets/fod-yolo'))
    parser.add_argument('--seed',type=int,default=42)
    args=parser.parse_args()
    if args.inventory:
        inventory(args.input,args.inventory)
    elif args.groups_csv:
        print(convert(args.input,args.output,args.groups_csv,args.seed))
    else:
        parser.error('Use --inventory or --groups-csv. Source groups are required to prevent adjacent-frame leakage.')
