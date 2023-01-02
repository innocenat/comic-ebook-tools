#!/usr/bin/env python3


from multiprocessing import Pool
from PIL import Image, ImageOps, ImageFilter
from os import path
import itertools
import math
import numpy as np
import functools
import io
import mozjpeg_lossless_optimization

MULTI_PROCESSING = True

PALETTE = [
    0x00, 0x00, 0x00,
    0x11, 0x11, 0x11,
    0x22, 0x22, 0x22,
    0x33, 0x33, 0x33,
    0x44, 0x44, 0x44,
    0x55, 0x55, 0x55,
    0x66, 0x66, 0x66,
    0x77, 0x77, 0x77,
    0x88, 0x88, 0x88,
    0x99, 0x99, 0x99,
    0xaa, 0xaa, 0xaa,
    0xbb, 0xbb, 0xbb,
    0xcc, 0xcc, 0xcc,
    0xdd, 0xdd, 0xdd,
    0xee, 0xee, 0xee,
    0xff, 0xff, 0xff,
]

PAL_IMG = Image.new('P', (1, 1))
PAL_IMG.putpalette(PALETTE)


class ComicProcessor:
    """
    crop_border = default
    split = none, rotate, split, both
    """

    def __init__(self, dir=1, merge=True, merge_pct=0.15, merge_contrast=0.25, crop_border='default', gamma=1.8,
                 split='both', split_overlap=True, resize=None):
        self.options = {
            'dir': dir,
            'merge': merge,
            'merge_pct': merge_pct,
            'merge_contrast': merge_contrast,
            'crop_border': crop_border,
            'gamma': gamma,
            'split': split,
            'split_overlap': split_overlap,
            'resize': resize
        }

        self.page_map = []
        self.spread_map = {}

    def process(self, files, output_dir, quality=60):
        with Pool() as pool:
            mapper = (lambda func, param: pool.starmap(func, param)) if MULTI_PROCESSING else (
                lambda func, param: list(itertools.starmap(func, param)))

            # Pass #1
            pass_1_inputs = list(zip(files, files[1:] + [None]))
            matrices = mapper(functools.partial(process_pass_1, self.options), pass_1_inputs)

            # Pass Immediate
            page_map, spread_map, pass_2_inputs = process_pass_immediate(self.options, files, matrices)
            self.page_map = page_map
            self.spread_map = spread_map

            # Pass #2
            list_of_images = mapper(functools.partial(process_pass_2, self.options, output_dir, quality), pass_2_inputs)

            return [x for y in list_of_images for x in y]


def process_pass_1(options, f0, f1):
    im0 = Image.open(f0)
    im1 = Image.open(f1) if f1 is not None else None

    size = (im0.width, im0.height)
    pct = 0
    contrast = 0

    # Only merge if both are vertical page
    if im1 is not None and options['merge'] and im0.width < im0.height and im1.width < im1.height:
        pct, contrast = spread_calculate(im0, im1, direction=options['dir'])

    if options['crop_border'] and options['crop_border'] != 'none':
        bounding = bbox_calculate(im0, mode=options['crop_border'])
    else:
        bounding = None

    im0.close()
    if im1 is not None:
        im1.close()

    return {
        'size': size,
        'merge': (pct, contrast),
        'bounding': bounding
    }


def process_pass_immediate(options, files, matrices):
    page_map = []
    spread_map = {}
    pass_2_inputs = []
    page_number = 0

    merged = False
    for i in range(len(files)):
        # Skip page if it has been merged
        if merged:
            merged = False
            continue

        current_input = [files[i]]
        page_size = matrices[i]['size']

        # Page merging
        # Also don't merge cover page
        if i > 0 and options['merge'] and i + 1 < len(files) and spread_should_merge(matrices[i]['merge'], options['merge_pct'],
                                                                           options['merge_contrast']):
            # Append second image
            current_input.append(files[i + 1])

            # Recalculate page size
            page_size = (matrices[i]['size'][0] + matrices[i + 1]['size'][0], matrices[i]['size'][1])

            # Calculate new bounding box
            if matrices[i]['bounding'] and matrices[i + 1]['bounding']:
                new_bbox = (
                    matrices[i]['bounding'][0] if options['dir'] == 1 else matrices[i + 1]['bounding'][0],
                    min(matrices[i]['bounding'][1], matrices[i + 1]['bounding'][1]),
                    matrices[i]['size'][0] + matrices[i + 1]['bounding'][2] if options['dir'] == 1 else
                    matrices[i + 1]['size'][0] + matrices[i]['bounding'][2],
                    max(matrices[i]['bounding'][3], matrices[i + 1]['bounding'][3]),
                )
                current_input.append(new_bbox)
            else:
                current_input.append(None)

            merged = True
        else:
            # No second image
            current_input.append(None)

            # Bounding as is
            current_input.append(matrices[i]['bounding'])

        # Whether we need splitting
        need_split = image_is_spread(page_size[0], page_size[1])

        # Generate page number
        pages = 1
        if need_split:
            if options['split'] == 'split':
                pages = 2
            elif options['split'] == 'both':
                pages = 3
        current_input.append(list(range(page_number, page_number + pages)))

        if pages == 1:
            page_map.append((i, page_number))
            if merged:
                page_map.append((i + 1, page_number))
            if need_split:
                spread_map[page_number] = 2
        elif pages == 2:
            page_map.append((i, page_number))
            if merged:
                page_map.append((i + 1, page_number + 1))
            spread_map[page_number] = -1
            spread_map[page_number + 1] = 1
        elif pages == 3:
            page_map.append((i, page_number + 1))
            if merged:
                page_map.append((i + 1, page_number + 2))
            spread_map[page_number] = 2
            spread_map[page_number + 1] = -1
            spread_map[page_number + 2] = 1

        page_number += pages

        pass_2_inputs.append(current_input)

    return page_map, spread_map, pass_2_inputs


