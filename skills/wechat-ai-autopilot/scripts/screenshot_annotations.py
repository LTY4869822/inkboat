"""Draw only declared frame overlays and verify every source pixel stays intact elsewhere."""
from pathlib import Path
import argparse,json,hashlib

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def framed(original, frames):
    from PIL import ImageDraw,ImageColor
    image=original.convert('RGB').copy()
    if not isinstance(frames,list) or not 1<=len(frames)<=4:
        raise ValueError('Declare one to four actual operation targets per screen')
    draw=ImageDraw.Draw(image)
    for frame in frames:
        x,y,width,height=(frame[k] for k in ('x','y','width','height'))
        stroke=frame.get('stroke_width',4)
        if any(type(v) is not int for v in (x,y,width,height,stroke)) or min(width,height)<8 or min(x,y)<0 or x+width>image.width or y+height>image.height or not 2<=stroke<=10:
            raise ValueError('Annotation rectangle must stay inside the original screen')
        color=ImageColor.getrgb(frame.get('color','#dc4b3f'))
        # Separate vector-like frames; no fill, labels, translation or reconstructed UI.
        draw.rounded_rectangle((x,y,x+width-1,y+height-1),radius=min(10,width//4,height//4),outline=color,width=stroke)
    return image

def annotate(original,output,frames):
    from PIL import Image
    original,output=Path(original),Path(output)
    if original.resolve()==output.resolve():raise ValueError('Never overwrite the unannotated screenshot')
    with Image.open(original) as raw:result=framed(raw,frames)
    output.parent.mkdir(parents=True,exist_ok=True);result.save(output,format='PNG')
    return {'source_sha256':digest(original),'output_sha256':digest(output),'pixel_operation':'frame_overlay_only','original_pixels_preserved':True,'verifier':'screenshot_annotations exact declared-frame pixel comparison','annotations':frames,'output_pixel_size':{'width':result.width,'height':result.height}}

def annotation_errors(run,image):
    import workflow as w
    record=image.get('provenance',{});errors=[]
    try:
        from PIL import Image
        original=w.within(Path(run).resolve(),record['original_image_file'])
        output=w.within(Path(run).resolve(),image['path'])
        if digest(original)!=record.get('original_image_sha256') or record.get('pixel_operation')!='frame_overlay_only':raise ValueError('Original or declared operation changed')
        if record.get('capture_method')=='source-image-annotation' and record.get('kind')!='tutorial-step':raise ValueError('Imported annotation needs tutorial origin')
        if len(record.get('user_instruction',''))<8:raise ValueError('Full-screen annotation needs the user preference')
        with Image.open(original) as raw,Image.open(output) as actual:
            width,height=raw.size
            if actual.size!=raw.size or record.get('viewport')!={'width':width,'height':height} or record.get('clip')!={'x':0,'y':0,'width':width,'height':height} or record.get('output_pixel_size')!={'width':width,'height':height}:raise ValueError('Complete screen dimensions must match the untouched original')
            if actual.convert('RGB').tobytes()!=framed(raw,record['annotations']).tobytes():raise ValueError('Pixels were changed beyond the declared frame overlays')
    except (ImportError,KeyError,ValueError,OSError,TypeError) as exc:errors.append('annotated screenshot is not an intact declared-frame screen: '+str(exc))
    return errors

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--original',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--frames',required=True,type=Path);p.add_argument('--record',required=True,type=Path);a=p.parse_args()
    record=annotate(a.original,a.output,json.loads(a.frames.read_text(encoding='utf-8')));a.record.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'status':'annotated','original_preserved':True,'frames':len(record['annotations'])}))
if __name__=='__main__':main()
