"""Convert Pascal VOC XML to YOLO using source groups or the supplied FOD-A splits."""
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
    root = root.resolve()
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
    return write_dataset(root, output, rows, assignment, ('train', 'val', 'test'), seed)


def convert_official(root, output):
    root = root.resolve()
    split_dir = root / 'ImageSets' / 'Main'
    assignment = {'trainval.txt': 'train', 'test.txt': 'val'}
    rows = []
    seen = {}
    validation_ids = set((split_dir / 'test.txt').read_text().split())
    train_ids = set((split_dir / 'trainval.txt').read_text().split())
    print(f'Shared IDs reserved for validation: {len(train_ids & validation_ids)}')
    for filename in assignment:
        ids = (split_dir / filename).read_text().split()
        if not ids:
            raise ValueError(f'{filename} is empty.')
        for image_id in ids:
            if filename == 'trainval.txt' and image_id in validation_ids:
                continue
            if not (image_id.isascii() and image_id.isdecimal()):
                raise ValueError(f'{filename}: expected a numeric FOD-A image ID, got {image_id!r}.')
            previous = seen.get(image_id)
            if previous == filename:
                continue
            if previous is not None:
                raise ValueError(f'Image ID {image_id} appears in both {previous} and {filename}.')
            seen[image_id] = filename
            rows.append({'annotation': f'Annotations/{image_id}.xml', 'group_id': filename})
    return write_dataset(root, output, rows, assignment, ('train', 'val'), None)


def write_dataset(root, output, rows, assignment, splits, seed):
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be empty to prevent stale split leakage.')
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
            raise ValueError('Identical images span splits; review the split definitions.')
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
    for split in splits:
        (output/'images'/split).mkdir(parents=True,exist_ok=True)
        (output/'labels'/split).mkdir(parents=True,exist_ok=True)
    counts = dict.fromkeys(splits, 0)
    for image,split,key,labels,_,_ in records:
        shutil.copyfile(image,output/'images'/split/(key+image.suffix.lower()))
        (output/'labels'/split/(key+'.txt')).write_text('\n'.join(labels)+'\n' if labels else '')
        counts[split]+=1
    # JSON string quoting is valid YAML; no unsafe filesystem interpolation.
    split_paths = ''.join(f'{split}: images/{split}\n' for split in splits)
    (output/'data.yaml').write_text(f'path: {json.dumps(str(output))}\n{split_paths}names:\n  0: debris\n')
    (output/'split_manifest.json').write_text(json.dumps({'seed':seed,'counts':counts,'group_splits':assignment,'items':[{'annotation':r[4],'group_id':r[5],'split':r[1],'output_id':r[2]} for r in records]},indent=2))
    return counts

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',type=Path,required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inventory', type=Path)
    mode.add_argument('--groups-csv', type=Path)
    mode.add_argument('--official-fod-split', action='store_true',
                      help='Use FOD-A trainval.txt for training and test.txt for validation.')
    parser.add_argument('--output',type=Path,default=Path('datasets/fod-yolo'))
    parser.add_argument('--seed',type=int,default=42)
    args=parser.parse_args()
    if args.inventory:
        inventory(args.input,args.inventory)
    elif args.groups_csv:
        print(convert(args.input,args.output,args.groups_csv,args.seed))
    else:
        print(convert_official(args.input, args.output))
