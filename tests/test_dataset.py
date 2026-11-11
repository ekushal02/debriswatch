import csv
import cv2
import numpy as np
import pytest
from scripts.prepare_dataset import convert

def dataset(root,duplicate=False):
    root.mkdir();manifest=root.parent/'groups.csv'
    with manifest.open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['annotation','group_id'])
        for i in range(6):
            cv2.imwrite(str(root/f'{i}.jpg'),np.full((20,20,3),30 if duplicate else i*30,dtype=np.uint8))
            (root/f'{i}.xml').write_text(f'<annotation><filename>{i}.jpg</filename><size><width>20</width><height>20</height></size><object><name>screw</name><bndbox><xmin>1</xmin><ymin>1</ymin><xmax>10</xmax><ymax>10</ymax></bndbox></object></annotation>')
            writer.writerow([f'{i}.xml',f'video{i//2}'])
    return manifest

def test_conversion_preserves_groups_and_normalizes_boxes(tmp_path):
    root=tmp_path/'voc';manifest=dataset(root);out=tmp_path/'yolo'
    assert convert(root,out,manifest)=={'train':2,'val':2,'test':2}
    labels=list(out.rglob('*.txt'));assert len(labels)==6
    assert labels[0].read_text().strip()=='0 0.25000000 0.25000000 0.50000000 0.50000000'
    assert '0: debris' in (out/'data.yaml').read_text()

def test_duplicate_images_across_splits_rejected(tmp_path):
    root=tmp_path/'voc';manifest=dataset(root,duplicate=True)
    with pytest.raises(ValueError,match='Identical'): convert(root,tmp_path/'yolo',manifest)
