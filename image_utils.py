from PIL import Image

def center_crop_square(im: Image.Image) -> Image.Image:
    w, h = im.size
    if w == h: return im
    if w > h:
        left = (w-h)//2
        return im.crop((left,0,left+h,h))
    top = (h-w)//2
    return im.crop((0,top,w,top+w))

def convert_to_square_rgb(width: int, img: Image.Image):
    im_sq = center_crop_square(img)
    im_sq = im_sq.resize((width,width), Image.LANCZOS)
    return im_sq.convert("RGB")