def process_pass_2(options, output_dir, quality, f0, f1, bounding, pages):
    im0 = Image.open(f0)

    # Merge image
    if f1 is not None and options['merge']:
        im1 = Image.open(f1)
        im_new = spread_merge(im0, im1, direction=options['dir'])
        im0.close()
        im1.close()

        im0 = im_new

    # First, convert to floating point (greyscale)
    im0 = im0.convert('F', dither=Image.Dither.FLOYDSTEINBERG)

    # Do cropping
    im0 = bbox_crop(im0, bounding)

    # Split image
    ims = image_split_resize(im0, options['split'], options['split_overlap'], options['resize'], options['dir'])

    if len(ims) != len(pages):
        raise Exception('Number of pages and resulting images not equal')

    for i in range(len(ims)):
        # Do gamma correction
        ims[i] = color_gamma_correction(ims[i], options['gamma'])

        # Quantize
        ims[i] = color_quantize(ims[i])

    images_list = []
    for i in range(len(ims)):
        filename = path.join(output_dir, '{:05d}.jpg'.format(pages[i]))
        images_list.append(filename)
        with io.BytesIO() as output:
            ims[i].save(output, format="JPEG", optimize=1, quality=quality)
            input_jpeg_bytes = output.getvalue()
            output_jpeg_bytes = mozjpeg_lossless_optimization.optimize(input_jpeg_bytes)
            with open(filename, "wb") as output_jpeg_file:
                output_jpeg_file.write(output_jpeg_bytes)

    return images_list


# Convert color to linear light according to sRGB
def c_lin(c):
    c /= 255
    if c <= 0.04045:
        return c / 12.92
    else:
        return ((c + 0.055) / 1.055) ** 2.4


# Calculate Root Mean Squared (RMS) of the list
def rms(l):
    return math.sqrt(sum([x ** 2 for x in l]) / len(l))


# Calculate contrast of the spread between two images
# Return: percentage of that is used to calculate, contrast
#
# We calculate the contrast along the seam of the page,
# ignoring the background color (white or black).
def spread_calculate(f0, f1, direction):
    if f0.height != f1.height:
        return 0, 0

    x0 = f0.width - 1
    x1 = 0
    if direction == -1:
        x0 = 0
        x1 = f1.width - 1

    if f0.mode != 'RGB':
        f0 = f0.convert('RGB')

    if f1.mode != 'RGB':
        f1 = f1.convert('RGB')

    ca, cb = [], []
    for y in range(f0.height):
        [r0, g0, b0] = [c_lin(x) for x in f0.getpixel((x0, y))]
        [r1, g1, b1] = [c_lin(x) for x in f1.getpixel((x1, y))]

        # Calculate luminance
        y0 = 0.2126 * r0 + 0.7152 * g0 + 0.0722 * b0
        y1 = 0.2126 * r1 + 0.7152 * g1 + 0.0722 * b1

        # Ignore white background
        if y0 < 0.95 and y1 < 0.95:
            ca.append(abs(y0 - y1))

        # Ignore black background
        if 0.05 < y0 and 0.05 < y1:
            cb.append(abs(y0 - y1))

    # If all the pixels are white or black, return 0
    if len(ca) == 0 or len(cb) == 0:
        return 0, 0

    # Return whichever has less percentage of content compared to background
    if len(ca) < len(cb):
        return len(ca) / f0.height, rms(ca)
    else:
        return len(cb) / f0.height, rms(cb)


# Merge to image together
def spread_merge(f0, f1, direction):
    if f0.height != f1.height:
        return None
    img = Image.new('RGB', (f0.width + f1.width, f0.height))
    if direction == 1:
        img.paste(f0, (0, 0))
        img.paste(f1, (f0.width, 0))
    else:
        img.paste(f1, (0, 0))
        img.paste(f0, (f1.width, 0))
    return img


# Whether the pages should be merged as a spread
def spread_should_merge(matrices, pct, contrast):
    return matrices[0] > pct and matrices[1] < contrast


# Detect bounding box
def bbbox_detect(bound_image, a, b):
    bound_image = bound_image.point(lambda x: 0 if a <= x <= b else 255)
    bbox = bound_image.getbbox()
    if bbox is not None:
        min_margin = [0, 0]
        max_margin = [int(0.1 * i + 0.5) for i in bound_image.size]
        bbox = (
            max(0, min(max_margin[0], bbox[0] - min_margin[0])),
            max(0, min(max_margin[1], bbox[1] - min_margin[1])),
            min(bound_image.size[0],
                max(bound_image.size[0] - max_margin[0], bbox[2] + min_margin[0])),
            min(bound_image.size[1],
                max(bound_image.size[1] - max_margin[1], bbox[3] + min_margin[1])),
        )
        return bbox
    else:
        return None


# Calculate bounding box
def bbox_calculate(img, mode):
    if not mode or mode == 'none':
        return None

    bb_img = img.convert('L')

    bbox1 = bbbox_detect(bb_img, 0, 16)
    bbox2 = bbbox_detect(bb_img, 235, 255)
    if bbox1 is None and bbox2 is None:
        return None
    elif bbox1 is None:
        return bbox2
    elif bbox2 is None:
        return bbox1
    else:
        return [max(bbox1[0], bbox2[0]), max(bbox1[1], bbox2[1]), min(bbox1[2], bbox2[2]), min(bbox1[3], bbox2[3])]


# Crop to bounding box
def bbox_crop(img, bbox):
    if bbox is None:
        return img
    return img.crop(bbox)


# Gamma correction
def color_gamma_correction(image, gamma):
    data = np.array(image.getdata())
    data = np.divide(data, 255)
    data = np.clip(data, 0, 1)
    data = np.power(data, gamma)
    min_, max_ = np.amin(data), np.amax(data)
    if min_ != max_:
        data = np.subtract(data, min_)
        data = np.multiply(data, 255 / (max_ - min_))
    else:
        data = np.multiply(data, 255)
    image.putdata(data)
    return image


# Quantize color to 16-bit greyscale
def color_quantize(img):
    img = img.convert('L')
    img = img.convert('RGB')
    img = img.quantize(colors=len(PALETTE) / 3, palette=PAL_IMG, dither=Image.Dither.FLOYDSTEINBERG)
    img = img.convert('RGB')

    return img


def image_is_spread(width, height):
    return width > height


def image_do_resize(img, size):
    if size is None:
        return img

    return ImageOps.pad(img, size, Image.Resampling.LANCZOS, color=255.0, centering=(0.5, 0.5))


# Split and resize page to final size
def image_split_resize(im0, split, split_overlap, resize, direction):
    is_spread = image_is_spread(im0.width, im0.height)
    ims = []

    if not is_spread:
        ims.append(image_do_resize(im0, resize))
    else:

        if split == 'rotate' or split == 'both':
            ims.append(image_do_resize(im0.transpose(Image.Transpose.ROTATE_90), resize))

        if split == 'split' or split == 'both':
            half = im0.width // 2
            bbox1 = (0, 0, half, im0.height)
            bbox2 = (half, 0, im0.width, im0.height)

            if resize is not None:
                # If target size is set, then we try to fill the page
                # even if half the split doesn't fill the page
                new_ratio = half / im0.height
                target_ratio = resize[0] / resize[1]

                if new_ratio < target_ratio and split_overlap:
                    # If half the spread would not fill the screen, then we cut more than half
                    fill_width = resize[0] * im0.height // resize[1]
                    bbox1 = (0, 0, fill_width, im0.height)
                    bbox2 = (im0.width - fill_width, 0, im0.width, im0.height)

            if direction == -1:
                # Swap for RTL
                bbox1, bbox2 = bbox2, bbox1

            ims.append(image_do_resize(im0.crop(bbox1), resize))
            ims.append(image_do_resize(im0.crop(bbox2), resize))

        if split != 'rotate' and split != 'split' and split != 'both':
            ims.append(image_do_resize(im0, resize))

    return ims
